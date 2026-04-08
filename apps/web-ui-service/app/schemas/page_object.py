from __future__ import annotations

from pydantic import BaseModel, Field


class PageObjectCreate(BaseModel):
    project_code: str = Field(default="atp", min_length=2, max_length=20)
    client: str = Field(default="web", min_length=2, max_length=10)
    page_code: str = Field(..., min_length=2, max_length=40)
    page_name: str = Field(..., min_length=1, max_length=120)
    page_url: str = Field(default="", max_length=256)
    precondition_state: str = Field(default="", max_length=4000)
    module_id: int = Field(default=0, ge=0)
    health_status: int = Field(default=1, ge=0, le=1)
    description: str = Field(default="", max_length=4000)
    status: str = Field(default="draft", min_length=1, max_length=20)
    created_by: str = Field(default="admin", max_length=60)


class PageObjectUpdate(BaseModel):
    page_name: str | None = Field(default=None, min_length=1, max_length=120)
    page_url: str | None = Field(default=None, max_length=256)
    precondition_state: str | None = Field(default=None, max_length=4000)
    module_id: int | None = Field(default=None, ge=0)
    health_status: int | None = Field(default=None, ge=0, le=1)
    description: str | None = Field(default=None, max_length=4000)
    status: str | None = Field(default=None, min_length=1, max_length=20)


class PageElementCreate(BaseModel):
    element_code: str = Field(..., min_length=2, max_length=80)
    element_name: str = Field(..., min_length=1, max_length=120)
    locator_type: str = Field(..., min_length=1, max_length=30)
    locator_value: str = Field(..., min_length=1, max_length=4000)
    backup_locator: str = Field(default="", max_length=512)
    health_status: int = Field(default=1, ge=0, le=1)
    role: str = Field(default="", max_length=60)
    status: str = Field(default="active", min_length=1, max_length=20)
    is_primary: bool = True
    owner: str = Field(default="", max_length=60)
    changed_by: str = Field(default="admin", max_length=60)
    change_summary: str = Field(default="element created", max_length=2000)


class PageElementUpdate(BaseModel):
    element_name: str | None = Field(default=None, min_length=1, max_length=120)
    locator_type: str | None = Field(default=None, min_length=1, max_length=30)
    locator_value: str | None = Field(default=None, min_length=1, max_length=4000)
    backup_locator: str | None = Field(default=None, max_length=512)
    health_status: int | None = Field(default=None, ge=0, le=1)
    role: str | None = Field(default=None, max_length=60)
    status: str | None = Field(default=None, min_length=1, max_length=20)
    is_primary: bool | None = None
    owner: str | None = Field(default=None, max_length=60)
    changed_by: str = Field(default="admin", max_length=60)
    change_summary: str = Field(default="element updated", max_length=2000)


class PageElementVersionCreate(BaseModel):
    changed_by: str = Field(default="admin", max_length=60)
    change_summary: str = Field(default="snapshot created", max_length=2000)


class PageObjectRefCreate(BaseModel):
    reference_type: str = Field(default="test_case", min_length=1, max_length=30)
    reference_key: str = Field(..., min_length=1, max_length=120)
    source: str = Field(default="manual", min_length=1, max_length=40)
    created_by: str = Field(default="admin", max_length=60)
