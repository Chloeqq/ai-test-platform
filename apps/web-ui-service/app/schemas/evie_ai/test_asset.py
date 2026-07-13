"""EvieAi 自然语言 TestAsset 契约。"""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.constants.evie_ai import TestAssetConversionStatus, TestAssetReviewStatus
from app.core.id_gen import (
    REQUIREMENT_ID_PATTERN,
    REQUIREMENT_VERSION_ID_PATTERN,
    TEST_ASSET_ID_PATTERN,
    TEST_ASSET_SOURCE_ID_PATTERN,
    TEST_ASSET_VERSION_ID_PATTERN,
)
from app.schemas.evie_ai.base import (
    SHA256_HEX_PATTERN,
    EvieAiReadSchema,
    EvieAiSchema,
)


class TestAssetCreate(EvieAiSchema):
    """创建资产聚合身份所需输入；状态和公共 ID 由后端决定。"""

    project_code: str = Field(min_length=1, max_length=20)
    asset_code: str = Field(min_length=1, max_length=120)


class TestAssetVersionCreate(EvieAiSchema):
    """自然语言资产正文；允许不完整内容进入资产中心。"""

    title: str = Field(default="", max_length=255)
    precondition: str | None = None
    natural_steps: list[str] = Field(default_factory=list)
    expected_result: str = ""
    priority: str | None = Field(default=None, max_length=20)
    tags: list[str] = Field(default_factory=list)


class TestAssetSourceCreate(EvieAiSchema):
    """Phase 0 Requirement 来源引用；不接收内部数据库 PK。"""

    requirement_id: str = Field(pattern=REQUIREMENT_ID_PATTERN)
    requirement_version_id: str = Field(pattern=REQUIREMENT_VERSION_ID_PATTERN)
    source_identity_hash: str = Field(pattern=SHA256_HEX_PATTERN)


class TestAssetRead(EvieAiReadSchema):
    test_asset_id: str = Field(pattern=TEST_ASSET_ID_PATTERN)
    project_code: str
    asset_code: str
    review_status: TestAssetReviewStatus
    conversion_status: TestAssetConversionStatus
    current_version_id: str | None = Field(
        default=None,
        pattern=TEST_ASSET_VERSION_ID_PATTERN,
    )
    row_version: int = Field(ge=1)
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None
    created_by: str
    updated_by: str


class TestAssetVersionRead(EvieAiReadSchema):
    test_asset_version_id: str = Field(pattern=TEST_ASSET_VERSION_ID_PATTERN)
    test_asset_id: str = Field(pattern=TEST_ASSET_ID_PATTERN)
    version_no: int = Field(ge=1)
    title: str
    precondition: str | None
    natural_steps: list[str]
    expected_result: str
    priority: str | None
    tags: list[str]
    content_checksum: str = Field(pattern=SHA256_HEX_PATTERN)
    created_at: datetime
    created_by: str


class TestAssetSourceRead(EvieAiReadSchema):
    test_asset_source_id: str = Field(pattern=TEST_ASSET_SOURCE_ID_PATTERN)
    test_asset_id: str = Field(pattern=TEST_ASSET_ID_PATTERN)
    requirement_id: str = Field(pattern=REQUIREMENT_ID_PATTERN)
    requirement_version_id: str = Field(pattern=REQUIREMENT_VERSION_ID_PATTERN)
    source_identity_hash: str = Field(pattern=SHA256_HEX_PATTERN)
    created_at: datetime
    created_by: str
