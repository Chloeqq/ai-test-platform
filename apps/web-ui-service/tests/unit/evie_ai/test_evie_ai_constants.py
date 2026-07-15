from __future__ import annotations

from app.constants.evie_ai import (
    TestAssetAuditEventType as AuditEventType,
)
from app.constants.evie_ai import (
    TestAssetConversionStatus as ConversionStatus,
)
from app.constants.evie_ai import (
    TestAssetOperationType as OperationType,
)
from app.constants.evie_ai import (
    TestAssetReviewAction as ReviewAction,
)
from app.constants.evie_ai import (
    TestAssetReviewStatus as ReviewStatus,
)
from app.constants.evie_ai import (
    TestAssetSourceType as SourceType,
)


def test_phase1_protocol_enums_have_only_approved_values() -> None:
    assert SourceType.values() == ("requirement", "manual")
    assert OperationType.values() == (
        "create_asset",
        "create_version",
        "restore_historical_version",
        "review_asset",
        "delete_asset",
        "restore_asset",
    )
    assert ReviewStatus.values() == ("pending", "approved", "rejected")
    assert ReviewAction.values() == ("approve", "reject", "reopen")
    assert AuditEventType.values() == (
        "asset_created",
        "exact_duplicate_reused",
        "source_added",
        "version_created",
        "version_restored",
        "review_changed",
        "asset_deleted",
        "asset_restored",
    )


def test_conversion_status_does_not_include_failed() -> None:
    assert ConversionStatus.values() == (
        "not_started",
        "processing",
        "blocked",
        "succeeded",
        "stale",
    )
    assert "failed" not in ConversionStatus.values()
