from pydantic import BaseModel, Field


class TestProjectCreate(BaseModel):
    project_code: str = Field(..., min_length=2, max_length=32)
    project_name: str = Field(..., min_length=1, max_length=100)
    description: str = Field(default="", max_length=2000)
    source_roots: list[str] = Field(default_factory=list)
    source_terms: dict[str, str] = Field(default_factory=dict)
    created_by: str = Field(default="admin", max_length=60)


class TestProjectUpdate(BaseModel):
    project_name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    source_roots: list[str] | None = None
    source_terms: dict[str, str] | None = None
    status: str | None = Field(default=None, min_length=1, max_length=20)
