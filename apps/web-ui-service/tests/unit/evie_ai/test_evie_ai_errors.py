from __future__ import annotations

from app.errors.evie_ai import (
    EVIE_AI_ERROR_DOMAIN,
    EvieAiDomainError,
    EvieAiErrorCode,
    EvieAiErrorStage,
)

EXPECTED_CODES = {
    "EVIE_ASSET_NOT_FOUND",
    "EVIE_ASSET_DELETED",
    "EVIE_ASSET_STATE_CONFLICT",
    "EVIE_IDEMPOTENCY_CONFLICT",
    "EVIE_IDEMPOTENCY_KEY_REQUIRED",
    "EVIE_ROW_VERSION_CONFLICT",
    "EVIE_EXACT_DUPLICATE_CONFLICT",
    "EVIE_RESTORE_DUPLICATE_CONFLICT",
    "EVIE_INVALID_REVIEW_TRANSITION",
    "EVIE_REVIEW_VERSION_NOT_CURRENT",
    "EVIE_VERSION_NOT_FOUND",
    "EVIE_VERSION_SCOPE_MISMATCH",
    "EVIE_SOURCE_SCOPE_MISMATCH",
    "EVIE_PROJECT_NOT_FOUND",
    "EVIE_PROJECT_INACTIVE",
    "EVIE_PROJECT_SCOPE_FORBIDDEN",
    "EVIE_DATA_INTEGRITY_ERROR",
}


def test_stable_error_code_set_matches_phase1_contract() -> None:
    assert {member.value for member in EvieAiErrorCode} == EXPECTED_CODES


def test_domain_error_exposes_structured_contract_without_transport_logic() -> None:
    error = EvieAiDomainError(
        EvieAiErrorCode.ROW_VERSION_CONFLICT,
        stage=EvieAiErrorStage.LIFECYCLE,
        message="The asset was modified by another request.",
        retryable=True,
        trace_id="trace-1",
        remediation="Reload the current asset before retrying.",
        related_entity_id="ta_example",
    )

    assert error.code is EvieAiErrorCode.ROW_VERSION_CONFLICT
    assert error.domain == EVIE_AI_ERROR_DOMAIN
    assert error.stage is EvieAiErrorStage.LIFECYCLE
    assert error.retryable is True
    assert error.trace_id == "trace-1"
    assert error.remediation
    assert error.related_entity_id == "ta_example"
