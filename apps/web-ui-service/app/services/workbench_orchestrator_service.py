from __future__ import annotations

import json
import socket
from typing import Any, Callable
from urllib import error as url_error
from urllib import request as url_request

from fastapi import status

from apps.shared_backend.observability import get_request_id

HttpExceptionFactory = Callable[..., Exception]


def post_json(
    url: str,
    payload: dict[str, Any],
    *,
    timeout_seconds: int = 300,
    http_exception_cls: HttpExceptionFactory = Exception,
    bad_gateway_status: int = status.HTTP_502_BAD_GATEWAY,
    gateway_timeout_status: int = status.HTTP_504_GATEWAY_TIMEOUT,
) -> dict[str, Any]:
    request_id = get_request_id()
    request = url_request.Request(
        url=url,
        method="POST",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            **({"X-Request-Id": request_id} if request_id else {}),
        },
    )
    try:
        with url_request.urlopen(request, timeout=timeout_seconds) as response:
            text = response.read().decode("utf-8")
    except url_error.HTTPError as exc:
        raw_body = exc.read().decode("utf-8", errors="ignore")
        detail: Any = raw_body.strip() or str(exc)
        try:
            parsed = json.loads(raw_body or "{}")
            if isinstance(parsed, dict):
                detail = parsed.get("error", parsed)
        except Exception:
            pass
        raise http_exception_cls(status_code=exc.code, detail=detail) from exc
    except url_error.URLError as exc:
        raise http_exception_cls(
            status_code=bad_gateway_status,
            detail=f"orchestrator unavailable: {exc.reason}",
        ) from exc
    except TimeoutError as exc:
        raise http_exception_cls(
            status_code=gateway_timeout_status,
            detail="orchestrator request timed out",
        ) from exc
    except socket.timeout as exc:
        raise http_exception_cls(
            status_code=gateway_timeout_status,
            detail="orchestrator request timed out",
        ) from exc

    try:
        data = json.loads(text or "{}")
    except Exception as exc:
        raise http_exception_cls(
            status_code=bad_gateway_status,
            detail="orchestrator returned non-json payload",
        ) from exc
    if not isinstance(data, dict):
        raise http_exception_cls(
            status_code=bad_gateway_status,
            detail="orchestrator returned invalid response object",
        )
    return data
