"""REQUIREMENT_MISMATCH — 步骤未覆盖 requirement 中声明的意图。

详见 docs/architecture/2026-06-17_Rule Catalog 规则目录.md
"""

from __future__ import annotations

from typing import Any

from shared_backend.quality_gate import (
    GateContext, Rule, RuleCategory, RuleResult, Severity, register_rule,
)
from ._common import normalized


# (intent/requirement 描述关键词, 期望步骤特征, 不匹配描述)
_CHECKS: list[tuple[list[str], Any, str]] = [
    (
        ["验证.*提示", "显示.*消息", "错误.*展示", "提示.*信息"],
        lambda steps: any(
            normalized(s.get("action")) in {"assert_text", "assert_visible"}
            for s in steps if isinstance(s, dict)
        ),
        "intent 期望验证提示/消息但步骤缺少 assert_text/assert_visible",
    ),
    (
        ["跳转", "重定向"],
        lambda steps: any(
            normalized(s.get("action")) in {"goto", "assert_url"}
            for s in steps if isinstance(s, dict)
        ),
        "intent 期望跳转/重定向但步骤缺少 goto/assert_url",
    ),
    (
        ["阻止", "拦截"],
        lambda steps: any(
            normalized(s.get("action")) in {"assert_url", "assert_visible"}
            for s in steps if isinstance(s, dict)
        ),
        "intent 期望阻止/拦截但步骤缺少对应断言",
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
            requirement.get("title")
            or requirement.get("description", "")
        )
        if not intent_title:
            return RuleResult(rule_id=self.rule_id, rule_name=self.rule_name,
                              severity=self.severity, category=self.category,
                              message="无 requirement 描述，跳过", passed=True)

        steps = (context.case_yaml.get("execution") or {}).get("steps") or []

        mismatches: list[str] = []
        for keywords, check_fn, desc in _CHECKS:
            # 用简单子串匹配（keywords 中的纯中文词），不用正则
            if not any(kw.replace(".*", "") in intent_title for kw in keywords):
                continue
            if not check_fn(steps):
                mismatches.append(desc)

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
