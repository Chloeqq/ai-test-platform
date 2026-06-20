"""测试 domain/case_lifecycle.py — CaseStatus 状态机。"""

from __future__ import annotations

import pytest

from shared_backend.quality_gate.domain.case_lifecycle import (
    CaseStatus,
    allowed_transitions,
    can_transition,
    is_forbidden,
    transition,
)


class TestCaseStatus:
    def test_all_statuses(self) -> None:
        values = [s.value for s in CaseStatus]
        assert "generated" in values
        assert "quality_checking" in values
        assert "repairing" in values
        assert "review_required" in values
        assert "rejected" in values
        assert "approved" in values
        assert "active" in values
        assert "deprecated" in values
        assert "archived" in values
        assert len(values) == 9


class TestCanTransition:
    def test_generated_to_quality_checking(self) -> None:
        assert can_transition(CaseStatus.GENERATED, CaseStatus.QUALITY_CHECKING) is True

    def test_generated_to_approved_not_allowed(self) -> None:
        assert can_transition(CaseStatus.GENERATED, CaseStatus.APPROVED) is False

    def test_quality_checking_to_approved(self) -> None:
        assert can_transition(CaseStatus.QUALITY_CHECKING, CaseStatus.APPROVED) is True

    def test_quality_checking_to_review_required(self) -> None:
        assert can_transition(CaseStatus.QUALITY_CHECKING, CaseStatus.REVIEW_REQUIRED) is True

    def test_review_required_to_approved(self) -> None:
        assert can_transition(CaseStatus.REVIEW_REQUIRED, CaseStatus.APPROVED) is True

    def test_review_required_to_active_not_allowed(self) -> None:
        assert can_transition(CaseStatus.REVIEW_REQUIRED, CaseStatus.ACTIVE) is False

    def test_quality_checking_to_repairing(self) -> None:
        assert can_transition(CaseStatus.QUALITY_CHECKING, CaseStatus.REPAIRING) is True

    def test_repairing_to_quality_checking(self) -> None:
        assert can_transition(CaseStatus.REPAIRING, CaseStatus.QUALITY_CHECKING) is True

    def test_quality_checking_to_rejected(self) -> None:
        assert can_transition(CaseStatus.QUALITY_CHECKING, CaseStatus.REJECTED) is True

    def test_rejected_to_archived(self) -> None:
        assert can_transition(CaseStatus.REJECTED, CaseStatus.ARCHIVED) is True

    def test_review_required_to_rejected(self) -> None:
        assert can_transition(CaseStatus.REVIEW_REQUIRED, CaseStatus.REJECTED) is True

    def test_approved_to_active(self) -> None:
        assert can_transition(CaseStatus.APPROVED, CaseStatus.ACTIVE) is True

    def test_active_to_deprecated(self) -> None:
        assert can_transition(CaseStatus.ACTIVE, CaseStatus.DEPRECATED) is True

    def test_deprecated_to_archived(self) -> None:
        assert can_transition(CaseStatus.DEPRECATED, CaseStatus.ARCHIVED) is True

    def test_archived_cannot_transition(self) -> None:
        for status in CaseStatus:
            assert can_transition(CaseStatus.ARCHIVED, status) is False


class TestIsForbidden:
    def test_generated_to_active_forbidden(self) -> None:
        assert is_forbidden(CaseStatus.GENERATED, CaseStatus.ACTIVE) is True

    def test_generated_to_approved_forbidden(self) -> None:
        assert is_forbidden(CaseStatus.GENERATED, CaseStatus.APPROVED) is True

    def test_generated_to_review_required_forbidden(self) -> None:
        assert is_forbidden(CaseStatus.GENERATED, CaseStatus.REVIEW_REQUIRED) is True

    def test_generated_to_rejected_forbidden(self) -> None:
        assert is_forbidden(CaseStatus.GENERATED, CaseStatus.REJECTED) is True

    def test_review_required_to_active_forbidden(self) -> None:
        assert is_forbidden(CaseStatus.REVIEW_REQUIRED, CaseStatus.ACTIVE) is True

    def test_quality_checking_to_active_forbidden(self) -> None:
        assert is_forbidden(CaseStatus.QUALITY_CHECKING, CaseStatus.ACTIVE) is True

    def test_repairing_to_active_forbidden(self) -> None:
        assert is_forbidden(CaseStatus.REPAIRING, CaseStatus.ACTIVE) is True

    def test_rejected_to_active_forbidden(self) -> None:
        assert is_forbidden(CaseStatus.REJECTED, CaseStatus.ACTIVE) is True

    def test_valid_transition_not_forbidden(self) -> None:
        assert is_forbidden(CaseStatus.GENERATED, CaseStatus.QUALITY_CHECKING) is False
        assert is_forbidden(CaseStatus.APPROVED, CaseStatus.ACTIVE) is False


class TestTransition:
    def test_valid_transition_returns_new_status(self) -> None:
        result = transition(CaseStatus.GENERATED, CaseStatus.QUALITY_CHECKING)
        assert result == CaseStatus.QUALITY_CHECKING

    def test_forbidden_transition_raises(self) -> None:
        with pytest.raises(ValueError, match="禁止的状态转换"):
            transition(CaseStatus.GENERATED, CaseStatus.ACTIVE)

    def test_unsupported_transition_raises(self) -> None:
        with pytest.raises(ValueError, match="不支持的状态转换"):
            transition(CaseStatus.ARCHIVED, CaseStatus.ACTIVE)


class TestAllowedTransitions:
    def test_generated_returns_quality_checking_only(self) -> None:
        allowed = allowed_transitions(CaseStatus.GENERATED)
        assert allowed == {CaseStatus.QUALITY_CHECKING}

    def test_quality_checking_returns_four(self) -> None:
        allowed = allowed_transitions(CaseStatus.QUALITY_CHECKING)
        assert allowed == {
            CaseStatus.APPROVED,
            CaseStatus.REPAIRING,
            CaseStatus.REVIEW_REQUIRED,
            CaseStatus.REJECTED,
        }

    def test_active_returns_deprecated(self) -> None:
        allowed = allowed_transitions(CaseStatus.ACTIVE)
        assert allowed == {CaseStatus.DEPRECATED}
