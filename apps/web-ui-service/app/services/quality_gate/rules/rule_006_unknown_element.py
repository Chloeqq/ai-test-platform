"""UNKNOWN_ELEMENT — 步骤引用的 element code 不在 page object 中。

检查 execution.steps 中每个 target: element:xxx 引用的 element code
是否在对应 page object 的 elements 列表中注册。

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

# DSL 规定 target 前缀严格小写，大写形式（如 "Element:"）视为无效，不参与检查
_ELEMENT_PREFIX = "element:"


def _extract_element_code(target: Any) -> str | None:
    """从 target 字段提取 element code。

    仅处理严格小写前缀 "element:"，大写形式不匹配（DSL 约定）。
    """
    if isinstance(target, str) and target.startswith(_ELEMENT_PREFIX):
        code = target[len(_ELEMENT_PREFIX):].strip()
        return code if code else None
    return None


def _build_known_codes(elements: Any) -> set[str]:
    """从 page object 的 elements 字段构建已注册 code 集合。

    支持两种格式：
    - dict: {"login_btn": {...}, "username": {...}}  → keys 为 code
    - list: ["login_btn", "username", ...]           → 元素本身为 code
    """
    if isinstance(elements, dict):
        return set(elements.keys())
    if isinstance(elements, list):
        return {str(e) for e in elements if e}
    return set()


@register_rule(
    rule_id="RULE_006",
    rule_name="UNKNOWN_ELEMENT",
    category=RuleCategory.PAGE_OBJECT,
    severity=Severity.ERROR,
    description="步骤引用的 element code 不在 page object 中",
)
class UnknownElementRule(Rule):
    """检查步骤中引用的 element code 是否在 page object 中注册。

    等效于 DSL V1.1 编译器 bind_targets() 的 target_binding_failed 检查，
    将其纳入 Quality Gate 统一框架。
    """

    def validate(self, context: GateContext) -> RuleResult:
        case = context.case_yaml
        execution = case.get("execution") if isinstance(case.get("execution"), dict) else {}
        steps = execution.get("steps") if isinstance(execution.get("steps"), list) else []

        page_object = context.page_object
        if not isinstance(page_object, dict) or not page_object:
            return RuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                severity=self.severity,
                category=self.category,
                message="无 page object 数据，跳过元素校验",
                passed=True,
            )

        known_codes = _build_known_codes(page_object.get("elements"))

        # 收集所有步骤引用的 element code → 步骤编号列表（保留位置信息便于排查）
        referenced: dict[str, list[int]] = {}
        for i, step in enumerate(steps, start=1):
            if not isinstance(step, dict):
                continue
            code = _extract_element_code(step.get("target"))
            if code:
                referenced.setdefault(code, []).append(i)

        if not referenced:
            return RuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                severity=self.severity,
                category=self.category,
                message="步骤中无 element 引用",
                passed=True,
            )

        # 检查每个引用的 element 是否在 page object 中
        unknown = [
            {"code": code, "steps": referenced[code]}
            for code in sorted(referenced)
            if code not in known_codes
        ]

        if unknown:
            unknown_codes = [item["code"] for item in unknown]
            return RuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                severity=self.severity,
                category=self.category,
                message=(
                    f"发现 {len(unknown)} 个未知 element: {', '.join(unknown_codes)}。"
                    "这些 element code 不在 page object 的 elements 列表中，"
                    "运行时 locator 解析将失败。"
                ),
                suggestion=(
                    "在 page object YAML 中注册这些 element，"
                    "或修正步骤中的 element code 拼写"
                ),
                evidence={
                    "unknown_elements": unknown,
                    "referenced_count": len(referenced),
                    "page_object_page": page_object.get("page", ""),
                },
                passed=False,
            )

        return RuleResult(
            rule_id=self.rule_id,
            rule_name=self.rule_name,
            severity=self.severity,
            category=self.category,
            message=(
                f"已检查 {len(referenced)} 个 element 引用，"
                f"均在 page object 中注册"
            ),
            evidence={
                "referenced_elements": sorted(referenced.keys()),
                "referenced_count": len(referenced),
            },
            passed=True,
        )
