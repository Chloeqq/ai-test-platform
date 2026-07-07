"""NEGATIVE_WEAK_ASSERTION — 负向/安全/边界用例的最后断言为 assert_url。

检查 requirement.type 为负向/边界/安全场景的用例，
其执行步骤中最后一个 assertion 是否为 assert_url（弱断言）。

详见 docs/architecture/2026-06-17_Rule Catalog 规则目录.md
"""

from __future__ import annotations

import re
from typing import Any

from shared_backend.quality_gate import (
    GateContext,
    Rule,
    RuleCategory,
    RuleResult,
    Severity,
    register_rule,
)

from ._common import normalized

# 触发此规则的场景类型
_TRIGGER_TYPES: set[str] = {
    "negative",
    "boundary",
    "format",
    "interaction_exception",
    "security",
}

# 预期结果为 URL 跳转/重定向的描述关键词 — 此类场景中 assert_url 是合理断言
# 不依赖标题，而是检查 expected_result 文本
_REDIRECT_EXPECTED_KEYWORDS: set[str] = {
    "跳转",
    "重定向",
    "拦截",
    "redirect",
    "navigate",
}

# URL级断言（弱断言）
_URL_ASSERTIONS: set[str] = {
    "assert_url",
    "assert_url_contains",
    "assert_redirect",
}


def _is_redirect_expected(expected_result: Any) -> bool:
    """检查 expected_result 是否描述的是 URL 跳转/重定向行为。

    对\"不跳转\"/\"没有跳转\"/\"未跳转\"等否定场景同样视为弱断言——
    assert_url 无法区分\"故意不跳转\"和\"出错了不跳转\"，不给豁免。
    """
    text = normalized(expected_result)
    if not text:
        return False
    for kw in _REDIRECT_EXPECTED_KEYWORDS:
        if kw in text:
            # 检查关键词是否被否定
            negated = re.search(rf"(不|没有|未|无法|不会)\s*{re.escape(kw)}", text)
            if negated:
                return False
            return True
    return False


@register_rule(
    rule_id="RULE_003",
    rule_name="NEGATIVE_WEAK_ASSERTION",
    category=RuleCategory.ASSERTION,
    severity=Severity.FATAL,
    description="负向/安全/边界用例的最后断言为 assert_url，缺少元素级断言验证实际错误状态",
)
class NegativeWeakAssertionRule(Rule):
    """检查负向/安全/边界用例的最后断言是否为弱断言。

    核心判断：步骤中最后一个 assertion 是否为 assert_url。
    如果最后断言是 assert_url，而预期结果不是"跳转/重定向"，
    则用例的最终验证无法区分"错误被正确展示"和"页面无响应"。
    """

    def validate(self, context: GateContext) -> RuleResult:
        case = context.case_yaml
        requirement = case.get("requirement") if isinstance(case.get("requirement"), dict) else {}
        execution = case.get("execution") if isinstance(case.get("execution"), dict) else {}
        steps = execution.get("steps") if isinstance(execution.get("steps"), list) else []

        # 1. 只对负向/边界/安全场景生效
        scenario_type = normalized(requirement.get("type"))
        if scenario_type not in _TRIGGER_TYPES:
            return RuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                severity=self.severity,
                category=self.category,
                message=f"场景类型为 '{scenario_type}'，不在检查范围内",
                passed=True,
            )

        # 2. 收集所有 assertion 步骤（保持顺序）
        assertion_steps: list[str] = []
        for step in steps:
            if not isinstance(step, dict):
                continue
            action = normalized(step.get("action"))
            if action.startswith("assert_"):
                assertion_steps.append(action)

        # 3. 无断言 → 不触发（由 RULE_008 处理）
        if not assertion_steps:
            return RuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                severity=self.severity,
                category=self.category,
                message=f"场景类型 '{scenario_type}'，但未发现任何断言步骤",
                passed=True,
            )

        # 4. 最后断言不是 assert_url → PASS
        last_assertion = assertion_steps[-1]
        if last_assertion not in _URL_ASSERTIONS:
            return RuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                severity=self.severity,
                category=self.category,
                message=(
                    f"场景类型 '{scenario_type}'，"
                    f"断言步骤: {assertion_steps}，"
                    f"最后断言为 '{last_assertion}'（非 assert_url）"
                ),
                evidence={
                    "scenario_type": scenario_type,
                    "assertion_types": assertion_steps,
                    "assertion_count": len(assertion_steps),
                    "last_assertion": last_assertion,
                },
                passed=True,
            )

        # 5. 最后断言是 assert_url → 检查预期结果是否为跳转/重定向
        expected = case.get("expected_result", "")
        if _is_redirect_expected(expected):
            return RuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                severity=self.severity,
                category=self.category,
                message=(
                    f"场景类型 '{scenario_type}'，最后断言为 assert_url，"
                    f"但 expected_result 描述的是跳转/重定向行为，assert_url 为合理断言"
                ),
                evidence={
                    "scenario_type": scenario_type,
                    "assertion_types": assertion_steps,
                    "assertion_count": len(assertion_steps),
                    "last_assertion": last_assertion,
                    "expected_result": normalized(expected)[:80],
                },
                passed=True,
            )

        # 6. 最后断言是 assert_url 且预期不是跳转 → 弱断言！
        return RuleResult(
            rule_id=self.rule_id,
            rule_name=self.rule_name,
            severity=self.severity,
            category=self.category,
            message=(
                f"场景类型 '{scenario_type}'，"
                f"断言步骤: {assertion_steps}，"
                f"最后断言为 'assert_url'。"
                "assert_url 仅检查 URL 未跳转，不验证错误提示、Toast 或 UI 状态是否真的出现。"
                "若登录按钮无响应、JS 报错或后端 500，URL 同样不变——用例会虚假通过。"
            ),
            suggestion="将最后断言改为 assert_visible（检查错误提示元素）或 assert_text（验证错误消息文本）",
            evidence={
                "scenario_type": scenario_type,
                "assertion_types": assertion_steps,
                "assertion_count": len(assertion_steps),
                "last_assertion": last_assertion,
            },
            passed=False,
        )
