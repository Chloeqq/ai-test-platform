from datetime import datetime

from pydantic import BaseModel, Field


class TestCaseListItem(BaseModel):
    id: int
    name: str
    product_line: str
    module: str
    priority: str
    tags: list[str]
    creator: str
    last_execution_result: str
    updated_at: datetime | None = None


class TestCaseCreate(BaseModel):
    mode: str = Field(default="manual", pattern="^(manual|ai)$")
    name: str = Field(default="", max_length=255)
    product_line: str = Field(min_length=1, max_length=120)
    module: str = Field(min_length=1, max_length=120)
    priority: str = Field(default="P2", max_length=20)
    tags: list[str] = Field(default_factory=list)
    creator: str = Field(default="admin", max_length=120)
    script_code: str = ""
    requirement: str = ""


class TestCaseScriptUpdate(BaseModel):
    script_code: str
    changed_by: str = Field(default="admin", max_length=120)


class BatchIdsPayload(BaseModel):
    ids: list[int] = Field(default_factory=list)


class BatchTagsUpdatePayload(BaseModel):
    ids: list[int] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    mode: str = Field(default="replace", pattern="^(replace|append)$")


class BatchExportPayload(BaseModel):
    ids: list[int] = Field(default_factory=list)
    format: str = Field(default="json", pattern="^(json|csv)$")
