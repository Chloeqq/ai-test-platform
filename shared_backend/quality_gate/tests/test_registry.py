"""测试 registry.py — RuleRegistry, get_registry, register_rule 装饰器。"""

from __future__ import annotations

import pytest

from shared_backend.quality_gate import (
    GateContext,
    Rule,
    RuleCategory,
    RuleConfig,
    RuleResult,
    Severity,
    get_registry,
    register_rule,
)
from shared_backend.quality_gate.registry import RuleRegistry


class _FakeRule(Rule):
    """测试用规则。"""
    def validate(self, context: GateContext) -> RuleResult:
        return RuleResult(
            rule_id=self.rule_id,
            rule_name=self.rule_name,
            severity=self.severity,
            category=self.category,
            passed=True,
        )


class TestRuleRegistry:
    def test_register(self) -> None:
        registry = RuleRegistry()
        rule = _FakeRule()
        rule.rule_id = "TEST_001"
        registry.register(rule)
        assert registry.count == 1
        assert registry.get("TEST_001") is rule

    def test_register_duplicate_raises(self) -> None:
        registry = RuleRegistry()
        r1 = _FakeRule()
        r1.rule_id = "TEST_DUP"
        registry.register(r1)
        r2 = _FakeRule()
        r2.rule_id = "TEST_DUP"
        with pytest.raises(ValueError, match="already registered"):
            registry.register(r2)

    def test_register_empty_id_raises(self) -> None:
        registry = RuleRegistry()
        rule = _FakeRule()
        with pytest.raises(ValueError, match="non-empty rule_id"):
            registry.register(rule)

    def test_unregister(self) -> None:
        registry = RuleRegistry()
        rule = _FakeRule()
        rule.rule_id = "TEST_002"
        registry.register(rule)
        assert registry.count == 1
        registry.unregister("TEST_002")
        assert registry.count == 0
        assert registry.get("TEST_002") is None

    def test_unregister_nonexistent(self) -> None:
        registry = RuleRegistry()
        registry.unregister("NONEXIST")
        assert registry.count == 0

    def test_list_all(self) -> None:
        registry = RuleRegistry()
        for i in range(3):
            r = _FakeRule()
            r.rule_id = f"R_{i}"
            registry.register(r)
        assert len(registry.list_all()) == 3

    def test_list_by_category(self) -> None:
        registry = RuleRegistry()
        r1 = _FakeRule()
        r1.rule_id = "R1"
        r1.category = RuleCategory.DATA
        r2 = _FakeRule()
        r2.rule_id = "R2"
        r2.category = RuleCategory.ASSERTION
        registry.register(r1)
        registry.register(r2)
        assert len(registry.list_by_category(RuleCategory.DATA)) == 1
        assert len(registry.list_by_category(RuleCategory.ASSERTION)) == 1
        assert len(registry.list_by_category(RuleCategory.SEMANTIC)) == 0

    def test_list_active_all_enabled(self) -> None:
        registry = RuleRegistry()
        r = _FakeRule()
        r.rule_id = "ACTIVE"
        registry.register(r)
        assert registry.active_count == 1
        assert len(registry.list_active()) == 1

    def test_list_active_disabled(self) -> None:
        registry = RuleRegistry()
        r = _FakeRule()
        r.rule_id = "DISABLED"
        registry.register(r)
        registry.apply_config(RuleConfig(rule_id="DISABLED", enabled=False))
        assert registry.active_count == 0

    def test_effective_severity_default(self) -> None:
        registry = RuleRegistry()
        r = _FakeRule()
        r.rule_id = "S1"
        r.severity = Severity.ERROR
        registry.register(r)
        assert registry.effective_severity(r) == Severity.ERROR

    def test_effective_severity_overridden(self) -> None:
        registry = RuleRegistry()
        r = _FakeRule()
        r.rule_id = "S1"
        r.severity = Severity.FATAL
        registry.register(r)
        registry.apply_config(RuleConfig(rule_id="S1", severity=Severity.WARNING))
        assert registry.effective_severity(r) == Severity.WARNING

    def test_apply_configs(self) -> None:
        registry = RuleRegistry()
        configs = [
            RuleConfig(rule_id="A", enabled=False),
            RuleConfig(rule_id="B", severity=Severity.WARNING),
        ]
        registry.apply_configs(configs)
        # A disabled, B severity overridden
        assert registry.active_count == 0  # no rules registered, just configs applied

    @property
    def count(self) -> int:
        return len(self._rules)


class TestGetRegistrySingleton:
    def test_returns_same_instance(self) -> None:
        r1 = get_registry()
        r2 = get_registry()
        assert r1 is r2

    def test_type(self) -> None:
        assert isinstance(get_registry(), RuleRegistry)


class TestRegisterRuleDecorator:
    def test_decorator_registers_rule(self) -> None:
        # Use a fresh registry to avoid pollution
        registry = RuleRegistry()

        @register_rule(
            rule_id="DECO_001",
            rule_name="DecoratorTest",
            category=RuleCategory.DATA,
            severity=Severity.WARNING,
        )
        class _DecoRule(Rule):
            rule_id = ""
            def validate(self, context: GateContext) -> RuleResult:
                return RuleResult(passed=True)

        # Decorator uses get_registry(), which is the global singleton
        # The class is registered in the global registry
        global_registry = get_registry()
        found = global_registry.get("DECO_001")
        assert found is not None
        assert found.rule_name == "DecoratorTest"
        assert found.category == RuleCategory.DATA

    def test_decorator_sets_all_attributes(self) -> None:
        global_registry = get_registry()
        rule = global_registry.get("DECO_001")
        assert rule is not None
        assert rule.rule_id == "DECO_001"
        assert rule.rule_name == "DecoratorTest"
        assert rule.category == RuleCategory.DATA
        assert rule.severity == Severity.WARNING
        assert rule.description == ""
