from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class TestCaseDataConfig(BaseModel):
    enabled: bool = False
    parameters: list[str] = Field(default_factory=list)
    rows: list[list[str]] = Field(default_factory=list)


class TestCaseListItem(BaseModel):
    id: int
    case_id: str
    project_code: str
    client: str
    page_code: str
    module_code: str
    case_type: str
    source: str
    name: str
    product_line: str
    module: str
    chain_stage: str = ""
    sut_service: str = ""
    priority: str
    test_type: str
    scenario_types: list[str] = Field(default_factory=list)
    tags: list[str]
    markers: list[str]
    creator: str
    assignee: str = ""
    pytest_path: str
    status: str
    automation_status: str = "manual"
    last_execution_result: str
    updated_at: datetime | None = None


class TestCaseCreate(BaseModel):
    mode: str = Field(default="manual", pattern="^(manual|ai)$")
    case_id: str = Field(default="", max_length=64)
    project_code: str = Field(default="atp", max_length=20)
    client: str = Field(default="web", max_length=10)
    page_code: str = Field(default="", max_length=20)
    module_code: str = Field(default="", max_length=20)
    case_type: str = Field(default="", max_length=10)
    source: str = Field(default="", max_length=10)
    name: str = Field(default="", max_length=255)
    product_line: str = Field(min_length=1, max_length=120)
    module: str = Field(min_length=1, max_length=120)
    chain_stage: str = Field(default="", max_length=120)
    sut_service: str = Field(default="", max_length=120)
    related_services: list[str] = Field(default_factory=list)
    priority: str = Field(default="P2", max_length=20)
    test_type: str = Field(default="ui", max_length=50)
    scenario_types: list[str] = Field(default_factory=list)
    trigger_entry: str = Field(default="", max_length=40)
    fault_injection_type: str = Field(default="", max_length=80)
    fault_injection_target: str = Field(default="", max_length=255)
    fault_injection_params: str = ""
    setup_sql: str = ""
    precondition_state: str = ""
    test_steps: list[dict[str, Any]] = Field(default_factory=list)
    test_steps_text: str = ""
    concurrency_model: str = Field(default="", max_length=120)
    retry_policy: str = ""
    expected_result: str = ""
    assert_sql: str = ""
    event_assertion: str = ""
    metric_assertion: str = ""
    cleanup_script: str = ""
    artifact_links: list[str] = Field(default_factory=list)
    notes: str = ""
    tags: list[str] = Field(default_factory=list)
    markers: list[str] = Field(default_factory=list)
    creator: str = Field(default="admin", max_length=120)
    assignee: str = Field(default="", max_length=120)
    pytest_path: str = Field(default="", max_length=500)
    status: str = Field(default="active", max_length=20)
    automation_status: str = Field(default="manual", max_length=20)
    source_ref: str = Field(default="", max_length=255)
    script_code: str = ""
    requirement: str = ""
    data_config: TestCaseDataConfig = Field(default_factory=TestCaseDataConfig)


class TestCaseUpdate(BaseModel):
    case_id: str | None = Field(default=None, max_length=64)
    project_code: str | None = Field(default=None, max_length=20)
    client: str | None = Field(default=None, max_length=10)
    page_code: str | None = Field(default=None, max_length=20)
    module_code: str | None = Field(default=None, max_length=20)
    case_type: str | None = Field(default=None, max_length=10)
    source: str | None = Field(default=None, max_length=10)
    name: str | None = Field(default=None, max_length=255)
    product_line: str | None = Field(default=None, max_length=120)
    module: str | None = Field(default=None, max_length=120)
    chain_stage: str | None = Field(default=None, max_length=120)
    sut_service: str | None = Field(default=None, max_length=120)
    related_services: list[str] | None = None
    priority: str | None = Field(default=None, max_length=20)
    test_type: str | None = Field(default=None, max_length=50)
    scenario_types: list[str] | None = None
    trigger_entry: str | None = Field(default=None, max_length=40)
    fault_injection_type: str | None = Field(default=None, max_length=80)
    fault_injection_target: str | None = Field(default=None, max_length=255)
    fault_injection_params: str | None = None
    setup_sql: str | None = None
    precondition_state: str | None = None
    test_steps: list[dict[str, Any]] | None = None
    test_steps_text: str | None = None
    concurrency_model: str | None = Field(default=None, max_length=120)
    retry_policy: str | None = None
    expected_result: str | None = None
    assert_sql: str | None = None
    event_assertion: str | None = None
    metric_assertion: str | None = None
    cleanup_script: str | None = None
    artifact_links: list[str] | None = None
    notes: str | None = None
    tags: list[str] | None = None
    markers: list[str] | None = None
    creator: str | None = Field(default=None, max_length=120)
    assignee: str | None = Field(default=None, max_length=120)
    pytest_path: str | None = Field(default=None, max_length=500)
    status: str | None = Field(default=None, max_length=20)
    automation_status: str | None = Field(default=None, max_length=20)
    source_ref: str | None = Field(default=None, max_length=255)
    script_code: str | None = None
    data_config: TestCaseDataConfig | None = None


class TestCaseScriptUpdate(BaseModel):
    script_code: str
    changed_by: str = Field(default="admin", max_length=120)


class BatchIdsPayload(BaseModel):
    ids: list[int] = Field(default_factory=list)
    case_ids: list[str] = Field(default_factory=list)


class BatchTagsUpdatePayload(BaseModel):
    ids: list[int] = Field(default_factory=list)
    case_ids: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    mode: str = Field(default="replace", pattern="^(replace|append)$")


class BatchStatusUpdatePayload(BaseModel):
    ids: list[int] = Field(default_factory=list)
    case_ids: list[str] = Field(default_factory=list)
    status: str = Field(..., max_length=20)


class BatchExportPayload(BaseModel):
    ids: list[int] = Field(default_factory=list)
    case_ids: list[str] = Field(default_factory=list)
    format: str = Field(default="json", pattern="^(json|csv|xlsx)$")


class TreeNodeCreatePayload(BaseModel):
    project_code: str = Field(default="atp", max_length=20)
    product_line: str = Field(..., min_length=1, max_length=120)
    module: str = Field(default="", max_length=120)


class TreeNodeUpdatePayload(BaseModel):
    project_code: str = Field(default="atp", max_length=20)
    product_line: str = Field(..., min_length=1, max_length=120)
    module: str = Field(default="", max_length=120)
    new_product_line: str = Field(..., min_length=1, max_length=120)
    new_module: str = Field(default="", max_length=120)


class TreeNodeDeletePayload(BaseModel):
    project_code: str = Field(default="atp", max_length=20)
    product_line: str = Field(..., min_length=1, max_length=120)
    module: str = Field(default="", max_length=120)
    cascade_cases: bool = Field(default=False)
