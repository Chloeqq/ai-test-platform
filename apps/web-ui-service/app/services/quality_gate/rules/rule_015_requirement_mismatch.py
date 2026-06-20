"""REQUIREMENT_MISMATCH — 步骤未覆盖 requirement 中声明的意图。

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
    rule_id="RULE_015",
    rule_name="REQUIREMENT_MISMATCH",
    category=RuleCategory.REQUIREMENT,
    severity=Severity.WARNING,
    description="步骤未覆盖 requirement 中声明的意图",
)
class RequirementMismatchRule(Rule):
    """步骤未覆盖 requirement 中声明的意图。"""

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
