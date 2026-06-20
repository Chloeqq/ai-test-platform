"""ASSERTION_TARGET_INVALID — 断言引用的目标元素无效。

检查 assert_visible / assert_text / assert_url 步骤的 target 引用：
1. 元素是否在 page object 中注册
2. assert_text 引用的元素 business_type 是否兼容（能展示文本内容）

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

# assert_text 不兼容的 business_type：这些元素不展示可读文本内容
_TEXT_INCOMPATIBLE_TYPES: frozenset[str] = frozenset({
    "button", "input", "text_input", "searchbox", "textarea",
    "password", "password_input", "checkbox", "radio", "switch",
    "password_toggle", "image", "icon", "spinbutton", "combobox",
    "slider", "progressbar", "scrollbar", "tab", "separator",
})


def _normalized(value: Any) -> str:
    return str(value or "").strip().lower()


def _extract_element_code(target: Any) -> str:
    """从 target 中提取 element code。支持 'element:xxx' 格式。"""
    if isinstance(target, str) and target.startswith("element:"):
        return target[len("element:"):]
    return ""


def _step_element_code(step: dict[str, Any]) -> str:
    return _extract_element_code(step.get("target", ""))


@register_rule(
    rule_id="RULE_009",
    rule_name="ASSERTION_TARGET_INVALID",
    category=RuleCategory.ASSERTION,
    severity=Severity.ERROR,
    description="断言引用的目标元素不存在或类型不兼容",
)
class AssertionTargetInvalidRule(Rule):
    """检查断言步骤的 target 引用是否有效。"""

    def validate(self, context: GateContext) -> RuleResult:
        case = context.case_yaml
        execution = case.get("execution") if isinstance(case.get("execution"), dict) else {}
        steps = execution.get("steps") if isinstance(execution.get("steps"), list) else []
        page_object = context.page_object if isinstance(context.page_object, dict) else {}
        elements = page_object.get("elements") if isinstance(page_object.get("elements"), dict) else {}

        issues: list[str] = []

        for i, step in enumerate(steps, start=1):
            if not isinstance(step, dict):
                continue

            action = _normalized(step.get("action"))
            if action not in {"assert_visible", "assert_text", "assert_url"}:
                continue

            element_code = _step_element_code(step)
            if not element_code:
                continue  # 无 element 引用，跳过

            # 检查 1：元素是否在 page object 中注册
            element_def = elements.get(element_code)
            if not isinstance(element_def, dict):
                issues.append(
                    f"步骤{i} ({action}): 元素 '{element_code}' 不在 page object 中"
                )
                continue

            # 检查 2：assert_text 的元素 business_type 是否兼容
            if action == "assert_text":
                business_type = _normalized(element_def.get("business_type", ""))
                if business_type in _TEXT_INCOMPATIBLE_TYPES:
                    issues.append(
                        f"步骤{i} (assert_text): 元素 '{element_code}' "
                        f"business_type='{business_type}' 不支持文本断言，"
                        f"建议改用 assert_visible"
                    )

        if issues:
            return RuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                severity=self.severity,
                category=self.category,
                message=f"发现 {len(issues)} 个无效的断言目标",
                suggestion="请检查断言步骤的 element 引用是否在 page object 中注册，"
                           "以及 assert_text 是否用于合适的元素类型",
                evidence={"issues": issues},
                passed=False,
            )

        assertion_count = sum(
            1 for s in steps
            if isinstance(s, dict) and _normalized(s.get("action")) in {"assert_visible", "assert_text", "assert_url"}
        )
        return RuleResult(
            rule_id=self.rule_id,
            rule_name=self.rule_name,
            severity=self.severity,
            category=self.category,
            message=f"已检查 {assertion_count} 个断言步骤，所有 target 引用有效",
            passed=True,
        )
