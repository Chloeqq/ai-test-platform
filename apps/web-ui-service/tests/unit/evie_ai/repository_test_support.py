"""Slice 4 Repository 测试专用对象工厂。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.constants.evie_ai import (
    RequirementStatus,
    RequirementVersionStatus,
    TestAssetAuditEventType,
    TestAssetConversionStatus,
    TestAssetOperationType,
    TestAssetReviewAction,
    TestAssetReviewStatus,
    TestAssetSourceType,
)
from app.core.id_gen import (
    generate_requirement_id,
    generate_requirement_version_id,
    generate_test_asset_audit_event_id,
    generate_test_asset_id,
    generate_test_asset_review_id,
    generate_test_asset_source_id,
    generate_test_asset_version_id,
)
from app.models.evie_ai import (
    Requirement,
    RequirementVersion,
    TestAsset,
    TestAssetAuditEvent,
    TestAssetContentClaim,
    TestAssetIdempotencyRecord,
    TestAssetReviewRecord,
    TestAssetSource,
    TestAssetVersion,
)

ACTOR = "user:usr_0123456789abcdef0123456789abcdef"
PROJECT_CODE = "project-a"


def make_requirement(*, project_code: str = PROJECT_CODE) -> Requirement:
    return Requirement(
        requirement_id=generate_requirement_id(),
        project_code=project_code,
        requirement_code=f"REQ-{generate_requirement_id()[-8:]}",
        status=RequirementStatus.ACTIVE.value,
        created_by=ACTOR,
        updated_by=ACTOR,
    )


def make_requirement_version(requirement_pk: int) -> RequirementVersion:
    return RequirementVersion(
        requirement_version_id=generate_requirement_version_id(),
        requirement_pk=requirement_pk,
        version_no=1,
        title="登录需求",
        content="用户可以登录系统",
        content_checksum="1" * 64,
        version_status=RequirementVersionStatus.EFFECTIVE.value,
        created_by=ACTOR,
    )


def make_asset(
    *,
    project_code: str = PROJECT_CODE,
    test_asset_id: str | None = None,
    deleted_at: datetime | None = None,
) -> TestAsset:
    public_id = test_asset_id or generate_test_asset_id()
    return TestAsset(
        test_asset_id=public_id,
        project_code=project_code,
        asset_code=public_id,
        review_status=TestAssetReviewStatus.PENDING.value,
        conversion_status=TestAssetConversionStatus.NOT_STARTED.value,
        deleted_at=deleted_at,
        created_by=ACTOR,
        updated_by=ACTOR,
    )


def make_asset_version(
    test_asset_pk: int,
    *,
    version_no: int = 1,
    title: str = "登录成功",
    priority: str = "P1",
    tags: list[str] | None = None,
) -> TestAssetVersion:
    return TestAssetVersion(
        test_asset_version_id=generate_test_asset_version_id(),
        test_asset_pk=test_asset_pk,
        version_no=version_no,
        title=title,
        precondition="用户已进入登录页",
        natural_steps=["输入账号密码", "点击登录"],
        expected_result="进入首页",
        priority=priority,
        tags=tags or ["login"],
        content_checksum=f"{version_no % 10}" * 64,
        created_by=ACTOR,
    )


def make_source(
    test_asset_pk: int,
    *,
    source_type: str = TestAssetSourceType.MANUAL.value,
    source_identity_hash: str = "2" * 64,
) -> TestAssetSource:
    return TestAssetSource(
        test_asset_source_id=generate_test_asset_source_id(),
        test_asset_pk=test_asset_pk,
        source_type=source_type,
        source_identity_hash=source_identity_hash,
        created_by=ACTOR,
    )


def make_idempotency_record(
    *,
    key: str = "request-key",
    fingerprint: str = "3" * 64,
    expires_at: datetime | None = None,
) -> TestAssetIdempotencyRecord:
    return TestAssetIdempotencyRecord(
        project_code=PROJECT_CODE,
        operation_type=TestAssetOperationType.CREATE_ASSET.value,
        actor_or_client_id=ACTOR,
        idempotency_key=key,
        request_fingerprint=fingerprint,
        expires_at=expires_at or datetime.now(UTC) + timedelta(days=7),
        generation=1,
    )


def make_content_claim(
    test_asset_pk: int,
    *,
    fingerprint: str = "4" * 64,
) -> TestAssetContentClaim:
    return TestAssetContentClaim(
        test_asset_pk=test_asset_pk,
        project_code=PROJECT_CODE,
        content_fingerprint=fingerprint,
    )


def make_review(
    *,
    test_asset_pk: int,
    test_asset_version_pk: int,
    reviewed_at: datetime | None = None,
    to_status: str = TestAssetReviewStatus.APPROVED.value,
) -> TestAssetReviewRecord:
    return TestAssetReviewRecord(
        test_asset_review_record_id=generate_test_asset_review_id(),
        test_asset_pk=test_asset_pk,
        test_asset_version_pk=test_asset_version_pk,
        from_status=TestAssetReviewStatus.PENDING.value,
        to_status=to_status,
        review_action=TestAssetReviewAction.APPROVE.value,
        reviewer=ACTOR,
        reviewed_at=reviewed_at or datetime.now(UTC),
        operation_type=TestAssetOperationType.REVIEW_ASSET.value,
        idempotency_scope_hash="5" * 64,
        idempotency_key_hash="6" * 64,
        idempotency_generation=1,
    )


def make_audit(
    *,
    test_asset_pk: int,
    event_type: str = TestAssetAuditEventType.ASSET_CREATED.value,
) -> TestAssetAuditEvent:
    return TestAssetAuditEvent(
        test_asset_audit_event_id=generate_test_asset_audit_event_id(),
        test_asset_pk=test_asset_pk,
        event_type=event_type,
        actor=ACTOR,
        channel="api",
        operation_type=TestAssetOperationType.CREATE_ASSET.value,
        idempotency_scope_hash="5" * 64,
        idempotency_key_hash="6" * 64,
        idempotency_generation=1,
        before_state_summary=None,
        after_state_summary={"review_status": "pending"},
    )
