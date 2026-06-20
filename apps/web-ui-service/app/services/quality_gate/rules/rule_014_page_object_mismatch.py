"""PAGE_OBJECT_MISMATCH — 步骤 locator 与 page object 定义不一致。

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
    rule_id="RULE_014",
    rule_name="PAGE_OBJECT_MISMATCH",
    category=RuleCategory.PAGE_OBJECT,
    severity=Severity.WARNING,
    description="步骤 locator 与 page object 定义不一致",
)
class PageObjectMismatchRule(Rule):
    """步骤 locator 与 page object 定义不一致。"""

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
