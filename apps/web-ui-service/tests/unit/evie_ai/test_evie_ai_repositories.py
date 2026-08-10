from __future__ import annotations

import ast
from datetime import UTC, datetime
from pathlib import Path

import pytest
from app.constants.evie_ai import (
    RequirementStatus,
    RequirementVersionStatus,
)
from app.constants.evie_ai import (
    TestAssetConversionStatus as AssetConversionStatus,
)
from app.constants.evie_ai import (
    TestAssetReviewStatus as AssetReviewStatus,
)
from app.constants.evie_ai import (
    TestAssetSourceType as AssetSourceType,
)
from app.core.id_gen import (
    generate_requirement_id,
    generate_requirement_version_id,
    generate_test_asset_id,
    generate_test_asset_source_id,
    generate_test_asset_version_id,
)
from app.models.evie_ai import (
    Requirement,
    RequirementVersion,
)
from app.models.evie_ai import (
    TestAsset as AssetModel,
)
from app.models.evie_ai import (
    TestAssetRequirementSource as RequirementSourceModel,
)
from app.models.evie_ai import (
    TestAssetSource as AssetSourceModel,
)
from app.models.evie_ai import (
    TestAssetVersion as AssetVersionModel,
)
from app.repositories.evie_ai import (
    CurrentVersionOwnershipError,
    OptimisticConcurrencyError,
    RepositoryDataIntegrityError,
    RequirementRepository,
    SourceOwnershipError,
)
from app.repositories.evie_ai import (
    TestAssetRepository as AssetRepository,
)
from app.repositories.evie_ai.test_asset_repository import ReviewStatusCasInput
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


def _requirement(*, code: str = "REQ-001") -> Requirement:
    return Requirement(
        requirement_id=generate_requirement_id(),
        project_code="project-a",
        requirement_code=code,
        status=RequirementStatus.DRAFT.value,
        created_by="tester",
        updated_by="tester",
    )


def _requirement_version(
    requirement_pk: int,
    *,
    version_no: int = 1,
) -> RequirementVersion:
    return RequirementVersion(
        requirement_version_id=generate_requirement_version_id(),
        requirement_pk=requirement_pk,
        version_no=version_no,
        title=f"需求版本 {version_no}",
        content="用户可以登录系统",
        content_checksum="1" * 64,
        version_status=RequirementVersionStatus.DRAFT.value,
        created_by="tester",
    )


def _test_asset(*, code: str = "ASSET-001") -> AssetModel:
    return AssetModel(
        test_asset_id=generate_test_asset_id(),
        project_code="project-a",
        asset_code=code,
        review_status=AssetReviewStatus.PENDING.value,
        conversion_status=AssetConversionStatus.NOT_STARTED.value,
        created_by="tester",
        updated_by="tester",
    )


def _test_asset_version(
    test_asset_pk: int,
    *,
    version_no: int = 1,
) -> AssetVersionModel:
    return AssetVersionModel(
        test_asset_version_id=generate_test_asset_version_id(),
        test_asset_pk=test_asset_pk,
        version_no=version_no,
        title=f"测试资产版本 {version_no}",
        natural_steps=["输入账号密码", "点击登录"],
        expected_result="进入首页",
        content_checksum="2" * 64,
        created_by="tester",
    )


def _source(
    *,
    test_asset_pk: int,
    source_identity_hash: str = "3" * 64,
) -> AssetSourceModel:
    return AssetSourceModel(
        test_asset_source_id=generate_test_asset_source_id(),
        test_asset_pk=test_asset_pk,
        source_type=AssetSourceType.REQUIREMENT.value,
        source_identity_hash=source_identity_hash,
        created_by="tester",
    )


def _bound_test_asset(
    repository: AssetRepository,
    *,
    asset_code: str,
    project_code: str = "project-a",
) -> tuple[AssetModel, AssetVersionModel]:
    test_asset = _test_asset(code=asset_code)
    test_asset.project_code = project_code
    test_asset = repository.add(test_asset)
    version = repository.add_version(_test_asset_version(test_asset.id))
    repository.bind_initial_version(
        test_asset,
        version,
        updated_by="tester",
    )
    return test_asset, version


def _asset_state(
    test_asset: AssetModel,
) -> tuple[int | None, str, str, int, datetime | None, str]:
    deleted_at = test_asset.deleted_at
    if deleted_at is not None:
        deleted_at = deleted_at.replace(tzinfo=None)
    return (
        test_asset.current_version_pk,
        test_asset.review_status,
        test_asset.conversion_status,
        test_asset.row_version,
        deleted_at,
        test_asset.updated_by,
    )


def _review_status_update(
    expected_review_status: AssetReviewStatus,
    new_review_status: AssetReviewStatus,
) -> ReviewStatusCasInput:
    return ReviewStatusCasInput(
        expected_review_status=expected_review_status,
        new_review_status=new_review_status,
        updated_by="reviewer",
    )


def test_requirement_repository_add_query_versions_and_current_version(
    evie_ai_session: Session,
) -> None:
    repository = RequirementRepository(evie_ai_session)
    requirement = repository.add(_requirement())
    first = repository.add_version(_requirement_version(requirement.id, version_no=1))
    second = repository.add_version(_requirement_version(requirement.id, version_no=2))

    repository.set_current_version(
        requirement,
        second,
        expected_row_version=1,
        updated_by="reviewer",
    )

    assert repository.get_by_pk(requirement.id) is requirement
    assert repository.get_by_requirement_id(requirement.requirement_id) is requirement
    assert repository.get_current_version(requirement.id) is second
    assert repository.list_versions(requirement.id) == [second, first]
    assert requirement.current_version_pk == second.id
    assert requirement.row_version == 2
    assert requirement.updated_by == "reviewer"


def test_test_asset_repository_add_query_versions_sources_and_current_version(
    evie_ai_session: Session,
) -> None:
    requirement_repository = RequirementRepository(evie_ai_session)
    requirement = requirement_repository.add(_requirement())
    requirement_version = requirement_repository.add_version(
        _requirement_version(requirement.id)
    )
    repository = AssetRepository(evie_ai_session)
    test_asset = repository.add(_test_asset())
    first_version = repository.add_version(_test_asset_version(test_asset.id))
    source = repository.add_source(
        _source(
            test_asset_pk=test_asset.id,
        ),
        requirement_pk=requirement.id,
        requirement_version_pk=requirement_version.id,
    )

    repository.bind_initial_version(
        test_asset,
        first_version,
        updated_by="reviewer",
    )
    assert test_asset.current_version_pk == first_version.id
    assert test_asset.row_version == 1

    second_version = repository.add_version(
        _test_asset_version(test_asset.id, version_no=2)
    )
    repository.set_current_version(
        test_asset,
        second_version,
        expected_row_version=1,
        updated_by="reviewer",
    )

    assert repository.get_by_pk(test_asset.id) is test_asset
    assert repository.get_by_test_asset_id(test_asset.test_asset_id) is test_asset
    assert repository.get_current_version(test_asset.id) is second_version
    assert repository.list_versions(test_asset.id) == [second_version, first_version]
    assert repository.list_sources(test_asset.id) == [source]
    requirement_source = evie_ai_session.execute(
        select(RequirementSourceModel)
    ).scalar_one()
    assert requirement_source.test_asset_source_pk == source.id
    assert requirement_source.requirement_pk == requirement.id
    assert requirement_source.requirement_version_pk == requirement_version.id
    assert test_asset.current_version_pk == second_version.id
    assert test_asset.row_version == 2


def test_requirement_source_resolution_enforces_public_ids_project_and_deletion(
    evie_ai_session: Session,
) -> None:
    repository = RequirementRepository(evie_ai_session)
    requirement = repository.add(_requirement())
    version = repository.add_version(_requirement_version(requirement.id))

    assert repository.resolve_source_version(
        project_code=requirement.project_code,
        requirement_id=requirement.requirement_id,
        requirement_version_id=version.requirement_version_id,
    ) == (requirement, version)
    assert (
        repository.resolve_source_version(
            project_code="project-b",
            requirement_id=requirement.requirement_id,
            requirement_version_id=version.requirement_version_id,
        )
        is None
    )
    assert (
        repository.resolve_source_version(
            project_code=requirement.project_code,
            requirement_id=requirement.requirement_id,
            requirement_version_id="reqv_" + "f" * 32,
        )
        is None
    )

    requirement.deleted_at = datetime.now(UTC)
    evie_ai_session.flush()
    assert (
        repository.resolve_source_version(
            project_code=requirement.project_code,
            requirement_id=requirement.requirement_id,
            requirement_version_id=version.requirement_version_id,
        )
        is None
    )


def test_initial_asset_version_binding_requires_version_one_and_is_single_use(
    evie_ai_session: Session,
) -> None:
    repository = AssetRepository(evie_ai_session)
    test_asset = repository.add(_test_asset())
    second_version = repository.add_version(
        _test_asset_version(test_asset.id, version_no=2)
    )

    with pytest.raises(RepositoryDataIntegrityError):
        repository.bind_initial_version(
            test_asset,
            second_version,
            updated_by="tester",
        )

    first_version = repository.add_version(_test_asset_version(test_asset.id))
    repository.bind_initial_version(
        test_asset,
        first_version,
        updated_by="tester",
    )
    with pytest.raises(RepositoryDataIntegrityError):
        repository.bind_initial_version(
            test_asset,
            first_version,
            updated_by="tester",
        )

    assert test_asset.current_version_pk == first_version.id
    assert test_asset.row_version == 1


def test_repository_queries_return_none_for_missing_or_soft_deleted_aggregates(
    evie_ai_session: Session,
) -> None:
    requirement_repository = RequirementRepository(evie_ai_session)
    asset_repository = AssetRepository(evie_ai_session)

    assert requirement_repository.get_by_pk(999_999) is None
    assert requirement_repository.get_by_requirement_id("req_missing") is None
    assert asset_repository.get_by_pk(999_999) is None
    assert asset_repository.get_by_test_asset_id("ta_missing") is None

    requirement = requirement_repository.add(_requirement())
    test_asset = asset_repository.add(_test_asset())
    requirement.deleted_at = datetime.now(UTC)
    test_asset.deleted_at = datetime.now(UTC)
    evie_ai_session.flush()

    assert requirement_repository.get_by_pk(requirement.id) is None
    assert asset_repository.get_by_pk(test_asset.id) is None


def test_requirement_current_version_must_belong_to_requirement(
    evie_ai_session: Session,
) -> None:
    repository = RequirementRepository(evie_ai_session)
    first = repository.add(_requirement(code="REQ-001"))
    second = repository.add(_requirement(code="REQ-002"))
    other_version = repository.add_version(_requirement_version(second.id))

    with pytest.raises(CurrentVersionOwnershipError) as exc_info:
        repository.set_current_version(
            first,
            other_version,
            expected_row_version=1,
            updated_by="tester",
        )

    assert exc_info.value.error_code == "EVIE_AI_CURRENT_VERSION_OWNERSHIP_MISMATCH"
    assert first.current_version_pk is None


def test_test_asset_current_version_must_belong_to_test_asset(
    evie_ai_session: Session,
) -> None:
    repository = AssetRepository(evie_ai_session)
    first = repository.add(_test_asset(code="ASSET-001"))
    second = repository.add(_test_asset(code="ASSET-002"))
    other_version = repository.add_version(_test_asset_version(second.id))

    with pytest.raises(CurrentVersionOwnershipError):
        repository.set_current_version(
            first,
            other_version,
            expected_row_version=1,
            updated_by="tester",
        )

    assert first.current_version_pk is None


def test_current_version_update_uses_optimistic_row_version(
    evie_ai_session: Session,
) -> None:
    repository = RequirementRepository(evie_ai_session)
    requirement = repository.add(_requirement())
    version = repository.add_version(_requirement_version(requirement.id))

    with pytest.raises(OptimisticConcurrencyError) as exc_info:
        repository.set_current_version(
            requirement,
            version,
            expected_row_version=99,
            updated_by="tester",
        )

    assert exc_info.value.error_code == "EVIE_AI_ROW_VERSION_CONFLICT"
    assert exc_info.value.retryable is True
    assert requirement.current_version_pk is None


def test_lifecycle_current_version_cas_advances_all_aggregate_state(
    evie_ai_session: Session,
) -> None:
    repository = AssetRepository(evie_ai_session)
    test_asset, initial_version = _bound_test_asset(
        repository,
        asset_code="ASSET-LIFECYCLE-001",
    )
    test_asset.review_status = AssetReviewStatus.APPROVED.value
    test_asset.conversion_status = AssetConversionStatus.SUCCEEDED.value
    evie_ai_session.flush()
    next_version = repository.add_version(
        _test_asset_version(test_asset.id, version_no=2)
    )

    assert repository.advance_current_version(
        project_code="project-a",
        test_asset_id=test_asset.test_asset_id,
        version=next_version,
        expected_row_version=1,
        updated_by="reviewer",
    )

    evie_ai_session.refresh(test_asset)
    assert test_asset.current_version_pk == next_version.id
    assert test_asset.current_version_pk != initial_version.id
    assert test_asset.review_status == AssetReviewStatus.PENDING.value
    assert test_asset.conversion_status == AssetConversionStatus.STALE.value
    assert test_asset.row_version == 2
    assert test_asset.updated_by == "reviewer"


def test_lifecycle_current_version_cas_rejects_stale_or_foreign_version(
    evie_ai_session: Session,
) -> None:
    repository = AssetRepository(evie_ai_session)
    test_asset, initial_version = _bound_test_asset(
        repository,
        asset_code="ASSET-LIFECYCLE-002",
    )
    next_version = repository.add_version(
        _test_asset_version(test_asset.id, version_no=2)
    )
    other_asset, _ = _bound_test_asset(
        repository,
        asset_code="ASSET-LIFECYCLE-003",
    )
    other_version = repository.add_version(
        _test_asset_version(other_asset.id, version_no=2)
    )

    assert not repository.advance_current_version(
        project_code="project-a",
        test_asset_id=test_asset.test_asset_id,
        version=next_version,
        expected_row_version=2,
        updated_by="reviewer",
    )
    assert not repository.advance_current_version(
        project_code="project-a",
        test_asset_id=test_asset.test_asset_id,
        version=other_version,
        expected_row_version=1,
        updated_by="reviewer",
    )

    evie_ai_session.refresh(test_asset)
    assert test_asset.current_version_pk == initial_version.id
    assert test_asset.row_version == 1
    assert test_asset.review_status == AssetReviewStatus.PENDING.value
    assert test_asset.conversion_status == AssetConversionStatus.NOT_STARTED.value


def test_lifecycle_cas_does_not_update_cross_project_asset(
    evie_ai_session: Session,
) -> None:
    repository = AssetRepository(evie_ai_session)
    test_asset, initial_version = _bound_test_asset(
        repository,
        asset_code="ASSET-LIFECYCLE-004",
    )
    next_version = repository.add_version(
        _test_asset_version(test_asset.id, version_no=2)
    )
    state_before = _asset_state(test_asset)
    version_rows_before = evie_ai_session.execute(
        select(
            AssetVersionModel.id,
            AssetVersionModel.test_asset_pk,
            AssetVersionModel.version_no,
            AssetVersionModel.title,
            AssetVersionModel.expected_result,
            AssetVersionModel.content_checksum,
        )
    ).all()

    assert not repository.advance_current_version(
        project_code="project-b",
        test_asset_id=test_asset.test_asset_id,
        version=next_version,
        expected_row_version=1,
        updated_by="reviewer",
    )

    evie_ai_session.refresh(test_asset)
    assert _asset_state(test_asset) == state_before
    assert test_asset.current_version_pk == initial_version.id
    assert (
        evie_ai_session.execute(
            select(
                AssetVersionModel.id,
                AssetVersionModel.test_asset_pk,
                AssetVersionModel.version_no,
                AssetVersionModel.title,
                AssetVersionModel.expected_result,
                AssetVersionModel.content_checksum,
            )
        ).all()
        == version_rows_before
    )


@pytest.mark.parametrize(
    "conversion_status",
    (
        AssetConversionStatus.NOT_STARTED,
        AssetConversionStatus.BLOCKED,
    ),
)
def test_lifecycle_current_version_cas_resets_pending_conversion_status(
    evie_ai_session: Session,
    conversion_status: AssetConversionStatus,
) -> None:
    repository = AssetRepository(evie_ai_session)
    test_asset, _ = _bound_test_asset(
        repository,
        asset_code=f"ASSET-LIFECYCLE-{conversion_status.value}",
    )
    test_asset.review_status = AssetReviewStatus.APPROVED.value
    test_asset.conversion_status = conversion_status.value
    next_version = repository.add_version(
        _test_asset_version(test_asset.id, version_no=2)
    )

    assert repository.advance_current_version(
        project_code="project-a",
        test_asset_id=test_asset.test_asset_id,
        version=next_version,
        expected_row_version=1,
        updated_by="reviewer",
    )

    evie_ai_session.refresh(test_asset)
    assert test_asset.current_version_pk == next_version.id
    assert test_asset.review_status == AssetReviewStatus.PENDING.value
    assert test_asset.conversion_status == AssetConversionStatus.NOT_STARTED.value
    assert test_asset.row_version == 2


def test_lifecycle_current_version_cas_preserves_stale_conversion_status(
    evie_ai_session: Session,
) -> None:
    repository = AssetRepository(evie_ai_session)
    test_asset, _ = _bound_test_asset(
        repository,
        asset_code="ASSET-LIFECYCLE-STALE",
    )
    test_asset.review_status = AssetReviewStatus.APPROVED.value
    test_asset.conversion_status = AssetConversionStatus.STALE.value
    next_version = repository.add_version(
        _test_asset_version(test_asset.id, version_no=2)
    )

    assert repository.advance_current_version(
        project_code="project-a",
        test_asset_id=test_asset.test_asset_id,
        version=next_version,
        expected_row_version=1,
        updated_by="reviewer",
    )

    evie_ai_session.refresh(test_asset)
    assert next_version.test_asset_pk == test_asset.id
    assert test_asset.current_version_pk == next_version.id
    assert test_asset.review_status == AssetReviewStatus.PENDING.value
    assert test_asset.conversion_status == AssetConversionStatus.STALE.value
    assert test_asset.row_version == 2


def test_lifecycle_current_version_cas_rejects_missing_asset_or_version(
    evie_ai_session: Session,
) -> None:
    repository = AssetRepository(evie_ai_session)
    test_asset, _ = _bound_test_asset(
        repository,
        asset_code="ASSET-LIFECYCLE-MISSING",
    )
    next_version = repository.add_version(
        _test_asset_version(test_asset.id, version_no=2)
    )
    state_before = _asset_state(test_asset)

    assert not repository.advance_current_version(
        project_code="project-a",
        test_asset_id="ta_missing",
        version=next_version,
        expected_row_version=1,
        updated_by="reviewer",
    )
    assert not repository.advance_current_version(
        project_code="project-a",
        test_asset_id=test_asset.test_asset_id,
        version=_test_asset_version(test_asset.id, version_no=3),
        expected_row_version=1,
        updated_by="reviewer",
    )

    evie_ai_session.refresh(test_asset)
    assert _asset_state(test_asset) == state_before


@pytest.mark.parametrize(
    ("conversion_status", "deleted_at"),
    (
        (AssetConversionStatus.PROCESSING, None),
        (AssetConversionStatus.NOT_STARTED, datetime(2026, 8, 2, tzinfo=UTC)),
    ),
)
def test_lifecycle_current_version_cas_rejects_processing_or_deleted_asset(
    evie_ai_session: Session,
    conversion_status: AssetConversionStatus,
    deleted_at: datetime | None,
) -> None:
    repository = AssetRepository(evie_ai_session)
    test_asset, _ = _bound_test_asset(
        repository,
        asset_code=f"ASSET-LIFECYCLE-{conversion_status.value}",
    )
    test_asset.conversion_status = conversion_status.value
    test_asset.deleted_at = deleted_at
    next_version = repository.add_version(
        _test_asset_version(test_asset.id, version_no=2)
    )
    evie_ai_session.flush()
    state_before = _asset_state(test_asset)

    assert not repository.advance_current_version(
        project_code="project-a",
        test_asset_id=test_asset.test_asset_id,
        version=next_version,
        expected_row_version=1,
        updated_by="reviewer",
    )

    evie_ai_session.refresh(test_asset)
    assert _asset_state(test_asset) == state_before


@pytest.mark.parametrize(
    "new_review_status",
    (AssetReviewStatus.APPROVED, AssetReviewStatus.REJECTED),
)
def test_review_status_cas_updates_pending_asset(
    evie_ai_session: Session,
    new_review_status: AssetReviewStatus,
) -> None:
    repository = AssetRepository(evie_ai_session)
    test_asset, _ = _bound_test_asset(
        repository,
        asset_code="ASSET-REVIEW-001",
    )
    test_asset.conversion_status = AssetConversionStatus.SUCCEEDED.value
    evie_ai_session.flush()

    assert repository.compare_and_set_review_status(
        project_code="project-a",
        test_asset_id=test_asset.test_asset_id,
        expected_row_version=1,
        status_update=_review_status_update(
            AssetReviewStatus.PENDING,
            new_review_status,
        ),
    )

    evie_ai_session.refresh(test_asset)
    assert test_asset.review_status == new_review_status.value
    assert test_asset.conversion_status == AssetConversionStatus.SUCCEEDED.value
    assert test_asset.row_version == 2


@pytest.mark.parametrize(
    ("current_review_status", "expected_review_status"),
    (
        (AssetReviewStatus.APPROVED, AssetReviewStatus.PENDING),
        (AssetReviewStatus.REJECTED, AssetReviewStatus.PENDING),
        (AssetReviewStatus.PENDING, AssetReviewStatus.APPROVED),
    ),
)
def test_review_status_cas_requires_matching_current_status(
    evie_ai_session: Session,
    current_review_status: AssetReviewStatus,
    expected_review_status: AssetReviewStatus,
) -> None:
    repository = AssetRepository(evie_ai_session)
    test_asset, _ = _bound_test_asset(
        repository,
        asset_code=f"ASSET-REVIEW-{current_review_status.value}",
    )
    test_asset.review_status = current_review_status.value
    test_asset.conversion_status = AssetConversionStatus.SUCCEEDED.value
    evie_ai_session.flush()
    state_before = _asset_state(test_asset)

    assert not repository.compare_and_set_review_status(
        project_code="project-a",
        test_asset_id=test_asset.test_asset_id,
        expected_row_version=1,
        status_update=_review_status_update(
            expected_review_status,
            AssetReviewStatus.REJECTED,
        ),
    )

    evie_ai_session.refresh(test_asset)
    assert _asset_state(test_asset) == state_before


def test_review_status_cas_rejects_stale_row_version(
    evie_ai_session: Session,
) -> None:
    repository = AssetRepository(evie_ai_session)
    test_asset, _ = _bound_test_asset(
        repository,
        asset_code="ASSET-REVIEW-STALE",
    )
    state_before = _asset_state(test_asset)

    assert not repository.compare_and_set_review_status(
        project_code="project-a",
        test_asset_id=test_asset.test_asset_id,
        expected_row_version=2,
        status_update=_review_status_update(
            AssetReviewStatus.PENDING,
            AssetReviewStatus.APPROVED,
        ),
    )

    evie_ai_session.refresh(test_asset)
    assert _asset_state(test_asset) == state_before


def test_review_status_cas_rejects_cross_project_or_missing_asset(
    evie_ai_session: Session,
) -> None:
    repository = AssetRepository(evie_ai_session)
    test_asset, _ = _bound_test_asset(
        repository,
        asset_code="ASSET-REVIEW-SCOPE",
        project_code="project-b",
    )
    state_before = _asset_state(test_asset)
    status_update = _review_status_update(
        AssetReviewStatus.PENDING,
        AssetReviewStatus.APPROVED,
    )

    assert not repository.compare_and_set_review_status(
        project_code="project-a",
        test_asset_id=test_asset.test_asset_id,
        expected_row_version=1,
        status_update=status_update,
    )
    assert not repository.compare_and_set_review_status(
        project_code="project-a",
        test_asset_id="ta_missing",
        expected_row_version=1,
        status_update=status_update,
    )

    evie_ai_session.refresh(test_asset)
    assert _asset_state(test_asset) == state_before


def test_review_status_cas_rejects_deleted_asset_without_changes(
    evie_ai_session: Session,
) -> None:
    repository = AssetRepository(evie_ai_session)
    test_asset, _ = _bound_test_asset(
        repository,
        asset_code="ASSET-REVIEW-DELETED",
    )
    assert repository.compare_and_set_deleted_at(
        project_code="project-a",
        test_asset_id=test_asset.test_asset_id,
        expected_row_version=1,
        deleted_at=datetime(2026, 8, 2, tzinfo=UTC),
        updated_by="reviewer",
    )
    state_before = _asset_state(test_asset)

    assert not repository.compare_and_set_review_status(
        project_code="project-a",
        test_asset_id=test_asset.test_asset_id,
        expected_row_version=2,
        status_update=_review_status_update(
            AssetReviewStatus.PENDING,
            AssetReviewStatus.APPROVED,
        ),
    )

    evie_ai_session.refresh(test_asset)
    assert _asset_state(test_asset) == state_before


def test_deleted_at_cas_rejects_stale_row_without_changing_asset(
    evie_ai_session: Session,
) -> None:
    repository = AssetRepository(evie_ai_session)
    test_asset, _ = _bound_test_asset(
        repository,
        asset_code="ASSET-DELETED-STALE",
    )
    test_asset.review_status = AssetReviewStatus.APPROVED.value
    test_asset.conversion_status = AssetConversionStatus.SUCCEEDED.value
    evie_ai_session.flush()
    state_before = _asset_state(test_asset)

    assert not repository.compare_and_set_deleted_at(
        project_code="project-a",
        test_asset_id=test_asset.test_asset_id,
        expected_row_version=2,
        deleted_at=datetime(2026, 8, 2, tzinfo=UTC),
        updated_by="reviewer",
    )

    evie_ai_session.refresh(test_asset)
    assert _asset_state(test_asset) == state_before


def test_deleted_at_cas_rejects_cross_project_delete_without_changes(
    evie_ai_session: Session,
) -> None:
    repository = AssetRepository(evie_ai_session)
    test_asset, _ = _bound_test_asset(
        repository,
        asset_code="ASSET-DELETED-CROSS-PROJECT",
    )
    test_asset.review_status = AssetReviewStatus.APPROVED.value
    test_asset.conversion_status = AssetConversionStatus.SUCCEEDED.value
    evie_ai_session.flush()
    state_before = _asset_state(test_asset)

    assert not repository.compare_and_set_deleted_at(
        project_code="project-b",
        test_asset_id=test_asset.test_asset_id,
        expected_row_version=1,
        deleted_at=datetime(2026, 8, 2, tzinfo=UTC),
        updated_by="reviewer",
    )

    evie_ai_session.refresh(test_asset)
    assert _asset_state(test_asset) == state_before


def test_deleted_at_cas_rejects_missing_asset_delete_without_changes(
    evie_ai_session: Session,
) -> None:
    repository = AssetRepository(evie_ai_session)
    test_asset, _ = _bound_test_asset(
        repository,
        asset_code="ASSET-DELETED-MISSING",
    )
    state_before = _asset_state(test_asset)
    asset_count = evie_ai_session.scalar(select(func.count()).select_from(AssetModel))
    version_count = evie_ai_session.scalar(
        select(func.count()).select_from(AssetVersionModel)
    )

    assert not repository.compare_and_set_deleted_at(
        project_code="project-a",
        test_asset_id="ta_missing",
        expected_row_version=1,
        deleted_at=datetime(2026, 8, 2, tzinfo=UTC),
        updated_by="reviewer",
    )

    evie_ai_session.refresh(test_asset)
    assert _asset_state(test_asset) == state_before
    assert (
        evie_ai_session.scalar(select(func.count()).select_from(AssetModel))
        == asset_count
    )
    assert (
        evie_ai_session.scalar(select(func.count()).select_from(AssetVersionModel))
        == version_count
    )


def test_deleted_at_cas_rejects_cross_project_restore_without_changes(
    evie_ai_session: Session,
) -> None:
    repository = AssetRepository(evie_ai_session)
    test_asset, _ = _bound_test_asset(
        repository,
        asset_code="ASSET-RESTORE-CROSS-PROJECT",
    )
    assert repository.compare_and_set_deleted_at(
        project_code="project-a",
        test_asset_id=test_asset.test_asset_id,
        expected_row_version=1,
        deleted_at=datetime(2026, 8, 2, tzinfo=UTC),
        updated_by="reviewer",
    )
    state_before = _asset_state(test_asset)

    assert not repository.compare_and_set_deleted_at(
        project_code="project-b",
        test_asset_id=test_asset.test_asset_id,
        expected_row_version=2,
        deleted_at=None,
        updated_by="reviewer",
    )

    evie_ai_session.refresh(test_asset)
    assert _asset_state(test_asset) == state_before


def test_deleted_at_cas_rejects_missing_asset_restore_without_changes(
    evie_ai_session: Session,
) -> None:
    repository = AssetRepository(evie_ai_session)
    test_asset, _ = _bound_test_asset(
        repository,
        asset_code="ASSET-RESTORE-MISSING",
    )
    state_before = _asset_state(test_asset)
    asset_count = evie_ai_session.scalar(select(func.count()).select_from(AssetModel))

    assert not repository.compare_and_set_deleted_at(
        project_code="project-a",
        test_asset_id="ta_missing",
        expected_row_version=1,
        deleted_at=None,
        updated_by="reviewer",
    )

    evie_ai_session.refresh(test_asset)
    assert _asset_state(test_asset) == state_before
    assert (
        evie_ai_session.scalar(select(func.count()).select_from(AssetModel))
        == asset_count
    )


def test_deleted_current_version_is_available_only_to_restore_query(
    evie_ai_session: Session,
) -> None:
    repository = AssetRepository(evie_ai_session)
    test_asset, version = _bound_test_asset(
        repository,
        asset_code="ASSET-RESTORE-001",
    )
    deleted_at = datetime(2026, 8, 2, tzinfo=UTC)

    assert repository.compare_and_set_deleted_at(
        project_code="project-a",
        test_asset_id=test_asset.test_asset_id,
        expected_row_version=1,
        deleted_at=deleted_at,
        updated_by="reviewer",
    )
    assert not repository.compare_and_set_deleted_at(
        project_code="project-a",
        test_asset_id=test_asset.test_asset_id,
        expected_row_version=2,
        deleted_at=datetime(2026, 8, 3, tzinfo=UTC),
        updated_by="reviewer",
    )
    assert (
        repository.get_by_test_asset_id(
            test_asset.test_asset_id,
            project_code="project-a",
        )
        is None
    )
    assert repository.get_current_version(test_asset.id) is None
    assert (
        repository.get_deleted_current_version_for_restore(
            project_code="project-a",
            test_asset_id=test_asset.test_asset_id,
        )
        is version
    )
    assert not repository.compare_and_set_deleted_at(
        project_code="project-a",
        test_asset_id=test_asset.test_asset_id,
        expected_row_version=1,
        deleted_at=None,
        updated_by="reviewer",
    )
    assert repository.compare_and_set_deleted_at(
        project_code="project-a",
        test_asset_id=test_asset.test_asset_id,
        expected_row_version=2,
        deleted_at=None,
        updated_by="reviewer",
    )
    assert not repository.compare_and_set_deleted_at(
        project_code="project-a",
        test_asset_id=test_asset.test_asset_id,
        expected_row_version=3,
        deleted_at=None,
        updated_by="reviewer",
    )

    evie_ai_session.refresh(test_asset)
    assert test_asset.deleted_at is None
    assert test_asset.row_version == 3


def test_deleted_current_version_restore_query_hides_ineligible_assets(
    evie_ai_session: Session,
) -> None:
    repository = AssetRepository(evie_ai_session)
    active_asset, _ = _bound_test_asset(
        repository,
        asset_code="ASSET-RESTORE-ACTIVE",
    )
    deleted_asset, _ = _bound_test_asset(
        repository,
        asset_code="ASSET-RESTORE-OTHER-PROJECT",
        project_code="project-b",
    )
    assert repository.compare_and_set_deleted_at(
        project_code="project-b",
        test_asset_id=deleted_asset.test_asset_id,
        expected_row_version=1,
        deleted_at=datetime(2026, 8, 2, tzinfo=UTC),
        updated_by="reviewer",
    )

    assert (
        repository.get_deleted_current_version_for_restore(
            project_code="project-a",
            test_asset_id=active_asset.test_asset_id,
        )
        is None
    )
    assert (
        repository.get_deleted_current_version_for_restore(
            project_code="project-a",
            test_asset_id=deleted_asset.test_asset_id,
        )
        is None
    )
    assert (
        repository.get_deleted_current_version_for_restore(
            project_code="project-b",
            test_asset_id="ta_missing",
        )
        is None
    )


def test_deleted_current_version_restore_query_fails_closed_without_pointer(
    evie_ai_session: Session,
) -> None:
    repository = AssetRepository(evie_ai_session)
    test_asset, _ = _bound_test_asset(
        repository,
        asset_code="ASSET-RESTORE-BROKEN-POINTER",
    )
    assert repository.compare_and_set_deleted_at(
        project_code="project-a",
        test_asset_id=test_asset.test_asset_id,
        expected_row_version=1,
        deleted_at=datetime(2026, 8, 2, tzinfo=UTC),
        updated_by="reviewer",
    )
    test_asset.current_version_pk = None
    evie_ai_session.flush()

    assert (
        repository.get_deleted_current_version_for_restore(
            project_code="project-a",
            test_asset_id=test_asset.test_asset_id,
        )
        is None
    )


def test_deleted_current_version_restore_query_rejects_foreign_current_version(
    evie_ai_session: Session,
) -> None:
    repository = AssetRepository(evie_ai_session)
    test_asset, _ = _bound_test_asset(
        repository,
        asset_code="ASSET-RESTORE-FOREIGN-POINTER",
    )
    other_asset, other_version = _bound_test_asset(
        repository,
        asset_code="ASSET-RESTORE-FOREIGN-VERSION",
    )
    assert repository.compare_and_set_deleted_at(
        project_code="project-a",
        test_asset_id=test_asset.test_asset_id,
        expected_row_version=1,
        deleted_at=datetime(2026, 8, 2, tzinfo=UTC),
        updated_by="reviewer",
    )
    test_asset.current_version_pk = other_version.id
    evie_ai_session.flush()
    asset_state_before = _asset_state(test_asset)
    other_asset_state_before = _asset_state(other_asset)

    assert (
        repository.get_deleted_current_version_for_restore(
            project_code="project-a",
            test_asset_id=test_asset.test_asset_id,
        )
        is None
    )

    evie_ai_session.refresh(test_asset)
    evie_ai_session.refresh(other_asset)
    assert _asset_state(test_asset) == asset_state_before
    assert _asset_state(other_asset) == other_asset_state_before
    assert other_version.expected_result == "进入首页"


def test_source_requirement_version_must_belong_to_requirement(
    evie_ai_session: Session,
) -> None:
    requirement_repository = RequirementRepository(evie_ai_session)
    first = requirement_repository.add(_requirement(code="REQ-001"))
    second = requirement_repository.add(_requirement(code="REQ-002"))
    second_version = requirement_repository.add_version(_requirement_version(second.id))
    asset_repository = AssetRepository(evie_ai_session)
    test_asset = asset_repository.add(_test_asset())

    with pytest.raises(SourceOwnershipError) as exc_info:
        asset_repository.add_source(
            _source(
                test_asset_pk=test_asset.id,
            ),
            requirement_pk=first.id,
            requirement_version_pk=second_version.id,
        )

    assert exc_info.value.error_code == "EVIE_AI_SOURCE_OWNERSHIP_MISMATCH"


def test_duplicate_version_number_is_rejected_by_database(
    evie_ai_session: Session,
) -> None:
    repository = RequirementRepository(evie_ai_session)
    requirement = repository.add(_requirement())
    repository.add_version(_requirement_version(requirement.id, version_no=1))

    with pytest.raises(IntegrityError):
        repository.add_version(_requirement_version(requirement.id, version_no=1))


def test_duplicate_asset_source_is_rejected_by_database(
    evie_ai_session: Session,
) -> None:
    requirement_repository = RequirementRepository(evie_ai_session)
    requirement = requirement_repository.add(_requirement())
    requirement_version = requirement_repository.add_version(
        _requirement_version(requirement.id)
    )
    asset_repository = AssetRepository(evie_ai_session)
    test_asset = asset_repository.add(_test_asset())
    source_kwargs = {
        "test_asset_pk": test_asset.id,
    }
    asset_repository.add_source(
        _source(**source_kwargs),
        requirement_pk=requirement.id,
        requirement_version_pk=requirement_version.id,
    )

    with pytest.raises(IntegrityError):
        asset_repository.add_source(
            _source(**source_kwargs),
            requirement_pk=requirement.id,
            requirement_version_pk=requirement_version.id,
        )


def test_requirement_source_main_and_subtype_roll_back_together(
    evie_ai_session: Session,
) -> None:
    requirement_repository = RequirementRepository(evie_ai_session)
    requirement = requirement_repository.add(_requirement())
    requirement_version = requirement_repository.add_version(
        _requirement_version(requirement.id)
    )
    asset_repository = AssetRepository(evie_ai_session)
    test_asset = asset_repository.add(_test_asset())

    asset_repository.add_source(
        _source(test_asset_pk=test_asset.id),
        requirement_pk=requirement.id,
        requirement_version_pk=requirement_version.id,
    )
    assert (
        evie_ai_session.scalar(select(func.count()).select_from(AssetSourceModel)) == 1
    )
    assert (
        evie_ai_session.scalar(select(func.count()).select_from(RequirementSourceModel))
        == 1
    )

    evie_ai_session.rollback()

    assert (
        evie_ai_session.scalar(select(func.count()).select_from(AssetSourceModel)) == 0
    )
    assert (
        evie_ai_session.scalar(select(func.count()).select_from(RequirementSourceModel))
        == 0
    )


def test_caller_rollback_removes_all_uncommitted_aggregate_rows(
    evie_ai_session: Session,
) -> None:
    repository = RequirementRepository(evie_ai_session)
    requirement = repository.add(_requirement())
    repository.add_version(_requirement_version(requirement.id, version_no=1))

    with pytest.raises(IntegrityError):
        repository.add_version(_requirement_version(requirement.id, version_no=1))
    evie_ai_session.rollback()

    requirement_count = evie_ai_session.execute(
        select(func.count()).select_from(Requirement)
    ).scalar_one()
    version_count = evie_ai_session.execute(
        select(func.count()).select_from(RequirementVersion)
    ).scalar_one()
    assert requirement_count == 0
    assert version_count == 0


def test_evie_ai_repositories_do_not_control_transactions() -> None:
    repository_dir = (
        Path(__file__).resolve().parents[3] / "app" / "repositories" / "evie_ai"
    )
    forbidden_calls: list[tuple[str, int, str]] = []

    for path in repository_dir.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in {"commit", "rollback"}
            ):
                forbidden_calls.append((path.name, node.lineno, node.func.attr))

    assert forbidden_calls == []
