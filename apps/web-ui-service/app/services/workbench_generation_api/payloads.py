from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from . import constants as _c


class GenerateCasePayload(BaseModel):
    # 优先取 payload 传入值，为空时 service 层用 context.default_project（DB 查询）
    project: str = Field(default="")
    page: str = Field(default="")
    page_url: str = Field(default="")
    requirement: str = Field(default="")
    title: str = Field(default="")
    case_id: str = Field(default="")
    priority: str = Field(default=_c.DEFAULT_PRIORITY)
    tags: list[str] = Field(default_factory=lambda: ["ai-generated"])
    source: str = Field(default="manual")
    input_sources: list[dict[str, Any]] = Field(default_factory=list)
    openapi_spec: dict[str, Any] | None = None
    prd_text: str = Field(default="")
    prd_url: str = Field(default="")
    user_story: str = Field(default="")
    git_diff: str = Field(default="")
    git_diff_path: str = Field(default="")
    openapi_url: str = Field(default="")
    defect_ticket: str = Field(default="")
    runtime_logs: str = Field(default="")
    preview_id: str = Field(default="")
    selected_candidates: list[dict[str, Any]] = Field(default_factory=list)
    selected_intent_ids: list[str] = Field(default_factory=list)


class PrecheckSelectedIntentsPayload(BaseModel):
    # 优先取 payload 传入值，为空时 service 层用 context.default_project（DB 查询）
    project: str = Field(default="")
    page: str = Field(default="")
    preview_id: str = Field(default="")
    selected_intent_ids: list[str] = Field(default_factory=list)
    selected_candidates: list[dict[str, Any]] = Field(default_factory=list)

