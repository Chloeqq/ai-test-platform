"""CASE_INCOMPLETE — 用例缺少必要的步骤或数据绑定。

仅检查其他规则未覆盖的信号：
1. 步骤数少于最小建议值（功能≥2, 负向/安全≥3）
2. execution.variables 为空但 data 段有数据

RULE_002/008 已覆盖 data 缺失和无断言检查，本规则不重复。

详见 docs/architecture/2026-06-17_Rule Catalog 规则目录.md
"""

from __future__ import annotations

from typing import Any

from shared_backend.quality_gate import (
    GateContext, Rule, RuleCategory, RuleResult, Severity, register_rule,
)
from ._common import normalized


@register_rule(
    rule_id="RULE_017",
    rule_name="CASE_INCOMPLETE",
    category=RuleCategory.AI_GENERATION,
    severity=Severity.WARNING,
    description="用例缺少必要的步骤或数据绑定",
)
class CaseIncompleteRule(Rule):
    """检查用例是否缺少必要的组成部分。"""

    def validate(self, context: GateContext) -> RuleResult:
        case = context.case_yaml
        requirement = case.get("requirement") if isinstance(case.get("requirement"), dict) else {}
        execution = case.get("execution") if isinstance(case.get("execution"), dict) else {}
        steps = execution.get("steps") if isinstance(execution.get("steps"), list) else []
        data = case.get("data") if isinstance(case.get("data"), dict) else {}
        variables = execution.get("variables") if isinstance(execution.get("variables"), dict) else {}

        issues: list[str] = []

        # ── 检查1: 步骤数 < 最小建议值 ──
        intent_type = normalized(requirement.get("type", "functional"))
        min_steps = 2 if intent_type in {"functional", ""} else 3
        actual = sum(1 for s in steps if isinstance(s, dict))
        if actual < min_steps:
            issues.append(
                f"步骤数 {actual} < 最小建议值 {min_steps} "
                f"(type={intent_type})"
            )

        # ── 检查2: variables 空但 data 非空 ──
        if not variables and isinstance(data, dict) and len(data) > 0:
            issues.append(
                f"execution.variables 为空但 data 段有 {len(data)} 个 key "
                f"({', '.join(sorted(data.keys())[:5])})"
            )

        if issues:
            return RuleResult(
                rule_id=self.rule_id, rule_name=self.rule_name,
                severity=self.severity, category=self.category,
                message=f"用例可能不完整: {'; '.join(issues)}",
                suggestion="请补充缺失的步骤或数据绑定",
                evidence={"issues": issues},
                passed=False,
            )

        return RuleResult(
            rule_id=self.rule_id, rule_name=self.rule_name,
            severity=self.severity, category=self.category,
            message=f"用例完整性检查通过 ({actual} 步骤, "
                    f"{len(data)} 数据项, "
                    f"{len(variables)} 变量映射)",
            passed=True,
        )
