from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from app.models.evie_ai import TestAssetContentClaim as AssetContentClaimModel
from app.repositories.evie_ai import (
    IdempotencyResultSummary,
    IdempotencyScope,
    RepositoryDataIntegrityError,
)
from app.repositories.evie_ai import (
    TestAssetContentClaimRepository as ContentClaimRepository,
)
from app.repositories.evie_ai import (
    TestAssetIdempotencyRepository as IdempotencyRepository,
)
from app.repositories.evie_ai import (
    TestAssetRepository as AssetRepository,
)
from sqlalchemy import Engine, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from .repository_test_support import (
    ACTOR,
    PROJECT_CODE,
    make_asset,
    make_content_claim,
    make_idempotency_record,
)


def _scope(key: str = "request-key") -> IdempotencyScope:
    return IdempotencyScope(
        project_code=PROJECT_CODE,
        operation_type="create_asset",
        actor_or_client_id=ACTOR,
        idempotency_key=key,
    )


def test_idempotency_scope_add_read_and_unique_constraint(
    evie_ai_session: Session,
) -> None:
    repository = IdempotencyRepository(evie_ai_session)
    record = repository.add(make_idempotency_record())

    assert repository.get_by_scope(_scope()) is record
    assert repository.get_by_scope(_scope("missing")) is None

    with pytest.raises(IntegrityError):
        repository.add(make_idempotency_record(fingerprint="7" * 64))


def test_expired_idempotency_record_is_reoccupied_with_generation_cas(
    evie_ai_session: Session,
) -> None:
    now = datetime.now(UTC)
    repository = IdempotencyRepository(evie_ai_session)
    record = repository.add(
        make_idempotency_record(expires_at=now - timedelta(seconds=1))
    )
    assert repository.complete(
        record_id=record.id,
        expected_generation=1,
        completed_at=now - timedelta(seconds=1),
        summary=IdempotencyResultSummary(
            result_http_status=201,
            result_type="test_asset",
            test_asset_id="ta_" + "a" * 32,
            created=True,
        ),
    )

    assert repository.try_reoccupy_expired(
        record_id=record.id,
        expected_generation=1,
        expired_at_or_before=now,
        request_fingerprint="8" * 64,
        expires_at=now + timedelta(days=7),
    )
    assert not repository.try_reoccupy_expired(
        record_id=record.id,
        expected_generation=1,
        expired_at_or_before=now,
        request_fingerprint="9" * 64,
        expires_at=now + timedelta(days=7),
    )

    evie_ai_session.expire_all()
    refreshed = repository.get_by_scope(_scope())
    assert refreshed is not None
    assert refreshed.generation == 2
    assert refreshed.request_fingerprint == "8" * 64
    assert refreshed.result_type is None
    assert refreshed.test_asset_id is None
    assert refreshed.created is None
    assert refreshed.completed_at is None


def test_stale_session_cannot_reoccupy_an_advanced_generation(
    evie_ai_session: Session,
    evie_ai_engine: Engine,
) -> None:
    now = datetime.now(UTC)
    record = IdempotencyRepository(evie_ai_session).add(
        make_idempotency_record(expires_at=now - timedelta(seconds=1))
    )
    evie_ai_session.commit()
    record_id = record.id
    session_factory = sessionmaker(bind=evie_ai_engine, future=True)

    with session_factory() as first, session_factory() as stale:
        first_record = IdempotencyRepository(first).get_by_scope(_scope())
        stale_record = IdempotencyRepository(stale).get_by_scope(_scope())
        assert first_record is not None and stale_record is not None

        assert IdempotencyRepository(first).try_reoccupy_expired(
            record_id=record_id,
            expected_generation=first_record.generation,
            expired_at_or_before=now,
            request_fingerprint="8" * 64,
            expires_at=now + timedelta(days=7),
        )
        first.commit()

        assert not IdempotencyRepository(stale).try_reoccupy_expired(
            record_id=record_id,
            expected_generation=stale_record.generation,
            expired_at_or_before=now,
            request_fingerprint="9" * 64,
            expires_at=now + timedelta(days=7),
        )


def test_idempotency_result_can_only_complete_current_generation_once(
    evie_ai_session: Session,
) -> None:
    repository = IdempotencyRepository(evie_ai_session)
    record = repository.add(make_idempotency_record())
    completed_at = datetime.now(UTC)
    summary = IdempotencyResultSummary(
        result_http_status=201,
        result_type="test_asset",
        test_asset_id="ta_" + "a" * 32,
        created=True,
        reused_existing=False,
        row_version=1,
        deleted=False,
    )

    assert repository.complete(
        record_id=record.id,
        expected_generation=1,
        completed_at=completed_at,
        summary=summary,
    )
    assert not repository.complete(
        record_id=record.id,
        expected_generation=1,
        completed_at=completed_at,
        summary=summary,
    )

    evie_ai_session.expire_all()
    refreshed = repository.get_by_scope(_scope())
    assert refreshed is not None
    assert refreshed.result_http_status == 201
    assert refreshed.created is True


def test_expired_cleanup_uses_generation_and_expiry_conditions(
    evie_ai_session: Session,
) -> None:
    now = datetime.now(UTC)
    repository = IdempotencyRepository(evie_ai_session)
    repository.add(
        make_idempotency_record(
            key="expired",
            expires_at=now - timedelta(seconds=1),
        )
    )
    repository.add(
        make_idempotency_record(
            key="active",
            expires_at=now + timedelta(days=1),
        )
    )

    assert repository.delete_expired(expired_at_or_before=now, limit=10) == 1
    assert repository.get_by_scope(_scope("expired")) is None
    assert repository.get_by_scope(_scope("active")) is not None


def test_content_claim_add_lookup_replace_and_conditional_delete(
    evie_ai_session: Session,
) -> None:
    asset = AssetRepository(evie_ai_session).add(make_asset())
    repository = ContentClaimRepository(evie_ai_session)
    claim = repository.add(make_content_claim(asset.id))

    assert repository.get_by_test_asset_pk(asset.id) is claim
    assert (
        repository.get_by_project_and_fingerprint(
            project_code=PROJECT_CODE,
            content_fingerprint="4" * 64,
        )
        is claim
    )
    assert repository.replace_fingerprint(
        test_asset_pk=asset.id,
        project_code=PROJECT_CODE,
        expected_fingerprint="4" * 64,
        new_fingerprint="5" * 64,
    )
    assert not repository.replace_fingerprint(
        test_asset_pk=asset.id,
        project_code=PROJECT_CODE,
        expected_fingerprint="4" * 64,
        new_fingerprint="6" * 64,
    )
    assert not repository.delete_by_test_asset_pk(
        asset.id,
        expected_fingerprint="4" * 64,
    )
    assert repository.delete_by_test_asset_pk(
        asset.id,
        expected_fingerprint="5" * 64,
    )


def test_content_claim_rejects_cross_project_or_deleted_asset(
    evie_ai_session: Session,
) -> None:
    repository = ContentClaimRepository(evie_ai_session)
    active = AssetRepository(evie_ai_session).add(make_asset())
    cross_project_claim = make_content_claim(active.id)
    cross_project_claim.project_code = "project-b"

    with pytest.raises(RepositoryDataIntegrityError):
        repository.add(cross_project_claim)

    deleted = AssetRepository(evie_ai_session).add(
        make_asset(deleted_at=datetime.now(UTC))
    )
    with pytest.raises(RepositoryDataIntegrityError):
        repository.add(make_content_claim(deleted.id))


def test_content_claim_unique_conflict_preserves_existing_claim_after_rollback(
    evie_ai_session: Session,
) -> None:
    assets = AssetRepository(evie_ai_session)
    first = assets.add(make_asset())
    second = assets.add(make_asset())
    evie_ai_session.commit()
    repository = ContentClaimRepository(evie_ai_session)
    repository.add(make_content_claim(first.id))
    evie_ai_session.commit()

    with pytest.raises(IntegrityError):
        repository.add(make_content_claim(second.id))
    evie_ai_session.rollback()

    claim_count = evie_ai_session.scalar(
        select(func.count()).select_from(AssetContentClaimModel)
    )
    assert claim_count == 1
    assert repository.get_by_test_asset_pk(first.id) is not None
