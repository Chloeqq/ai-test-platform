from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.constants.evie_ai import (
    RequirementStatus,
    RequirementVersionStatus,
    TestAssetConversionStatus as AssetConversionStatus,
    TestAssetReviewStatus as AssetReviewStatus,
)
from app.schemas.evie_ai import (
    RequirementCreate,
    RequirementRead,
    RequirementVersionCreate,
    RequirementVersionRead,
    TestAssetCreate as AssetCreate,
    TestAssetRead as AssetRead,
    TestAssetSourceCreate as AssetSourceCreate,
    TestAssetSourceRead as AssetSourceRead,
    TestAssetVersionCreate as AssetVersionCreate,
    TestAssetVersionRead as AssetVersionRead,
)


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
    AssetCreate,
    AssetVersionCreate,
    AssetSourceCreate,
    AssetRead,
    AssetVersionRead,
    AssetSourceRead,
)


def test_all_evie_ai_schemas_forbid_undeclared_fields() -> None:
    for schema in SCHEMAS:
        assert schema.model_config.get("extra") == "forbid"


def test_evie_ai_schemas_contain_no_machine_execution_fields() -> None:
    for schema in SCHEMAS:
        assert FORBIDDEN_MACHINE_FIELDS.isdisjoint(schema.model_fields)


def test_create_schemas_do_not_accept_client_controlled_public_ids() -> None:
    with pytest.raises(ValidationError):
        RequirementCreate(
            project_code="project-a",
            requirement_code="REQ-001",
            requirement_id="req_0123456789abcdef0123456789abcdef",
        )

    with pytest.raises(ValidationError):
        AssetCreate(
            project_code="project-a",
            asset_code="ASSET-001",
            test_asset_id="ta_0123456789abcdef0123456789abcdef",
        )


def test_test_asset_version_accepts_incomplete_natural_language_content() -> None:
    value = AssetVersionCreate()

    assert value.title == ""
    assert value.natural_steps == []
    assert value.expected_result == ""


def test_test_asset_version_rejects_machine_execution_payload() -> None:
    with pytest.raises(ValidationError) as exc_info:
        AssetVersionCreate(
            title="登录",
            natural_steps=["点击登录"],
            expected_result="进入首页",
            structured_steps=[{"action": "click", "target": "login-button"}],
        )

    assert exc_info.value.errors()[0]["type"] == "extra_forbidden"


def test_test_asset_source_requires_existing_public_id_formats() -> None:
    value = AssetSourceCreate(
        requirement_id="req_0123456789abcdef0123456789abcdef",
        requirement_version_id="reqv_0123456789abcdef0123456789abcdef",
        source_identity_hash="a" * 64,
    )
    assert value.requirement_id.startswith("req_")

    with pytest.raises(ValidationError):
        AssetSourceCreate(
            requirement_id="request-1",
            requirement_version_id="reqv_0123456789abcdef0123456789abcdef",
            source_identity_hash="a" * 64,
        )


def test_read_schemas_expose_public_ids_without_internal_primary_keys() -> None:
    now = datetime.now(timezone.utc)
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
        created_by="tester",
        updated_by="tester",
    )
    test_asset = AssetRead(
        test_asset_id="ta_0123456789abcdef0123456789abcdef",
        project_code="project-a",
        asset_code="ASSET-001",
        review_status=AssetReviewStatus.PENDING,
        conversion_status=AssetConversionStatus.NOT_STARTED,
        current_version_id=None,
        row_version=1,
        created_at=now,
        updated_at=now,
        deleted_at=None,
        created_by="tester",
        updated_by="tester",
    )

    assert "id" not in RequirementRead.model_fields
    assert "current_version_pk" not in RequirementRead.model_fields
    assert "id" not in AssetRead.model_fields
    assert "current_version_pk" not in AssetRead.model_fields


def test_version_read_schemas_are_immutable_by_shape() -> None:
    for schema in (RequirementVersionRead, AssetVersionRead):
        assert "updated_at" not in schema.model_fields
        assert "updated_by" not in schema.model_fields

    assert RequirementVersionStatus.DRAFT.value == "draft"
