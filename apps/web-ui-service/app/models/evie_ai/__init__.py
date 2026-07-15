"""EvieAi 自然语言资产持久化模型。"""

from app.models.evie_ai.requirement import Requirement, RequirementVersion
from app.models.evie_ai.test_asset import TestAsset, TestAssetVersion
from app.models.evie_ai.test_asset_coordination import (
    TestAssetContentClaim,
    TestAssetIdempotencyRecord,
)
from app.models.evie_ai.test_asset_governance import (
    TestAssetAuditEvent,
    TestAssetReviewRecord,
)
from app.models.evie_ai.test_asset_source import (
    TestAssetRequirementSource,
    TestAssetSource,
)

__all__ = [
    "Requirement",
    "RequirementVersion",
    "TestAsset",
    "TestAssetVersion",
    "TestAssetSource",
    "TestAssetRequirementSource",
    "TestAssetIdempotencyRecord",
    "TestAssetContentClaim",
    "TestAssetReviewRecord",
    "TestAssetAuditEvent",
]
