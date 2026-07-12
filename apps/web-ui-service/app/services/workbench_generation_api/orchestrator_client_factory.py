from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status

from app.core.config import get_settings
from app.services import workbench_orchestrator_service
from shared_backend.execution_compiler import (
    extract_quality_gate,
    is_quality_gate_blocked,
    render_requirement_spec_markdown,
)

from .orchestrator_client import OrchestratorClient


def _post_json(url: str, payload: dict[str, Any], *, timeout_seconds: int) -> dict[str, Any]:
    return workbench_orchestrator_service.post_json(
        url,
        payload,
        timeout_seconds=timeout_seconds,
        http_exception_cls=HTTPException,
        bad_gateway_status=status.HTTP_502_BAD_GATEWAY,
        gateway_timeout_status=status.HTTP_504_GATEWAY_TIMEOUT,
    )


def build_orchestrator_client() -> OrchestratorClient:
    settings = get_settings()

    def _run_parse(**kwargs: Any) -> dict[str, Any]:
        endpoint = f"{settings.orchestrator_url.rstrip('/')}/requirements/parse"
        payload: dict[str, Any] = {
            "requirement": kwargs.get("requirement", ""),
            "page": kwargs.get("page", ""),
            "source": kwargs.get("source", ""),
        }
        if kwargs.get("input_sources"):
            payload["input_sources"] = kwargs["input_sources"]
        if isinstance(kwargs.get("openapi_spec"), dict) and kwargs.get("openapi_spec"):
            payload["openapi_spec"] = kwargs["openapi_spec"]
        # Prompt override: 从 DB template 渲染后注入,agent 优先使用
        for override_key in ("prompt_system", "prompt_user"):
            val = kwargs.get(override_key)
            if val:
                payload[override_key] = val
        for key in (
            "prd_text",
            "prd_url",
            "user_story",
            "git_diff",
            "git_diff_path",
            "openapi_url",
            "defect_ticket",
            "runtime_logs",
        ):
            value = str(kwargs.get(key, "") or "").strip()
            if value:
                payload[key] = value
        return _post_json(endpoint, payload, timeout_seconds=settings.orchestrator_timeout_seconds)

    def _run_generate(**kwargs: Any) -> dict[str, Any]:
        endpoint = f"{settings.orchestrator_url.rstrip('/')}/orchestrate"
        payload: dict[str, Any] = {
            "requirement": kwargs.get("requirement", ""),
            "page": kwargs.get("page", ""),
            "source": kwargs.get("source", ""),
            "mode": "generate_only",
            "execute": False,
        }
        if kwargs.get("input_sources"):
            payload["input_sources"] = kwargs["input_sources"]
        if isinstance(kwargs.get("openapi_spec"), dict) and kwargs.get("openapi_spec"):
            payload["openapi_spec"] = kwargs["openapi_spec"]
        for key in (
            "prd_text",
            "prd_url",
            "user_story",
            "git_diff",
            "git_diff_path",
            "openapi_url",
            "defect_ticket",
            "runtime_logs",
        ):
            value = str(kwargs.get(key, "") or "").strip()
            if value:
                payload[key] = value
        return _post_json(endpoint, payload, timeout_seconds=settings.orchestrator_timeout_seconds)

    return OrchestratorClient(
        run_generate=_run_generate,
        run_parse=_run_parse,
        extract_quality_gate=extract_quality_gate,
        is_quality_gate_blocked=is_quality_gate_blocked,
        render_requirement_spec_markdown=render_requirement_spec_markdown,
    )
