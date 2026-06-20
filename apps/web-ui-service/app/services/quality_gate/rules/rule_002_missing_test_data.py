"""MISSING_TEST_DATA — 步骤引用的变量在 data 段中不存在。

检查 execution.steps 中每个 input/fill 步骤的 {{var}} 模板引用，
能否通过 execution.variables 映射在 data 段中找到对应的 key。

详见 docs/architecture/2026-06-17_Rule Catalog 规则目录.md
"""

from __future__ import annotations

import re
from typing import Any

from shared_backend.quality_gate import (
    GateContext,
    Rule,
    RuleCategory,
    RuleResult,
    Severity,
    register_rule,
)

# 匹配 {{ variable_name }} 模板
_VAR_TEMPLATE_RE = re.compile(r"^\{\{\s*([A-Za-z_][A-Za-z0-9_.-]*)\s*\}\}$")


def _is_template(value: Any) -> bool:
    """检查值是否为 {{var}} 模板。"""
    return isinstance(value, str) and bool(_VAR_TEMPLATE_RE.match(value))


def _template_key(value: str) -> str:
    """从 {{var}} 中提取变量名。"""
    m = _VAR_TEMPLATE_RE.match(value)
    return m.group(1) if m else ""


def _normalized(value: Any) -> str:
    """标准化字符串。"""
    return str(value or "").strip().lower()


def _step_element_code(step: dict[str, Any]) -> str:
    """从步骤中提取 element code。"""
    target = step.get("target", "")
    if isinstance(target, str) and target.startswith("element:"):
        return target[len("element:"):]
    return ""


@register_rule(
    rule_id="RULE_002",
    rule_name="MISSING_TEST_DATA",
    category=RuleCategory.DATA,
    severity=Severity.ERROR,
    description="步骤引用的变量在 data 段中不存在",
)
class MissingTestDataRule(Rule):
    """检查 input/fill 步骤的变量引用是否在 data 段有对应的 key。"""

    def validate(self, context: GateContext) -> RuleResult:
        case = context.case_yaml
        execution = case.get("execution") if isinstance(case.get("execution"), dict) else {}
        steps = execution.get("steps") if isinstance(execution.get("steps"), list) else []
        data = case.get("data") if isinstance(case.get("data"), dict) else {}
        variables = execution.get("variables") if isinstance(execution.get("variables"), dict) else {}

        # 构建 variable_name → data_key 的映射
        # 例: login_username → username (因为 variables 中 login_username: '{{username}}')
        var_to_data: dict[str, str] = {}
        for var_name, template in variables.items():
            if isinstance(template, str) and _is_template(template):
                data_key = _template_key(template)
                if data_key:
                    var_to_data[var_name] = data_key

        missing: list[str] = []

        for i, step in enumerate(steps, start=1):
            if not isinstance(step, dict):
                continue

            action = _normalized(step.get("action"))
            if action not in {"input", "fill"}:
                continue

            value = step.get("value")
            if value is None:
                # input 步骤完全没有 value 字段
                element = _step_element_code(step)
                missing.append(
                    f"步骤{i} (element: {element}): input 步骤缺少 value"
                )
                continue

            if not _is_template(value):
                # 字面值（如 "admin"），不需要 data key 映射
                continue

            # {{var}} 模板 → 解析变量链
            var_name = _template_key(value)
            # 1. 先查 variables 映射: var_name → data_key
            data_key = var_to_data.get(var_name, var_name)

            if data_key not in data:
                element = _step_element_code(step)
                if var_name != data_key:
                    missing.append(
                        f"步骤{i} (element: {element}): 变量 '{{{{{var_name}}}}}' "
                        f"→ '{{{{{data_key}}}}}', data key '{data_key}' 不存在"
                    )
                else:
                    missing.append(
                        f"步骤{i} (element: {element}): 变量 '{{{{{var_name}}}}}' "
                        f"引用的 data key '{data_key}' 不存在"
                    )

        if missing:
            return RuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                severity=self.severity,
                category=self.category,
                message=f"发现 {len(missing)} 个缺失的测试数据",
                suggestion="请在 data 段中添加缺失的 key，并确保 execution.variables 映射正确",
                evidence={"missing": missing},
                passed=False,
            )

        return RuleResult(
            rule_id=self.rule_id,
            rule_name=self.rule_name,
            severity=self.severity,
            category=self.category,
            message=f"已检查 {sum(1 for s in steps if isinstance(s, dict) and _normalized(s.get('action')) in {'input', 'fill'})} 个 input 步骤，数据完整",
            passed=True,
        )
