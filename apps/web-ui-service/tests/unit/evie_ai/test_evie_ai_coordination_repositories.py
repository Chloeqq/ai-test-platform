from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from app.models.evie_ai import TestAsset as AssetModel
from app.models.evie_ai import TestAssetContentClaim as AssetContentClaimModel
from app.models.evie_ai import TestAssetVersion as AssetVersionModel
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
    make_asset_version,
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


def _bound_asset(
    session: Session,
    *,
    project_code: str = PROJECT_CODE,
    content_fingerprint: str | None = None,
) -> tuple[AssetModel, AssetVersionModel]:
    repository = AssetRepository(session)
    asset = repository.add(make_asset(project_code=project_code))
    version = make_asset_version(asset.id)
    if content_fingerprint is not None:
        version.content_checksum = content_fingerprint
    version = repository.add_version(version)
    repository.bind_initial_version(asset, version, updated_by=ACTOR)
    return asset, version


def _asset_state(
    asset: AssetModel,
) -> tuple[int | None, str, str, int, datetime | None]:
    deleted_at = asset.deleted_at
    if deleted_at is not None:
        deleted_at = deleted_at.replace(tzinfo=None)
    return (
        asset.current_version_pk,
        asset.review_status,
        asset.conversion_status,
        asset.row_version,
        deleted_at,
    )


def _assert_restore_acquire_has_no_side_effects(
    session: Session,
    *,
    asset_pk: int,
    state_before: tuple[int | None, str, str, int, datetime | None],
    claim_count_before: int,
) -> None:
    session.expire_all()
    asset = session.get(AssetModel, asset_pk)
    assert asset is not None
    assert _asset_state(asset) == state_before
    assert (
        session.scalar(select(func.count()).select_from(AssetContentClaimModel))
        == claim_count_before
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


def test_restore_only_claim_acquire_accepts_deleted_current_version(
    evie_ai_session: Session,
) -> None:
    asset_repository = AssetRepository(evie_ai_session)
    asset, version = _bound_asset(evie_ai_session)
    assert asset_repository.compare_and_set_deleted_at(
        project_code=PROJECT_CODE,
        test_asset_id=asset.test_asset_id,
        expected_row_version=1,
        deleted_at=datetime(2026, 8, 3, tzinfo=UTC),
        updated_by=ACTOR,
    )
    state_before = _asset_state(asset)

    claim = ContentClaimRepository(evie_ai_session).acquire_for_deleted_asset_restore(
        project_code=PROJECT_CODE,
        test_asset_id=asset.test_asset_id,
        test_asset_version_id=version.test_asset_version_id,
        content_fingerprint=version.content_checksum,
    )

    assert claim is not None
    assert claim.test_asset_pk == asset.id
    assert claim.project_code == PROJECT_CODE
    assert claim.content_fingerprint == version.content_checksum
    _assert_restore_acquire_has_no_side_effects(
        evie_ai_session,
        asset_pk=asset.id,
        state_before=state_before,
        claim_count_before=1,
    )


def test_restore_only_claim_acquire_rejects_active_asset_without_side_effects(
    evie_ai_session: Session,
) -> None:
    asset, version = _bound_asset(evie_ai_session)
    state_before = _asset_state(asset)

    claim = ContentClaimRepository(evie_ai_session).acquire_for_deleted_asset_restore(
        project_code=PROJECT_CODE,
        test_asset_id=asset.test_asset_id,
        test_asset_version_id=version.test_asset_version_id,
        content_fingerprint=version.content_checksum,
    )

    assert claim is None
    _assert_restore_acquire_has_no_side_effects(
        evie_ai_session,
        asset_pk=asset.id,
        state_before=state_before,
        claim_count_before=0,
    )


@pytest.mark.parametrize(
    ("project_code", "test_asset_id"),
    (("project-b", None), (PROJECT_CODE, "ta_missing")),
)
def test_restore_only_claim_acquire_hides_cross_project_and_missing_assets(
    evie_ai_session: Session,
    project_code: str,
    test_asset_id: str | None,
) -> None:
    asset_repository = AssetRepository(evie_ai_session)
    asset, version = _bound_asset(evie_ai_session)
    assert asset_repository.compare_and_set_deleted_at(
        project_code=PROJECT_CODE,
        test_asset_id=asset.test_asset_id,
        expected_row_version=1,
        deleted_at=datetime(2026, 8, 3, tzinfo=UTC),
        updated_by=ACTOR,
    )
    state_before = _asset_state(asset)

    claim = ContentClaimRepository(evie_ai_session).acquire_for_deleted_asset_restore(
        project_code=project_code,
        test_asset_id=test_asset_id or asset.test_asset_id,
        test_asset_version_id=version.test_asset_version_id,
        content_fingerprint=version.content_checksum,
    )

    assert claim is None
    _assert_restore_acquire_has_no_side_effects(
        evie_ai_session,
        asset_pk=asset.id,
        state_before=state_before,
        claim_count_before=0,
    )


def test_restore_only_claim_acquire_rejects_historical_version_without_side_effects(
    evie_ai_session: Session,
) -> None:
    asset_repository = AssetRepository(evie_ai_session)
    asset, historical_version = _bound_asset(evie_ai_session)
    current_version = asset_repository.add_version(
        make_asset_version(asset.id, version_no=2)
    )
    assert asset_repository.advance_current_version(
        project_code=PROJECT_CODE,
        test_asset_id=asset.test_asset_id,
        version=current_version,
        expected_row_version=1,
        updated_by=ACTOR,
    )
    assert asset_repository.compare_and_set_deleted_at(
        project_code=PROJECT_CODE,
        test_asset_id=asset.test_asset_id,
        expected_row_version=2,
        deleted_at=datetime(2026, 8, 3, tzinfo=UTC),
        updated_by=ACTOR,
    )
    state_before = _asset_state(asset)

    claim = ContentClaimRepository(evie_ai_session).acquire_for_deleted_asset_restore(
        project_code=PROJECT_CODE,
        test_asset_id=asset.test_asset_id,
        test_asset_version_id=historical_version.test_asset_version_id,
        content_fingerprint=historical_version.content_checksum,
    )

    assert claim is None
    _assert_restore_acquire_has_no_side_effects(
        evie_ai_session,
        asset_pk=asset.id,
        state_before=state_before,
        claim_count_before=0,
    )


def test_restore_only_claim_acquire_rejects_foreign_version_without_side_effects(
    evie_ai_session: Session,
) -> None:
    asset_repository = AssetRepository(evie_ai_session)
    asset, _ = _bound_asset(evie_ai_session)
    other_asset, other_version = _bound_asset(evie_ai_session)
    assert asset_repository.compare_and_set_deleted_at(
        project_code=PROJECT_CODE,
        test_asset_id=asset.test_asset_id,
        expected_row_version=1,
        deleted_at=datetime(2026, 8, 3, tzinfo=UTC),
        updated_by=ACTOR,
    )
    state_before = _asset_state(asset)

    claim = ContentClaimRepository(evie_ai_session).acquire_for_deleted_asset_restore(
        project_code=PROJECT_CODE,
        test_asset_id=asset.test_asset_id,
        test_asset_version_id=other_version.test_asset_version_id,
        content_fingerprint=other_version.content_checksum,
    )

    assert claim is None
    _assert_restore_acquire_has_no_side_effects(
        evie_ai_session,
        asset_pk=asset.id,
        state_before=state_before,
        claim_count_before=0,
    )
    assert other_asset.current_version_pk == other_version.id


def test_restore_only_claim_acquire_rejects_corrupted_current_pointer(
    evie_ai_session: Session,
) -> None:
    asset_repository = AssetRepository(evie_ai_session)
    asset, _ = _bound_asset(evie_ai_session)
    _, foreign_version = _bound_asset(evie_ai_session)
    assert asset_repository.compare_and_set_deleted_at(
        project_code=PROJECT_CODE,
        test_asset_id=asset.test_asset_id,
        expected_row_version=1,
        deleted_at=datetime(2026, 8, 3, tzinfo=UTC),
        updated_by=ACTOR,
    )
    asset.current_version_pk = foreign_version.id
    evie_ai_session.flush()
    state_before = _asset_state(asset)

    claim = ContentClaimRepository(evie_ai_session).acquire_for_deleted_asset_restore(
        project_code=PROJECT_CODE,
        test_asset_id=asset.test_asset_id,
        test_asset_version_id=foreign_version.test_asset_version_id,
        content_fingerprint=foreign_version.content_checksum,
    )

    assert claim is None
    _assert_restore_acquire_has_no_side_effects(
        evie_ai_session,
        asset_pk=asset.id,
        state_before=state_before,
        claim_count_before=0,
    )


def test_restore_only_claim_acquire_rejects_mismatched_fingerprint(
    evie_ai_session: Session,
) -> None:
    asset_repository = AssetRepository(evie_ai_session)
    asset, version = _bound_asset(evie_ai_session)
    assert asset_repository.compare_and_set_deleted_at(
        project_code=PROJECT_CODE,
        test_asset_id=asset.test_asset_id,
        expected_row_version=1,
        deleted_at=datetime(2026, 8, 3, tzinfo=UTC),
        updated_by=ACTOR,
    )
    state_before = _asset_state(asset)

    claim = ContentClaimRepository(evie_ai_session).acquire_for_deleted_asset_restore(
        project_code=PROJECT_CODE,
        test_asset_id=asset.test_asset_id,
        test_asset_version_id=version.test_asset_version_id,
        content_fingerprint="f" * 64,
    )

    assert claim is None
    _assert_restore_acquire_has_no_side_effects(
        evie_ai_session,
        asset_pk=asset.id,
        state_before=state_before,
        claim_count_before=0,
    )


def test_restore_only_claim_acquire_preserves_foreign_claim_on_unique_conflict(
    evie_ai_session: Session,
) -> None:
    asset_repository = AssetRepository(evie_ai_session)
    restoring_asset, restoring_version = _bound_asset(evie_ai_session)
    owner_asset, _ = _bound_asset(
        evie_ai_session,
        content_fingerprint=restoring_version.content_checksum,
    )
    assert asset_repository.compare_and_set_deleted_at(
        project_code=PROJECT_CODE,
        test_asset_id=restoring_asset.test_asset_id,
        expected_row_version=1,
        deleted_at=datetime(2026, 8, 3, tzinfo=UTC),
        updated_by=ACTOR,
    )
    claim_repository = ContentClaimRepository(evie_ai_session)
    owner_claim = claim_repository.add(
        make_content_claim(
            owner_asset.id,
            fingerprint=restoring_version.content_checksum,
        )
    )
    evie_ai_session.commit()
    restoring_asset_pk = restoring_asset.id
    restoring_state_before = _asset_state(restoring_asset)
    owner_claim_id = owner_claim.id

    with pytest.raises(IntegrityError):
        claim_repository.acquire_for_deleted_asset_restore(
            project_code=PROJECT_CODE,
            test_asset_id=restoring_asset.test_asset_id,
            test_asset_version_id=restoring_version.test_asset_version_id,
            content_fingerprint=restoring_version.content_checksum,
        )
    evie_ai_session.rollback()

    _assert_restore_acquire_has_no_side_effects(
        evie_ai_session,
        asset_pk=restoring_asset_pk,
        state_before=restoring_state_before,
        claim_count_before=1,
    )
    persisted_owner_claim = claim_repository.get_by_test_asset_pk(owner_asset.id)
    assert persisted_owner_claim is not None
    assert persisted_owner_claim.id == owner_claim_id


def test_restore_only_claim_acquire_rejects_retained_deleted_asset_claim(
    evie_ai_session: Session,
) -> None:
    asset, version = _bound_asset(evie_ai_session)
    claim_repository = ContentClaimRepository(evie_ai_session)
    claim_repository.add(
        make_content_claim(asset.id, fingerprint=version.content_checksum)
    )
    asset.deleted_at = datetime(2026, 8, 3, tzinfo=UTC)
    evie_ai_session.flush()
    state_before = _asset_state(asset)

    with pytest.raises(RepositoryDataIntegrityError):
        claim_repository.acquire_for_deleted_asset_restore(
            project_code=PROJECT_CODE,
            test_asset_id=asset.test_asset_id,
            test_asset_version_id=version.test_asset_version_id,
            content_fingerprint=version.content_checksum,
        )

    _assert_restore_acquire_has_no_side_effects(
        evie_ai_session,
        asset_pk=asset.id,
        state_before=state_before,
        claim_count_before=1,
    )
