"""EvieAi Requirement 自然语言领域契约。"""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.constants.evie_ai import RequirementStatus, RequirementVersionStatus
from app.core.id_gen import REQUIREMENT_ID_PATTERN, REQUIREMENT_VERSION_ID_PATTERN
from app.schemas.evie_ai.base import (
    SHA256_HEX_PATTERN,
    EvieAiReadSchema,
    EvieAiSchema,
)


class RequirementCreate(EvieAiSchema):
    """创建 Requirement 聚合所需的调用方输入。"""

    project_code: str = Field(min_length=1, max_length=20)
    requirement_code: str = Field(min_length=1, max_length=120)
    external_requirement_key: str | None = Field(default=None, max_length=255)


class RequirementVersionCreate(EvieAiSchema):
    """新 RequirementVersion 的正文输入；版本身份和状态由编排层决定。"""

    title: str = Field(max_length=255)
    content: str


class RequirementRead(EvieAiReadSchema):
    requirement_id: str = Field(pattern=REQUIREMENT_ID_PATTERN)
    project_code: str
    requirement_code: str
    external_requirement_key: str | None
    status: RequirementStatus
    current_version_id: str | None = Field(
        default=None,
        pattern=REQUIREMENT_VERSION_ID_PATTERN,
    )
    row_version: int = Field(ge=1)
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None
    created_by: str
    updated_by: str


class RequirementVersionRead(EvieAiReadSchema):
    requirement_version_id: str = Field(pattern=REQUIREMENT_VERSION_ID_PATTERN)
    requirement_id: str = Field(pattern=REQUIREMENT_ID_PATTERN)
    version_no: int = Field(ge=1)
    title: str
    content: str
    content_checksum: str = Field(pattern=SHA256_HEX_PATTERN)
    version_status: RequirementVersionStatus
    created_at: datetime
    created_by: str
