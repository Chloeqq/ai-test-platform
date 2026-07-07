"""REQUIREMENT_MISMATCH — 步骤未覆盖 requirement 中声明的意图。

与 RULE_012 的边界：
- RULE_012 检查 case.title vs steps
- RULE_015 检查 requirement.title/description vs steps
  两者检查对象不同（标题 vs 需求描述），但检查逻辑共用同一语义模式。

详见 docs/architecture/2026-06-17_Rule Catalog 规则目录.md
"""

from __future__ import annotations

from typing import Any, Callable

from shared_backend.quality_gate import (
    GateContext, Rule, RuleCategory, RuleResult, Severity, register_rule,
)
from ._common import has_assert_for_block_intercept, has_assert_for_error_message, normalized

_CheckFn = Callable[[list[dict[str, Any]]], bool]


# (requirement 关键词, 期望步骤特征, 不匹配描述)
_CHECKS: list[tuple[list[str], _CheckFn, str]] = [
    (
        ["提示", "错误信息", "错误提示"],
        has_assert_for_error_message(),
        "intent 期望验证错误提示但步骤缺少 assert_text/assert_visible（target/expected 不含 error/toast/message 语义）",
    ),
    (
        ["跳转", "重定向"],
        lambda steps: any(
            normalized(s.get("action")) == "assert_url"
            for s in steps if isinstance(s, dict)
        ),
        "intent 期望跳转/重定向但步骤缺少 assert_url（注：RULE_003 认为负向场景中 assert_url 是弱断言，但在跳转场景中合理）",
    ),
    (
        ["阻止", "拦截"],
        has_assert_for_block_intercept(),
        "intent 期望阻止/拦截但缺少对应的拒绝/阻断断言",
    ),
]


@register_rule(
    rule_id="RULE_015",
    rule_name="REQUIREMENT_MISMATCH",
    category=RuleCategory.REQUIREMENT,
    severity=Severity.WARNING,
    description="步骤未覆盖 requirement 中声明的意图",
)
class RequirementMismatchRule(Rule):
    def validate(self, context: GateContext) -> RuleResult:
        requirement = context.case_yaml.get("requirement") or {}
        intent_title = normalized(
            " ".join(filter(None, [
                requirement.get("title", ""),
                requirement.get("description", ""),
            ]))
        )
        if not intent_title:
            return RuleResult(rule_id=self.rule_id, rule_name=self.rule_name,
                              severity=self.severity, category=self.category,
                              message="无 requirement 描述，跳过", passed=True)

        execution = context.case_yaml.get("execution") if isinstance(context.case_yaml.get("execution"), dict) else {}
        steps = execution.get("steps") if isinstance(execution.get("steps"), list) else []

        mismatches: list[str] = []
        for keywords, check_fn, desc in _CHECKS:
            matched_kw = next((kw for kw in keywords if kw in intent_title), None)
            if not matched_kw:
                continue
            if not check_fn(steps):
                mismatches.append(f"requirement 含'{matched_kw}'→{desc}")

        if mismatches:
            return RuleResult(
                rule_id=self.rule_id, rule_name=self.rule_name,
                severity=self.severity, category=self.category,
                message=f"requirement 意图未覆盖: {'; '.join(mismatches)}",
                suggestion="请添加对应步骤以覆盖 requirement 中声明的意图",
                evidence={"intent_title": intent_title[:120], "mismatches": mismatches},
                passed=False,
            )

        return RuleResult(
            rule_id=self.rule_id, rule_name=self.rule_name,
            severity=self.severity, category=self.category,
            message=f"requirement 意图与步骤一致: '{intent_title[:60]}'",
            passed=True,
        )
