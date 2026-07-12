from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.services import workbench_generation_service
from app.services.prompt_manager import PromptManager
from shared_backend.execution_compiler import (
    build_system_requirement,
    has_multisource_inputs,
    normalize_page_slug,
)

from .orchestrator_client_factory import build_orchestrator_client

_LOGGER = logging.getLogger(__name__)


class preview_usecase:
    def __init__(self, *, orchestrator_client: Any, db: Session) -> None:
        self._orchestrator_client = orchestrator_client
        self._db = db

    def execute(self, payload: Any) -> dict[str, Any]:
        project = str(getattr(payload, "project", "") or "").strip() or "mall"
        page = str(getattr(payload, "page", "") or "").strip()
        normalized_page = normalize_page_slug(page) if page else ""
        requirement_text = str(getattr(payload, "requirement", "") or "").strip()
        source = str(getattr(payload, "source", "") or "").strip() or "manual"
        input_sources = [
            item for item in (getattr(payload, "input_sources", None) or [])
            if isinstance(item, dict)
        ]
        openapi_spec = getattr(payload, "openapi_spec", None)
        openapi_spec = openapi_spec if isinstance(openapi_spec, dict) else {}
        multisource_enabled = has_multisource_inputs(
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
            or build_system_requirement(page=normalized_page, has_multisource_inputs=multisource_enabled)
        )

        # resolve prompt override from DB (DB is sole source of truth, no hardcoded fallback)
        prompt_system: str | None = None
        prompt_user: str | None = None
        try:
            template = PromptManager.get_template(self._db, "requirement_parse")
            if template:
                prompt_system, prompt_user = PromptManager.render(template, {
                    "requirement": effective_requirement,
                    "page": normalized_page,
                })
        except Exception:
            _LOGGER.warning("failed to resolve prompt from DB, using agent built-in", exc_info=True)

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
            project=project,
            prompt_system=prompt_system,
            prompt_user=prompt_user,
        )


def build_preview_usecase(*, db: Session) -> preview_usecase:
    orchestrator_client = build_orchestrator_client()
    return preview_usecase(orchestrator_client=orchestrator_client, db=db)
