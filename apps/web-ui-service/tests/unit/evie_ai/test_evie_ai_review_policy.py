from __future__ import annotations

import pytest
from app.constants.evie_ai import (
    TestAssetReviewAction as ReviewAction,
)
from app.constants.evie_ai import (
    TestAssetReviewStatus as ReviewStatus,
)
from app.errors.evie_ai import EvieAiDomainError, EvieAiErrorCode
from app.policies.evie_ai.review_policy import resolve_review_transition


@pytest.mark.parametrize(
    ("status", "action", "expected"),
    [
        (
            ReviewStatus.PENDING,
            ReviewAction.APPROVE,
            ReviewStatus.APPROVED,
        ),
        (
            ReviewStatus.PENDING,
            ReviewAction.REJECT,
            ReviewStatus.REJECTED,
        ),
        (
            ReviewStatus.APPROVED,
            ReviewAction.REOPEN,
            ReviewStatus.PENDING,
        ),
        (
            ReviewStatus.REJECTED,
            ReviewAction.REOPEN,
            ReviewStatus.PENDING,
        ),
    ],
)
def test_review_policy_allows_approved_transitions(
    status: ReviewStatus,
    action: ReviewAction,
    expected: ReviewStatus,
) -> None:
    reason = "required context" if action in {
        ReviewAction.REJECT,
        ReviewAction.REOPEN,
    } else None

    assert resolve_review_transition(status, action, reason=reason) is expected


def test_reopen_is_an_action_not_a_review_status() -> None:
    assert "reopen" in ReviewAction.values()
    assert "reopen" not in ReviewStatus.values()


@pytest.mark.parametrize(
    ("status", "action", "reason"),
    [
        (ReviewStatus.APPROVED, ReviewAction.APPROVE, None),
        (ReviewStatus.PENDING, ReviewAction.REOPEN, "why"),
        (ReviewStatus.PENDING, ReviewAction.REJECT, "  "),
        (ReviewStatus.REJECTED, ReviewAction.REOPEN, None),
    ],
)
def test_review_policy_rejects_invalid_or_unexplained_transitions(
    status: ReviewStatus,
    action: ReviewAction,
    reason: str | None,
) -> None:
    with pytest.raises(EvieAiDomainError) as exc_info:
        resolve_review_transition(status, action, reason=reason)

    assert exc_info.value.code is EvieAiErrorCode.INVALID_REVIEW_TRANSITION
