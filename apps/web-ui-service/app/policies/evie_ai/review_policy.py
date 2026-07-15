"""Pure review state-transition policy."""

from __future__ import annotations

from app.constants.evie_ai import TestAssetReviewAction, TestAssetReviewStatus
from app.errors.evie_ai import EvieAiDomainError, EvieAiErrorCode, EvieAiErrorStage

_REVIEW_TRANSITIONS = {
    (TestAssetReviewStatus.PENDING, TestAssetReviewAction.APPROVE): (
        TestAssetReviewStatus.APPROVED
    ),
    (TestAssetReviewStatus.PENDING, TestAssetReviewAction.REJECT): (
        TestAssetReviewStatus.REJECTED
    ),
    (TestAssetReviewStatus.APPROVED, TestAssetReviewAction.REOPEN): (
        TestAssetReviewStatus.PENDING
    ),
    (TestAssetReviewStatus.REJECTED, TestAssetReviewAction.REOPEN): (
        TestAssetReviewStatus.PENDING
    ),
}
_ACTIONS_REQUIRING_REASON = {
    TestAssetReviewAction.REJECT,
    TestAssetReviewAction.REOPEN,
}


def resolve_review_transition(
    current_status: TestAssetReviewStatus,
    action: TestAssetReviewAction,
    *,
    reason: str | None,
) -> TestAssetReviewStatus:
    target_status = _REVIEW_TRANSITIONS.get((current_status, action))
    reason_missing = action in _ACTIONS_REQUIRING_REASON and not str(
        reason or ""
    ).strip()
    if target_status is None or reason_missing:
        raise EvieAiDomainError(
            EvieAiErrorCode.INVALID_REVIEW_TRANSITION,
            stage=EvieAiErrorStage.REVIEW,
            message="The requested review transition is not allowed.",
            retryable=False,
        )
    return target_status
