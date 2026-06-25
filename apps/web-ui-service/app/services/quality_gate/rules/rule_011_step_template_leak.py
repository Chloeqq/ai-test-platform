"""STEP_TEMPLATE_LEAK — 步骤与标题行为关键词不匹配。

检查 title 中的行为关键词（重复点击/超时/弱网/并发）是否在 steps 中有对应操作。
触发条件来自 Rule Catalog §3.3，详见 docs/architecture/2026-06-17_Rule Catalog 规则目录.md
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


def _count_clicks(steps: list[dict[str, Any]]) -> int:
    """统计步骤中 click 动作的数量（含 click + dblclick）。"""
    count = 0
    for s in steps:
        if not isinstance(s, dict):
            continue
        action = normalized(s.get("action"))
        if action in {"click", "dblclick"}:
            count += 1
    return count


def _has_wait_or_timeout(steps: list[dict[str, Any]]) -> bool:
    """检查是否有 wait 步骤或超时配置。"""
    for s in steps:
        if not isinstance(s, dict):
            continue
        if normalized(s.get("action")) == "wait":
            return True
        if s.get("timeout_ms") or s.get("timeout"):
            return True
    return False


def _title_contains_any(title: str, keywords: list[str]) -> bool:
    """检查 title 是否包含任意关键词。"""
    lower = title.lower()
    return any(kw in lower for kw in keywords)


# 行为关键词 → 期望步骤特征 的检查规则
# 注：以下按 DSL 版本的可用动作逐步激活。
#     "并发" — V1.1 无并行标记，待 DSL >= V2.0 后激活。
#     "弱网" — V1.1 无 route/throttle 动作，待 DSL >= V2.0 后激活。
#     当前只激活 V1.1 能验证的检查。
_BEHAVIOR_CHECKS: list[tuple[list[str], Any, str, str]] = [
    (
        ["重复点击", "双击"],
        lambda steps: _count_clicks(steps) >= 2,
        "click 步骤 ≥ 2 次",
        "click 步骤仅 1 次，标题声称重复/双击但步骤未体现多次点击",
    ),
    (
        ["超时"],
        lambda steps: _has_wait_or_timeout(steps),
        "含 wait 步骤或 timeout 配置",
        "无 wait 步骤或 timeout 配置，标题声称超时但步骤可能瞬间完成",
    ),
    # ── 以下两项待 DSL 升级后激活 ──
    # (
    #     ["弱网"],
    #     lambda steps: _has_network_control(steps),
    #     "含网络控制步骤 (route/throttle)",
    #     "无网络控制步骤，标题声称弱网但步骤未模拟网络条件",
    # ),
    # (
    #     ["并发"],
    #     lambda steps: _has_parallel_steps(steps),
    #     "含并行执行标记",
    #     "无并行标记，标题声称并发但步骤为线性序列",
    # ),
]


@register_rule(
    rule_id="RULE_011",
    rule_name="STEP_TEMPLATE_LEAK",
    category=RuleCategory.STEP,
    severity=Severity.WARNING,
    description="步骤与标题行为关键词不匹配",
)
class StepTemplateLeakRule(Rule):
    """检查 title 中的行为关键词是否在 steps 中有对应操作。"""

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
            if not _title_contains_any(title, keywords):
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
                suggestion="请在步骤中添加标题声称的行为（多次点击/wait/弱网模拟等），"
                           "或修正标题以匹配实际步骤",
                evidence={"title": title[:120], "mismatches": mismatches},
                passed=False,
            )

        # check which keywords actually matched
        matched_keywords = [
            kw for kw_set, _, _, _ in _BEHAVIOR_CHECKS
            if _title_contains_any(title, kw_set)
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
