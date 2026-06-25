"""TITLE_STEP_MISMATCH — 标题声称的测试场景与步骤实际行为不一致。

详见 docs/architecture/2026-06-17_Rule Catalog 规则目录.md
"""

from __future__ import annotations

from typing import Any

from shared_backend.quality_gate import (
    GateContext, Rule, RuleCategory, RuleResult, Severity, register_rule,
)
from ._common import normalized


# (title关键词, 期望步骤特征检查函数, 不匹配描述)
_CHECKS: list[tuple[list[str], Any, str]] = [
    (
        ["验证错误提示", "显示错误", "错误信息", "提示错误"],
        lambda steps: any(
            normalized(s.get("action")) in {"assert_text", "assert_visible"}
            and any(kw in normalized(s.get("target", ""))
                    for kw in ("error", "toast", "message", "错误", "提示"))
            for s in steps if isinstance(s, dict)
        ),
        "缺少错误提示相关断言",
    ),
    (
        ["登录后", "已登录"],
        lambda steps: (
            any(normalized(s.get("action")) == "click" for s in steps if isinstance(s, dict))
            and any("login" in normalized(s.get("target", ""))
                    for s in steps if isinstance(s, dict))
        ),
        "标题声称登录后但步骤缺少登录操作",
    ),
    (
        ["拦截", "阻止"],
        lambda steps: any(
            normalized(s.get("action")) in {"assert_url", "assert_visible"}
            for s in steps if isinstance(s, dict)
        ),
        "标题声称拦截/阻止但缺少对应断言",
    ),
]


@register_rule(
    rule_id="RULE_012",
    rule_name="TITLE_STEP_MISMATCH",
    category=RuleCategory.SEMANTIC,
    severity=Severity.WARNING,
    description="标题声称的测试场景与步骤实际行为不一致",
)
class TitleStepMismatchRule(Rule):
    def validate(self, context: GateContext) -> RuleResult:
        title = normalized(context.case_yaml.get("title", ""))
        if not title:
            return RuleResult(rule_id=self.rule_id, rule_name=self.rule_name,
                              severity=self.severity, category=self.category,
                              message="无用例标题", passed=True)

        steps = (context.case_yaml.get("execution") or {}).get("steps") or []

        mismatches: list[str] = []
        for keywords, check_fn, desc in _CHECKS:
            if not any(kw in title for kw in keywords):
                continue
            if not check_fn(steps):
                mismatches.append(f"标题含'{keywords[0]}'→{desc}")

        if mismatches:
            return RuleResult(
                rule_id=self.rule_id, rule_name=self.rule_name,
                severity=self.severity, category=self.category,
                message=f"标题与步骤行为不一致: {'; '.join(mismatches)}",
                suggestion="请在步骤中添加对应行为或修正标题",
                evidence={"title": title[:120], "mismatches": mismatches},
                passed=False,
            )

        matched = [kw for kw_set, _, _ in _CHECKS for kw in kw_set if kw in title]
        return RuleResult(
            rule_id=self.rule_id, rule_name=self.rule_name,
            severity=self.severity, category=self.category,
            message="标题与步骤行为一致" + (f" (关键词: {matched})" if matched else ""),
            passed=True,
        )
