"""PAGE_OBJECT_MISMATCH — 步骤 locator 与 page object 定义不一致。

检查步骤中的 `locator_type` 是否与 page object 中对应 element 的定义一致。
elements 支持 dict 格式（有 element 定义可比较）和 list 格式（只有 code，跳过比较）。

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
        page_object = context.page_object
        if not isinstance(page_object, dict) or not page_object:
            return RuleResult(rule_id=self.rule_id, rule_name=self.rule_name,
                              severity=self.severity, category=self.category,
                              message="无 page object 数据，跳过", passed=True)

        elements = page_object.get("elements")
        if not isinstance(elements, dict):
            # list 格式或空 → 无法比较 locator_type（list 没有 element 定义细节）
            msg = ("page object 中 elements 为 list 格式，无法比较 locator_type"
                   if isinstance(elements, list) and elements
                   else "page object 中无 elements 定义")
            return RuleResult(rule_id=self.rule_id, rule_name=self.rule_name,
                              severity=self.severity, category=self.category,
                              message=msg, passed=True)

        execution = context.case_yaml.get("execution") if isinstance(context.case_yaml.get("execution"), dict) else {}
        steps = execution.get("steps") if isinstance(execution.get("steps"), list) else []
        if not steps:
            return RuleResult(rule_id=self.rule_id, rule_name=self.rule_name,
                              severity=self.severity, category=self.category,
                              message="无步骤数据", passed=True)

        mismatches: list[dict[str, Any]] = []
        checked = 0  # 实际检查的步骤数（有 element 引用 + 有 locator_type）

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
            if not step_locator_type:
                continue  # 步骤未声明 locator → 不需要检查

            checked += 1

            po_locator_type = normalized(element_def.get("locator_type", ""))
            po_role = normalized(element_def.get("role", ""))

            if po_role:
                if step_locator_type != "role":
                    mismatches.append({
                        "step_index": i,
                        "element": element_code,
                        "step_locator": step_locator_type,
                        "po_locator": f"role:{po_role}",
                    })
                continue

            if not po_locator_type:
                # element 定义无 locator_type 也无 role → 定义不完整，跳过但记录
                continue

            if step_locator_type != po_locator_type:
                mismatches.append({
                    "step_index": i,
                    "element": element_code,
                    "step_locator": step_locator_type,
                    "po_locator": po_locator_type,
                })

        if mismatches:
            summary = ", ".join(
                f"步骤{m['step_index']} {m['element']}: step={m['step_locator']} vs po={m['po_locator']}"
                for m in mismatches[:5]
            )
            return RuleResult(
                rule_id=self.rule_id, rule_name=self.rule_name,
                severity=self.severity, category=self.category,
                message=f"发现 {len(mismatches)} 处 locator 与 page object 不一致: {summary}",
                suggestion="请统一步骤中的 locator_type 与 page object 定义",
                evidence={"mismatches": mismatches, "checked": checked},
                passed=False,
            )

        return RuleResult(
            rule_id=self.rule_id, rule_name=self.rule_name,
            severity=self.severity, category=self.category,
            message=f"已检查 {checked} 个带 locator 的步骤，与 page object 定义一致",
            evidence={"checked": checked},
            passed=True,
        )
