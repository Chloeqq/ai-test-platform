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


class TestPointPlan(BaseModel):
    page: str
    requirement: List[str] = []
    source_type: Optional[str] = None
    source_name: Optional[str] = None
    source_ref: Optional[str] = None
    priority: Optional[str] = None
    points: List[TestPoint]
