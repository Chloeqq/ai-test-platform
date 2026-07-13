"""EvieAi Phase 0 领域状态常量。"""

from __future__ import annotations

from enum import Enum


class _StringEnum(str, Enum):
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
