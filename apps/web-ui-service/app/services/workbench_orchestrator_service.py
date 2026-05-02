from __future__ import annotations

import json
import logging
import socket
import time
from typing import Any, Callable
from urllib import error as url_error
from urllib import request as url_request

from fastapi import status

from app.core.config import get_settings
from shared_backend.observability import get_request_id, summarize_http_context

HttpExceptionFactory = Callable[..., Exception]
_LOGGER = logging.getLogger(__name__)


def post_json(
    url: str,
    payload: dict[str, Any],
    *,
    timeout_seconds: int = 300,
    http_exception_cls: HttpExceptionFactory = Exception,
    bad_gateway_status: int = status.HTTP_502_BAD_GATEWAY,
    gateway_timeout_status: int = status.HTTP_504_GATEWAY_TIMEOUT,
) -> dict[str, Any]:
    settings = get_settings()
    request_id = get_request_id()
    start = time.perf_counter()
    _LOGGER.info(
        "orchestrator_post_start %s",
        summarize_http_context(
            method="POST",
            path=url,
            request_id=request_id,
            payload=payload,
        ),
    )
    request = url_request.Request(
        url=url,
        method="POST",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            **({"X-Api-Key": settings.orchestrator_api_key} if settings.orchestrator_api_key else {}),
            **({"X-Request-Id": request_id} if request_id else {}),
        },
    )
    try:
        with url_request.urlopen(request, timeout=timeout_seconds) as response:
            text = response.read().decode("utf-8")
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            _LOGGER.info(
                "orchestrator_post_end %s",
                summarize_http_context(
                    method="POST",
                    path=url,
                    request_id=request_id,
                    status_code=getattr(response, "status", 200),
                    duration_ms=duration_ms,
                ),
            )
    except url_error.HTTPError as exc:
        raw_body = exc.read().decode("utf-8", errors="ignore")
        detail: Any = raw_body.strip() or str(exc)
        try:
            parsed = json.loads(raw_body or "{}")
            if isinstance(parsed, dict):
                detail = parsed.get("error", parsed)
        except Exception:
            pass
        _LOGGER.warning(
            "orchestrator_post_http_error %s",
            summarize_http_context(
                method="POST",
                path=url,
                request_id=request_id,
                status_code=exc.code,
                duration_ms=round((time.perf_counter() - start) * 1000, 2),
                error=detail,
            ),
        )
        raise http_exception_cls(status_code=exc.code, detail=detail) from exc
    except url_error.URLError as exc:
        _LOGGER.warning(
            "orchestrator_post_unavailable %s",
            summarize_http_context(
                method="POST",
                path=url,
                request_id=request_id,
                duration_ms=round((time.perf_counter() - start) * 1000, 2),
                error=exc.reason,
            ),
        )
        raise http_exception_cls(
            status_code=bad_gateway_status,
            detail=f"orchestrator unavailable: {exc.reason}",
        ) from exc
    except TimeoutError as exc:
        _LOGGER.warning(
            "orchestrator_post_timeout %s",
            summarize_http_context(
                method="POST",
                path=url,
                request_id=request_id,
                duration_ms=round((time.perf_counter() - start) * 1000, 2),
                error="timeout",
            ),
        )
        raise http_exception_cls(
            status_code=gateway_timeout_status,
            detail="orchestrator request timed out",
        ) from exc
    except socket.timeout as exc:
        _LOGGER.warning(
            "orchestrator_post_timeout %s",
            summarize_http_context(
                method="POST",
                path=url,
                request_id=request_id,
                duration_ms=round((time.perf_counter() - start) * 1000, 2),
                error="socket_timeout",
            ),
        )
        raise http_exception_cls(
            status_code=gateway_timeout_status,
            detail="orchestrator request timed out",
        ) from exc

    try:
        data = json.loads(text or "{}")
    except Exception as exc:
        _LOGGER.warning(
            "orchestrator_post_invalid_json %s",
            summarize_http_context(
                method="POST",
                path=url,
                request_id=request_id,
                duration_ms=round((time.perf_counter() - start) * 1000, 2),
                error="invalid_json",
            ),
        )
        raise http_exception_cls(
            status_code=bad_gateway_status,
            detail="orchestrator returned non-json payload",
        ) from exc
    if not isinstance(data, dict):
        _LOGGER.warning(
            "orchestrator_post_invalid_response %s",
            summarize_http_context(
                method="POST",
                path=url,
                request_id=request_id,
                duration_ms=round((time.perf_counter() - start) * 1000, 2),
                error="invalid_response_object",
            ),
        )
        raise http_exception_cls(
            status_code=bad_gateway_status,
            detail="orchestrator returned invalid response object",
        )
    return data
