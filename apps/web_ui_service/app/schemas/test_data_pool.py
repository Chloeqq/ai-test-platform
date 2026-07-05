from __future__ import annotations

from pydantic import BaseModel, Field


class TestDataPoolCreate(BaseModel):
    pool_name: str = Field(..., min_length=1, max_length=120)
    description: str = Field(default="", max_length=2000)
    status: str = Field(default="active", max_length=20)
    created_by: str = Field(default="admin", max_length=120)


class TestDataPoolUpdate(BaseModel):
    description: str | None = Field(default=None, max_length=2000)
    status: str | None = Field(default=None, max_length=20)
    updated_by: str = Field(default="admin", max_length=120)


class TestDataPoolItemUpsert(BaseModel):
    item_value: str = Field(default="")
    status: str = Field(default="active", max_length=20)
    note: str = Field(default="", max_length=2000)
    changed_by: str = Field(default="admin", max_length=120)


class TestDataPoolItemDelete(BaseModel):
    note: str = Field(default="", max_length=2000)
    changed_by: str = Field(default="admin", max_length=120)
