"""ASSERTION_TARGET_INVALID — 断言引用的目标元素无效。

详见 docs/architecture/2026-06-17_Rule Catalog 规则目录.md
"""

from __future__ import annotations

from shared_backend.quality_gate import (
    GateContext,
    Rule,
    RuleCategory,
    RuleResult,
    Severity,
    register_rule,
)


@register_rule(
    rule_id="RULE_009",
    rule_name="ASSERTION_TARGET_INVALID",
    category=RuleCategory.ASSERTION,
    severity=Severity.ERROR,
    description="断言引用的目标元素无效",
)
class AssertionTargetInvalidRule(Rule):
    """断言引用的目标元素无效。"""

    def validate(self, context: GateContext) -> RuleResult:
        # TODO: 实现校验逻辑
        return RuleResult(
            rule_id=self.rule_id,
            rule_name=self.rule_name,
            severity=self.severity,
            category=self.category,
            message="",
            suggestion="",
            passed=True,
        )
