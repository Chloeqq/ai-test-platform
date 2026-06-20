"""RuleRegistry — 全局规则注册中心。

所有规则通过 register() 注册到此单例。
RuleEngine 从注册中心获取规则列表执行。
"""

from __future__ import annotations

from typing import Callable

from .models import RuleCategory, RuleConfig, RuleResult, Severity
from .rule_interface import Rule


class RuleRegistry:
    """全局规则注册中心。

    维护所有已注册规则的集合，支持注册、注销、查询、配置。
    """

    def __init__(self) -> None:
        self._rules: list[Rule] = []
        self._configs: dict[str, RuleConfig] = {}

    # -- 注册 --

    def register(self, rule: Rule) -> None:
        if not rule.rule_id:
            raise ValueError("Rule must have a non-empty rule_id")
        if self.get(rule.rule_id) is not None:
            raise ValueError(f"Rule '{rule.rule_id}' is already registered")
        self._rules.append(rule)

    def unregister(self, rule_id: str) -> None:
        self._rules = [r for r in self._rules if r.rule_id != rule_id]

    # -- 查询 --

    def get(self, rule_id: str) -> Rule | None:
        for rule in self._rules:
            if rule.rule_id == rule_id:
                return rule
        return None

    def list_all(self) -> list[Rule]:
        return list(self._rules)

    def list_active(self) -> list[Rule]:
        return [r for r in self._rules if self._is_enabled(r.rule_id)]

    def list_by_category(self, category: RuleCategory) -> list[Rule]:
        return [r for r in self._rules if r.category == category]

    # -- 配置 --

    def apply_config(self, config: RuleConfig) -> None:
        self._configs[config.rule_id] = config

    def apply_configs(self, configs: list[RuleConfig]) -> None:
        for c in configs:
            self.apply_config(c)

    def effective_severity(self, rule: Rule) -> Severity:
        config = self._configs.get(rule.rule_id)
        if config is not None and config.severity is not None:
            return config.severity
        return rule.severity

    # -- 内部 --

    def _is_enabled(self, rule_id: str) -> bool:
        config = self._configs.get(rule_id)
        if config is not None:
            return config.enabled
        return True

    # -- 计数 --

    @property
    def count(self) -> int:
        return len(self._rules)

    @property
    def active_count(self) -> int:
        return len(self.list_active())


# ---------------------------------------------------------------------------
# 单例
# ---------------------------------------------------------------------------

_registry: RuleRegistry | None = None


def get_registry() -> RuleRegistry:
    global _registry
    if _registry is None:
        _registry = RuleRegistry()
    return _registry


# ---------------------------------------------------------------------------
# 装饰器
# ---------------------------------------------------------------------------

def register_rule(
    *,
    rule_id: str,
    rule_name: str,
    category: RuleCategory,
    severity: Severity,
    description: str = "",
) -> Callable[[type[Rule]], type[Rule]]:
    """装饰器：将 Rule 子类实例化并注册到全局注册中心。

    Usage:

        @register_rule(
            rule_id="RULE_002",
            rule_name="MISSING_TEST_DATA",
            category=RuleCategory.DATA,
            severity=Severity.ERROR,
        )
        class MissingTestDataRule(Rule):
            def validate(self, context):
                ...
    """
    def decorator(cls: type[Rule]) -> type[Rule]:
        instance = cls()
        instance.rule_id = rule_id
        instance.rule_name = rule_name
        instance.category = category
        instance.severity = severity
        instance.description = description
        get_registry().register(instance)
        return cls
    return decorator
