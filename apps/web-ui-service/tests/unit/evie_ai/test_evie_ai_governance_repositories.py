from __future__ import annotations

import ast
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from app.repositories.evie_ai import (
    RepositoryDataIntegrityError,
)
from app.repositories.evie_ai import (
    TestAssetAuditRepository as AuditRepository,
)
from app.repositories.evie_ai import (
    TestAssetIdempotencyRepository as IdempotencyRepository,
)
from app.repositories.evie_ai import (
    TestAssetRepository as AssetRepository,
)
from app.repositories.evie_ai import (
    TestAssetReviewRepository as ReviewRepository,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .repository_test_support import (
    make_asset,
    make_asset_version,
    make_audit,
    make_idempotency_record,
    make_review,
)


def _asset_with_version(session: Session):
    repository = AssetRepository(session)
    asset = repository.add(make_asset())
    version = repository.add_version(make_asset_version(asset.id))
    repository.set_current_version(
        asset,
        version,
        expected_row_version=1,
        updated_by=asset.updated_by,
    )
    return asset, version


def test_review_repository_appends_and_pages_in_stable_order(
    evie_ai_session: Session,
) -> None:
    asset, version = _asset_with_version(evie_ai_session)
    repository = ReviewRepository(evie_ai_session)
    now = datetime.now(UTC)
    older = repository.add(
        make_review(
            test_asset_pk=asset.id,
            test_asset_version_pk=version.id,
            reviewed_at=now - timedelta(minutes=1),
        )
    )
    newer = repository.add(
        make_review(
            test_asset_pk=asset.id,
            test_asset_version_pk=version.id,
            reviewed_at=now,
        )
    )

    assert repository.get_latest(asset.id) is newer
    first_page = repository.list_by_asset(asset.id, page=1, page_size=1)
    second_page = repository.list_by_asset(asset.id, page=2, page_size=1)
    assert first_page.items == [newer]
    assert second_page.items == [older]
    assert (first_page.total, first_page.page, first_page.page_size) == (2, 1, 1)


def test_review_record_version_must_belong_to_asset(
    evie_ai_session: Session,
) -> None:
    first, _first_version = _asset_with_version(evie_ai_session)
    _second, second_version = _asset_with_version(evie_ai_session)

    with pytest.raises(RepositoryDataIntegrityError):
        ReviewRepository(evie_ai_session).add(
            make_review(
                test_asset_pk=first.id,
                test_asset_version_pk=second_version.id,
            )
        )


def test_review_public_id_uniqueness_is_enforced(
    evie_ai_session: Session,
) -> None:
    asset, version = _asset_with_version(evie_ai_session)
    repository = ReviewRepository(evie_ai_session)
    first = repository.add(
        make_review(test_asset_pk=asset.id, test_asset_version_pk=version.id)
    )
    duplicate = make_review(
        test_asset_pk=asset.id,
        test_asset_version_pk=version.id,
    )
    duplicate.test_asset_review_record_id = first.test_asset_review_record_id

    with pytest.raises(IntegrityError):
        repository.add(duplicate)


def test_audit_repository_appends_and_pages_without_content_fields(
    evie_ai_session: Session,
) -> None:
    asset, _version = _asset_with_version(evie_ai_session)
    repository = AuditRepository(evie_ai_session)
    first = repository.add(make_audit(test_asset_pk=asset.id))
    second = repository.add(make_audit(test_asset_pk=asset.id))

    page = repository.list_by_asset(asset.id, page=1, page_size=10)
    assert page.items == [second, first]
    assert page.total == 2
    assert not hasattr(first, "natural_steps")
    assert not hasattr(first, "expected_result")


def test_governance_repositories_expose_no_update_or_delete_methods() -> None:
    path = (
        Path(__file__).resolve().parents[3]
        / "app"
        / "repositories"
        / "evie_ai"
        / "governance_repository.py"
    )
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    method_names = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name not in {"__init__"}
    }
    assert not any(name.startswith(("update", "delete")) for name in method_names)


def test_governance_idempotency_snapshots_survive_record_reoccupation(
    evie_ai_session: Session,
) -> None:
    now = datetime.now(UTC)
    asset, version = _asset_with_version(evie_ai_session)
    review = ReviewRepository(evie_ai_session).add(
        make_review(test_asset_pk=asset.id, test_asset_version_pk=version.id)
    )
    audit = AuditRepository(evie_ai_session).add(make_audit(test_asset_pk=asset.id))
    idempotency = IdempotencyRepository(evie_ai_session)
    record = idempotency.add(
        make_idempotency_record(expires_at=now - timedelta(seconds=1))
    )

    assert idempotency.try_reoccupy_expired(
        record_id=record.id,
        expected_generation=1,
        expired_at_or_before=now,
        request_fingerprint="9" * 64,
        expires_at=now + timedelta(days=7),
    )
    evie_ai_session.expire_all()

    assert review.idempotency_generation == 1
    assert audit.idempotency_generation == 1
    assert review.idempotency_scope_hash == "5" * 64
    assert audit.idempotency_key_hash == "6" * 64
