"""STEP_DATA_INCONSISTENCY — 步骤变量引用链断裂。

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
    rule_id="RULE_010",
    rule_name="STEP_DATA_INCONSISTENCY",
    category=RuleCategory.STEP,
    severity=Severity.ERROR,
    description="步骤变量引用链断裂",
)
class StepDataInconsistencyRule(Rule):
    """步骤变量引用链断裂。"""

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
