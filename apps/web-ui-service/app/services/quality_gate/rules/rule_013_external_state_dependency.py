"""EXTERNAL_STATE_DEPENDENCY — 依赖外部系统状态但无对应 setup 步骤。

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
    rule_id="RULE_013",
    rule_name="EXTERNAL_STATE_DEPENDENCY",
    category=RuleCategory.DEPENDENCY,
    severity=Severity.WARNING,
    description="依赖外部系统状态但无对应 setup 步骤",
)
class ExternalStateDependencyRule(Rule):
    """依赖外部系统状态但无对应 setup 步骤。"""

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
