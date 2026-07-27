"""EvieAi 自然语言测试资产的统一 Intake 事务入口。"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.constants.evie_ai import (
    TestAssetAuditEventType,
    TestAssetConversionStatus,
    TestAssetOperationType,
    TestAssetReviewStatus,
    TestAssetSourceType,
)
from app.core.id_gen import (
    generate_test_asset_audit_event_id,
    generate_test_asset_id,
    generate_test_asset_source_id,
    generate_test_asset_version_id,
)
from app.errors.evie_ai import (
    EvieAiDomainError,
    EvieAiErrorCode,
    EvieAiErrorStage,
)
from app.models.evie_ai import (
    Requirement,
    RequirementVersion,
    TestAsset,
    TestAssetAuditEvent,
    TestAssetContentClaim,
    TestAssetIdempotencyRecord,
    TestAssetSource,
    TestAssetVersion,
)
from app.policies.evie_ai.asset_code_policy import asset_code_for_new_asset
from app.policies.evie_ai.content_fingerprint import (
    TestAssetContent,
    build_content_fingerprint,
    normalize_test_asset_content,
    sha256_hex,
)
from app.policies.evie_ai.request_fingerprint import (
    CreateAssetFingerprintInput,
    build_create_asset_request_fingerprint,
)
from app.policies.evie_ai.source_policy import (
    ManualSourceIdentity,
    RequirementSourceIdentity,
    build_manual_source_identity_hash,
    build_requirement_source_identity_hash,
)
from app.repositories.evie_ai.content_claim_repository import (
    TestAssetContentClaimRepository,
)
from app.repositories.evie_ai.governance_repository import (
    TestAssetAuditRepository,
)
from app.repositories.evie_ai.idempotency_repository import (
    IdempotencyResultSummary,
    IdempotencyScope,
    TestAssetIdempotencyRepository,
)
from app.repositories.evie_ai.requirement_repository import RequirementRepository
from app.repositories.evie_ai.source_repository import TestAssetSourceRepository
from app.repositories.evie_ai.test_asset_repository import TestAssetRepository
from app.repositories.test_project_repository import TestProjectRepository
from app.schemas.evie_ai.operations import TestAssetOperationResult
from app.schemas.evie_ai.source import (
    ManualTestAssetSourceCreate,
    RequirementTestAssetSourceCreate,
)
from app.schemas.evie_ai.test_asset import TestAssetCreate
from app.services.evie_ai.project_access_authorizer import ProjectAccessAuthorizer
from app.services.evie_ai.project_scope_service import ProjectScopeService
from app.services.evie_ai.request_actor_context import RequestActorContext
from app.services.evie_ai.request_channel_context import RequestChannelContext
from app.services.evie_ai.request_trace_context import RequestTraceContext
from app.services.evie_ai.user_public_identity_service import TrustedUserPrincipal

_IDEMPOTENCY_CONSTRAINT = "uq_test_asset_idempotency_scope_key"
_CONTENT_CLAIM_CONSTRAINT = (
    "uq_test_asset_content_claims_project_fingerprint"
)
_IDEMPOTENCY_RESULT_TYPE = "test_asset"
_OUTCOME_CREATED = "created"
_OUTCOME_EXACT_DUPLICATE = "exact_duplicate_reused"
_OUTCOME_IDEMPOTENCY_REPLAY = "idempotency_replay"
_HTTP_OK = 200
_HTTP_CREATED = 201
_MAX_IDEMPOTENCY_KEY_LENGTH = 255
_RETRY_OUTCOME_BY_CONSTRAINT = {
    _IDEMPOTENCY_CONSTRAINT: _OUTCOME_IDEMPOTENCY_REPLAY,
    _CONTENT_CLAIM_CONSTRAINT: _OUTCOME_EXACT_DUPLICATE,
}
_SQLITE_UNIQUE_SIGNATURES = {
    (
        "test_asset_idempotency_records.project_code",
        "test_asset_idempotency_records.operation_type",
        "test_asset_idempotency_records.actor_or_client_id",
        "test_asset_idempotency_records.idempotency_key",
    ): _IDEMPOTENCY_CONSTRAINT,
    (
        "test_asset_content_claims.project_code",
        "test_asset_content_claims.content_fingerprint",
    ): _CONTENT_CLAIM_CONSTRAINT,
}


@dataclass(frozen=True, slots=True)
class _ResolvedSource:
    source_type: TestAssetSourceType
    source_identity_hash: str
    requirement: Requirement | None = None
    requirement_version: RequirementVersion | None = None


@dataclass(frozen=True, slots=True)
class _AttemptContext:
    project_code: str
    actor: str
    channel: str
    trace: RequestTraceContext
    idempotency_key: str
    request_fingerprint: str
    content: TestAssetContent
    content_fingerprint: str | None = None
    source: _ResolvedSource | None = None


@dataclass(frozen=True, slots=True)
class _AttemptResult:
    result: TestAssetOperationResult
    outcome: str


@dataclass(frozen=True, slots=True)
class _IdempotencyClaim:
    record: TestAssetIdempotencyRecord
    replay: TestAssetOperationResult | None = None


class TestAssetIntakeService:
    """创建或精确复用自然语言 TestAsset 的唯一公开入口。"""

    def __init__(
        self,
        session_factory: Callable[[], Session],
        *,
        idempotency_retention_days: int,
    ) -> None:
        if idempotency_retention_days < 1:
            raise ValueError("idempotency_retention_days must be positive")
        self._session_factory = session_factory
        self._retention = timedelta(days=idempotency_retention_days)

    def execute(
        self,
        command: TestAssetCreate,
        *,
        principal: TrustedUserPrincipal,
        idempotency_key: str,
        trace_context: RequestTraceContext,
    ) -> TestAssetOperationResult:
        key = self._validate_inputs(
            command=command,
            principal=principal,
            idempotency_key=idempotency_key,
            trace_context=trace_context,
        )
        expected_retry_outcome: str | None = None

        for attempt_no in range(2):
            try:
                attempt_result = self._run_attempt(
                    command=command,
                    principal=principal,
                    idempotency_key=key,
                    trace_context=trace_context,
                )
            except IntegrityError as exc:
                constraint = _retryable_constraint_name(exc)
                if attempt_no == 0 and constraint is not None:
                    expected_retry_outcome = _RETRY_OUTCOME_BY_CONSTRAINT[constraint]
                    continue
                raise _data_integrity_error(trace_context) from exc
            except EvieAiDomainError:
                raise
            except Exception as exc:
                raise _data_integrity_error(trace_context) from exc

            if (
                expected_retry_outcome is not None
                and attempt_result.outcome != expected_retry_outcome
            ):
                raise _data_integrity_error(trace_context)
            return attempt_result.result

        raise _data_integrity_error(trace_context)

    def _run_attempt(
        self,
        *,
        command: TestAssetCreate,
        principal: TrustedUserPrincipal,
        idempotency_key: str,
        trace_context: RequestTraceContext,
    ) -> _AttemptResult:
        session = self._session_factory()
        try:
            with session.begin():
                return self._execute_transaction(
                    session=session,
                    command=command,
                    principal=principal,
                    idempotency_key=idempotency_key,
                    trace_context=trace_context,
                )
        finally:
            session.close()

    def _execute_transaction(
        self,
        *,
        session: Session,
        command: TestAssetCreate,
        principal: TrustedUserPrincipal,
        idempotency_key: str,
        trace_context: RequestTraceContext,
    ) -> _AttemptResult:
        context = self._build_attempt_context(
            session=session,
            command=command,
            principal=principal,
            idempotency_key=idempotency_key,
            trace_context=trace_context,
        )
        claim = self._claim_idempotency(session=session, context=context)
        if claim.replay is not None:
            return _AttemptResult(claim.replay, _OUTCOME_IDEMPOTENCY_REPLAY)

        context = replace(
            context,
            content_fingerprint=build_content_fingerprint(context.content),
            source=_resolve_source(
                session=session,
                command=command,
                project_code=context.project_code,
                actor=context.actor,
                idempotency_key=context.idempotency_key,
                request_fingerprint=context.request_fingerprint,
                trace_context=context.trace,
            ),
        )
        content_claim = TestAssetContentClaimRepository(
            session
        ).get_by_project_and_fingerprint(
            project_code=context.project_code,
            content_fingerprint=_required_content_fingerprint(context),
            for_update=True,
        )
        if content_claim is not None:
            return self._reuse_exact_duplicate(
                session=session,
                context=context,
                idempotency_record=claim.record,
                content_claim=content_claim,
            )
        return self._create_asset(
            session=session,
            context=context,
            idempotency_record=claim.record,
        )

    def _build_attempt_context(
        self,
        *,
        session: Session,
        command: TestAssetCreate,
        principal: TrustedUserPrincipal,
        idempotency_key: str,
        trace_context: RequestTraceContext,
    ) -> _AttemptContext:
        ProjectAccessAuthorizer().execute(principal)
        project = ProjectScopeService(
            TestProjectRepository(session)
        ).execute(command.project_code)
        actor = RequestActorContext().execute(principal)
        channel = RequestChannelContext().execute()
        content = _normalized_content(command)
        request_fingerprint = _request_fingerprint(command, content)
        return _AttemptContext(
            project_code=project.project_code,
            actor=actor,
            channel=channel,
            trace=trace_context,
            idempotency_key=idempotency_key,
            request_fingerprint=request_fingerprint,
            content=content,
        )

    def _claim_idempotency(
        self,
        *,
        session: Session,
        context: _AttemptContext,
    ) -> _IdempotencyClaim:
        repository = TestAssetIdempotencyRepository(session)
        scope = _idempotency_scope(context)
        now = datetime.now(UTC)
        record = repository.get_by_scope(scope, for_update=True)
        if record is None:
            return _IdempotencyClaim(
                repository.add(
                    TestAssetIdempotencyRecord(
                        project_code=context.project_code,
                        operation_type=TestAssetOperationType.CREATE_ASSET.value,
                        actor_or_client_id=context.actor,
                        idempotency_key=context.idempotency_key,
                        request_fingerprint=context.request_fingerprint,
                        expires_at=now + self._retention,
                        generation=1,
                    )
                )
            )

        if _is_expired(record.expires_at, now):
            occupied = repository.try_reoccupy_expired(
                record_id=record.id,
                expected_generation=record.generation,
                expired_at_or_before=now,
                request_fingerprint=context.request_fingerprint,
                expires_at=now + self._retention,
            )
            if not occupied:
                session.expire_all()
                record = repository.get_by_scope(scope, for_update=True)
                if record is None or _is_expired(record.expires_at, now):
                    raise _data_integrity_error(context.trace)
                return self._resolve_existing_idempotency(record, context)
            session.flush()
            session.refresh(record)
            return _IdempotencyClaim(record)

        return self._resolve_existing_idempotency(record, context)

    @staticmethod
    def _resolve_existing_idempotency(
        record: TestAssetIdempotencyRecord,
        context: _AttemptContext,
    ) -> _IdempotencyClaim:
        if record.request_fingerprint != context.request_fingerprint:
            raise EvieAiDomainError(
                EvieAiErrorCode.IDEMPOTENCY_CONFLICT,
                stage=EvieAiErrorStage.INTAKE,
                message="The idempotency key belongs to a different request.",
                retryable=False,
                trace_id=context.trace.correlation_id,
            )
        if record.completed_at is None:
            raise _data_integrity_error(context.trace)
        return _IdempotencyClaim(record, _result_from_record(record, context.trace))

    def _create_asset(
        self,
        *,
        session: Session,
        context: _AttemptContext,
        idempotency_record: TestAssetIdempotencyRecord,
    ) -> _AttemptResult:
        asset_repository = TestAssetRepository(session)
        source_context = _required_source(context)
        test_asset_id = generate_test_asset_id()
        asset = asset_repository.add(
            TestAsset(
                test_asset_id=test_asset_id,
                project_code=context.project_code,
                asset_code=asset_code_for_new_asset(test_asset_id),
                review_status=TestAssetReviewStatus.PENDING.value,
                conversion_status=TestAssetConversionStatus.NOT_STARTED.value,
                created_by=context.actor,
                updated_by=context.actor,
            )
        )
        version = asset_repository.add_version(
            _new_version(asset=asset, context=context)
        )
        source = _add_source(session=session, asset=asset, context=context)
        TestAssetContentClaimRepository(session).add(
            TestAssetContentClaim(
                test_asset_pk=asset.id,
                project_code=context.project_code,
                content_fingerprint=_required_content_fingerprint(context),
            )
        )
        asset_repository.bind_initial_version(
            asset,
            version,
            updated_by=context.actor,
            trace_id=context.trace.correlation_id,
        )
        _append_audit(
            session=session,
            asset=asset,
            version=version,
            source=source,
            context=context,
            idempotency_record=idempotency_record,
            event_type=TestAssetAuditEventType.ASSET_CREATED,
            after_state_summary=_asset_state_summary(
                asset=asset,
                version=version,
                source_type=source_context.source_type,
            ),
        )
        result = _operation_result(
            asset=asset,
            version=version,
            created=True,
            reused_existing=False,
        )
        _complete_idempotency(
            session=session,
            record=idempotency_record,
            result=result,
            context=context,
            http_status=_HTTP_CREATED,
        )
        return _AttemptResult(result, _OUTCOME_CREATED)

    def _reuse_exact_duplicate(
        self,
        *,
        session: Session,
        context: _AttemptContext,
        idempotency_record: TestAssetIdempotencyRecord,
        content_claim: TestAssetContentClaim,
    ) -> _AttemptResult:
        asset_repository = TestAssetRepository(session)
        source_context = _required_source(context)
        asset = asset_repository.get_by_pk(
            content_claim.test_asset_pk,
            for_update=True,
        )
        if asset is None or asset.project_code != context.project_code:
            raise _data_integrity_error(context.trace)
        version = asset_repository.get_current_version(asset.id)
        if (
            version is None
            or version.content_checksum != _required_content_fingerprint(context)
        ):
            raise _data_integrity_error(context.trace)

        source_repository = TestAssetSourceRepository(session)
        source = source_repository.get_by_identity(
            test_asset_pk=asset.id,
            source_identity_hash=source_context.source_identity_hash,
        )
        if source is None:
            source = _add_source(session=session, asset=asset, context=context)
            _append_audit(
                session=session,
                asset=asset,
                version=version,
                source=source,
                context=context,
                idempotency_record=idempotency_record,
                event_type=TestAssetAuditEventType.SOURCE_ADDED,
                after_state_summary={
                    "source_added": True,
                    "source_type": source_context.source_type.value,
                    "row_version": asset.row_version,
                },
            )

        _append_audit(
            session=session,
            asset=asset,
            version=version,
            source=source,
            context=context,
            idempotency_record=idempotency_record,
            event_type=TestAssetAuditEventType.EXACT_DUPLICATE_REUSED,
            after_state_summary={
                "reused_existing": True,
                "source_type": source_context.source_type.value,
                "row_version": asset.row_version,
            },
        )
        result = _operation_result(
            asset=asset,
            version=version,
            created=False,
            reused_existing=True,
        )
        _complete_idempotency(
            session=session,
            record=idempotency_record,
            result=result,
            context=context,
            http_status=_HTTP_OK,
        )
        return _AttemptResult(result, _OUTCOME_EXACT_DUPLICATE)

    @staticmethod
    def _validate_inputs(
        *,
        command: TestAssetCreate,
        principal: TrustedUserPrincipal,
        idempotency_key: str,
        trace_context: RequestTraceContext,
    ) -> str:
        if not isinstance(command, TestAssetCreate):
            raise EvieAiDomainError(
                EvieAiErrorCode.DATA_INTEGRITY_ERROR,
                stage=EvieAiErrorStage.INTAKE,
                message="A validated TestAsset create command is required.",
                retryable=False,
            )
        if not isinstance(principal, TrustedUserPrincipal):
            raise EvieAiDomainError(
                EvieAiErrorCode.DATA_INTEGRITY_ERROR,
                stage=EvieAiErrorStage.IDENTITY,
                message="A trusted user principal is required.",
                retryable=False,
            )
        if not isinstance(trace_context, RequestTraceContext):
            raise EvieAiDomainError(
                EvieAiErrorCode.DATA_INTEGRITY_ERROR,
                stage=EvieAiErrorStage.INTAKE,
                message="A trusted request trace context is required.",
                retryable=False,
            )
        if not isinstance(idempotency_key, str):
            raise _idempotency_key_error(trace_context)
        normalized_key = idempotency_key.strip()
        if (
            not normalized_key
            or len(normalized_key) > _MAX_IDEMPOTENCY_KEY_LENGTH
            or any(
                ord(character) < 32 or ord(character) == 127
                for character in normalized_key
            )
        ):
            raise _idempotency_key_error(trace_context)
        return normalized_key


def _normalized_content(command: TestAssetCreate) -> TestAssetContent:
    return normalize_test_asset_content(
        TestAssetContent(
            title=command.content.title,
            precondition=command.content.precondition,
            natural_steps=tuple(command.content.natural_steps),
            expected_result=command.content.expected_result,
            priority=command.content.priority,
            tags=tuple(command.content.tags),
        )
    )


def _request_fingerprint(
    command: TestAssetCreate,
    content: TestAssetContent,
) -> str:
    source = command.source
    if isinstance(source, RequirementTestAssetSourceCreate):
        fingerprint_input = CreateAssetFingerprintInput(
            source_type=TestAssetSourceType.REQUIREMENT,
            content=content,
            requirement_id=source.requirement_id,
            requirement_version_id=source.requirement_version_id,
        )
    elif isinstance(source, ManualTestAssetSourceCreate):
        fingerprint_input = CreateAssetFingerprintInput(
            source_type=TestAssetSourceType.MANUAL,
            content=content,
        )
    else:
        raise ValueError("unsupported TestAsset source type")
    return build_create_asset_request_fingerprint(fingerprint_input)


def _resolve_source(
    *,
    session: Session,
    command: TestAssetCreate,
    project_code: str,
    actor: str,
    idempotency_key: str,
    request_fingerprint: str,
    trace_context: RequestTraceContext,
) -> _ResolvedSource:
    source = command.source
    if isinstance(source, ManualTestAssetSourceCreate):
        identity_hash = build_manual_source_identity_hash(
            ManualSourceIdentity(
                project_code=project_code,
                actor_or_client_id=actor,
                operation_type=TestAssetOperationType.CREATE_ASSET,
                idempotency_key=idempotency_key,
                request_fingerprint=request_fingerprint,
            )
        )
        return _ResolvedSource(TestAssetSourceType.MANUAL, identity_hash)

    if isinstance(source, RequirementTestAssetSourceCreate):
        resolved = RequirementRepository(session).resolve_source_version(
            project_code=project_code,
            requirement_id=source.requirement_id,
            requirement_version_id=source.requirement_version_id,
        )
        if resolved is None:
            raise EvieAiDomainError(
                EvieAiErrorCode.SOURCE_SCOPE_MISMATCH,
                stage=EvieAiErrorStage.INTAKE,
                message="The Requirement source is outside the validated scope.",
                retryable=False,
                trace_id=trace_context.correlation_id,
            )
        requirement, requirement_version = resolved
        identity_hash = build_requirement_source_identity_hash(
            RequirementSourceIdentity(
                requirement_id=requirement.requirement_id,
                requirement_version_id=requirement_version.requirement_version_id,
            )
        )
        return _ResolvedSource(
            TestAssetSourceType.REQUIREMENT,
            identity_hash,
            requirement=requirement,
            requirement_version=requirement_version,
        )
    raise ValueError("unsupported TestAsset source type")


def _new_version(
    *,
    asset: TestAsset,
    context: _AttemptContext,
) -> TestAssetVersion:
    return TestAssetVersion(
        test_asset_version_id=generate_test_asset_version_id(),
        test_asset_pk=asset.id,
        version_no=1,
        title=context.content.title,
        precondition=context.content.precondition,
        natural_steps=list(context.content.natural_steps),
        expected_result=context.content.expected_result,
        priority=context.content.priority,
        tags=list(context.content.tags),
        content_checksum=_required_content_fingerprint(context),
        created_by=context.actor,
    )


def _add_source(
    *,
    session: Session,
    asset: TestAsset,
    context: _AttemptContext,
) -> TestAssetSource:
    source_context = _required_source(context)
    source = TestAssetSource(
        test_asset_source_id=generate_test_asset_source_id(),
        test_asset_pk=asset.id,
        source_type=source_context.source_type.value,
        source_identity_hash=source_context.source_identity_hash,
        created_by=context.actor,
    )
    repository = TestAssetSourceRepository(session)
    if source_context.source_type is TestAssetSourceType.MANUAL:
        return repository.add_manual_source(
            source,
            trace_id=context.trace.correlation_id,
        )
    if (
        source_context.requirement is None
        or source_context.requirement_version is None
    ):
        raise _data_integrity_error(context.trace)
    return repository.add_requirement_source(
        source,
        requirement_pk=source_context.requirement.id,
        requirement_version_pk=source_context.requirement_version.id,
        trace_id=context.trace.correlation_id,
    )


def _append_audit(
    *,
    session: Session,
    asset: TestAsset,
    version: TestAssetVersion,
    source: TestAssetSource,
    context: _AttemptContext,
    idempotency_record: TestAssetIdempotencyRecord,
    event_type: TestAssetAuditEventType,
    after_state_summary: dict[str, object],
) -> None:
    scope_hash, key_hash = _idempotency_hashes(context)
    TestAssetAuditRepository(session).add(
        TestAssetAuditEvent(
            test_asset_audit_event_id=generate_test_asset_audit_event_id(),
            test_asset_pk=asset.id,
            event_type=event_type.value,
            actor=context.actor,
            channel=context.channel,
            request_id=context.trace.request_id,
            correlation_id=context.trace.correlation_id,
            operation_type=TestAssetOperationType.CREATE_ASSET.value,
            idempotency_scope_hash=scope_hash,
            idempotency_key_hash=key_hash,
            idempotency_generation=idempotency_record.generation,
            related_test_asset_version_id=version.test_asset_version_id,
            related_test_asset_source_id=source.test_asset_source_id,
            after_state_summary=after_state_summary,
        )
    )


def _complete_idempotency(
    *,
    session: Session,
    record: TestAssetIdempotencyRecord,
    result: TestAssetOperationResult,
    context: _AttemptContext,
    http_status: int,
) -> None:
    completed = TestAssetIdempotencyRepository(session).complete(
        record_id=record.id,
        expected_generation=record.generation,
        completed_at=datetime.now(UTC),
        summary=IdempotencyResultSummary(
            result_http_status=http_status,
            result_type=_IDEMPOTENCY_RESULT_TYPE,
            test_asset_id=result.test_asset_id,
            test_asset_version_id=result.test_asset_version_id,
            created=result.created,
            reused_existing=result.reused_existing,
            changed=result.changed,
            row_version=result.row_version,
            deleted=result.deleted,
        ),
    )
    if not completed:
        raise _data_integrity_error(context.trace)


def _operation_result(
    *,
    asset: TestAsset,
    version: TestAssetVersion,
    created: bool,
    reused_existing: bool,
) -> TestAssetOperationResult:
    return TestAssetOperationResult(
        operation_type=TestAssetOperationType.CREATE_ASSET,
        test_asset_id=asset.test_asset_id,
        test_asset_version_id=version.test_asset_version_id,
        created=created,
        reused_existing=reused_existing,
        changed=False,
        row_version=asset.row_version,
        deleted=False,
    )


def _result_from_record(
    record: TestAssetIdempotencyRecord,
    trace_context: RequestTraceContext,
) -> TestAssetOperationResult:
    required = (
        record.result_type == _IDEMPOTENCY_RESULT_TYPE,
        record.result_http_status in {_HTTP_OK, _HTTP_CREATED},
        isinstance(record.test_asset_id, str),
        isinstance(record.test_asset_version_id, str),
        isinstance(record.created, bool),
        isinstance(record.reused_existing, bool),
        isinstance(record.changed, bool),
        isinstance(record.row_version, int),
        isinstance(record.deleted, bool),
        record.test_asset_review_record_id is None,
    )
    if not all(required):
        raise _data_integrity_error(trace_context)
    valid_create_result = (
        record.result_http_status == _HTTP_CREATED
        and record.created is True
        and record.reused_existing is False
    )
    valid_reuse_result = (
        record.result_http_status == _HTTP_OK
        and record.created is False
        and record.reused_existing is True
    )
    if (
        not (valid_create_result or valid_reuse_result)
        or record.changed is not False
        or record.deleted is not False
        or record.row_version < 1
    ):
        raise _data_integrity_error(trace_context)
    return TestAssetOperationResult(
        operation_type=TestAssetOperationType.CREATE_ASSET,
        test_asset_id=record.test_asset_id,
        test_asset_version_id=record.test_asset_version_id,
        created=record.created,
        reused_existing=record.reused_existing,
        changed=record.changed,
        row_version=record.row_version,
        deleted=record.deleted,
    )


def _idempotency_scope(context: _AttemptContext) -> IdempotencyScope:
    return IdempotencyScope(
        project_code=context.project_code,
        operation_type=TestAssetOperationType.CREATE_ASSET.value,
        actor_or_client_id=context.actor,
        idempotency_key=context.idempotency_key,
    )


def _idempotency_hashes(context: _AttemptContext) -> tuple[str, str]:
    return (
        sha256_hex(
            {
                "project_code": context.project_code,
                "operation_type": TestAssetOperationType.CREATE_ASSET.value,
                "actor_or_client_id": context.actor,
                "idempotency_key": context.idempotency_key,
            }
        ),
        sha256_hex({"idempotency_key": context.idempotency_key}),
    )


def _asset_state_summary(
    *,
    asset: TestAsset,
    version: TestAssetVersion,
    source_type: TestAssetSourceType,
) -> dict[str, object]:
    return {
        "review_status": asset.review_status,
        "conversion_status": asset.conversion_status,
        "row_version": asset.row_version,
        "version_no": version.version_no,
        "content_checksum": version.content_checksum,
        "source_type": source_type.value,
    }


def _required_source(context: _AttemptContext) -> _ResolvedSource:
    if context.source is None:
        raise _data_integrity_error(context.trace)
    return context.source


def _required_content_fingerprint(context: _AttemptContext) -> str:
    if context.content_fingerprint is None:
        raise _data_integrity_error(context.trace)
    return context.content_fingerprint


def _is_expired(expires_at: datetime, now: datetime) -> bool:
    comparable_now = now
    if expires_at.tzinfo is None and now.tzinfo is not None:
        comparable_now = now.replace(tzinfo=None)
    return expires_at <= comparable_now


def _retryable_constraint_name(exc: IntegrityError) -> str | None:
    diagnostic = getattr(exc.orig, "diag", None)
    named_constraint = getattr(diagnostic, "constraint_name", None)
    if named_constraint in _RETRY_OUTCOME_BY_CONSTRAINT:
        return named_constraint

    message = str(exc.orig)
    prefix = "UNIQUE constraint failed: "
    if not message.startswith(prefix):
        return None
    columns = tuple(part.strip() for part in message[len(prefix) :].split(","))
    return _SQLITE_UNIQUE_SIGNATURES.get(columns)


def _idempotency_key_error(
    trace_context: RequestTraceContext,
) -> EvieAiDomainError:
    return EvieAiDomainError(
        EvieAiErrorCode.IDEMPOTENCY_KEY_REQUIRED,
        stage=EvieAiErrorStage.INTAKE,
        message="A valid idempotency key is required.",
        retryable=False,
        trace_id=trace_context.correlation_id,
    )


def _data_integrity_error(
    trace_context: RequestTraceContext,
) -> EvieAiDomainError:
    return EvieAiDomainError(
        EvieAiErrorCode.DATA_INTEGRITY_ERROR,
        stage=EvieAiErrorStage.INTAKE,
        message="The TestAsset intake transaction could not be completed safely.",
        retryable=False,
        trace_id=trace_context.correlation_id,
    )
