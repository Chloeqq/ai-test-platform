from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


FieldType = Literal["string", "integer", "float", "boolean", "email", "enum"]


class FieldSpec(BaseModel):
    name: str = Field(min_length=1)
    type: FieldType = "string"
    required: bool = True
    unique: bool = False
    nullable: bool = False
    prefix: str = ""
    pattern: str = ""
    options: list[str] = Field(default_factory=list)
    min_value: int | float | None = None
    max_value: int | float | None = None
    min_length: int | None = None
    max_length: int | None = None


class DataRequirement(BaseModel):
    requirement_id: str = Field(min_length=1)
    data_type: str = Field(min_length=1)
    template_key: str = ""
    quantity: int = Field(default=1, ge=1, le=200)
    fields: list[FieldSpec] = Field(default_factory=list)
    relationships: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class DataGenerationRequest(BaseModel):
    request_id: str = Field(min_length=1)
    project: str = "default"
    environment: str = "test"
    cleanup_policy: str = "auto"
    requirements: list[DataRequirement] = Field(default_factory=list)


class GeneratedRecord(BaseModel):
    record_id: str
    requirement_id: str
    data_type: str
    values: dict[str, Any] = Field(default_factory=dict)
    relationships: dict[str, str] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class ValidationResult(BaseModel):
    requirement_id: str
    passed: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class CleanupInstruction(BaseModel):
    requirement_id: str
    record_ids: list[str] = Field(default_factory=list)
    strategy: str = "delete_by_record_id"


class RegistryEntrySummary(BaseModel):
    version: str = "DataGenerationRegistryEntryV1"
    request_id: str
    project: str = "default"
    environment: str = "test"
    status: str = "generated"
    cleanup_status: str = "pending"
    created_at: str
    cleaned_at: str = ""
    total_records: int = 0
    requirement_ids: list[str] = Field(default_factory=list)
    registry_path: str = ""


class DataGenerationResponse(BaseModel):
    version: str = "DataGenerationResponseV1"
    request_id: str
    project: str = "default"
    environment: str = "test"
    generated: dict[str, list[GeneratedRecord]] = Field(default_factory=dict)
    validations: list[ValidationResult] = Field(default_factory=list)
    cleanup_instructions: list[CleanupInstruction] = Field(default_factory=list)
    registry_entry: RegistryEntrySummary | None = None
    template_summary: dict[str, Any] = Field(default_factory=dict)
    generation_confidence: float = Field(default=0.95, ge=0.0, le=1.0)
    warnings: list[str] = Field(default_factory=list)
