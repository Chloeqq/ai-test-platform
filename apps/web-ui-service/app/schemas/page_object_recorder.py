from __future__ import annotations

from pydantic import BaseModel, Field


class RecorderSessionCreate(BaseModel):
    project_code: str = Field(default="atp", min_length=2, max_length=20)
    client: str = Field(default="web", min_length=2, max_length=10)
    page_code: str = Field(..., min_length=2, max_length=40)
    page_name: str = Field(..., min_length=1, max_length=120)
    url: str = Field(..., min_length=1, max_length=512)
    started_by: str = Field(default="admin", max_length=60)


class RecorderSessionStopPayload(BaseModel):
    ingest_to_page_object: bool = True
    cascade_elements: bool = False
    verify_locators: bool = False
    verify_timeout_ms: int = Field(default=4000, ge=500, le=20000)
    changed_by: str = Field(default="admin", max_length=60)


class RecorderSessionHeartbeatPayload(BaseModel):
    heartbeat_by: str = Field(default="admin", max_length=60)


class RecorderSessionCreateCasePayload(BaseModel):
    name: str = Field(default="", max_length=255)
    product_line: str = Field(default="", max_length=120)
    module: str = Field(default="", max_length=120)
    priority: str = Field(default="P1", max_length=20)
    creator: str = Field(default="admin", max_length=120)
    assignee: str = Field(default="", max_length=120)
    tags: list[str] = Field(default_factory=list)
    status: str = Field(default="active", max_length=20)
    link_page_refs: bool = True
