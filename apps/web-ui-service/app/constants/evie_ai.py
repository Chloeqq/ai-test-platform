"""EvieAi 领域协议常量。"""

from __future__ import annotations

from enum import StrEnum


class _StringEnum(StrEnum):
    @classmethod
    def values(cls) -> tuple[str, ...]:
        return tuple(member.value for member in cls)


class RequirementStatus(_StringEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    CLOSED = "closed"
    ARCHIVED = "archived"


class RequirementVersionStatus(_StringEnum):
    DRAFT = "draft"
    EFFECTIVE = "effective"
    SUPERSEDED = "superseded"
    REMOVED = "removed"


class TestAssetReviewStatus(_StringEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class TestAssetConversionStatus(_StringEnum):
    NOT_STARTED = "not_started"
    PROCESSING = "processing"
    BLOCKED = "blocked"
    SUCCEEDED = "succeeded"
    STALE = "stale"


class TestAssetSourceType(_StringEnum):
    REQUIREMENT = "requirement"
    MANUAL = "manual"


class TestAssetOperationType(_StringEnum):
    CREATE_ASSET = "create_asset"
    CREATE_VERSION = "create_version"
    RESTORE_HISTORICAL_VERSION = "restore_historical_version"
    REVIEW_ASSET = "review_asset"
    DELETE_ASSET = "delete_asset"
    RESTORE_ASSET = "restore_asset"


class TestAssetReviewAction(_StringEnum):
    APPROVE = "approve"
    REJECT = "reject"
    REOPEN = "reopen"


class TestAssetAuditEventType(_StringEnum):
    ASSET_CREATED = "asset_created"
    EXACT_DUPLICATE_REUSED = "exact_duplicate_reused"
    SOURCE_ADDED = "source_added"
    VERSION_CREATED = "version_created"
    VERSION_RESTORED = "version_restored"
    REVIEW_CHANGED = "review_changed"
    ASSET_DELETED = "asset_deleted"
    ASSET_RESTORED = "asset_restored"
