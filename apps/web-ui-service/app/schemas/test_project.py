from pydantic import BaseModel, Field


class TestProjectCreate(BaseModel):
    project_code: str = Field(..., min_length=2, max_length=32)
    project_name: str = Field(..., min_length=1, max_length=100)
    description: str = Field(default="", max_length=2000)
    created_by: str = Field(default="admin", max_length=60)


class TestProjectUpdate(BaseModel):
    project_name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    status: str | None = Field(default=None, min_length=1, max_length=20)
