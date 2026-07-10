
"""Workbench HTTP 工具函数。"""
from __future__ import annotations

import json
import logging
import time
from typing import Any
from urllib import error as url_error
from urllib import request as url_request

from fastapi import HTTPException, status

from shared_backend.observability import get_request_id, summarize_http_context


def get_json(url: str, *, timeout_seconds: int = 300) -> dict[str, Any]:
    """请求 orchestrator JSON 接口，并将网络/协议异常映射为 HTTPException。"""
    request_id = get_request_id()
    start = time.perf_counter()
    request = url_request.Request(url=url, method="GET")
    if request_id:
        request.add_header("X-Request-Id", request_id)
    try:
        with url_request.urlopen(request, timeout=timeout_seconds) as response:
            text = response.read().decode("utf-8")
            logging.getLogger(__name__).info(
                "orchestrator_get_end %s",
                summarize_http_context(
                    method="GET",
                    path=url,
                    request_id=request_id,
                    status_code=getattr(response, "status", 200),
                    duration_ms=round((time.perf_counter() - start) * 1000, 2),
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
        logging.getLogger(__name__).warning(
            "orchestrator_get_http_error %s",
            summarize_http_context(
                method="GET",
                path=url,
                request_id=request_id,
                status_code=exc.code,
                duration_ms=round((time.perf_counter() - start) * 1000, 2),
                error=detail,
            ),
        )
        raise HTTPException(status_code=exc.code, detail=detail) from exc
    except url_error.URLError as exc:
        logging.getLogger(__name__).warning(
            "orchestrator_get_unavailable %s",
            summarize_http_context(
                method="GET",
                path=url,
                request_id=request_id,
                duration_ms=round((time.perf_counter() - start) * 1000, 2),
                error=exc.reason,
            ),
        )
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"orchestrator unavailable: {exc.reason}") from exc
    except TimeoutError as exc:  # noqa: B025
        logging.getLogger(__name__).warning(
            "orchestrator_get_timeout %s",
            summarize_http_context(
                method="GET",
                path=url,
                request_id=request_id,
                duration_ms=round((time.perf_counter() - start) * 1000, 2),
                error="timeout",
            ),
        )
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="orchestrator request timed out") from exc
    except TimeoutError as exc:  # noqa: B025
        logging.getLogger(__name__).warning(
            "orchestrator_get_timeout %s",
            summarize_http_context(
                method="GET",
                path=url,
                request_id=request_id,
                duration_ms=round((time.perf_counter() - start) * 1000, 2),
                error="socket_timeout",
            ),
        )
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="orchestrator request timed out") from exc

    try:
        data = json.loads(text or "{}")
    except Exception as exc:
        logging.getLogger(__name__).warning(
            "orchestrator_get_invalid_json %s",
            summarize_http_context(
                method="GET",
                path=url,
                request_id=request_id,
                duration_ms=round((time.perf_counter() - start) * 1000, 2),
                error="invalid_json",
            ),
        )
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="orchestrator returned non-json payload") from exc
    if not isinstance(data, dict):
        logging.getLogger(__name__).warning(
            "orchestrator_get_invalid_response %s",
            summarize_http_context(
                method="GET",
                path=url,
                request_id=request_id,
                duration_ms=round((time.perf_counter() - start) * 1000, 2),
                error="invalid_response_object",
            ),
        )
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="orchestrator returned invalid response object")
    return data
