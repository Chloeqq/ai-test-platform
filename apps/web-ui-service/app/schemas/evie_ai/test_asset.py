"""EvieAi 自然语言 TestAsset 内容、聚合和版本契约。"""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.constants.evie_ai import TestAssetConversionStatus, TestAssetReviewStatus
from app.core.id_gen import (
    TEST_ASSET_ID_PATTERN,
    TEST_ASSET_VERSION_ID_PATTERN,
)
from app.schemas.evie_ai.base import (
    SHA256_HEX_PATTERN,
    EvieAiReadSchema,
    EvieAiSchema,
)
from app.schemas.evie_ai.source import TestAssetSourceCreate


class TestAssetContent(EvieAiSchema):
    """TestAssetVersion 允许持久化的六个自然语言字段。"""

    title: str = Field(default="", max_length=255)
    precondition: str | None = None
    natural_steps: list[str] = Field(default_factory=list)
    expected_result: str = ""
    priority: str | None = Field(default=None, max_length=20)
    tags: list[str] = Field(default_factory=list)


class TestAssetCreate(EvieAiSchema):
    """统一 Intake 的创建请求；公共 ID、asset_code 和 actor 由后端决定。"""

    project_code: str = Field(min_length=1, max_length=20)
    source: TestAssetSourceCreate
    content: TestAssetContent


class TestAssetVersionCreate(EvieAiSchema):
    """编辑资产并创建不可变新版本。"""

    expected_row_version: int = Field(ge=1)
    content: TestAssetContent
    reason: str | None = None


class TestAssetHistoricalVersionRestore(EvieAiSchema):
    """复制历史版本内容并创建新版本。"""

    expected_row_version: int = Field(ge=1)
    reason: str = Field(min_length=1)


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
