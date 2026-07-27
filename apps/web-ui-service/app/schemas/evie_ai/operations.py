"""EvieAi 审核、删除恢复、结果和错误契约。"""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.constants.evie_ai import (
    TestAssetAuditEventType,
    TestAssetOperationType,
    TestAssetReviewAction,
    TestAssetReviewStatus,
)
from app.core.id_gen import (
    TEST_ASSET_AUDIT_EVENT_ID_PATTERN,
    TEST_ASSET_ID_PATTERN,
    TEST_ASSET_REVIEW_ID_PATTERN,
    TEST_ASSET_SOURCE_ID_PATTERN,
    TEST_ASSET_VERSION_ID_PATTERN,
)
from app.errors.evie_ai import EvieAiErrorCode, EvieAiErrorStage
from app.schemas.evie_ai.base import SHA256_HEX_PATTERN, EvieAiReadSchema, EvieAiSchema


class TestAssetReviewCreate(EvieAiSchema):
    test_asset_version_id: str = Field(pattern=TEST_ASSET_VERSION_ID_PATTERN)
    expected_row_version: int = Field(ge=1)
    decision: TestAssetReviewAction
    comment: str | None = None
    reason: str | None = None


class TestAssetDeleteRequest(EvieAiSchema):
    expected_row_version: int = Field(ge=1)
    reason: str = Field(min_length=1)


class TestAssetRestoreRequest(EvieAiSchema):
    expected_row_version: int = Field(ge=1)
    reason: str = Field(min_length=1)


class TestAssetOperationResult(EvieAiReadSchema):
    operation_type: TestAssetOperationType
    test_asset_id: str = Field(pattern=TEST_ASSET_ID_PATTERN)
    test_asset_version_id: str | None = Field(
        default=None,
        pattern=TEST_ASSET_VERSION_ID_PATTERN,
    )
    test_asset_review_record_id: str | None = Field(
        default=None,
        pattern=TEST_ASSET_REVIEW_ID_PATTERN,
    )
    created: bool = False
    reused_existing: bool = False
    changed: bool = False
    row_version: int = Field(ge=1)
    deleted: bool = False


class TestAssetReviewRead(EvieAiReadSchema):
    test_asset_review_record_id: str = Field(pattern=TEST_ASSET_REVIEW_ID_PATTERN)
    test_asset_id: str = Field(pattern=TEST_ASSET_ID_PATTERN)
    test_asset_version_id: str = Field(pattern=TEST_ASSET_VERSION_ID_PATTERN)
    from_status: TestAssetReviewStatus
    to_status: TestAssetReviewStatus
    review_action: TestAssetReviewAction
    reviewer: str
    reviewed_at: datetime
    comment: str | None
    reason: str | None
    request_id: str | None
    correlation_id: str | None


class TestAssetAuditEventRead(EvieAiReadSchema):
    test_asset_audit_event_id: str = Field(
        pattern=TEST_ASSET_AUDIT_EVENT_ID_PATTERN
    )
    test_asset_id: str = Field(pattern=TEST_ASSET_ID_PATTERN)
    event_type: TestAssetAuditEventType
    actor: str
    channel: str
    operation_type: TestAssetOperationType
    related_test_asset_version_id: str | None = Field(
        default=None,
        pattern=TEST_ASSET_VERSION_ID_PATTERN,
    )
    related_test_asset_source_id: str | None = Field(
        default=None,
        pattern=TEST_ASSET_SOURCE_ID_PATTERN,
    )
    related_review_record_id: str | None = Field(
        default=None,
        pattern=TEST_ASSET_REVIEW_ID_PATTERN,
    )
    reason: str | None = None
    before_state_summary: dict[str, object] | None = None
    after_state_summary: dict[str, object] | None = None
    created_at: datetime


class IdempotencyAssociationSnapshot(EvieAiSchema):
    operation_type: TestAssetOperationType
    idempotency_scope_hash: str = Field(pattern=SHA256_HEX_PATTERN)
    idempotency_key_hash: str = Field(pattern=SHA256_HEX_PATTERN)
    idempotency_generation: int = Field(ge=1)


class EvieAiErrorBody(EvieAiReadSchema):
    code: EvieAiErrorCode
    domain: str
    stage: EvieAiErrorStage
    message: str
    retryable: bool
    trace_id: str | None = None
    details: dict[str, object] = Field(default_factory=dict)
    request_id: str


class EvieAiErrorResponse(EvieAiReadSchema):
    error: EvieAiErrorBody
