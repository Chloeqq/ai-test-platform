"""EvieAi Manual/Requirement 来源的强类型契约。"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field

from app.constants.evie_ai import TestAssetSourceType
from app.core.id_gen import (
    REQUIREMENT_ID_PATTERN,
    REQUIREMENT_VERSION_ID_PATTERN,
    TEST_ASSET_ID_PATTERN,
    TEST_ASSET_SOURCE_ID_PATTERN,
)
from app.schemas.evie_ai.base import (
    SHA256_HEX_PATTERN,
    EvieAiReadSchema,
    EvieAiSchema,
)


class ManualTestAssetSourceCreate(EvieAiSchema):
    type: Literal[TestAssetSourceType.MANUAL] = TestAssetSourceType.MANUAL


class RequirementTestAssetSourceCreate(EvieAiSchema):
    type: Literal[TestAssetSourceType.REQUIREMENT] = TestAssetSourceType.REQUIREMENT
    requirement_id: str = Field(pattern=REQUIREMENT_ID_PATTERN)
    requirement_version_id: str = Field(pattern=REQUIREMENT_VERSION_ID_PATTERN)


TestAssetSourceCreate = Annotated[
    ManualTestAssetSourceCreate | RequirementTestAssetSourceCreate,
    Field(discriminator="type"),
]


class TestAssetSourceReadBase(EvieAiReadSchema):
    test_asset_source_id: str = Field(pattern=TEST_ASSET_SOURCE_ID_PATTERN)
    test_asset_id: str = Field(pattern=TEST_ASSET_ID_PATTERN)
    source_identity_hash: str = Field(pattern=SHA256_HEX_PATTERN)
    created_at: datetime
    created_by: str


class ManualTestAssetSourceRead(TestAssetSourceReadBase):
    source_type: Literal[TestAssetSourceType.MANUAL]


class RequirementTestAssetSourceRead(TestAssetSourceReadBase):
    source_type: Literal[TestAssetSourceType.REQUIREMENT]
    requirement_id: str = Field(pattern=REQUIREMENT_ID_PATTERN)
    requirement_version_id: str = Field(pattern=REQUIREMENT_VERSION_ID_PATTERN)


TestAssetSourceRead = Annotated[
    ManualTestAssetSourceRead | RequirementTestAssetSourceRead,
    Field(discriminator="source_type"),
]
