"""ASSERTION_TARGET_INVALID — 断言引用的目标元素类型不兼容。

只检查 assert_text 引用的元素 business_type 是否与文本断言兼容。
元素存在性由 RULE_006 (UNKNOWN_ELEMENT) 负责，本规则不重复检查。

RULE_006 vs RULE_009 职责边界:
────────────────────────────────────────────────────────────
             RULE_006                    RULE_009
────────────────────────────────────────────────────────────
检查范围     所有步骤 (input/click/     仅 assert_text
             assert_visible/text/url/..)
触发条件     element code 不在           element 存在 且
             page object 中注册           business_type 为纯视觉控件
问题         "这个元素存在吗?"           "这个元素能承载文本吗?"
────────────────────────────────────────────────────────────
互补示例:
  assert_text target=element:nonexistent → 006 报(不存在), 009 跳过
  assert_text target=element:slider      → 006 通过, 009 报(不兼容)
  assert_text target=element:toast       → 006 通过, 009 通过

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

# assert_text 明确不兼容的 business_type：纯视觉/交互控件，完全不承载可读文本。
# 使用白名单思路——只拦截确定不可能有文本的类型，其余默认放行，降低误报。
# 注意：button 可含文本("登录")、input 应使用 assert_value 但 assert_text 可能
#       读 aria-label 等可访问性文本 → 不放行也不拦截，规则不做判断。
_TEXT_INCOMPATIBLE_TYPES: frozenset[str] = frozenset({
    "slider",
    "scrollbar",
    "separator",
    "progressbar",
})


def _normalized(value: Any) -> str:
    return str(value or "").strip().lower()


def _extract_element_code(target: Any) -> str:
    """从 target 中提取 element code。支持 'element:xxx' 格式。"""
    if isinstance(target, str) and target.startswith("element:"):
        return target[len("element:"):]
    return ""


@register_rule(
    rule_id="RULE_009",
    rule_name="ASSERTION_TARGET_INVALID",
    category=RuleCategory.ASSERTION,
    severity=Severity.ERROR,
    description="assert_text 引用的元素 business_type 不兼容",
)
class AssertionTargetInvalidRule(Rule):
    """检查 assert_text 的 target 元素 business_type 是否兼容。"""

    def validate(self, context: GateContext) -> RuleResult:
        case = context.case_yaml
        execution = case.get("execution") if isinstance(case.get("execution"), dict) else {}
        steps = execution.get("steps") if isinstance(execution.get("steps"), list) else []
        page_object = context.page_object if isinstance(context.page_object, dict) else {}
        elements = page_object.get("elements") if isinstance(page_object.get("elements"), dict) else {}

        issues: list[str] = []
        checked = 0  # 实际被检查的断言步骤数（带 element 引用 + assert_text）

        for i, step in enumerate(steps, start=1):
            if not isinstance(step, dict):
                continue

            action = _normalized(step.get("action"))
            if action != "assert_text":
                continue  # assert_visible 适用于所有类型；assert_url 不绑定 element

            element_code = _extract_element_code(step.get("target", ""))
            if not element_code:
                continue  # 无 element 引用，跳过

            # 元素存在性由 RULE_006 负责，此处不重复检查
            element_def = elements.get(element_code)
            if not isinstance(element_def, dict):
                continue

            checked += 1
            business_type = _normalized(element_def.get("business_type", ""))
            if business_type in _TEXT_INCOMPATIBLE_TYPES:
                issues.append(
                    f"步骤{i} (assert_text): 元素 '{element_code}' "
                    f"business_type='{business_type}' 为纯视觉控件，"
                    f"不支持文本断言，建议改用 assert_visible"
                )

        if issues:
            return RuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                severity=self.severity,
                category=self.category,
                message=f"发现 {len(issues)} 个无效的断言目标",
                suggestion="请检查 assert_text 步骤的 element business_type 是否兼容",
                evidence={"issues": issues},
                passed=False,
            )

        return RuleResult(
            rule_id=self.rule_id,
            rule_name=self.rule_name,
            severity=self.severity,
            category=self.category,
            message=f"已检查 {checked} 个 assert_text 步骤，business_type 均兼容",
            passed=True,
        )
