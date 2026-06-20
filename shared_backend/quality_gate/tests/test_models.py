"""测试 models.py — Severity, Decision, RuleCategory 枚举及所有数据类。"""

from __future__ import annotations

import pytest

from shared_backend.quality_gate.models import (
    CaseScore,
    Decision,
    GateContext,
    RuleCategory,
    RuleConfig,
    RuleResult,
    Severity,
    ValidationReport,
)


class TestSeverity:
    def test_severity_values(self) -> None:
        assert Severity.FATAL.value == "fatal"
        assert Severity.ERROR.value == "error"
        assert Severity.WARNING.value == "warning"
        assert Severity.INFO.value == "info"

    def test_is_blocking_fatal(self) -> None:
        assert Severity.FATAL.is_blocking is True

    def test_is_blocking_error(self) -> None:
        assert Severity.ERROR.is_blocking is True

    def test_is_blocking_warning(self) -> None:
        assert Severity.WARNING.is_blocking is False

    def test_is_blocking_info(self) -> None:
        assert Severity.INFO.is_blocking is False

    def test_severity_from_string(self) -> None:
        assert Severity("fatal") == Severity.FATAL
        assert Severity("warning") == Severity.WARNING


class TestDecision:
    def test_decision_values(self) -> None:
        assert Decision.PASS.value == "pass"
        assert Decision.REPAIR.value == "repair"
        assert Decision.REVIEW.value == "review"
        assert Decision.REJECT.value == "reject"

    def test_all_four_decisions(self) -> None:
        assert len(Decision) == 4


class TestRuleCategory:
    def test_all_categories_exist(self) -> None:
        categories = {c.value for c in RuleCategory}
        assert categories == {
            "data", "assertion", "semantic", "step",
            "dependency", "page_object", "requirement", "ai_generation",
        }


class TestRuleResult:
    def test_default_values(self) -> None:
        r = RuleResult()
        assert r.rule_id == ""
        assert r.severity == Severity.INFO
        assert r.category == RuleCategory.DATA
        assert r.passed is True
        assert r.evidence == {}

    def test_with_values(self) -> None:
        r = RuleResult(
            rule_id="RULE_001",
            rule_name="Test",
            severity=Severity.ERROR,
            message="found issue",
            suggestion="fix it",
            category=RuleCategory.SEMANTIC,
            evidence={"key": "val"},
            passed=False,
        )
        assert r.rule_id == "RULE_001"
        assert r.message == "found issue"
        assert r.passed is False

    def test_evidence_default_factory_isolation(self) -> None:
        r1 = RuleResult(evidence={"a": 1})
        r2 = RuleResult(evidence={"b": 2})
        r1.evidence["c"] = 3
        assert "c" not in r2.evidence


class TestCaseScore:
    def test_default_scores(self) -> None:
        s = CaseScore()
        assert s.total_score == 100
        assert s.data_score == 30
        assert s.assertion_score == 30
        assert s.semantic_score == 20
        assert s.dependency_score == 10
        assert s.page_object_score == 10

    def test_grade_a(self) -> None:
        assert CaseScore(total_score=95).grade == "A"
        assert CaseScore(total_score=100).grade == "A"

    def test_grade_b(self) -> None:
        assert CaseScore(total_score=80).grade == "B"
        assert CaseScore(total_score=94).grade == "B"

    def test_grade_c(self) -> None:
        assert CaseScore(total_score=0).grade == "C"
        assert CaseScore(total_score=79).grade == "C"


class TestGateContext:
    def test_default_values(self) -> None:
        ctx = GateContext()
        assert ctx.case_yaml == {}
        assert ctx.requirement == {}
        assert ctx.intent == {}
        assert ctx.page_object == {}
        assert ctx.seed_data_provider is None
        assert ctx.project == ""

    def test_with_values(self) -> None:
        ctx = GateContext(project="mall", case_yaml={"id": "test-001"})
        assert ctx.project == "mall"
        assert ctx.case_yaml["id"] == "test-001"

    def test_seed_data_provider_is_none_by_default(self) -> None:
        ctx = GateContext()
        assert ctx.seed_data_provider is None

    def test_default_factory_isolation(self) -> None:
        ctx1 = GateContext(case_yaml={"a": 1})
        ctx2 = GateContext(case_yaml={"b": 2})
        ctx1.case_yaml["c"] = 3
        assert "c" not in ctx2.case_yaml


class TestValidationReport:
    def test_default_values(self) -> None:
        r = ValidationReport()
        assert r.case_id == ""
        assert r.results == []
        assert r.decision == Decision.PASS
        assert r.summary == ""

    def test_passed(self) -> None:
        assert ValidationReport(decision=Decision.PASS).passed is True
        assert ValidationReport(decision=Decision.REVIEW).passed is False
        assert ValidationReport(decision=Decision.REJECT).passed is False

    def test_requires_review(self) -> None:
        assert ValidationReport(decision=Decision.PASS).requires_review is False
        assert ValidationReport(decision=Decision.REVIEW).requires_review is True
        assert ValidationReport(decision=Decision.REJECT).requires_review is False

    def test_is_rejected(self) -> None:
        assert ValidationReport(decision=Decision.PASS).is_rejected is False
        assert ValidationReport(decision=Decision.REVIEW).is_rejected is False
        assert ValidationReport(decision=Decision.REJECT).is_rejected is True


class TestRuleConfig:
    def test_default_values(self) -> None:
        c = RuleConfig(rule_id="RULE_X")
        assert c.rule_id == "RULE_X"
        assert c.enabled is True
        assert c.severity is None

    def test_disabled(self) -> None:
        c = RuleConfig(rule_id="X", enabled=False)
        assert c.enabled is False

    def test_severity_override(self) -> None:
        c = RuleConfig(rule_id="X", severity=Severity.WARNING)
        assert c.severity == Severity.WARNING
