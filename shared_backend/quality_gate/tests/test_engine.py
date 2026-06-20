"""测试 engine.py — RuleEngine 执行流程和决策逻辑。"""

from __future__ import annotations

from shared_backend.quality_gate import (
    Decision,
    GateContext,
    Rule,
    RuleCategory,
    RuleEngine,
    RuleResult,
    Severity,
)
from shared_backend.quality_gate.registry import RuleRegistry, get_registry


class _StubRule(Rule):
    def __init__(
        self,
        rule_id: str = "STUB",
        rule_name: str = "Stub",
        category: RuleCategory = RuleCategory.DATA,
        severity: Severity = Severity.ERROR,
        passed: bool = True,
    ) -> None:
        self.rule_id = rule_id
        self.rule_name = rule_name
        self.category = category
        self.severity = severity
        self._passed = passed

    def validate(self, context: GateContext) -> RuleResult:
        return RuleResult(
            rule_id=self.rule_id,
            rule_name=self.rule_name,
            severity=self.severity,
            category=self.category,
            passed=self._passed,
            message="" if self._passed else "test failure",
        )


class _ExceptionRule(Rule):
    rule_id = "EXC"
    rule_name = "Exception"
    category = RuleCategory.DATA
    severity = Severity.ERROR

    def validate(self, context: GateContext) -> RuleResult:
        raise RuntimeError("simulated rule failure")


class TestRuleEngineExecuteAll:
    def test_execute_all_with_local_registry(self) -> None:
        """使用临时 registry 验证执行流程。"""
        engine = RuleEngine()
        context = GateContext()

        registry = RuleRegistry()
        registry.register(_StubRule(rule_id="R1", passed=True))
        registry.register(_StubRule(rule_id="R2", passed=True))

        results = engine.execute_all(context, registry=registry)
        assert len(results) == 2
        assert all(r.passed for r in results)

    def test_execute_mixed_results(self) -> None:
        engine = RuleEngine()
        registry = RuleRegistry()
        registry.register(_StubRule(rule_id="R1", passed=True))
        registry.register(_StubRule(rule_id="R2", passed=False, severity=Severity.ERROR))

        results = engine.execute_all(GateContext(), registry=registry)
        assert len(results) == 2
        assert sum(1 for r in results if r.passed) == 1

    def test_execute_exception_caught(self) -> None:
        engine = RuleEngine()
        registry = RuleRegistry()
        registry.register(_ExceptionRule())

        results = engine.execute_all(GateContext(), registry=registry)
        assert len(results) == 1
        assert results[0].passed is False
        assert "simulated rule failure" in results[0].message

    def test_execute_from_global_registry(self) -> None:
        """通过 import app.services.quality_gate 触发注册后，全局 registry 应有规则。"""
        from app.services.quality_gate import rules  # noqa: F401
        engine = RuleEngine()
        results = engine.execute_all(GateContext())
        assert len(results) > 0
        assert all(isinstance(r, RuleResult) for r in results)


class TestRuleEngineAggregate:
    def test_all_pass(self) -> None:
        engine = RuleEngine()
        results = [
            RuleResult(rule_id="R1", passed=True, severity=Severity.INFO),
            RuleResult(rule_id="R2", passed=True, severity=Severity.WARNING),
        ]
        report = engine.aggregate(results)
        assert report.decision == Decision.PASS

    def test_fatal_causes_reject(self) -> None:
        engine = RuleEngine()
        results = [
            RuleResult(rule_id="R1", passed=True),
            RuleResult(rule_id="R2", passed=False, severity=Severity.FATAL),
        ]
        report = engine.aggregate(results)
        assert report.decision == Decision.REJECT

    def test_error_causes_review(self) -> None:
        engine = RuleEngine()
        results = [
            RuleResult(rule_id="R1", passed=False, severity=Severity.ERROR),
        ]
        report = engine.aggregate(results)
        assert report.decision == Decision.REVIEW

    def test_info_only_causes_repair(self) -> None:
        engine = RuleEngine()
        results = [
            RuleResult(rule_id="R1", passed=False, severity=Severity.INFO),
        ]
        report = engine.aggregate(results)
        assert report.decision == Decision.REPAIR

    def test_warning_causes_review(self) -> None:
        engine = RuleEngine()
        results = [
            RuleResult(rule_id="R1", passed=False, severity=Severity.WARNING),
        ]
        report = engine.aggregate(results)
        assert report.decision == Decision.REVIEW

    def test_empty_results(self) -> None:
        engine = RuleEngine()
        report = engine.aggregate([])
        assert report.decision == Decision.PASS

    def test_fatal_priority_over_error(self) -> None:
        engine = RuleEngine()
        results = [
            RuleResult(rule_id="R1", passed=False, severity=Severity.ERROR),
            RuleResult(rule_id="R2", passed=False, severity=Severity.FATAL),
        ]
        report = engine.aggregate(results)
        assert report.decision == Decision.REJECT

    def test_summary_format(self) -> None:
        engine = RuleEngine()
        results = [
            RuleResult(rule_id="R1", passed=False, severity=Severity.ERROR),
            RuleResult(rule_id="R2", passed=False, severity=Severity.WARNING),
        ]
        report = engine.aggregate(results)
        assert "REVIEW" in report.summary
        assert "ERROR" in report.summary
        assert "WARNING" in report.summary
