from __future__ import annotations

from datetime import UTC, datetime

import pytest
from app.constants.evie_ai import (
    RequirementStatus,
    RequirementVersionStatus,
)
from app.constants.evie_ai import (
    TestAssetConversionStatus as AssetConversionStatus,
)
from app.constants.evie_ai import (
    TestAssetOperationType as AssetOperationType,
)
from app.constants.evie_ai import (
    TestAssetReviewAction as AssetReviewAction,
)
from app.constants.evie_ai import (
    TestAssetReviewStatus as AssetReviewStatus,
)
from app.constants.evie_ai import (
    TestAssetSourceType as AssetSourceType,
)
from app.schemas.evie_ai import (
    EvieAiErrorBody,
    EvieAiErrorResponse,
    IdempotencyAssociationSnapshot,
    ManualTestAssetSourceCreate,
    ManualTestAssetSourceRead,
    RequirementCreate,
    RequirementRead,
    RequirementTestAssetSourceCreate,
    RequirementTestAssetSourceRead,
    RequirementVersionCreate,
    RequirementVersionRead,
)
from app.schemas.evie_ai import (
    TestAssetContent as AssetContent,
)
from app.schemas.evie_ai import (
    TestAssetCreate as AssetCreate,
)
from app.schemas.evie_ai import (
    TestAssetDeleteRequest as AssetDeleteRequest,
)
from app.schemas.evie_ai import (
    TestAssetHistoricalVersionRestore as AssetHistoricalVersionRestore,
)
from app.schemas.evie_ai import (
    TestAssetListQuery as AssetListQuery,
)
from app.schemas.evie_ai import (
    TestAssetOperationResult as AssetOperationResult,
)
from app.schemas.evie_ai import (
    TestAssetRead as AssetRead,
)
from app.schemas.evie_ai import (
    TestAssetRestoreRequest as AssetRestoreRequest,
)
from app.schemas.evie_ai import (
    TestAssetReviewCreate as AssetReviewCreate,
)
from app.schemas.evie_ai import (
    TestAssetSourceCreate as AssetSourceCreate,
)
from app.schemas.evie_ai import (
    TestAssetVersionCreate as AssetVersionCreate,
)
from app.schemas.evie_ai import (
    TestAssetVersionRead as AssetVersionRead,
)
from pydantic import TypeAdapter, ValidationError

FORBIDDEN_MACHINE_FIELDS = {
    "action",
    "target",
    "value",
    "locator",
    "selector",
    "structured_steps",
    "steps_hint",
    "compiler_ir",
    "dsl",
    "script_code",
    "runner_steps",
    "selected_candidates",
}
SCHEMAS = (
    RequirementCreate,
    RequirementVersionCreate,
    RequirementRead,
    RequirementVersionRead,
    AssetContent,
    AssetCreate,
    AssetVersionCreate,
    AssetHistoricalVersionRestore,
    AssetRead,
    AssetVersionRead,
    ManualTestAssetSourceCreate,
    RequirementTestAssetSourceCreate,
    ManualTestAssetSourceRead,
    RequirementTestAssetSourceRead,
    AssetReviewCreate,
    AssetDeleteRequest,
    AssetRestoreRequest,
    AssetOperationResult,
    IdempotencyAssociationSnapshot,
    EvieAiErrorBody,
    EvieAiErrorResponse,
    AssetListQuery,
)


def test_all_evie_ai_schemas_forbid_undeclared_fields() -> None:
    for schema in SCHEMAS:
        assert schema.model_config.get("extra") == "forbid"


def test_evie_ai_schemas_contain_no_machine_execution_fields() -> None:
    for schema in SCHEMAS:
        assert FORBIDDEN_MACHINE_FIELDS.isdisjoint(schema.model_fields)


def test_intake_rejects_client_controlled_identity_and_governance_fields() -> None:
    valid = {
        "project_code": "project-a",
        "source": {"type": "manual"},
        "content": {"title": "Login"},
    }
    value = AssetCreate.model_validate(valid)
    assert value.source.type is AssetSourceType.MANUAL

    for forbidden_field, forbidden_value in (
        ("test_asset_id", "ta_0123456789abcdef0123456789abcdef"),
        ("asset_code", "ASSET-001"),
        ("actor_or_client_id", "user:usr_fake"),
        ("source_identity_hash", "a" * 64),
    ):
        with pytest.raises(ValidationError):
            AssetCreate.model_validate(
                {**valid, forbidden_field: forbidden_value}
            )


def test_source_discriminated_union_accepts_only_approved_shapes() -> None:
    adapter = TypeAdapter(AssetSourceCreate)
    manual = adapter.validate_python({"type": "manual"})
    requirement = adapter.validate_python(
        {
            "type": "requirement",
            "requirement_id": "req_0123456789abcdef0123456789abcdef",
            "requirement_version_id": "reqv_0123456789abcdef0123456789abcdef",
        }
    )
    assert isinstance(manual, ManualTestAssetSourceCreate)
    assert isinstance(requirement, RequirementTestAssetSourceCreate)

    with pytest.raises(ValidationError):
        adapter.validate_python(
            {
                "type": "manual",
                "requirement_id": "req_0123456789abcdef0123456789abcdef",
            }
        )
    with pytest.raises(ValidationError):
        adapter.validate_python(
            {"type": "requirement", "source_identity_hash": "a" * 64}
        )


def test_natural_language_content_accepts_incomplete_content() -> None:
    value = AssetContent()
    assert value.title == ""
    assert value.natural_steps == []
    assert value.expected_result == ""


def test_natural_language_content_rejects_machine_execution_payload() -> None:
    with pytest.raises(ValidationError) as exc_info:
        AssetContent(
            title="Login",
            structured_steps=[{"action": "click", "target": "login-button"}],
        )
    assert exc_info.value.errors()[0]["type"] == "extra_forbidden"


def test_version_and_lifecycle_writes_require_positive_row_version() -> None:
    with pytest.raises(ValidationError):
        AssetVersionCreate(
            expected_row_version=0,
            content=AssetContent(),
        )
    with pytest.raises(ValidationError):
        AssetDeleteRequest(expected_row_version=0, reason="cleanup")
    with pytest.raises(ValidationError):
        AssetRestoreRequest(expected_row_version=0, reason="restore")
    with pytest.raises(ValidationError):
        AssetHistoricalVersionRestore(expected_row_version=0, reason="restore")


def test_review_write_targets_explicit_version_and_current_row_version() -> None:
    value = AssetReviewCreate(
        test_asset_version_id="tav_0123456789abcdef0123456789abcdef",
        expected_row_version=2,
        decision=AssetReviewAction.APPROVE,
    )
    assert value.expected_row_version == 2
    assert value.decision is AssetReviewAction.APPROVE


def test_read_schemas_expose_public_ids_without_internal_primary_keys() -> None:
    now = datetime.now(UTC)
    requirement = RequirementRead(
        requirement_id="req_0123456789abcdef0123456789abcdef",
        project_code="project-a",
        requirement_code="REQ-001",
        external_requirement_key=None,
        status=RequirementStatus.DRAFT,
        current_version_id=None,
        row_version=1,
        created_at=now,
        updated_at=now,
        deleted_at=None,
        created_by="user:usr_0123456789abcdef0123456789abcdef",
        updated_by="user:usr_0123456789abcdef0123456789abcdef",
    )
    asset = AssetRead(
        test_asset_id="ta_0123456789abcdef0123456789abcdef",
        project_code="project-a",
        asset_code="ta_0123456789abcdef0123456789abcdef",
        review_status=AssetReviewStatus.PENDING,
        conversion_status=AssetConversionStatus.NOT_STARTED,
        current_version_id=None,
        row_version=1,
        created_at=now,
        updated_at=now,
        deleted_at=None,
        created_by="user:usr_0123456789abcdef0123456789abcdef",
        updated_by="user:usr_0123456789abcdef0123456789abcdef",
    )
    assert requirement.requirement_id.startswith("req_")
    assert asset.test_asset_id.startswith("ta_")
    assert "id" not in RequirementRead.model_fields
    assert "current_version_pk" not in RequirementRead.model_fields
    assert "id" not in AssetRead.model_fields
    assert "current_version_pk" not in AssetRead.model_fields


def test_version_read_schemas_are_immutable_by_shape() -> None:
    for schema in (RequirementVersionRead, AssetVersionRead):
        assert "updated_at" not in schema.model_fields
        assert "updated_by" not in schema.model_fields
    assert RequirementVersionStatus.DRAFT.value == "draft"


def test_operation_result_contains_only_stable_public_result_summary() -> None:
    result = AssetOperationResult(
        operation_type=AssetOperationType.CREATE_ASSET,
        test_asset_id="ta_0123456789abcdef0123456789abcdef",
        created=True,
        row_version=1,
    )
    assert result.created is True
    assert "natural_steps" not in AssetOperationResult.model_fields
    assert "idempotency_key" not in AssetOperationResult.model_fields


def test_list_query_has_frozen_pagination_defaults_and_limits() -> None:
    query = AssetListQuery(project_code="project-a")
    assert (query.page, query.page_size) == (1, 20)
    with pytest.raises(ValidationError):
        AssetListQuery(project_code="project-a", page_size=101)
