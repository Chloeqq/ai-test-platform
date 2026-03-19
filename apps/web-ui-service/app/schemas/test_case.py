from datetime import datetime

from pydantic import BaseModel, Field


class TestCaseDataConfig(BaseModel):
    enabled: bool = False
    parameters: list[str] = Field(default_factory=list)
    rows: list[list[str]] = Field(default_factory=list)


class TestCaseListItem(BaseModel):
    id: int
    name: str
    product_line: str
    module: str
    priority: str
    test_type: str
    tags: list[str]
    markers: list[str]
    creator: str
    pytest_path: str
    status: str
    last_execution_result: str
    updated_at: datetime | None = None


class TestCaseCreate(BaseModel):
    mode: str = Field(default="manual", pattern="^(manual|ai)$")
    name: str = Field(default="", max_length=255)
    product_line: str = Field(min_length=1, max_length=120)
    module: str = Field(min_length=1, max_length=120)
    priority: str = Field(default="P2", max_length=20)
    test_type: str = Field(default="ui", max_length=50)
    tags: list[str] = Field(default_factory=list)
    markers: list[str] = Field(default_factory=list)
    creator: str = Field(default="admin", max_length=120)
    pytest_path: str = Field(default="", max_length=500)
    status: str = Field(default="active", max_length=20)
    script_code: str = ""
    requirement: str = ""
    data_config: TestCaseDataConfig = Field(default_factory=TestCaseDataConfig)


class TestCaseUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    product_line: str | None = Field(default=None, max_length=120)
    module: str | None = Field(default=None, max_length=120)
    priority: str | None = Field(default=None, max_length=20)
    test_type: str | None = Field(default=None, max_length=50)
    tags: list[str] | None = None
    markers: list[str] | None = None
    creator: str | None = Field(default=None, max_length=120)
    pytest_path: str | None = Field(default=None, max_length=500)
    status: str | None = Field(default=None, max_length=20)
    script_code: str | None = None
    data_config: TestCaseDataConfig | None = None


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
