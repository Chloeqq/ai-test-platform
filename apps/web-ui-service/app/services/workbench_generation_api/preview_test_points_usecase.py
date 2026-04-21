from __future__ import annotations

from typing import Any

from app.services import workbench_generation_service
from shared_backend.execution_compiler import (
    _extract_quality_gate,
    _normalize_page_slug,
    _render_requirement_spec_markdown,
    _build_system_requirement,
    _has_multisource_inputs,
    _list_value,
    _dict_value,
)

from .orchestrator_client_factory import build_orchestrator_client


class preview_usecase:
    def __init__(self, *, orchestrator_client: Any) -> None:
        self._orchestrator_client = orchestrator_client

    def execute(self, payload: Any) -> dict[str, Any]:
        page = str(getattr(payload, "page", "") or "").strip()
        normalized_page = _normalize_page_slug(page) if page else ""
        requirement_text = str(getattr(payload, "requirement", "") or "").strip()
        source = str(getattr(payload, "source", "") or "").strip() or "manual"
        input_sources = [
            item for item in (getattr(payload, "input_sources", None) or [])
            if isinstance(item, dict)
        ]
        openapi_spec = getattr(payload, "openapi_spec", None)
        openapi_spec = openapi_spec if isinstance(openapi_spec, dict) else {}
        multisource_enabled = _has_multisource_inputs(
            input_sources=input_sources,
            openapi_spec=openapi_spec,
            prd_text=getattr(payload, "prd_text", ""),
            prd_url=getattr(payload, "prd_url", ""),
            user_story=getattr(payload, "user_story", ""),
            git_diff=getattr(payload, "git_diff", ""),
            git_diff_path=getattr(payload, "git_diff_path", ""),
            openapi_url=getattr(payload, "openapi_url", ""),
            defect_ticket=getattr(payload, "defect_ticket", ""),
            runtime_logs=getattr(payload, "runtime_logs", ""),
        )
        effective_requirement = (
            requirement_text
            or _build_system_requirement(page=normalized_page, has_multisource_inputs=multisource_enabled)
        )

        return workbench_generation_service.build_preview_response(
            effective_requirement=effective_requirement,
            normalized_page=normalized_page,
            source=source,
            input_sources=input_sources,
            openapi_spec=openapi_spec,
            prd_text=str(getattr(payload, "prd_text", "") or ""),
            prd_url=str(getattr(payload, "prd_url", "") or ""),
            user_story=str(getattr(payload, "user_story", "") or ""),
            git_diff=str(getattr(payload, "git_diff", "") or ""),
            git_diff_path=str(getattr(payload, "git_diff_path", "") or ""),
            openapi_url=str(getattr(payload, "openapi_url", "") or ""),
            defect_ticket=str(getattr(payload, "defect_ticket", "") or ""),
            runtime_logs=str(getattr(payload, "runtime_logs", "") or ""),
            run_orchestrator_parse=self._orchestrator_client.parse,
            render_requirement_spec_markdown=self._orchestrator_client.render_requirement_spec_markdown,
            extract_quality_gate=self._orchestrator_client.extract_quality_gate,
        )


def build_preview_usecase() -> preview_usecase:
    orchestrator_client = build_orchestrator_client()
    return preview_usecase(orchestrator_client=orchestrator_client)
