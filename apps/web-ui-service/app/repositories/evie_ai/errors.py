"""EvieAi Phase 0 持久化领域错误。"""

from __future__ import annotations


class EvieAiPersistenceError(RuntimeError):
    """带稳定错误元数据的持久化领域错误。"""

    domain = "evie_ai"
    stage = "persistence"
    retryable = False

    def __init__(
        self,
        *,
        error_code: str,
        message: str,
        entity_id: str | None = None,
        trace_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.entity_id = entity_id
        self.trace_id = trace_id


class CurrentVersionOwnershipError(EvieAiPersistenceError):
    """current_version 不属于目标聚合。"""

    def __init__(
        self,
        *,
        aggregate_type: str,
        aggregate_id: str,
        trace_id: str | None = None,
    ) -> None:
        super().__init__(
            error_code="EVIE_AI_CURRENT_VERSION_OWNERSHIP_MISMATCH",
            message=f"current version does not belong to {aggregate_type}",
            entity_id=aggregate_id,
            trace_id=trace_id,
        )


class SourceOwnershipError(EvieAiPersistenceError):
    """来源引用的 RequirementVersion 不属于 Requirement。"""

    def __init__(
        self,
        *,
        source_id: str,
        trace_id: str | None = None,
    ) -> None:
        super().__init__(
            error_code="EVIE_AI_SOURCE_OWNERSHIP_MISMATCH",
            message="source requirement version does not belong to requirement",
            entity_id=source_id,
            trace_id=trace_id,
        )


class OptimisticConcurrencyError(EvieAiPersistenceError):
    """聚合 row_version 已被其他事务推进。"""

    retryable = True

    def __init__(
        self,
        *,
        aggregate_type: str,
        aggregate_id: str,
        trace_id: str | None = None,
    ) -> None:
        super().__init__(
            error_code="EVIE_AI_ROW_VERSION_CONFLICT",
            message=f"{aggregate_type} row version conflict",
            entity_id=aggregate_id,
            trace_id=trace_id,
        )
