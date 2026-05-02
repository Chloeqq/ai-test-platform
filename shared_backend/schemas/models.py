"""Shared Pydantic models for the test pipeline contract layer.

These models serve as the single source of truth for data structures flowing
between the orchestrator, normalizer, and compiler. All producers and consumers
should validate against these models.
"""
from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field, model_validator


class TestPointStepV1(BaseModel):
    """A single executable step within a test point."""
    action: str = ""
    target: str = ""
    value: Any = None
    raw_text: str = ""


class DependencyReviewEntryV1(BaseModel):
    key: str = ""
    label: str = ""
    confidence: float = 0.0
    warnings: list[str] = Field(default_factory=list)


class DependencyReviewV1(BaseModel):
    mode: str = "none"
    propagated: bool = False
    involved_elements: list[str] = Field(default_factory=list)
    matched_elements: list[str] = Field(default_factory=list)
    low_confidence_dependencies: list[DependencyReviewEntryV1] = Field(default_factory=list)
    low_confidence_dependency_count: int = 0
    missing_dependencies: list[str] = Field(default_factory=list)
    missing_dependency_count: int = 0
    base_confidence: float = 0.0
    inherited_confidence: float = 0.0
    requires_review: bool = False
    evidence: list[str] = Field(default_factory=list)


class TestPointV1(BaseModel):
    """Normalized test point — the central contract for the pipeline.

    `intent_id` is the full-chain primary key (required).
    `involved_elements` is the canonical element list.
    `steps` carries the structured action sequence.
    """
    key: str = Field(default="")
    intent_id: str = Field(default="")
    point_type: str = Field(default="action")
    action: str = Field(default="")
    description: str = Field(default="")
    field_key: str = Field(default="")
    target: str = Field(default="")
    value: Any = None
    parameter_location: str = Field(default="")
    api_method: str = Field(default="")
    api_path: str = Field(default="")
    priority: str = Field(default="P1")
    expected_result: str = Field(default="")
    dependencies: list[str] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)
    involved_elements: list[str] = Field(default_factory=list)
    steps: list[TestPointStepV1] | None = None
    step_index: int = 0
    confidence: float | None = None
    technique_type: str = Field(default="normal")
    technique_source: str = Field(default="")
    technique_confidence: float = 0.0
    execution_scope: str = Field(default="mainline")
    warnings: list[str] = Field(default_factory=list)
    requires_review: bool = False
    suggestion: str = Field(default="")
    review_reason: str = Field(default="")
    dependency_review: DependencyReviewV1 = Field(default_factory=DependencyReviewV1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TestPointPlanV1(BaseModel):
    """Top-level container for a set of normalized test points."""
    version: str = Field(default="TestPointPlanV1")
    project: str = Field(default="mall")
    case_id: str = Field(default="")
    page: str = Field(default="")
    points: list[TestPointV1] = Field(default_factory=list)
    quality_gate: dict[str, Any] | None = None
    traceability_summary: dict[str, Any] | None = None
    warnings: list[str] = Field(default_factory=list)


class PageElementMapping(BaseModel):
    """A single page element with its selector binding."""
    selector: str
    type: str = "css"


class PageObjectV1(BaseModel):
    """Page object with element mappings, used by the compiler for target binding."""
    elements: dict[str, PageElementMapping] = Field(default_factory=dict)


class QualityGateThresholds(BaseModel):
    """Source-type specific quality gate thresholds."""
    source_type: str = "manual"
    min_test_intents: int = 1
    min_parse_confidence: float = 0.3
    max_coverage_gap_ratio: float = 1.0
    block_high_ambiguity: bool = True


# Allowed action vocabulary for validation
ALLOWED_ACTIONS: frozenset[str] = frozenset({
    "click", "fill", "select", "check", "uncheck",
    "hover", "scroll", "wait", "navigate",
    "assert_visible", "assert_text", "assert_value",
    "assert_hidden", "assert_enabled", "assert_disabled",
    "assert_count", "assert_url", "assert_title", "assert_metric",
    "upload", "download", "drag",
    "press_key", "clear", "focus", "blur",
    "noop",
})

# Source types that the quality gate recognizes
VALID_SOURCE_TYPES: frozenset[str] = frozenset({
    "prd_text", "openapi_spec", "git_diff",
    "user_story", "defect_ticket", "mixed", "manual",
})
