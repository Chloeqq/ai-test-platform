"""AI 测试质量评估中心 — Pydantic Schemas。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ── Dataset ──────────────────────────────────────────────────

class EvalItemInput(BaseModel):
    requirement_text: str
    expected_coverage: list[str] = Field(default_factory=list)
    expected_assertions: list[dict] = Field(default_factory=list)
    expected_page_codes: list[str] = Field(default_factory=list)
    perturbed_requirement: str = ""
    known_issues: list[str] = Field(default_factory=list)
    category: str = ""
    context_json: dict[str, Any] = Field(default_factory=dict)


class CreateDatasetRequest(BaseModel):
    project_code: str = "atp"
    name: str
    description: str = ""
    task_type: str = "test_case_generation"
    eval_dimensions: list[str] = Field(default_factory=list)
    items: list[EvalItemInput] = Field(default_factory=list)


class DatasetResponse(BaseModel):
    dataset_id: str
    project_code: str
    name: str
    description: str
    task_type: str
    eval_dimensions: list[str]
    item_count: int
    version: int
    created_at: datetime | None = None
    updated_at: datetime | None = None


class DatasetDetailResponse(DatasetResponse):
    items: list[dict[str, Any]] = Field(default_factory=list)


# ── Run ──────────────────────────────────────────────────────

class CreateRunRequest(BaseModel):
    dataset_id: str
    project_code: str = "atp"
    agent_version: str = ""
    llm_model: str = ""
    prompt_version: str = ""
    gate_rule_version: str = ""
    task_type: str = "test_case_generation"
    eval_dimensions: list[str] = Field(default_factory=list)
    repeat_count: int = Field(default=1, ge=1, le=5)


class RunResponse(BaseModel):
    run_id: str
    dataset_id: str
    project_code: str
    agent_version: str
    llm_model: str
    prompt_version: str
    gate_rule_version: str
    task_type: str
    eval_dimensions: list[str]
    status: str
    total_items: int
    completed_items: int
    overall_score: float
    coverage_score: float
    assertion_score: float
    executability_score: float
    consistency_score: float
    robustness_score: float
    hallucination_risk: float
    created_at: datetime | None = None
    finished_at: datetime | None = None


# ── Result ───────────────────────────────────────────────────

class EvalResultResponse(BaseModel):
    result_id: str
    run_id: str
    item_id: str
    requirement_text: str = ""
    coverage_score: float
    coverage_detail: dict[str, Any] = Field(default_factory=dict)
    assertion_score: float
    assertion_detail: dict[str, Any] = Field(default_factory=dict)
    executability_score: float
    executability_detail: dict[str, Any] = Field(default_factory=dict)
    consistency_score: float
    robustness_score: float
    hallucination_flags: list[str] = Field(default_factory=list)
    hallucination_score: float
    weighted_score: float
    latency_ms: int = 0
    error_message: str = ""


# ── Report ───────────────────────────────────────────────────

class RunReportResponse(BaseModel):
    run_id: str
    dataset_name: str
    task_type: str
    agent_version: str
    llm_model: str
    status: str
    overall_score: float
    dimension_scores: dict[str, float] = Field(default_factory=dict)
    issue_breakdown: dict[str, int] = Field(default_factory=dict)
    compared_to_previous: dict[str, Any] | None = None
    worst_items: list[dict[str, Any]] = Field(default_factory=list)