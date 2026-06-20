"""STEP_DATA_INCONSISTENCY — 步骤变量引用链断裂。

检查两个维度：
1. execution.variables 中的映射是否指向了不存在的 data key（声明了但不可解析的变量）
2. input/fill 步骤数与其引用的 data key 数是否存在结构性失衡

RULE_002 检查步骤→data 的单项可达性，本规则补充检查变量声明层的完整性和整体平衡性。

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

_VAR_TEMPLATE_RE = re.compile(r"^\{\{\s*([A-Za-z_][A-Za-z0-9_.-]*)\s*\}\}$")


def _normalized(value: Any) -> str:
    return str(value or "").strip().lower()


def _is_template(value: Any) -> bool:
    return isinstance(value, str) and bool(_VAR_TEMPLATE_RE.match(value))


def _template_key(value: str) -> str:
    m = _VAR_TEMPLATE_RE.match(value)
    return m.group(1) if m else ""


@register_rule(
    rule_id="RULE_010",
    rule_name="STEP_DATA_INCONSISTENCY",
    category=RuleCategory.STEP,
    severity=Severity.ERROR,
    description="步骤变量引用链断裂",
)
class StepDataInconsistencyRule(Rule):
    """检查变量声明层的完整性和步骤→数据的结构一致性。"""

    def validate(self, context: GateContext) -> RuleResult:
        case = context.case_yaml
        execution = case.get("execution") if isinstance(case.get("execution"), dict) else {}
        steps = execution.get("steps") if isinstance(execution.get("steps"), list) else []
        data = case.get("data") if isinstance(case.get("data"), dict) else {}
        variables = execution.get("variables") if isinstance(execution.get("variables"), dict) else {}

        issues: list[str] = []

        # ── 1. 检查 execution.variables 中的悬挂引用 ──
        #    变量声明了 var_name → {{data_key}}，但 data_key 在 data 中不存在
        var_to_data: dict[str, str] = {}
        dangling_vars: list[str] = []
        for var_name, template in variables.items():
            if isinstance(template, str) and _is_template(template):
                data_key = _template_key(template)
                if data_key:
                    var_to_data[var_name] = data_key
                    if data_key not in data:
                        dangling_vars.append(
                            f"变量 '{var_name}' → '{{{{{data_key}}}}}'，"
                            f"但 data key '{data_key}' 不存在"
                        )
        if dangling_vars:
            issues.append(
                f"execution.variables 中有 {len(dangling_vars)} 个悬挂引用: "
                + "; ".join(dangling_vars)
            )

        # ── 2. 检查 input/fill 步骤数与其引用的 data key 数的结构性失衡 ──
        input_step_indices: list[int] = []
        resolved_data_keys: list[str] = []

        for i, step in enumerate(steps, start=1):
            if not isinstance(step, dict):
                continue
            action = _normalized(step.get("action"))
            if action not in {"input", "fill"}:
                continue

            value = step.get("value")
            if value is None:
                continue  # missing value → RULE_002 handles this

            if _is_template(value):
                input_step_indices.append(i)
                var_name = _template_key(str(value))
                # resolve through variables → data
                data_key = var_to_data.get(var_name, var_name)
                if data_key not in resolved_data_keys:
                    resolved_data_keys.append(data_key)

        # 有模板引用的 input 步骤数 与 去重后的 data key 数 严重不匹配
        # 条件：至少 2 个 input 步骤，且差值 ≥ 2（如 3步骤→1key 或 4步骤→1key）
        input_count = len(input_step_indices)
        data_key_count = len(resolved_data_keys)
        if input_count >= 3 and abs(input_count - data_key_count) >= 2:
            issues.append(
                f"input/fill 步骤 {input_count} 个 (步骤 {', '.join(str(i) for i in input_step_indices)})，"
                f"但仅解析到 {data_key_count} 个不同的 data key ({', '.join(resolved_data_keys)})，"
                f"可能存在步骤与数据不匹配"
            )

        if issues:
            return RuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                severity=self.severity,
                category=self.category,
                message=f"发现 {len(issues)} 个步骤数据不一致",
                suggestion="请检查 execution.variables 的映射是否正确，"
                           "以及 input 步骤数与 data key 数是否匹配",
                evidence={"issues": issues},
                passed=False,
            )

        return RuleResult(
            rule_id=self.rule_id,
            rule_name=self.rule_name,
            severity=self.severity,
            category=self.category,
            message="变量引用链完整，步骤与数据一致性检查通过",
            passed=True,
        )
