"""STEP_TEMPLATE_LEAK — 步骤与标题行为关键词不匹配。

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
    rule_id="RULE_011",
    rule_name="STEP_TEMPLATE_LEAK",
    category=RuleCategory.STEP,
    severity=Severity.WARNING,
    description="步骤与标题行为关键词不匹配",
)
class StepTemplateLeakRule(Rule):
    """步骤与标题行为关键词不匹配。"""

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
