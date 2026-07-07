"""EXTERNAL_STATE_DEPENDENCY — 依赖外部系统状态但无对应 setup 步骤。

详见 docs/architecture/2026-06-17_Rule Catalog 规则目录.md
"""

from __future__ import annotations

import re
from typing import Any, Callable

from shared_backend.quality_gate import (
    GateContext, Rule, RuleCategory, RuleResult, Severity, register_rule,
)
from ._common import normalized

_CheckFn = Callable[[list[dict[str, Any]]], bool]

# setup 步骤可能出现的 action 类型
_SETUP_ACTIONS: frozenset[str] = frozenset({"api_call", "http_request", "sql"})


def _step_has_keywords(step: dict[str, Any], keywords: tuple[str, ...]) -> bool:
    """检查步骤的语义相关字段是否含任一关键词。

    只检查 url/endpoint/body/description/params 等承载操作语义的字段，
    不检查 action/target 等结构字段。避免 str(step) 序列化整个 dict
    导致 key 名（如 "account"）误匹配。
    """
    candidate = " ".join(
        normalized(str(step.get(f, "")))
        for f in ("url", "endpoint", "path", "body", "description", "params", "target")
    )
    return any(kw in candidate for kw in keywords)


def _has_setup_step(steps: list[dict[str, Any]], keywords: tuple[str, ...]) -> bool:
    """检查步骤中是否有 setup 动作且语义字段含指定关键词。"""
    return any(
        isinstance(s, dict)
        and normalized(s.get("action")) in _SETUP_ACTIONS
        and _step_has_keywords(s, keywords)
        for s in steps
    )


# (precondition 关键词正则, 检查函数, 失败描述, 用户可读触发标签)
_CHECKS: list[tuple[str, _CheckFn, str, str]] = [
    (
        r"账号.*锁定|锁定.*账号|account.*lock|lock.*account",
        lambda steps: _has_setup_step(steps, ("lock", "锁定", "freeze", "suspend")),
        "缺少锁定账号的 setup 步骤 (API/SQL)",
        "账号锁定",
    ),
    (
        r"账号.*禁用|禁用.*账号|account.*disable|disable.*account",
        lambda steps: _has_setup_step(steps, ("disable", "禁用", "deactivate", "ban")),
        "缺少禁用账号的 setup 步骤 (API/SQL)",
        "账号禁用",
    ),
    (
        r"数据库.*状态|db.*state|cache.*expir|缓存.*过期",
        lambda steps: _has_setup_step(
            steps,
            ("cache", "redis", "db", "database", "expire", "缓存", "过期", "数据库"),
        ),
        "缺少数据库/缓存 setup 步骤",
        "数据库/缓存状态",
    ),
]


@register_rule(
    rule_id="RULE_013",
    rule_name="EXTERNAL_STATE_DEPENDENCY",
    category=RuleCategory.DEPENDENCY,
    severity=Severity.WARNING,
    description="依赖外部系统状态但无对应 setup 步骤",
)
class ExternalStateDependencyRule(Rule):
    def validate(self, context: GateContext) -> RuleResult:
        # V2.0: preconditions 块已声明了外部状态依赖的处理方式，跳过文本检查
        preconditions = context.case_yaml.get("preconditions")
        if isinstance(preconditions, list) and preconditions:
            for entry in preconditions:
                if isinstance(entry, dict) and entry.get("type") == "account_state":
                    return RuleResult(rule_id=self.rule_id, rule_name=self.rule_name,
                                      severity=self.severity, category=self.category,
                                      message="V2.0 preconditions 块已声明 account_state，跳过文本检查",
                                      passed=True)

        requirement = context.case_yaml.get("requirement") or {}
        precondition_text = requirement.get("precondition", "")
        if not precondition_text or not isinstance(precondition_text, str) or not precondition_text.strip():
            return RuleResult(rule_id=self.rule_id, rule_name=self.rule_name,
                              severity=self.severity, category=self.category,
                              message="无前置条件声明", passed=True)

        precondition = normalized(precondition_text)

        execution = context.case_yaml.get("execution") if isinstance(context.case_yaml.get("execution"), dict) else {}
        steps = execution.get("steps") if isinstance(execution.get("steps"), list) else []

        issues: list[str] = []
        for pattern, check_fn, desc, label in _CHECKS:
            if not re.search(pattern, precondition):
                continue
            if not check_fn(steps):
                issues.append(f"precondition 描述了'{label}'→{desc}")

        if issues:
            return RuleResult(
                rule_id=self.rule_id, rule_name=self.rule_name,
                severity=self.severity, category=self.category,
                message=f"依赖外部状态但缺少 setup: {'; '.join(issues)}",
                suggestion="请添加对应的 API/SQL setup 步骤，或在 V2.0 preconditions 块中声明",
                evidence={"precondition": precondition[:120], "issues": issues},
                passed=False,
            )

        return RuleResult(
            rule_id=self.rule_id, rule_name=self.rule_name,
            severity=self.severity, category=self.category,
            message=f"外部状态依赖检查通过: '{precondition[:60]}'",
            passed=True,
        )
