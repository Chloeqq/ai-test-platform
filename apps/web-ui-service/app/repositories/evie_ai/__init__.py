"""EvieAi Requirement 与 TestAsset Repository。"""

from app.repositories.evie_ai.content_claim_repository import (
    TestAssetContentClaimRepository,
)
from app.repositories.evie_ai.errors import (
    CurrentVersionOwnershipError,
    EvieAiPersistenceError,
    OptimisticConcurrencyError,
    RepositoryDataIntegrityError,
    SourceOwnershipError,
)
from app.repositories.evie_ai.governance_repository import (
    TestAssetAuditRepository,
    TestAssetReviewRepository,
)
from app.repositories.evie_ai.idempotency_repository import (
    IdempotencyResultSummary,
    IdempotencyScope,
    TestAssetIdempotencyRepository,
)
from app.repositories.evie_ai.query_repository import (
    TestAssetDetailRecord,
    TestAssetListFilters,
    TestAssetListRecord,
    TestAssetQueryRepository,
)
from app.repositories.evie_ai.requirement_repository import RequirementRepository
from app.repositories.evie_ai.source_repository import (
    TestAssetSourceRecord,
    TestAssetSourceRepository,
)
from app.repositories.evie_ai.test_asset_repository import TestAssetRepository
from app.repositories.evie_ai.types import RepositoryPage

__all__ = [
    "RequirementRepository",
    "TestAssetRepository",
    "TestAssetSourceRepository",
    "TestAssetSourceRecord",
    "TestAssetIdempotencyRepository",
    "IdempotencyScope",
    "IdempotencyResultSummary",
    "TestAssetContentClaimRepository",
    "TestAssetReviewRepository",
    "TestAssetAuditRepository",
    "TestAssetQueryRepository",
    "TestAssetListFilters",
    "TestAssetListRecord",
    "TestAssetDetailRecord",
    "RepositoryPage",
    "EvieAiPersistenceError",
    "CurrentVersionOwnershipError",
    "SourceOwnershipError",
    "OptimisticConcurrencyError",
    "RepositoryDataIntegrityError",
]
