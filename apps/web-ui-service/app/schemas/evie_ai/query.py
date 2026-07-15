"""EvieAi 资产列表、详情和分页查询契约。"""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.constants.evie_ai import (
    TestAssetConversionStatus,
    TestAssetReviewStatus,
    TestAssetSourceType,
)
from app.core.id_gen import REQUIREMENT_ID_PATTERN
from app.schemas.evie_ai.base import EvieAiReadSchema, EvieAiSchema
from app.schemas.evie_ai.operations import TestAssetReviewRead
from app.schemas.evie_ai.source import TestAssetSourceRead
from app.schemas.evie_ai.test_asset import (
    TestAssetRead,
    TestAssetVersionRead,
)


class TestAssetListQuery(EvieAiSchema):
    project_code: str = Field(min_length=1, max_length=20)
    review_status: TestAssetReviewStatus | None = None
    conversion_status: TestAssetConversionStatus | None = None
    priority: str | None = Field(default=None, max_length=20)
    tags: list[str] = Field(default_factory=list)
    requirement_id: str | None = Field(default=None, pattern=REQUIREMENT_ID_PATTERN)
    source_type: TestAssetSourceType | None = None
    created_by: str | None = None
    created_from: datetime | None = None
    created_to: datetime | None = None
    keyword: str | None = None
    include_deleted: bool = False
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class TestAssetListItem(EvieAiReadSchema):
    asset: TestAssetRead
    current_version: TestAssetVersionRead
    source_types: list[TestAssetSourceType] = Field(default_factory=list)
    latest_review: TestAssetReviewRead | None = None


class TestAssetListResponse(EvieAiReadSchema):
    items: list[TestAssetListItem]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    total: int = Field(ge=0)


class TestAssetDetailResponse(EvieAiReadSchema):
    asset: TestAssetRead
    current_version: TestAssetVersionRead
    sources: list[TestAssetSourceRead]
    latest_review: TestAssetReviewRead | None = None


class TestAssetVersionHistoryResponse(EvieAiReadSchema):
    items: list[TestAssetVersionRead]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    total: int = Field(ge=0)


class TestAssetReviewHistoryResponse(EvieAiReadSchema):
    items: list[TestAssetReviewRead]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    total: int = Field(ge=0)
