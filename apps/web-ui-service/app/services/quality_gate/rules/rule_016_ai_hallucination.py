"""AI_HALLUCINATION — AI 生成了不存在的对象/URL/文本。

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
    rule_id="RULE_016",
    rule_name="AI_HALLUCINATION",
    category=RuleCategory.AI_GENERATION,
    severity=Severity.ERROR,
    description="AI 生成了不存在的对象/URL/文本",
)
class AiHallucinationRule(Rule):
    """AI 生成了不存在的对象/URL/文本。"""

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
