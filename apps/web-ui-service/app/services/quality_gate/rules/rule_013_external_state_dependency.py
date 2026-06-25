"""EXTERNAL_STATE_DEPENDENCY — 依赖外部系统状态但无对应 setup 步骤。

详见 docs/architecture/2026-06-17_Rule Catalog 规则目录.md
"""

from __future__ import annotations

import re
from typing import Any

from shared_backend.quality_gate import (
    GateContext, Rule, RuleCategory, RuleResult, Severity, register_rule,
)
from ._common import normalized


# (precondition 关键词正则, 需要的步骤特征, 描述)
_CHECKS: list[tuple[str, Any, str]] = [
    (
        r"账号.*锁定|锁定.*账号|account.*lock|lock.*account",
        lambda steps: any(
            normalized(s.get("action")) in {"api_call", "http_request", "sql"}
            and any(kw in normalized(str(s))
                    for kw in ("lock", "锁定", "account", "账号"))
            for s in steps if isinstance(s, dict)
        ),
        "缺少锁定账号的 setup 步骤 (API/SQL)",
    ),
    (
        r"账号.*禁用|禁用.*账号|account.*disable|disable.*account",
        lambda steps: any(
            normalized(s.get("action")) in {"api_call", "http_request", "sql"}
            and any(kw in normalized(str(s))
                    for kw in ("disable", "禁用", "account", "账号"))
            for s in steps if isinstance(s, dict)
        ),
        "缺少禁用账号的 setup 步骤 (API/SQL)",
    ),
    (
        r"数据库.*状态|db.*state|cache.*expir|缓存.*过期",
        lambda steps: any(
            normalized(s.get("action")) in {"sql", "api_call", "http_request"}
            for s in steps if isinstance(s, dict)
        ),
        "缺少数据库/缓存 setup 步骤",
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
        requirement = context.case_yaml.get("requirement") or {}
        precondition = normalized(requirement.get("precondition", ""))
        if not precondition:
            return RuleResult(rule_id=self.rule_id, rule_name=self.rule_name,
                              severity=self.severity, category=self.category,
                              message="无前置条件声明", passed=True)

        steps = (context.case_yaml.get("execution") or {}).get("steps") or []

        issues: list[str] = []
        for pattern, check_fn, desc in _CHECKS:
            if not re.search(pattern, precondition, re.IGNORECASE):
                continue
            if not check_fn(steps):
                issues.append(f"precondition 含'{pattern[:20]}'→{desc}")

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
