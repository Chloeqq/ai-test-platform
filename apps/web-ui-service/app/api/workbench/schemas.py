from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class GenerateCasePayload(BaseModel):
    project: str = Field(default="default")
    page: str = Field(default="")
    requirement: str = Field(default="")
    title: str = Field(default="")
    case_id: str = Field(default="")
    priority: str = Field(default="P1")
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
    selected_candidates: list[dict[str, Any]] = Field(default_factory=list)


class SaveCasePayload(BaseModel):
    project: str = Field(default="default")
    yaml_content: str = Field(min_length=1)


class RunCasePayload(BaseModel):
    project: str = Field(default="default")
    case_id: str = Field(min_length=1)
    case_path: str = Field(default="")
    source: str = Field(default="manual")


class AutoRunPayload(BaseModel):
    project: str = Field(default="default")
    requirement: str = Field(default="")
    page_urls: list[str] = Field(min_length=1, max_length=20)
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
    wait_seconds: int = Field(default=240, ge=30, le=1800)


class DefectPayload(BaseModel):
    case_id: str = Field(min_length=1)
    defect_id: str = Field(min_length=1)
    defect_url: str = Field(default="")
    system: str = Field(default="manual")
    note: str = Field(default="")


class WorkbenchReviewPayload(BaseModel):
    project: str = Field(default="default")
    run_id: str = Field(min_length=1)
    case_id: str = Field(default="")
    page: str = Field(min_length=1)
    review_type: str = Field(min_length=1)
    status: str = Field(default="confirmed")
    items: list[dict[str, Any]] = Field(default_factory=list)
    note: str = Field(default="")
    failure_source_feedback: dict[str, Any] | None = None


class ExecutionGateDecisionPayload(BaseModel):
    project: str = Field(default="default")
    run_id: str = Field(min_length=1)
    case_id: str = Field(default="")
    page: str = Field(min_length=1)
    decision: str = Field(min_length=1)
    note: str = Field(default="")


class ExecutionGateDecisionActionPayload(BaseModel):
    project: str = Field(default="default")
    run_id: str = Field(min_length=1)
    page: str = Field(min_length=1)
    note: str = Field(default="")
