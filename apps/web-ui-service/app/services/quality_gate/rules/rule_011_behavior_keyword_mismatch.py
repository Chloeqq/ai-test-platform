"""BEHAVIOR_KEYWORD_MISMATCH — 标题声称的行为关键词在步骤中无对应操作。

检查 title 中的行为关键词是否在 steps 中有对应操作。
原名 STEP_TEMPLATE_LEAK，2026-06-25 重命名为 BEHAVIOR_KEYWORD_MISMATCH，
因原名称暗示 AI 模板残留（应归属 RULE_016），实际检查的是标题-步骤行为一致性。

详见 docs/architecture/2026-06-17_Rule Catalog 规则目录.md
"""

from __future__ import annotations

from collections import Counter
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

from ._common import normalized

_CheckFn = Callable[[list[dict[str, Any]]], bool]


def _has_repeated_click_on_same_target(steps: list[dict[str, Any]]) -> bool:
    """检查是否有同一 target 被 click 多次（真正的重复点击）。"""
    targets = [
        s.get("target") for s in steps
        if isinstance(s, dict)
        and normalized(s.get("action")) == "click"
        and s.get("target")
    ]
    return any(c >= 2 for c in Counter(targets).values())


def _has_dblclick(steps: list[dict[str, Any]]) -> bool:
    """检查是否有 dblclick 动作（双击手势）。"""
    return any(
        isinstance(s, dict) and normalized(s.get("action")) == "dblclick"
        for s in steps
    )


def _has_wait_or_timeout(steps: list[dict[str, Any]]) -> bool:
    """检查是否有明确的超时等待步骤。

    已知局限：V1.1 的 wait 通常用于等页面渲染，与"模拟接口超时"是不同语义。
    当前的启发式检查只判断存在性，不验证超时阈值是否合理。
    精确的超时模拟检测需等 DSL 支持 simulate_timeout/mock_delay 后实现。
    """
    for s in steps:
        if not isinstance(s, dict):
            continue
        if normalized(s.get("action")) == "wait":
            return True
        if s.get("timeout_ms") or s.get("timeout"):
            return True
    return False


# 行为关键词 → 期望步骤特征的检查规则
# 以下按 DSL 版本的可用动作逐步激活：
#   已激活 — V1.1 可验证的检查
#   TODO — 待 DSL >= V2.0 后激活（弱网需 route/throttle 动作，并发需并行标记）
_BEHAVIOR_CHECKS: list[tuple[list[str], _CheckFn, str, str]] = [
    (
        ["重复点击", "连续点击"],
        _has_repeated_click_on_same_target,
        "同 target 被 click ≥ 2 次",
        "无同 target 多次点击，标题声称重复但步骤未体现",
    ),
    (
        ["双击"],
        _has_dblclick,
        "含 dblclick 步骤",
        "无 dblclick 步骤，标题声称双击但步骤未体现",
    ),
    (
        ["超时"],
        _has_wait_or_timeout,
        "含 wait 步骤或 timeout 配置",
        "无 wait 或 timeout，标题声称超时但步骤未体现（注：V1.1 wait≠接口超时，检查有局限性）",
    ),
    # TODO: 弱网 — 待 DSL 支持 route/throttle 动作后激活
    # TODO: 并发 — 待 DSL 支持并行标记后激活
]


@register_rule(
    rule_id="RULE_011",
    rule_name="BEHAVIOR_KEYWORD_MISMATCH",
    category=RuleCategory.STEP,
    severity=Severity.WARNING,
    description="标题声称的行为关键词在步骤中无对应操作",
)
class BehaviorKeywordMismatchRule(Rule):
    """检查 title 中的行为关键词是否在 steps 中有对应操作。

    原名 StepTemplateLeakRule，重命名原因见模块 docstring。
    """

    def validate(self, context: GateContext) -> RuleResult:
        case = context.case_yaml
        title = normalized(case.get("title", ""))
        if not title:
            return RuleResult(
                rule_id=self.rule_id, rule_name=self.rule_name,
                severity=self.severity, category=self.category,
                message="无用例标题", passed=True,
            )

        execution = case.get("execution") if isinstance(case.get("execution"), dict) else {}
        steps = execution.get("steps") if isinstance(execution.get("steps"), list) else []

        mismatches: list[dict[str, Any]] = []

        for keywords, check_fn, expected, fail_msg in _BEHAVIOR_CHECKS:
            if not any(kw in title for kw in keywords):
                continue

            if not check_fn(steps):
                mismatches.append({
                    "title_keywords": keywords,
                    "expected": expected,
                    "actual": fail_msg,
                })

        if mismatches:
            detail = "; ".join(
                f"标题含'{m['title_keywords']}'→期望{m['expected']}"
                for m in mismatches
            )
            return RuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                severity=self.severity,
                category=self.category,
                message=f"步骤行为与标题关键词不匹配: {detail}",
                suggestion="请在步骤中添加标题声称的行为（多次点击同元素/dblclick/wait等），"
                           "或修正标题以匹配实际步骤",
                evidence={"title": title[:120], "mismatches": mismatches},
                passed=False,
            )

        matched_keywords = [
            kw for kw_set, _, _, _ in _BEHAVIOR_CHECKS
            if any(kw in title for kw in kw_set)
            for kw in kw_set
            if kw in title
        ]
        if matched_keywords:
            msg = f"标题含行为关键词 {matched_keywords}，步骤特征匹配"
        else:
            msg = "标题中未识别到特定行为关键词，跳过"
        return RuleResult(
            rule_id=self.rule_id,
            rule_name=self.rule_name,
            severity=self.severity,
            category=self.category,
            message=msg,
            passed=True,
        )
