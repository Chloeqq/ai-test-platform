"""TITLE_STEP_MISMATCH — 标题声称的测试场景与步骤实际行为不一致。

边界说明：
- "登录后/已登录" 由 RULE_005 统一检查，本规则不重复
- "拦截/阻止" 需要 target/expected 含拦截语义关键词，not just any assert_url

详见 docs/architecture/2026-06-17_Rule Catalog 规则目录.md
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from shared_backend.quality_gate import (
    GateContext,
    Rule,
    RuleCategory,
    RuleResult,
    Severity,
    register_rule,
)

from ._common import (
    has_assert_for_block_intercept,
    has_assert_for_error_message,
    normalized,
)

_CheckFn = Callable[[list[dict[str, Any]]], bool]


# (title关键词, 期望步骤特征检查函数, 不匹配描述)
_CHECKS: list[tuple[list[str], _CheckFn, str]] = [
    (
        ["验证错误提示", "显示错误", "错误信息", "提示错误"],
        has_assert_for_error_message(),
        "缺少错误提示相关断言（assert_text/assert_visible 验证 error/toast/message）",
    ),
    (
        ["拦截", "阻止"],
        has_assert_for_block_intercept(),
        "标题声称拦截/阻止但缺少对应的拒绝/阻断断言（若RULE_003已FAIL则无需额外处理）",
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

        execution = context.case_yaml.get("execution") if isinstance(context.case_yaml.get("execution"), dict) else {}
        steps = execution.get("steps") if isinstance(execution.get("steps"), list) else []

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
