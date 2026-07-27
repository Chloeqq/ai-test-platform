"""Stable EvieAi domain error contract without transport coupling."""

from __future__ import annotations

from enum import StrEnum

EVIE_AI_ERROR_DOMAIN = "evie_ai"


class EvieAiErrorCode(StrEnum):
    ASSET_NOT_FOUND = "EVIE_ASSET_NOT_FOUND"
    ASSET_DELETED = "EVIE_ASSET_DELETED"
    ASSET_STATE_CONFLICT = "EVIE_ASSET_STATE_CONFLICT"
    IDEMPOTENCY_CONFLICT = "EVIE_IDEMPOTENCY_CONFLICT"
    IDEMPOTENCY_KEY_REQUIRED = "EVIE_IDEMPOTENCY_KEY_REQUIRED"
    ROW_VERSION_CONFLICT = "EVIE_ROW_VERSION_CONFLICT"
    EXACT_DUPLICATE_CONFLICT = "EVIE_EXACT_DUPLICATE_CONFLICT"
    RESTORE_DUPLICATE_CONFLICT = "EVIE_RESTORE_DUPLICATE_CONFLICT"
    INVALID_REVIEW_TRANSITION = "EVIE_INVALID_REVIEW_TRANSITION"
    REVIEW_VERSION_NOT_CURRENT = "EVIE_REVIEW_VERSION_NOT_CURRENT"
    VERSION_NOT_FOUND = "EVIE_VERSION_NOT_FOUND"
    VERSION_SCOPE_MISMATCH = "EVIE_VERSION_SCOPE_MISMATCH"
    SOURCE_SCOPE_MISMATCH = "EVIE_SOURCE_SCOPE_MISMATCH"
    PROJECT_NOT_FOUND = "EVIE_PROJECT_NOT_FOUND"
    PROJECT_INACTIVE = "EVIE_PROJECT_INACTIVE"
    PROJECT_SCOPE_FORBIDDEN = "EVIE_PROJECT_SCOPE_FORBIDDEN"
    AUTHENTICATION_REQUIRED = "EVIE_AUTHENTICATION_REQUIRED"
    REQUEST_VALIDATION_ERROR = "EVIE_REQUEST_VALIDATION_ERROR"
    DATA_INTEGRITY_ERROR = "EVIE_DATA_INTEGRITY_ERROR"


class EvieAiErrorStage(StrEnum):
    REQUEST_VALIDATION = "request_validation"
    AUTHORIZATION = "authorization"
    IDENTITY = "identity"
    INTAKE = "intake"
    LIFECYCLE = "lifecycle"
    REVIEW = "review"
    PERSISTENCE = "persistence"


class EvieAiDomainError(Exception):
    """Typed domain failure that future adapters can map to stable responses."""

    def __init__(
        self,
        code: EvieAiErrorCode,
        *,
        stage: EvieAiErrorStage,
        message: str,
        retryable: bool = False,
        trace_id: str | None = None,
        remediation: str | None = None,
        related_entity_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.domain = EVIE_AI_ERROR_DOMAIN
        self.stage = stage
        self.message = message
        self.retryable = retryable
        self.trace_id = trace_id
        self.remediation = remediation
        self.related_entity_id = related_entity_id
