from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from typing import cast

import pytest
from app.constants.evie_ai import (
    RequirementStatus,
    RequirementVersionStatus,
)
from app.constants.evie_ai import (
    TestAssetAuditEventType as AuditEventType,
)
from app.constants.evie_ai import (
    TestAssetConversionStatus as AssetConversionStatus,
)
from app.constants.evie_ai import (
    TestAssetReviewStatus as AssetReviewStatus,
)
from app.core.id_gen import (
    generate_requirement_id,
    generate_requirement_version_id,
)
from app.errors.evie_ai import (
    EvieAiDomainError,
    EvieAiErrorCode,
    EvieAiErrorStage,
)
from app.models.evie_ai import (
    Requirement,
    RequirementVersion,
)
from app.models.evie_ai import (
    TestAsset as AssetModel,
)
from app.models.evie_ai import (
    TestAssetAuditEvent as AuditEventModel,
)
from app.models.evie_ai import (
    TestAssetContentClaim as ContentClaimModel,
)
from app.models.evie_ai import (
    TestAssetIdempotencyRecord as IdempotencyRecordModel,
)
from app.models.evie_ai import (
    TestAssetRequirementSource as RequirementSourceModel,
)
from app.models.evie_ai import (
    TestAssetReviewRecord as ReviewRecordModel,
)
from app.models.evie_ai import (
    TestAssetSource as SourceModel,
)
from app.models.evie_ai import (
    TestAssetVersion as VersionModel,
)
from app.models.test_project import TestProject as ProjectModel
from app.repositories.evie_ai.content_claim_repository import (
    TestAssetContentClaimRepository as ContentClaimRepository,
)
from app.repositories.evie_ai.governance_repository import (
    TestAssetAuditRepository as AuditRepository,
)
from app.repositories.evie_ai.idempotency_repository import (
    TestAssetIdempotencyRepository as IdempotencyRepository,
)
from app.repositories.evie_ai.requirement_repository import RequirementRepository
from app.repositories.evie_ai.source_repository import (
    TestAssetSourceRepository as SourceRepository,
)
from app.repositories.evie_ai.test_asset_repository import (
    TestAssetRepository as AssetRepository,
)
from app.schemas.evie_ai.source import (
    ManualTestAssetSourceCreate,
    RequirementTestAssetSourceCreate,
)
from app.schemas.evie_ai.test_asset import (
    TestAssetContent as AssetContentSchema,
)
from app.schemas.evie_ai.test_asset import TestAssetCreate as AssetCreateCommand
from app.services.evie_ai import test_asset_intake_service as intake_service_module
from app.services.evie_ai.project_scope_service import ProjectScopeService
from app.services.evie_ai.request_trace_context import RequestTraceContext
from app.services.evie_ai.test_asset_intake_service import (
    TestAssetIntakeService as IntakeService,
)
from app.services.evie_ai.user_public_identity_service import TrustedUserPrincipal
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

PROJECT_A = "projecta"
PROJECT_B = "projectb"
ACTOR_PUBLIC_ID = "usr_0123456789abcdef0123456789abcdef"
FIXED_NOW = datetime(2026, 7, 28, 8, 0, tzinfo=UTC)


def _utc_clock() -> datetime:
    return FIXED_NOW


@pytest.fixture()
def principal() -> TrustedUserPrincipal:
    return TrustedUserPrincipal(
        user_public_id=ACTOR_PUBLIC_ID,
        role="admin",
        is_active=True,
    )


@pytest.fixture()
def trace_context() -> RequestTraceContext:
    return RequestTraceContext.from_request_id("request-slice-6")


@pytest.fixture()
def intake_service(
    evie_ai_session_factory: sessionmaker[Session],
) -> IntakeService:
    return IntakeService(
        evie_ai_session_factory,
        idempotency_retention_days=7,
        clock=_utc_clock,
    )


def _seed_project(
    session_factory: sessionmaker[Session],
    project_code: str = PROJECT_A,
    *,
    status: str = "active",
) -> None:
    with session_factory.begin() as session:
        session.add(
            ProjectModel(
                project_code=project_code,
                project_name=f"Project {project_code}",
                status=status,
                created_by="test",
            )
        )


def _seed_requirement(
    session_factory: sessionmaker[Session],
    *,
    project_code: str = PROJECT_A,
    deleted: bool = False,
) -> tuple[str, str]:
    with session_factory.begin() as session:
        repository = RequirementRepository(session)
        requirement = repository.add(
            Requirement(
                requirement_id=generate_requirement_id(),
                project_code=project_code,
                requirement_code=f"REQ-{generate_requirement_id()[-8:]}",
                status=RequirementStatus.ACTIVE.value,
                deleted_at=datetime.now(UTC) if deleted else None,
                created_by="test",
                updated_by="test",
            )
        )
        version = repository.add_version(
            RequirementVersion(
                requirement_version_id=generate_requirement_version_id(),
                requirement_pk=requirement.id,
                version_no=1,
                title="登录需求",
                content="用户可以登录系统",
                content_checksum="1" * 64,
                version_status=RequirementVersionStatus.EFFECTIVE.value,
                created_by="test",
            )
        )
        return requirement.requirement_id, version.requirement_version_id


def _content(
    *,
    title: str = " 登录成功 ",
    expected_result: str = " 进入首页 ",
) -> AssetContentSchema:
    return AssetContentSchema(
        title=title,
        precondition=" 用户位于登录页 ",
        natural_steps=[" 输入账号密码 ", " 点击登录 "],
        expected_result=expected_result,
        priority=" P1 ",
        tags=[" smoke ", "login", "smoke"],
    )


def _manual_command(
    *,
    project_code: str = PROJECT_A,
    title: str = " 登录成功 ",
    expected_result: str = " 进入首页 ",
) -> AssetCreateCommand:
    return AssetCreateCommand(
        project_code=project_code,
        source=ManualTestAssetSourceCreate(),
        content=_content(title=title, expected_result=expected_result),
    )


def _requirement_command(
    *,
    requirement_id: str,
    requirement_version_id: str,
    project_code: str = PROJECT_A,
) -> AssetCreateCommand:
    return AssetCreateCommand(
        project_code=project_code,
        source=RequirementTestAssetSourceCreate(
            requirement_id=requirement_id,
            requirement_version_id=requirement_version_id,
        ),
        content=_content(),
    )


def _count(session: Session, model: type[object]) -> int:
    return int(session.scalar(select(func.count()).select_from(model)) or 0)


def _write_counts(
    session_factory: sessionmaker[Session],
) -> dict[type[object], int]:
    models = (
        AssetModel,
        VersionModel,
        SourceModel,
        RequirementSourceModel,
        ContentClaimModel,
        AuditEventModel,
        IdempotencyRecordModel,
        ReviewRecordModel,
    )
    with session_factory() as session:
        return {model: _count(session, model) for model in models}


def _write_rows(
    session_factory: sessionmaker[Session],
) -> dict[str, tuple[dict[str, object], ...]]:
    models = (
        AssetModel,
        VersionModel,
        SourceModel,
        RequirementSourceModel,
        ContentClaimModel,
        AuditEventModel,
        IdempotencyRecordModel,
        ReviewRecordModel,
    )
    with session_factory() as session:
        return {
            model.__tablename__: tuple(
                dict(row)
                for row in session.execute(
                    select(model.__table__).order_by(model.__table__.c.id)
                ).mappings()
            )
            for model in models
        }


def _serialized_audit_payload(event: AuditEventModel) -> str:
    public_payload = {
        "event_type": event.event_type,
        "actor": event.actor,
        "channel": event.channel,
        "request_id": event.request_id,
        "correlation_id": event.correlation_id,
        "operation_type": event.operation_type,
        "idempotency_scope_hash": event.idempotency_scope_hash,
        "idempotency_key_hash": event.idempotency_key_hash,
        "idempotency_generation": event.idempotency_generation,
        "related_test_asset_version_id": event.related_test_asset_version_id,
        "related_test_asset_source_id": event.related_test_asset_source_id,
        "reason": event.reason,
        "before_state_summary": event.before_state_summary,
        "after_state_summary": event.after_state_summary,
    }
    return json.dumps(public_payload, ensure_ascii=False, sort_keys=True)


def test_manual_intake_creates_complete_aggregate_with_row_version_one(
    evie_ai_session_factory: sessionmaker[Session],
    intake_service: IntakeService,
    principal: TrustedUserPrincipal,
    trace_context: RequestTraceContext,
) -> None:
    _seed_project(evie_ai_session_factory)

    result = intake_service.execute(
        _manual_command(),
        principal=principal,
        idempotency_key="manual-create-1",
        trace_context=trace_context,
    )

    assert result.created is True
    assert result.reused_existing is False
    assert result.row_version == 1
    with evie_ai_session_factory() as session:
        asset = session.execute(select(AssetModel)).scalar_one()
        version = session.execute(select(VersionModel)).scalar_one()
        source = session.execute(select(SourceModel)).scalar_one()
        audit = session.execute(select(AuditEventModel)).scalar_one()
        record = session.execute(select(IdempotencyRecordModel)).scalar_one()

        assert asset.current_version_pk == version.id
        assert asset.row_version == 1
        assert asset.review_status == AssetReviewStatus.PENDING.value
        assert asset.conversion_status == AssetConversionStatus.NOT_STARTED.value
        assert version.version_no == 1
        assert version.title == "登录成功"
        assert version.natural_steps == ["输入账号密码", "点击登录"]
        assert version.tags == ["login", "smoke"]
        assert source.source_type == "manual"
        assert _count(session, ContentClaimModel) == 1
        assert _count(session, ReviewRecordModel) == 0
        assert audit.event_type == AuditEventType.ASSET_CREATED.value
        assert audit.request_id == trace_context.request_id
        assert audit.correlation_id == trace_context.correlation_id
        assert record.completed_at is not None
        assert record.result_http_status == 201
        assert record.row_version == 1

        audit_payload = json.dumps(audit.after_state_summary, ensure_ascii=False)
        assert "登录成功" not in audit_payload
        assert "manual-create-1" not in audit_payload
        assert not hasattr(audit, "idempotency_key")


def test_intake_accepts_incomplete_natural_language_content(
    evie_ai_session_factory: sessionmaker[Session],
    intake_service: IntakeService,
    principal: TrustedUserPrincipal,
    trace_context: RequestTraceContext,
) -> None:
    _seed_project(evie_ai_session_factory)
    command = AssetCreateCommand(
        project_code=PROJECT_A,
        source=ManualTestAssetSourceCreate(),
        content=AssetContentSchema(
            title="",
            precondition=None,
            natural_steps=[],
            expected_result="",
            priority=None,
            tags=[],
        ),
    )

    result = intake_service.execute(
        command,
        principal=principal,
        idempotency_key="low-quality-content",
        trace_context=trace_context,
    )

    assert result.created is True
    with evie_ai_session_factory() as session:
        version = session.execute(select(VersionModel)).scalar_one()
        assert version.title == ""
        assert version.natural_steps == []
        assert version.expected_result == ""


def test_requirement_intake_creates_typed_source(
    evie_ai_session_factory: sessionmaker[Session],
    intake_service: IntakeService,
    principal: TrustedUserPrincipal,
    trace_context: RequestTraceContext,
) -> None:
    _seed_project(evie_ai_session_factory)
    requirement_id, version_id = _seed_requirement(evie_ai_session_factory)

    result = intake_service.execute(
        _requirement_command(
            requirement_id=requirement_id,
            requirement_version_id=version_id,
        ),
        principal=principal,
        idempotency_key="requirement-create-1",
        trace_context=trace_context,
    )

    assert result.created is True
    with evie_ai_session_factory() as session:
        source = session.execute(select(SourceModel)).scalar_one()
        subtype = session.execute(select(RequirementSourceModel)).scalar_one()
        requirement = session.execute(
            select(Requirement).where(Requirement.requirement_id == requirement_id)
        ).scalar_one()
        requirement_version = session.execute(
            select(RequirementVersion).where(
                RequirementVersion.requirement_version_id == version_id
            )
        ).scalar_one()
        assert source.source_type == "requirement"
        assert subtype.requirement_pk == requirement.id
        assert subtype.requirement_version_pk == requirement_version.id


@pytest.mark.parametrize(
    "scenario",
    ("unknown", "wrong-parent", "cross-project", "deleted"),
)
def test_requirement_intake_rejects_invalid_source_scope_without_partial_writes(
    scenario: str,
    evie_ai_session_factory: sessionmaker[Session],
    intake_service: IntakeService,
    principal: TrustedUserPrincipal,
    trace_context: RequestTraceContext,
) -> None:
    _seed_project(evie_ai_session_factory)
    _seed_project(evie_ai_session_factory, PROJECT_B)
    first_id, first_version_id = _seed_requirement(evie_ai_session_factory)

    if scenario == "unknown":
        requirement_id = "req_" + "e" * 32
        version_id = "reqv_" + "e" * 32
    elif scenario == "wrong-parent":
        _second_id, second_version_id = _seed_requirement(evie_ai_session_factory)
        requirement_id = first_id
        version_id = second_version_id
    elif scenario == "cross-project":
        requirement_id, version_id = _seed_requirement(
            evie_ai_session_factory,
            project_code=PROJECT_B,
        )
    else:
        requirement_id, version_id = _seed_requirement(
            evie_ai_session_factory,
            deleted=True,
        )

    with pytest.raises(EvieAiDomainError) as exc_info:
        intake_service.execute(
            _requirement_command(
                requirement_id=requirement_id,
                requirement_version_id=version_id,
            ),
            principal=principal,
            idempotency_key=f"invalid-source-{scenario}",
            trace_context=trace_context,
        )

    assert exc_info.value.code is EvieAiErrorCode.SOURCE_SCOPE_MISMATCH
    assert exc_info.value.stage is EvieAiErrorStage.INTAKE
    counts = _write_counts(evie_ai_session_factory)
    assert counts[AssetModel] == 0
    assert counts[IdempotencyRecordModel] == 0
    assert first_version_id


def test_same_idempotency_key_replays_result_and_rejects_changed_request(
    evie_ai_session_factory: sessionmaker[Session],
    intake_service: IntakeService,
    principal: TrustedUserPrincipal,
    trace_context: RequestTraceContext,
) -> None:
    _seed_project(evie_ai_session_factory)
    command = _manual_command()
    first = intake_service.execute(
        command,
        principal=principal,
        idempotency_key="replay-key",
        trace_context=trace_context,
    )
    replay = intake_service.execute(
        command,
        principal=principal,
        idempotency_key="replay-key",
        trace_context=trace_context,
    )

    assert replay == first
    counts = _write_counts(evie_ai_session_factory)
    assert counts[AssetModel] == 1
    assert counts[SourceModel] == 1
    assert counts[AuditEventModel] == 1
    assert counts[IdempotencyRecordModel] == 1

    with pytest.raises(EvieAiDomainError) as exc_info:
        intake_service.execute(
            _manual_command(title="另一个测试点"),
            principal=principal,
            idempotency_key="replay-key",
            trace_context=trace_context,
        )
    assert exc_info.value.code is EvieAiErrorCode.IDEMPOTENCY_CONFLICT
    assert exc_info.value.stage is EvieAiErrorStage.INTAKE


def test_corrupted_idempotency_result_fails_closed(
    evie_ai_session_factory: sessionmaker[Session],
    intake_service: IntakeService,
    principal: TrustedUserPrincipal,
    trace_context: RequestTraceContext,
) -> None:
    _seed_project(evie_ai_session_factory)
    command = _manual_command()
    intake_service.execute(
        command,
        principal=principal,
        idempotency_key="corrupted-result",
        trace_context=trace_context,
    )
    with evie_ai_session_factory.begin() as session:
        record = session.execute(select(IdempotencyRecordModel)).scalar_one()
        record.created = False

    with pytest.raises(EvieAiDomainError) as exc_info:
        intake_service.execute(
            command,
            principal=principal,
            idempotency_key="corrupted-result",
            trace_context=trace_context,
        )

    assert exc_info.value.code is EvieAiErrorCode.DATA_INTEGRITY_ERROR
    assert _write_counts(evie_ai_session_factory)[AssetModel] == 1


def test_created_replay_with_row_version_two_fails_closed(
    evie_ai_session_factory: sessionmaker[Session],
    intake_service: IntakeService,
    principal: TrustedUserPrincipal,
    trace_context: RequestTraceContext,
) -> None:
    _seed_project(evie_ai_session_factory)
    command = _manual_command()
    intake_service.execute(
        command,
        principal=principal,
        idempotency_key="corrupted-row-version",
        trace_context=trace_context,
    )
    before = _write_counts(evie_ai_session_factory)
    with evie_ai_session_factory.begin() as session:
        record = session.execute(select(IdempotencyRecordModel)).scalar_one()
        record.row_version = 2

    with pytest.raises(EvieAiDomainError) as exc_info:
        intake_service.execute(
            command,
            principal=principal,
            idempotency_key="corrupted-row-version",
            trace_context=trace_context,
        )

    assert exc_info.value.code is EvieAiErrorCode.DATA_INTEGRITY_ERROR
    assert _write_counts(evie_ai_session_factory) == before


def test_completed_replay_rejects_different_content_asset_without_side_effects(
    evie_ai_session_factory: sessionmaker[Session],
    intake_service: IntakeService,
    principal: TrustedUserPrincipal,
    trace_context: RequestTraceContext,
) -> None:
    _seed_project(evie_ai_session_factory)
    command_a = _manual_command(title="内容 A")
    command_b = _manual_command(title="内容 B")
    winner_a = intake_service.execute(
        command_a,
        principal=principal,
        idempotency_key="content-a-key",
        trace_context=trace_context,
    )
    winner_b = intake_service.execute(
        command_b,
        principal=principal,
        idempotency_key="content-b-key",
        trace_context=trace_context,
    )
    assert winner_a.test_asset_id != winner_b.test_asset_id

    with evie_ai_session_factory.begin() as session:
        record_a = session.execute(
            select(IdempotencyRecordModel).where(
                IdempotencyRecordModel.idempotency_key == "content-a-key"
            )
        ).scalar_one()
        record_a.test_asset_id = winner_b.test_asset_id
        record_a.test_asset_version_id = winner_b.test_asset_version_id
        record_a.row_version = winner_b.row_version

    before_counts = _write_counts(evie_ai_session_factory)
    before_rows = _write_rows(evie_ai_session_factory)
    with pytest.raises(EvieAiDomainError) as exc_info:
        intake_service.execute(
            command_a,
            principal=principal,
            idempotency_key="content-a-key",
            trace_context=trace_context,
        )

    assert exc_info.value.code is EvieAiErrorCode.DATA_INTEGRITY_ERROR
    assert exc_info.value.stage is EvieAiErrorStage.INTAKE
    assert _write_counts(evie_ai_session_factory) == before_counts
    assert _write_rows(evie_ai_session_factory) == before_rows


def test_expired_idempotency_record_is_reoccupied_for_a_new_request(
    evie_ai_session_factory: sessionmaker[Session],
    intake_service: IntakeService,
    principal: TrustedUserPrincipal,
    trace_context: RequestTraceContext,
) -> None:
    _seed_project(evie_ai_session_factory)
    intake_service.execute(
        _manual_command(),
        principal=principal,
        idempotency_key="expired-key",
        trace_context=trace_context,
    )
    with evie_ai_session_factory.begin() as session:
        record = session.execute(select(IdempotencyRecordModel)).scalar_one()
        record.expires_at = FIXED_NOW - timedelta(seconds=1)

    second = intake_service.execute(
        _manual_command(title="支付成功"),
        principal=principal,
        idempotency_key="expired-key",
        trace_context=trace_context,
    )

    assert second.created is True
    counts = _write_counts(evie_ai_session_factory)
    assert counts[AssetModel] == 2
    assert counts[IdempotencyRecordModel] == 1
    with evie_ai_session_factory() as session:
        record = session.execute(select(IdempotencyRecordModel)).scalar_one()
        assert record.generation == 2
        assert record.test_asset_id == second.test_asset_id


def test_exact_duplicate_reuses_asset_and_adds_only_a_new_manual_source(
    evie_ai_session_factory: sessionmaker[Session],
    intake_service: IntakeService,
    principal: TrustedUserPrincipal,
    trace_context: RequestTraceContext,
) -> None:
    _seed_project(evie_ai_session_factory)
    first = intake_service.execute(
        _manual_command(),
        principal=principal,
        idempotency_key="duplicate-key-1",
        trace_context=trace_context,
    )
    duplicate = intake_service.execute(
        _manual_command(),
        principal=principal,
        idempotency_key="duplicate-key-2",
        trace_context=trace_context,
    )
    before_replay = _write_counts(evie_ai_session_factory)
    replay = intake_service.execute(
        _manual_command(),
        principal=principal,
        idempotency_key="duplicate-key-2",
        trace_context=trace_context,
    )

    assert duplicate.test_asset_id == first.test_asset_id
    assert duplicate.test_asset_version_id == first.test_asset_version_id
    assert duplicate.created is False
    assert duplicate.reused_existing is True
    assert replay == duplicate
    assert _write_counts(evie_ai_session_factory) == before_replay
    counts = _write_counts(evie_ai_session_factory)
    assert counts[AssetModel] == 1
    assert counts[VersionModel] == 1
    assert counts[ContentClaimModel] == 1
    assert counts[SourceModel] == 2
    assert counts[AuditEventModel] == 3
    with evie_ai_session_factory() as session:
        event_types = list(
            session.scalars(
                select(AuditEventModel.event_type).order_by(AuditEventModel.id)
            )
        )
        assert event_types == [
            AuditEventType.ASSET_CREATED.value,
            AuditEventType.SOURCE_ADDED.value,
            AuditEventType.EXACT_DUPLICATE_REUSED.value,
        ]


def test_exact_duplicate_with_same_requirement_source_does_not_add_source(
    evie_ai_session_factory: sessionmaker[Session],
    intake_service: IntakeService,
    principal: TrustedUserPrincipal,
    trace_context: RequestTraceContext,
) -> None:
    _seed_project(evie_ai_session_factory)
    requirement_id, version_id = _seed_requirement(evie_ai_session_factory)
    command = _requirement_command(
        requirement_id=requirement_id,
        requirement_version_id=version_id,
    )
    intake_service.execute(
        command,
        principal=principal,
        idempotency_key="requirement-duplicate-1",
        trace_context=trace_context,
    )
    duplicate = intake_service.execute(
        command,
        principal=principal,
        idempotency_key="requirement-duplicate-2",
        trace_context=trace_context,
    )

    assert duplicate.reused_existing is True
    counts = _write_counts(evie_ai_session_factory)
    assert counts[SourceModel] == 1
    assert counts[AuditEventModel] == 2


def test_all_intake_audit_payloads_exclude_content_keys_and_sensitive_values(
    evie_ai_session_factory: sessionmaker[Session],
    intake_service: IntakeService,
    principal: TrustedUserPrincipal,
    trace_context: RequestTraceContext,
) -> None:
    _seed_project(evie_ai_session_factory)
    requirement_id, version_id = _seed_requirement(evie_ai_session_factory)
    command = _requirement_command(
        requirement_id=requirement_id,
        requirement_version_id=version_id,
    )
    intake_service.execute(
        command,
        principal=principal,
        idempotency_key="audit-requirement-key",
        trace_context=trace_context,
    )
    intake_service.execute(
        _manual_command(),
        principal=principal,
        idempotency_key="audit-manual-key",
        trace_context=trace_context,
    )

    with evie_ai_session_factory() as session:
        events = list(
            session.scalars(select(AuditEventModel).order_by(AuditEventModel.id))
        )
    assert [event.event_type for event in events] == [
        AuditEventType.ASSET_CREATED.value,
        AuditEventType.SOURCE_ADDED.value,
        AuditEventType.EXACT_DUPLICATE_REUSED.value,
    ]
    payloads = [_serialized_audit_payload(event) for event in events]
    forbidden_values = {
        "登录成功",
        "用户位于登录页",
        "输入账号密码",
        "点击登录",
        "进入首页",
        "用户可以登录系统",
        "audit-requirement-key",
        "audit-manual-key",
    }
    forbidden_keys = {
        "title",
        "precondition",
        "natural_steps",
        "expected_result",
        "idempotency_key",
        "test_asset_pk",
        "requirement_pk",
        "sql",
        "token",
        "authorization",
        "password",
    }
    for payload in payloads:
        assert all(value not in payload for value in forbidden_values)
        assert all(f'"{key}"' not in payload.lower() for key in forbidden_keys)


def test_content_claim_is_project_scoped(
    evie_ai_session_factory: sessionmaker[Session],
    intake_service: IntakeService,
    principal: TrustedUserPrincipal,
    trace_context: RequestTraceContext,
) -> None:
    _seed_project(evie_ai_session_factory, PROJECT_A)
    _seed_project(evie_ai_session_factory, PROJECT_B)

    first = intake_service.execute(
        _manual_command(project_code=PROJECT_A),
        principal=principal,
        idempotency_key="project-a-key",
        trace_context=trace_context,
    )
    second = intake_service.execute(
        _manual_command(project_code=PROJECT_B),
        principal=principal,
        idempotency_key="project-b-key",
        trace_context=trace_context,
    )

    assert first.test_asset_id != second.test_asset_id
    counts = _write_counts(evie_ai_session_factory)
    assert counts[AssetModel] == 2
    assert counts[ContentClaimModel] == 2


def test_semantically_similar_but_not_exact_content_is_not_blocked(
    evie_ai_session_factory: sessionmaker[Session],
    intake_service: IntakeService,
    principal: TrustedUserPrincipal,
    trace_context: RequestTraceContext,
) -> None:
    _seed_project(evie_ai_session_factory)
    first = intake_service.execute(
        _manual_command(title="用户登录成功"),
        principal=principal,
        idempotency_key="semantic-1",
        trace_context=trace_context,
    )
    second = intake_service.execute(
        _manual_command(title="用户可以成功登录"),
        principal=principal,
        idempotency_key="semantic-2",
        trace_context=trace_context,
    )

    assert first.created is True
    assert second.created is True
    assert first.test_asset_id != second.test_asset_id


def test_stale_content_claim_cannot_reuse_a_mismatched_current_version(
    evie_ai_session_factory: sessionmaker[Session],
    intake_service: IntakeService,
    principal: TrustedUserPrincipal,
    trace_context: RequestTraceContext,
) -> None:
    _seed_project(evie_ai_session_factory)
    command = _manual_command()
    intake_service.execute(
        command,
        principal=principal,
        idempotency_key="claim-integrity-1",
        trace_context=trace_context,
    )
    with evie_ai_session_factory.begin() as session:
        version = session.execute(select(VersionModel)).scalar_one()
        version.content_checksum = "f" * 64

    with pytest.raises(EvieAiDomainError) as exc_info:
        intake_service.execute(
            command,
            principal=principal,
            idempotency_key="claim-integrity-2",
            trace_context=trace_context,
        )

    assert exc_info.value.code is EvieAiErrorCode.DATA_INTEGRITY_ERROR
    counts = _write_counts(evie_ai_session_factory)
    assert counts[AssetModel] == 1
    assert counts[AuditEventModel] == 1
    assert counts[IdempotencyRecordModel] == 1


@pytest.mark.parametrize(
    ("key", "expected_code"),
    (
        (None, EvieAiErrorCode.IDEMPOTENCY_KEY_REQUIRED),
        ("", EvieAiErrorCode.IDEMPOTENCY_KEY_REQUIRED),
        ("   ", EvieAiErrorCode.IDEMPOTENCY_KEY_REQUIRED),
        ("bad\nkey", EvieAiErrorCode.IDEMPOTENCY_KEY_REQUIRED),
        ("x" * 256, EvieAiErrorCode.IDEMPOTENCY_KEY_REQUIRED),
    ),
)
def test_invalid_idempotency_key_fails_before_database_writes(
    key: object,
    expected_code: EvieAiErrorCode,
    evie_ai_session_factory: sessionmaker[Session],
    intake_service: IntakeService,
    principal: TrustedUserPrincipal,
    trace_context: RequestTraceContext,
) -> None:
    _seed_project(evie_ai_session_factory)

    with pytest.raises(EvieAiDomainError) as exc_info:
        intake_service.execute(
            _manual_command(),
            principal=principal,
            idempotency_key=cast(str, key),
            trace_context=trace_context,
        )

    assert exc_info.value.code is expected_code
    assert exc_info.value.stage is EvieAiErrorStage.INTAKE
    assert _write_counts(evie_ai_session_factory)[AssetModel] == 0


def test_project_and_principal_checks_fail_closed_without_intake_writes(
    evie_ai_session_factory: sessionmaker[Session],
    intake_service: IntakeService,
    trace_context: RequestTraceContext,
) -> None:
    _seed_project(evie_ai_session_factory, PROJECT_A, status="inactive")
    non_admin = TrustedUserPrincipal(
        user_public_id=ACTOR_PUBLIC_ID,
        role="member",
        is_active=True,
    )

    with pytest.raises(EvieAiDomainError) as forbidden:
        intake_service.execute(
            _manual_command(),
            principal=non_admin,
            idempotency_key="forbidden",
            trace_context=trace_context,
        )
    assert forbidden.value.code is EvieAiErrorCode.PROJECT_SCOPE_FORBIDDEN

    admin = TrustedUserPrincipal(
        user_public_id=ACTOR_PUBLIC_ID,
        role="admin",
        is_active=True,
    )
    with pytest.raises(EvieAiDomainError) as inactive:
        intake_service.execute(
            _manual_command(),
            principal=admin,
            idempotency_key="inactive",
            trace_context=trace_context,
        )
    assert inactive.value.code is EvieAiErrorCode.PROJECT_INACTIVE

    with pytest.raises(EvieAiDomainError) as missing:
        intake_service.execute(
            _manual_command(project_code="projectmissing"),
            principal=admin,
            idempotency_key="missing",
            trace_context=trace_context,
        )
    assert missing.value.code is EvieAiErrorCode.PROJECT_NOT_FOUND
    assert _write_counts(evie_ai_session_factory)[AssetModel] == 0


@pytest.mark.parametrize(
    ("repository_type", "method_name"),
    (
        (IdempotencyRepository, "add"),
        (AssetRepository, "add"),
        (AssetRepository, "add_version"),
        (SourceRepository, "add_manual_source"),
        (ContentClaimRepository, "add"),
        (AssetRepository, "bind_initial_version"),
        (AuditRepository, "add"),
        (IdempotencyRepository, "complete"),
    ),
)
def test_each_persistence_stage_failure_rolls_back_the_complete_transaction(
    repository_type: type[object],
    method_name: str,
    monkeypatch: pytest.MonkeyPatch,
    evie_ai_session_factory: sessionmaker[Session],
    intake_service: IntakeService,
    principal: TrustedUserPrincipal,
    trace_context: RequestTraceContext,
) -> None:
    _seed_project(evie_ai_session_factory)

    def fail_stage(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError(f"injected {method_name} failure")

    monkeypatch.setattr(repository_type, method_name, fail_stage)
    with pytest.raises(EvieAiDomainError) as exc_info:
        intake_service.execute(
            _manual_command(),
            principal=principal,
            idempotency_key="rollback-key",
            trace_context=trace_context,
        )

    assert exc_info.value.code is EvieAiErrorCode.DATA_INTEGRITY_ERROR
    assert set(_write_counts(evie_ai_session_factory).values()) == {0}


def test_requirement_typed_source_failure_rolls_back_complete_intake(
    monkeypatch: pytest.MonkeyPatch,
    evie_ai_session_factory: sessionmaker[Session],
    intake_service: IntakeService,
    principal: TrustedUserPrincipal,
    trace_context: RequestTraceContext,
) -> None:
    _seed_project(evie_ai_session_factory)
    requirement_id, version_id = _seed_requirement(evie_ai_session_factory)
    original_add = SourceRepository.add_requirement_source

    def fail_after_typed_source(
        repository: SourceRepository,
        source: SourceModel,
        *,
        requirement_pk: int,
        requirement_version_pk: int,
        trace_id: str | None = None,
    ) -> SourceModel:
        original_add(
            repository,
            source,
            requirement_pk=requirement_pk,
            requirement_version_pk=requirement_version_pk,
            trace_id=trace_id,
        )
        raise RuntimeError("injected requirement subtype failure")

    monkeypatch.setattr(
        SourceRepository,
        "add_requirement_source",
        fail_after_typed_source,
    )
    with pytest.raises(EvieAiDomainError) as exc_info:
        intake_service.execute(
            _requirement_command(
                requirement_id=requirement_id,
                requirement_version_id=version_id,
            ),
            principal=principal,
            idempotency_key="typed-source-rollback",
            trace_context=trace_context,
        )

    assert exc_info.value.code is EvieAiErrorCode.DATA_INTEGRITY_ERROR
    assert set(_write_counts(evie_ai_session_factory).values()) == {0}


def test_idempotency_unique_race_retries_with_a_fresh_session_and_replays_winner(
    monkeypatch: pytest.MonkeyPatch,
    evie_ai_session_factory: sessionmaker[Session],
    intake_service: IntakeService,
    principal: TrustedUserPrincipal,
    trace_context: RequestTraceContext,
) -> None:
    _seed_project(evie_ai_session_factory)
    command = _manual_command()
    winner = intake_service.execute(
        command,
        principal=principal,
        idempotency_key="idempotency-race",
        trace_context=trace_context,
    )
    original_get = IdempotencyRepository.get_by_scope
    original_scope_execute = ProjectScopeService.execute
    calls = 0
    scope_calls = 0

    def miss_once(
        repository: IdempotencyRepository,
        scope: object,
        *,
        for_update: bool = False,
    ) -> IdempotencyRecordModel | None:
        nonlocal calls
        calls += 1
        if calls == 1:
            return None
        return original_get(repository, scope, for_update=for_update)

    sessions: list[Session] = []

    def tracking_factory() -> Session:
        session = evie_ai_session_factory()
        sessions.append(session)
        return session

    def count_scope_validation(
        service: ProjectScopeService,
        project_code: str,
    ) -> object:
        nonlocal scope_calls
        scope_calls += 1
        return original_scope_execute(service, project_code)

    monkeypatch.setattr(
        IdempotencyRepository,
        "get_by_scope",
        miss_once,
    )
    monkeypatch.setattr(
        ProjectScopeService,
        "execute",
        count_scope_validation,
    )
    retrying_service = IntakeService(
        tracking_factory,
        idempotency_retention_days=7,
        clock=_utc_clock,
    )
    replay = retrying_service.execute(
        command,
        principal=principal,
        idempotency_key="idempotency-race",
        trace_context=trace_context,
    )

    assert replay == winner
    assert len(sessions) == 2
    assert sessions[0] is not sessions[1]
    assert all(not session.in_transaction() for session in sessions)
    assert scope_calls == 2


def test_content_claim_unique_race_retries_and_reuses_winner(
    monkeypatch: pytest.MonkeyPatch,
    evie_ai_session_factory: sessionmaker[Session],
    intake_service: IntakeService,
    principal: TrustedUserPrincipal,
    trace_context: RequestTraceContext,
) -> None:
    _seed_project(evie_ai_session_factory)
    command = _manual_command()
    winner = intake_service.execute(
        command,
        principal=principal,
        idempotency_key="claim-race-winner",
        trace_context=trace_context,
    )
    original_get = ContentClaimRepository.get_by_project_and_fingerprint
    calls = 0

    def miss_once(
        repository: ContentClaimRepository,
        *,
        project_code: str,
        content_fingerprint: str,
        for_update: bool = False,
    ) -> ContentClaimModel | None:
        nonlocal calls
        calls += 1
        if calls == 1:
            return None
        return original_get(
            repository,
            project_code=project_code,
            content_fingerprint=content_fingerprint,
            for_update=for_update,
        )

    sessions: list[Session] = []

    def tracking_factory() -> Session:
        session = evie_ai_session_factory()
        sessions.append(session)
        return session

    monkeypatch.setattr(
        ContentClaimRepository,
        "get_by_project_and_fingerprint",
        miss_once,
    )
    retrying_service = IntakeService(
        tracking_factory,
        idempotency_retention_days=7,
        clock=_utc_clock,
    )
    duplicate = retrying_service.execute(
        command,
        principal=principal,
        idempotency_key="claim-race-loser",
        trace_context=trace_context,
    )

    assert duplicate.test_asset_id == winner.test_asset_id
    assert duplicate.reused_existing is True
    assert len(sessions) == 2
    assert _write_counts(evie_ai_session_factory)[AssetModel] == 1


@pytest.mark.parametrize(
    ("repository_type", "constraint_message"),
    (
        (
            IdempotencyRepository,
            "UNIQUE constraint failed: "
            "test_asset_idempotency_records.project_code, "
            "test_asset_idempotency_records.operation_type, "
            "test_asset_idempotency_records.actor_or_client_id, "
            "test_asset_idempotency_records.idempotency_key",
        ),
        (
            ContentClaimRepository,
            "UNIQUE constraint failed: "
            "test_asset_content_claims.project_code, "
            "test_asset_content_claims.content_fingerprint",
        ),
    ),
)
def test_whitelisted_conflict_without_readable_winner_leaves_zero_residue(
    repository_type: type[object],
    constraint_message: str,
    monkeypatch: pytest.MonkeyPatch,
    evie_ai_session_factory: sessionmaker[Session],
    principal: TrustedUserPrincipal,
    trace_context: RequestTraceContext,
) -> None:
    _seed_project(evie_ai_session_factory)
    original_add = repository_type.add
    calls = 0
    sessions: list[Session] = []

    def conflict_once(repository: object, record: object) -> object:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise IntegrityError(
                "INSERT",
                {},
                sqlite3.IntegrityError(constraint_message),
            )
        return original_add(repository, record)

    def tracking_factory() -> Session:
        session = evie_ai_session_factory()
        sessions.append(session)
        return session

    monkeypatch.setattr(repository_type, "add", conflict_once)
    service = IntakeService(
        tracking_factory,
        idempotency_retention_days=7,
        clock=_utc_clock,
    )
    with pytest.raises(EvieAiDomainError) as exc_info:
        service.execute(
            _manual_command(),
            principal=principal,
            idempotency_key="winner-unavailable",
            trace_context=trace_context,
        )

    assert exc_info.value.code is EvieAiErrorCode.DATA_INTEGRITY_ERROR
    assert calls == 2
    assert len(sessions) == 2
    assert sessions[0] is not sessions[1]
    assert set(_write_counts(evie_ai_session_factory).values()) == {0}


def test_non_whitelisted_integrity_error_fails_closed_without_retry(
    monkeypatch: pytest.MonkeyPatch,
    evie_ai_session_factory: sessionmaker[Session],
    principal: TrustedUserPrincipal,
    trace_context: RequestTraceContext,
) -> None:
    _seed_project(evie_ai_session_factory)
    sessions: list[Session] = []

    def tracking_factory() -> Session:
        session = evie_ai_session_factory()
        sessions.append(session)
        return session

    def fail_with_non_whitelisted_constraint(
        _repository: AuditRepository,
        _event: AuditEventModel,
    ) -> AuditEventModel:
        raise IntegrityError(
            "INSERT",
            {},
            sqlite3.IntegrityError(
                "UNIQUE constraint failed: "
                "test_asset_sources.test_asset_pk, "
                "test_asset_sources.source_identity_hash"
            ),
        )

    monkeypatch.setattr(
        AuditRepository,
        "add",
        fail_with_non_whitelisted_constraint,
    )
    service = IntakeService(
        tracking_factory,
        idempotency_retention_days=7,
        clock=_utc_clock,
    )
    with pytest.raises(EvieAiDomainError) as exc_info:
        service.execute(
            _manual_command(),
            principal=principal,
            idempotency_key="non-whitelisted",
            trace_context=trace_context,
        )

    assert exc_info.value.code is EvieAiErrorCode.DATA_INTEGRITY_ERROR
    assert len(sessions) == 1
    assert set(_write_counts(evie_ai_session_factory).values()) == {0}


def test_second_whitelisted_conflict_fails_closed_after_one_retry(
    monkeypatch: pytest.MonkeyPatch,
    evie_ai_session_factory: sessionmaker[Session],
    intake_service: IntakeService,
    principal: TrustedUserPrincipal,
    trace_context: RequestTraceContext,
) -> None:
    _seed_project(evie_ai_session_factory)
    command = _manual_command()
    intake_service.execute(
        command,
        principal=principal,
        idempotency_key="repeat-conflict",
        trace_context=trace_context,
    )
    sessions: list[Session] = []

    def tracking_factory() -> Session:
        session = evie_ai_session_factory()
        sessions.append(session)
        return session

    monkeypatch.setattr(
        IdempotencyRepository,
        "get_by_scope",
        lambda _repository, _scope, *, for_update=False: None,
    )
    service = IntakeService(
        tracking_factory,
        idempotency_retention_days=7,
        clock=_utc_clock,
    )
    with pytest.raises(EvieAiDomainError) as exc_info:
        service.execute(
            command,
            principal=principal,
            idempotency_key="repeat-conflict",
            trace_context=trace_context,
        )

    assert exc_info.value.code is EvieAiErrorCode.DATA_INTEGRITY_ERROR
    assert len(sessions) == 2


@pytest.mark.parametrize(
    ("constraint_name", "expected"),
    (
        (
            "uq_test_asset_idempotency_scope_key",
            "uq_test_asset_idempotency_scope_key",
        ),
        (
            "uq_test_asset_content_claims_project_fingerprint",
            "uq_test_asset_content_claims_project_fingerprint",
        ),
        ("uq_test_asset_sources_test_asset_pk_source_identity_hash", None),
    ),
)
def test_postgresql_unique_constraint_classification_is_exact(
    constraint_name: str,
    expected: str | None,
) -> None:
    class DriverError(Exception):
        def __init__(self, name: str) -> None:
            super().__init__("unique violation")
            self.diag = type("Diagnostic", (), {"constraint_name": name})()

    error = IntegrityError("INSERT", {}, DriverError(constraint_name))

    assert intake_service_module._retryable_constraint_name(error) == expected
