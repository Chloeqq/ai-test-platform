"""RuleEngine — 规则执行引擎。

遍历已注册规则，对 GateContext 逐一执行，聚合结果为 ValidationReport。
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .models import Decision, GateContext, RuleResult, Severity, ValidationReport
from .registry import get_registry

if TYPE_CHECKING:
    from .registry import RuleRegistry

LOGGER = logging.getLogger(__name__)


class RuleEngine:
    """规则执行引擎。

    遍历 RuleRegistry 中的所有活跃规则，对 GateContext 逐一执行，
    收集 RuleResult 列表，最终聚合为 ValidationReport。
    """

    def execute_all(
        self,
        context: GateContext,
        *,
        registry: RuleRegistry | None = None,
    ) -> list[RuleResult]:
        """执行所有已注册的活跃规则。

        registry 参数用于测试注入；为 None 时使用全局单例。
        """
        if registry is None:
            registry = get_registry()
        results: list[RuleResult] = []

        for rule in registry.list_active():
            try:
                result = rule.validate(context)
            except Exception as exc:
                LOGGER.warning(
                    "Rule '%s' raised exception: %s", rule.rule_id, exc
                )
                result = RuleResult(
                    rule_id=rule.rule_id,
                    rule_name=rule.rule_name,
                    severity=rule.severity,
                    category=rule.category,
                    message=f"规则执行异常: {exc}",
                    suggestion="请联系平台管理员检查规则实现",
                    passed=False,
                )
            results.append(result)

        return results

    def aggregate(self, results: list[RuleResult]) -> ValidationReport:
        """聚合规则执行结果，生成 ValidationReport。"""
        decision = self._decide(results)
        return ValidationReport(
            results=results,
            decision=decision,
            summary=self._summarize(results, decision),
        )

    # -- 内部 --

    @staticmethod
    def _decide(results: list[RuleResult]) -> Decision:
        failed = [r for r in results if not r.passed]
        severities = {r.severity for r in failed}

        if Severity.FATAL in severities:
            return Decision.REJECT
        if Severity.ERROR in severities:
            return Decision.REVIEW
        if Severity.WARNING in severities:
            return Decision.REVIEW

        # INFO-only failures → auto-repairable
        if severities == {Severity.INFO}:
            return Decision.REPAIR

        return Decision.PASS

    @staticmethod
    def _summarize(results: list[RuleResult], decision: Decision) -> str:
        total = len(results)
        failed = [r for r in results if not r.passed]
        fatals = [r for r in failed if r.severity == Severity.FATAL]
        errors = [r for r in failed if r.severity == Severity.ERROR]
        warnings = [r for r in failed if r.severity == Severity.WARNING]

        parts = [f"{total} 条规则已执行"]
        if fatals:
            parts.append(f"{len(fatals)} FATAL")
        if errors:
            parts.append(f"{len(errors)} ERROR")
        if warnings:
            parts.append(f"{len(warnings)} WARNING")
        parts.append(f"→ {decision.value.upper()}")
        return "; ".join(parts)
