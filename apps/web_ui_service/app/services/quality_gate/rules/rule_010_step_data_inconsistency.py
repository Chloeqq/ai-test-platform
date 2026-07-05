"""STEP_DATA_INCONSISTENCY — 步骤变量引用链断裂。

检查两个维度：
1. execution.variables 中被步骤实际引用的变量，其映射是否指向了不存在的 data key
2. input/fill 步骤数与去重后 data key 数是否存在结构性失衡

RULE_002 检查步骤→data 的单项可达性，本规则补充检查变量声明层的完整性和整体平衡性。

边界说明：
- RULE_002：逐步骤检查 {{var}} → variables → data 的可达性
- RULE_010：检查 variables 声明的完整性 + 步骤与 data 的结构性平衡
  未使用的变量声明只报 WARNING（死代码），被引用但不可达报 ERROR。

详见 docs/architecture/2026-06-17_Rule Catalog 规则目录.md
"""

from __future__ import annotations
from shared_backend.quality_gate import (
    GateContext,
    Rule,
    RuleCategory,
    RuleResult,
    Severity,
    register_rule,
)

from ._common import is_template, normalized, template_key


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

        errors: list[str] = []    # ERROR: 被引用的悬挂变量（会导致运行时失败）
        warnings: list[str] = []  # WARNING: 未引用的悬挂变量 / 结构性失衡

        # ── 1. 构建变量映射 + 收集步骤实际引用的变量 ──
        var_to_data: dict[str, str] = {}
        dangling_vars: set[str] = set()  # 声明的变量中 data_key 不存在的

        for var_name, tmpl in variables.items():
            if isinstance(tmpl, str) and is_template(tmpl):
                data_key = template_key(tmpl)
                if data_key:
                    var_to_data[var_name] = data_key
                    if data_key not in data:
                        dangling_vars.add(var_name)

        # 收集步骤中实际引用的变量名（从 {{var}} 模板中提取）
        referenced_vars: set[str] = set()
        for step in steps:
            if not isinstance(step, dict):
                continue
            value = step.get("value")
            if isinstance(value, str) and is_template(value):
                referenced_vars.add(template_key(value))

        # dangling 且被引用 → ERROR（运行时必然失败）
        # dangling 但未被引用 → WARNING（死代码）
        dangling_errors = dangling_vars & referenced_vars
        dangling_warnings = dangling_vars - referenced_vars

        if dangling_errors:
            errors.append(
                f"有 {len(dangling_errors)} 个被步骤引用的变量无法解析到 data: "
                + ", ".join(
                    f"'{v}' → '{{{{{var_to_data.get(v, '?')}}}}}'"
                    for v in sorted(dangling_errors)
                )
                + f"，但对应的 data key 不存在（data keys: {sorted(data.keys()) or ['(空)']})"
            )
        if dangling_warnings:
            warnings.append(
                f"execution.variables 中有 {len(dangling_warnings)} 个未使用的悬挂声明: "
                + ", ".join(
                    f"'{v}' → '{{{{{var_to_data.get(v, '?')}}}}}'"
                    for v in sorted(dangling_warnings)
                )
                + "（未被任何步骤引用，不影响执行）"
            )

        # ── 2. 检查 input/fill 步骤数与其引用的 data key 数的结构性失衡 ──
        input_step_indices: list[int] = []
        seen_keys: set[str] = set()
        resolved_data_keys: list[str] = []

        for i, step in enumerate(steps, start=1):
            if not isinstance(step, dict):
                continue
            if normalized(step.get("action")) not in {"input", "fill"}:
                continue

            value = step.get("value")
            if value is None:
                continue  # RULE_002 handles missing value
            if not is_template(value):
                continue  # literal values don't create data dependencies

            input_step_indices.append(i)
            var_name = template_key(str(value))
            data_key = var_to_data.get(var_name, var_name)
            if data_key not in seen_keys:
                seen_keys.add(data_key)
                resolved_data_keys.append(data_key)

        input_count = len(input_step_indices)
        data_key_count = len(resolved_data_keys)
        # 阈值选择：至少2步且差值≥2才告警。差值=1(如2步→1key)可能是同key合理复用。
        if input_count >= 2 and abs(input_count - data_key_count) >= 2:
            warnings.append(
                f"input/fill 步骤 {input_count} 个 (步骤 {', '.join(str(i) for i in input_step_indices)})，"
                f"但仅解析到 {data_key_count} 个不同的 data key ({', '.join(resolved_data_keys)})，"
                f"可能存在步骤与数据不匹配（也可能是同 key 合理复用，请人工确认）"
            )

        # ── 3. 汇总结果 ──
        all_issues = errors + warnings
        if all_issues:
            # 有 ERROR → result severity = ERROR；纯 WARNING → WARNING
            result_severity = Severity.ERROR if errors else Severity.WARNING
            return RuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                severity=result_severity,
                category=self.category,
                message=f"发现 {len(all_issues)} 个步骤数据不一致"
                        f"{' (' + str(len(errors)) + ' ERROR, ' + str(len(warnings)) + ' WARNING)' if errors and warnings else ''}",
                suggestion="请检查 execution.variables 的映射是否正确，"
                           "以及 input 步骤数与 data key 数是否匹配",
                evidence={"errors": errors, "warnings": warnings},
                passed=False,
            )

        # 统计实际被检查的内容
        var_count = len(var_to_data)
        template_step_count = input_count
        if var_count == 0 and template_step_count == 0:
            detail = "无变量映射和模板引用，无需检查"
        else:
            detail = (f"{var_count} 个变量映射, "
                      f"{template_step_count} 个模板引用步骤, "
                      f"均完整")
        return RuleResult(
            rule_id=self.rule_id,
            rule_name=self.rule_name,
            severity=self.severity,
            category=self.category,
            message=f"变量引用链完整: {detail}",
            passed=True,
        )
