"""TITLE_STEP_MISMATCH — 标题声称的测试场景与步骤行为不一致。

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
    rule_id="RULE_012",
    rule_name="TITLE_STEP_MISMATCH",
    category=RuleCategory.SEMANTIC,
    severity=Severity.WARNING,
    description="标题声称的测试场景与步骤行为不一致",
)
class TitleStepMismatchRule(Rule):
    """标题声称的测试场景与步骤行为不一致。"""

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
