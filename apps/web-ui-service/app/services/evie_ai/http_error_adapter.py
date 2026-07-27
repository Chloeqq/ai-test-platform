"""EvieAi 命名空间内的结构化 HTTP 错误适配。"""

from __future__ import annotations

from fastapi import HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.errors.evie_ai import (
    EVIE_AI_ERROR_DOMAIN,
    EvieAiDomainError,
    EvieAiErrorCode,
    EvieAiErrorStage,
)
from app.schemas.evie_ai.operations import EvieAiErrorBody, EvieAiErrorResponse


_HTTP_STATUS_BY_ERROR_CODE = {
    EvieAiErrorCode.ASSET_NOT_FOUND: 404,
    EvieAiErrorCode.VERSION_NOT_FOUND: 404,
    EvieAiErrorCode.PROJECT_NOT_FOUND: 404,
    EvieAiErrorCode.ASSET_DELETED: 410,
    EvieAiErrorCode.ASSET_STATE_CONFLICT: 409,
    EvieAiErrorCode.IDEMPOTENCY_CONFLICT: 409,
    EvieAiErrorCode.IDEMPOTENCY_KEY_REQUIRED: 422,
    EvieAiErrorCode.ROW_VERSION_CONFLICT: 409,
    EvieAiErrorCode.EXACT_DUPLICATE_CONFLICT: 409,
    EvieAiErrorCode.RESTORE_DUPLICATE_CONFLICT: 409,
    EvieAiErrorCode.INVALID_REVIEW_TRANSITION: 422,
    EvieAiErrorCode.REVIEW_VERSION_NOT_CURRENT: 409,
    EvieAiErrorCode.VERSION_SCOPE_MISMATCH: 409,
    EvieAiErrorCode.SOURCE_SCOPE_MISMATCH: 409,
    EvieAiErrorCode.PROJECT_INACTIVE: 409,
    EvieAiErrorCode.PROJECT_SCOPE_FORBIDDEN: 403,
    EvieAiErrorCode.AUTHENTICATION_REQUIRED: 401,
    EvieAiErrorCode.REQUEST_VALIDATION_ERROR: 422,
    EvieAiErrorCode.DATA_INTEGRITY_ERROR: 500,
}

_HTTP_EXCEPTION_METADATA = {
    401: (
        EvieAiErrorCode.AUTHENTICATION_REQUIRED,
        EvieAiErrorStage.IDENTITY,
        "Authentication is required.",
    ),
    403: (
        EvieAiErrorCode.PROJECT_SCOPE_FORBIDDEN,
        EvieAiErrorStage.AUTHORIZATION,
        "The requested operation is forbidden.",
    ),
    404: (
        EvieAiErrorCode.PROJECT_NOT_FOUND,
        EvieAiErrorStage.REQUEST_VALIDATION,
        "The requested resource was not found.",
    ),
    409: (
        EvieAiErrorCode.PROJECT_INACTIVE,
        EvieAiErrorStage.REQUEST_VALIDATION,
        "The requested operation conflicts with the current state.",
    ),
    422: (
        EvieAiErrorCode.REQUEST_VALIDATION_ERROR,
        EvieAiErrorStage.REQUEST_VALIDATION,
        "The request is invalid.",
    ),
}


def response_for_domain_error(
    error: EvieAiDomainError,
    *,
    request_id: str,
) -> JSONResponse:
    return _error_response(
        status_code=_HTTP_STATUS_BY_ERROR_CODE.get(error.code, 500),
        code=error.code,
        stage=error.stage,
        message=error.message,
        retryable=error.retryable,
        request_id=request_id,
        trace_id=error.trace_id,
    )


def response_for_http_exception(
    error: HTTPException,
    *,
    request_id: str,
) -> JSONResponse:
    code, stage, message = _HTTP_EXCEPTION_METADATA.get(
        error.status_code,
        (
            EvieAiErrorCode.DATA_INTEGRITY_ERROR,
            EvieAiErrorStage.PERSISTENCE,
            "The request could not be completed.",
        ),
    )
    return _error_response(
        status_code=error.status_code,
        code=code,
        stage=stage,
        message=message,
        retryable=False,
        request_id=request_id,
    )


def response_for_request_validation_error(
    error: RequestValidationError,
    *,
    request_id: str,
) -> JSONResponse:
    return _error_response(
        status_code=422,
        code=EvieAiErrorCode.REQUEST_VALIDATION_ERROR,
        stage=EvieAiErrorStage.REQUEST_VALIDATION,
        message="The request is invalid.",
        retryable=False,
        request_id=request_id,
        details=_controlled_validation_details(error),
    )


def response_for_unexpected_exception(*, request_id: str) -> JSONResponse:
    return _error_response(
        status_code=500,
        code=EvieAiErrorCode.DATA_INTEGRITY_ERROR,
        stage=EvieAiErrorStage.PERSISTENCE,
        message="An internal EvieAi error occurred.",
        retryable=False,
        request_id=request_id,
    )


def _controlled_validation_details(error: RequestValidationError) -> dict[str, object]:
    validation_errors: list[dict[str, object]] = []
    for item in error.errors():
        raw_location = item.get("loc", ())
        location = [str(part) for part in raw_location]
        validation_errors.append(
            {
                "loc": location,
                "type": str(item.get("type", "validation_error")),
            }
        )
    return {"validation_errors": validation_errors}


def _error_response(
    *,
    status_code: int,
    code: EvieAiErrorCode,
    stage: EvieAiErrorStage,
    message: str,
    retryable: bool,
    request_id: str,
    trace_id: str | None = None,
    details: dict[str, object] | None = None,
) -> JSONResponse:
    response = EvieAiErrorResponse(
        error=EvieAiErrorBody(
            code=code,
            domain=EVIE_AI_ERROR_DOMAIN,
            stage=stage,
            message=message,
            retryable=retryable,
            trace_id=trace_id,
            details=details or {},
            request_id=_response_request_id(request_id),
        )
    )
    return JSONResponse(status_code=status_code, content=response.model_dump(mode="json"))


def _response_request_id(request_id: str) -> str:
    if isinstance(request_id, str) and request_id.strip():
        return request_id.strip()
    return "-"
