from typing import List, Optional
from pydantic import BaseModel


class Step(BaseModel):
    action: str
    target: Optional[str] = None
    value: Optional[str] = None


class Execution(BaseModel):
    runner: str
    page: str
    variables: dict = {}
    steps: List[Step]


class TestCase(BaseModel):
    version: str
    id: str
    title: str
    module: str
    priority: Optional[str] = "P1"
    tags: List[str] = []
    owner: Optional[str] = "qa-team"
    status: Optional[str] = "automated"
    description: Optional[str] = None
    requirement: Optional[List[str]] = []
    data: dict = {}
    execution: Execution


class TestPoint(BaseModel):
    key: str
    point_type: str
    description: str
    action: str
    target: Optional[str] = None
    value: Optional[str] = None
    field_key: Optional[str] = None
    confidence: Optional[float] = None
    warnings: List[str] = []
    requires_review: Optional[bool] = None
    suggestion: Optional[str] = None
    review_reason: Optional[str] = None
    dependent_elements: List[str] = []
    source_ids: List[str] = []
    technique_type: Optional[str] = "normal"
    technique_source: Optional[str] = None
    technique_confidence: Optional[float] = None
    execution_scope: Optional[str] = "mainline"


class TestPointPlan(BaseModel):
    page: str
    requirement: List[str] = []
    source_type: Optional[str] = None
    source_name: Optional[str] = None
    source_ref: Optional[str] = None
    priority: Optional[str] = None
    points: List[TestPoint]
    confidence: Optional[float] = None
    warnings: List[str] = []
    requires_review: Optional[bool] = None
    review_summary: dict = {}
