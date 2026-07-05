"""MISSING_ASSERTION — AI 用例无可执行断言。

检查 AI 生成的用例是否包含至少一个可执行断言步骤。
无断言的用例执行后无法验证任何业务结果，完全无效。

详见 docs/architecture/2026-06-17_Rule Catalog 规则目录.md
"""

from __future__ import annotations

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


def _is_ai_generated(case: dict[str, Any]) -> bool:
    """判断用例是否为 AI 生成（通过 tags 中的 'ai-generated' 标签）。"""
    tags = case.get("tags")
    if isinstance(tags, list):
        if any(normalized(t) == "ai-generated" for t in tags):
            return True
    return False


def _count_assertions(steps: list[dict[str, Any]], assertions: Any) -> int:
    """统计可执行断言总数（steps 中的 assert_* + 顶层 assertions 中的有效条目）。"""
    count = 0
    for step in steps:
        if not isinstance(step, dict):
            continue
        if normalized(step.get("action")).startswith("assert_"):
            count += 1
    if isinstance(assertions, list):
        count += sum(1 for a in assertions if isinstance(a, dict) and a)
    return count


@register_rule(
    rule_id="RULE_008",
    rule_name="MISSING_ASSERTION",
    category=RuleCategory.ASSERTION,
    severity=Severity.FATAL,
    description="用例无可执行断言（AI 用例 FATAL，非 AI 用例 ERROR）",
)
class MissingAssertionRule(Rule):
    """检查用例是否包含至少一个可执行断言。

    AI 生成的用例无断言 → FATAL（完全无效）
    非 AI 用例无断言 → ERROR（可能是手动草稿，需审核）
    """

    def validate(self, context: GateContext) -> RuleResult:
        case = context.case_yaml
        ai = _is_ai_generated(case)

        execution = case.get("execution") if isinstance(case.get("execution"), dict) else {}
        steps = execution.get("steps") if isinstance(execution.get("steps"), list) else []
        assertions = case.get("assertions")

        assertion_count = _count_assertions(steps, assertions)

        if assertion_count == 0:
            # AI 用例无断言 → FATAL；非 AI → ERROR（关闭 RULE_003 的盲区）
            effective_severity = Severity.FATAL if ai else Severity.ERROR
            return RuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                severity=effective_severity,
                category=self.category,
                message=(
                    "用例没有任何可执行断言。"
                    "无断言的用例执行后无法验证任何业务结果。"
                    + ("AI 生成 + 无断言 = 完全无效。" if ai else "")
                ),
                suggestion=(
                    "在 execution.steps 中至少添加一个 assert_visible 或 assert_text 步骤，"
                    "或在 assertions 字段中定义可执行断言"
                ),
                evidence={
                    "assertion_count": 0,
                    "steps_count": len(steps),
                    "ai_generated": ai,
                },
                passed=False,
            )

        return RuleResult(
            rule_id=self.rule_id,
            rule_name=self.rule_name,
            severity=self.severity,
            category=self.category,
            message=f"已确认 {assertion_count} 个可执行断言",
            evidence={
                "assertion_count": assertion_count,
                "ai_generated": ai,
            },
            passed=True,
        )


