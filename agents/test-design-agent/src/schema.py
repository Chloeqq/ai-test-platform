from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class Step(BaseModel):
    action: str = Field(min_length=1)
    target: str | None = None
    value: Any = None


class Execution(BaseModel):
    runner: str = Field(min_length=1)
    page: str = Field(min_length=1)
    variables: dict[str, Any] = Field(default_factory=dict)
    steps: list[Step] = Field(default_factory=list, min_length=1)


class TestCase(BaseModel):
    version: str = Field(min_length=1)
    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    module: str = Field(min_length=1)
    priority: str = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)
    owner: str = Field(min_length=1)
    status: str = Field(min_length=1)
    description: str = ""
    requirement: list[str] = Field(default_factory=list)
    data: dict[str, list[Any]] = Field(default_factory=dict)
    execution: Execution


class DesignBundle(BaseModel):
    version: str = Field(min_length=1)
    page: str = Field(min_length=1)
    requirement: list[str] = Field(default_factory=list)
    requirement_spec: dict[str, Any] = Field(default_factory=dict)
    case: TestCase
    test_points: dict[str, Any] = Field(default_factory=dict)
    traceability: dict[str, Any] = Field(default_factory=dict)
    review_summary: dict[str, Any] = Field(default_factory=dict)
    confidence: float | None = None
    warnings: list[str] = Field(default_factory=list)
    requires_review: bool | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class TestPoint(BaseModel):
    key: str
    intent_id: str = ""
    point_type: str
    description: str
    action: str
    target: str | None = None
    value: Any = None
    field_key: str | None = None
    confidence: float | None = None
    warnings: list[str] = Field(default_factory=list)
    requires_review: bool | None = None
    suggestion: str | None = None
    review_reason: str | None = None
    involved_elements: list[str] = Field(default_factory=list)
    steps: list[dict[str, Any]] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)
    technique_type: str | None = "normal"
    technique_source: str | None = None
    technique_confidence: float | None = None
    execution_scope: str | None = "mainline"


class TestPointPlan(BaseModel):
    page: str
    requirement: list[str] = Field(default_factory=list)
    source_type: str | None = None
    source_name: str | None = None
    source_ref: str | None = None
    priority: str | None = None
    points: list[TestPoint] = Field(default_factory=list)
    confidence: float | None = None
    warnings: list[str] = Field(default_factory=list)
    requires_review: bool | None = None
    review_summary: dict[str, Any] = Field(default_factory=dict)
