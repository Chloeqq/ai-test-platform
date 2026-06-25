"""PAGE_OBJECT_MISMATCH — 步骤 locator 与 page object 定义不一致。

详见 docs/architecture/2026-06-17_Rule Catalog 规则目录.md
"""

from __future__ import annotations

from typing import Any

from shared_backend.quality_gate import (
    GateContext, Rule, RuleCategory, RuleResult, Severity, register_rule,
)
from ._common import extract_element_code, normalized


@register_rule(
    rule_id="RULE_014",
    rule_name="PAGE_OBJECT_MISMATCH",
    category=RuleCategory.PAGE_OBJECT,
    severity=Severity.WARNING,
    description="步骤 locator 与 page object 定义不一致",
)
class PageObjectMismatchRule(Rule):
    """检查步骤中的 locator_type 是否与 page object 定义一致。"""

    def validate(self, context: GateContext) -> RuleResult:
        page_object = context.page_object or {}
        elements = page_object.get("elements") if isinstance(page_object, dict) else {}
        if not elements:
            return RuleResult(rule_id=self.rule_id, rule_name=self.rule_name,
                              severity=self.severity, category=self.category,
                              message="无 page object 数据，跳过", passed=True)

        steps = (context.case_yaml.get("execution") or {}).get("steps") or []
        if not steps:
            return RuleResult(rule_id=self.rule_id, rule_name=self.rule_name,
                              severity=self.severity, category=self.category,
                              message="无步骤数据", passed=True)

        mismatches: list[dict[str, Any]] = []

        for i, step in enumerate(steps, start=1):
            if not isinstance(step, dict):
                continue

            element_code = extract_element_code(step.get("target", ""))
            if not element_code:
                continue

            element_def = elements.get(element_code)
            if not isinstance(element_def, dict):
                continue  # element 不存在 → RULE_006 负责

            step_locator_type = normalized(step.get("locator_type", ""))

            # 步骤未声明 locator → 不需要检查
            if not step_locator_type:
                continue

            # 对比步骤 locator 与 page object 定义
            po_locator_type = normalized(element_def.get("locator_type", ""))
            po_role = normalized(element_def.get("role", ""))

            # role-based elements 视为一种 locator_type
            if po_role and step_locator_type == "role":
                continue  # 一致

            if po_locator_type and step_locator_type != po_locator_type:
                mismatches.append({
                    "step_index": i,
                    "element": element_code,
                    "step_locator": step_locator_type,
                    "po_locator": po_locator_type or ("role:" + po_role if po_role else "unknown"),
                })

        if mismatches:
            # 汇总
            summary = ", ".join(
                f"步骤{m['step_index']} {m['element']}: step={m['step_locator']} vs po={m['po_locator']}"
                for m in mismatches[:5]
            )
            return RuleResult(
                rule_id=self.rule_id, rule_name=self.rule_name,
                severity=self.severity, category=self.category,
                message=f"发现 {len(mismatches)} 处 locator 与 page object 不一致: {summary}",
                suggestion="请统一步骤中的 locator_type 与 page object 定义",
                evidence={"mismatches": mismatches},
                passed=False,
            )

        return RuleResult(
            rule_id=self.rule_id, rule_name=self.rule_name,
            severity=self.severity, category=self.category,
            message="所有步骤 locator 与 page object 定义一致",
            passed=True,
        )
