"""Case 生命周期状态机。

定义 CaseStatus 枚举及其合法/非法转换。
"""

from __future__ import annotations

from enum import Enum


class CaseStatus(str, Enum):
    """用例生命周期状态。"""
    GENERATED = "generated"
    QUALITY_CHECKING = "quality_checking"
    REPAIRING = "repairing"               # Gate 返回 REPAIR，自动修复中
    REVIEW_REQUIRED = "review_required"   # Gate 返回 REVIEW，等待人工审核
    REJECTED = "rejected"                 # Gate 返回 REJECT，驳回但保留记录
    APPROVED = "approved"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


# 合法转换映射：from_status → set of valid to_statuses
_ALLOWED_TRANSITIONS: dict[CaseStatus, set[CaseStatus]] = {
    CaseStatus.GENERATED: {
        CaseStatus.QUALITY_CHECKING,
    },
    CaseStatus.QUALITY_CHECKING: {
        CaseStatus.APPROVED,          # Gate PASS
        CaseStatus.REPAIRING,         # Gate REPAIR
        CaseStatus.REVIEW_REQUIRED,   # Gate REVIEW
        CaseStatus.REJECTED,          # Gate REJECT
    },
    CaseStatus.REPAIRING: {
        CaseStatus.QUALITY_CHECKING,  # 修复完成，重新进入 Gate
    },
    CaseStatus.REVIEW_REQUIRED: {
        CaseStatus.APPROVED,          # 人工审核通过
        CaseStatus.REJECTED,          # 人工驳回
    },
    CaseStatus.REJECTED: {
        CaseStatus.ARCHIVED,          # 归档
    },
    CaseStatus.APPROVED: {
        CaseStatus.ACTIVE,            # 激活
        CaseStatus.REJECTED,          # 人工驳回
    },
    CaseStatus.ACTIVE: {
        CaseStatus.DEPRECATED,
    },
    CaseStatus.DEPRECATED: {
        CaseStatus.ARCHIVED,
    },
    CaseStatus.ARCHIVED: set(),
}

# 明确禁止的转换
_FORBIDDEN_TRANSITIONS: set[tuple[CaseStatus, CaseStatus]] = {
    (CaseStatus.GENERATED, CaseStatus.ACTIVE),
    (CaseStatus.GENERATED, CaseStatus.APPROVED),
    (CaseStatus.GENERATED, CaseStatus.REVIEW_REQUIRED),
    (CaseStatus.GENERATED, CaseStatus.REJECTED),
    (CaseStatus.REVIEW_REQUIRED, CaseStatus.ACTIVE),
    (CaseStatus.QUALITY_CHECKING, CaseStatus.ACTIVE),
    (CaseStatus.REPAIRING, CaseStatus.ACTIVE),
    (CaseStatus.REJECTED, CaseStatus.ACTIVE),
}


def can_transition(
    from_status: CaseStatus,
    to_status: CaseStatus,
) -> bool:
    """检查状态转换是否合法。"""
    allowed = _ALLOWED_TRANSITIONS.get(from_status, set())
    return to_status in allowed


def is_forbidden(
    from_status: CaseStatus,
    to_status: CaseStatus,
) -> bool:
    """检查状态转换是否被明确禁止。"""
    return (from_status, to_status) in _FORBIDDEN_TRANSITIONS


def transition(
    from_status: CaseStatus,
    to_status: CaseStatus,
) -> CaseStatus:
    """执行状态转换。合法则返回新状态，非法则抛出 ValueError。"""
    if is_forbidden(from_status, to_status):
        raise ValueError(
            f"禁止的状态转换: {from_status.value} → {to_status.value}"
        )
    if not can_transition(from_status, to_status):
        raise ValueError(
            f"不支持的状态转换: {from_status.value} → {to_status.value}"
        )
    return to_status


def allowed_transitions(from_status: CaseStatus) -> set[CaseStatus]:
    """返回从指定状态可转换到的所有状态。"""
    return _ALLOWED_TRANSITIONS.get(from_status, set())
