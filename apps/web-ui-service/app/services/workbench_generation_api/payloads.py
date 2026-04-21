from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class FullChainRunPayload(BaseModel):
    project: str = Field(default="atp")
    page: str = Field(default="")
    requirement: str = Field(default="")
    source: str = Field(default="manual")
    page_urls: list[str] = Field(default_factory=list)
    title: str = Field(default="")
    priority: str = Field(default="P1")
    tags: list[str] = Field(default_factory=lambda: ["ai-generated"])
    case_id: str = Field(default="")
    max_cases: int = Field(default=10, ge=1, le=20)
    combination_mode: str = Field(default="intent_based")
    coverage_profile: str = Field(default="normal+abnormal+boundary")
    coverage_threshold: float = Field(default=1.0, ge=0.0, le=1.0)
    coverage_gate_block_on_gap: bool = Field(default=False)
    wait_seconds: int = Field(default=240, ge=10, le=1800)
    run_after_generate: bool = Field(default=True)
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


class AutoRunPayload(BaseModel):
    project: str = Field(default="default")
    requirement: str = Field(default="")
    page_urls: list[str] = Field(default_factory=list, min_length=1, max_length=20)
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
