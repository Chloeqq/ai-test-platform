from __future__ import annotations

from fastapi import HTTPException
from fastapi.exceptions import RequestValidationError

from app.errors.evie_ai import EvieAiDomainError, EvieAiErrorCode, EvieAiErrorStage
from app.services.evie_ai.http_error_adapter import (
    response_for_domain_error,
    response_for_http_exception,
    response_for_request_validation_error,
    response_for_unexpected_exception,
)


def test_domain_error_adapter_returns_stable_envelope_and_status() -> None:
    response = response_for_domain_error(
        EvieAiDomainError(
            EvieAiErrorCode.PROJECT_SCOPE_FORBIDDEN,
            stage=EvieAiErrorStage.AUTHORIZATION,
            message="forbidden",
        ),
        request_id="request-123",
    )
    payload = response.body.decode("utf-8")

    assert response.status_code == 403
    assert "EVIE_PROJECT_SCOPE_FORBIDDEN" in payload
    assert '"request_id":"request-123"' in payload
    assert '"error":' in payload


def test_http_401_uses_approved_authentication_error_code() -> None:
    response = response_for_http_exception(
        HTTPException(status_code=401, detail="token value must not leak"),
        request_id="request-123",
    )
    payload = response.body.decode("utf-8")

    assert response.status_code == 401
    assert "EVIE_AUTHENTICATION_REQUIRED" in payload
    assert "token value must not leak" not in payload


def test_request_validation_adapter_omits_sensitive_input_values() -> None:
    response = response_for_request_validation_error(
        RequestValidationError(
            [
                {
                    "type": "string_type",
                    "loc": ("body", "project_code"),
                    "msg": "Input should be a valid string",
                    "input": "secret request body",
                }
            ]
        ),
        request_id="request-123",
    )
    payload = response.body.decode("utf-8")

    assert response.status_code == 422
    assert "EVIE_REQUEST_VALIDATION_ERROR" in payload
    assert "secret request body" not in payload
    assert '"loc":["body","project_code"]' in payload
    assert '"input"' not in payload


def test_unexpected_error_adapter_hides_internal_exception_details() -> None:
    response = response_for_unexpected_exception(request_id="request-123")
    payload = response.body.decode("utf-8")

    assert response.status_code == 500
    assert "EVIE_DATA_INTEGRITY_ERROR" in payload
    assert "request-123" in payload
    assert "Traceback" not in payload
