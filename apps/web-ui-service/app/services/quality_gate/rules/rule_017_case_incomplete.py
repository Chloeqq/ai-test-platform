"""CASE_INCOMPLETE — 用例缺少必要的步骤或断言。

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
    rule_id="RULE_017",
    rule_name="CASE_INCOMPLETE",
    category=RuleCategory.AI_GENERATION,
    severity=Severity.WARNING,
    description="用例缺少必要的步骤或断言",
)
class CaseIncompleteRule(Rule):
    """用例缺少必要的步骤或断言。"""

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
