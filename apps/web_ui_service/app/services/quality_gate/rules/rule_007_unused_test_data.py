"""UNUSED_TEST_DATA — data 段有值但无步骤消费。

检查 data 段中定义了值但未被任何步骤引用的 key。
与 RULE_002（步骤引用缺失 data）对称——RULE_002 检查"有引用无定义"，
RULE_007 检查"有定义无引用"。

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

from ._common import is_template, template_key


def _should_check_unused(data_entry: Any) -> bool:
    """判断 data 条目是否应被 RULE_007 检查。

    仅检查 inline 类型的非空字符串值。
    pool/env 是外部引用，"是否被使用"由外部系统决定，不在本规则范围。
    """
    if isinstance(data_entry, dict):
        if data_entry.get("source_type") != "inline":
            return False  # pool/env — 外部引用，跳过
        val = data_entry.get("value")
        return isinstance(val, str) and bool(val.strip())
    if isinstance(data_entry, str):
        return bool(data_entry.strip())
    return False


@register_rule(
    rule_id="RULE_007",
    rule_name="UNUSED_TEST_DATA",
    category=RuleCategory.DATA,
    severity=Severity.INFO,
    description="data 段有值但无步骤消费",
)
class UnusedTestDataRule(Rule):
    """检查 data 段中定义了非空值但未被步骤引用的 key。"""

    def validate(self, context: GateContext) -> RuleResult:
        case = context.case_yaml
        data = case.get("data") if isinstance(case.get("data"), dict) else {}
        execution = case.get("execution") if isinstance(case.get("execution"), dict) else {}
        steps = execution.get("steps") if isinstance(execution.get("steps"), list) else []
        variables = execution.get("variables") if isinstance(execution.get("variables"), dict) else {}

        # 构建 variable_name → data_key 反向映射
        var_to_data: dict[str, str] = {}
        for var_name, template in variables.items():
            if isinstance(template, str) and is_template(template):
                dk = template_key(template)
                if dk:
                    var_to_data[var_name] = dk

        # 收集所有被步骤引用的 data key。
        # 只扫描 step.value 字段——这是 DSL V1.1 的约定：
        # 模板变量（{{var}}）仅出现在 input/fill 的 value 字段中。
        # assert_text 的 expected 等字段若未来支持模板，需扩展此处。
        referenced_keys: set[str] = set()
        for step in steps:
            if not isinstance(step, dict):
                continue
            value = step.get("value")
            if not is_template(value):
                continue
            var_name = template_key(value)
            # 通过 variables 映射找到 data key。
            # fallback: 若 var_name 不在 variables 中，直接将变量名当作 data key。
            # 这与 RULE_002 和 runner 的变量解析逻辑一致，
            # 但意味着：若 variables 中有字面值变量恰好与 data key 同名，
            # 该 data key 会被标记为"已引用"而逃过检查。这是已知取舍。
            data_key = var_to_data.get(var_name, var_name)
            referenced_keys.add(data_key)

        # 找出 data 中有非空值但未被引用的 key
        unused: list[str] = []
        checkable_count = 0
        for data_key in sorted(data):
            if not _should_check_unused(data[data_key]):
                continue
            checkable_count += 1
            if data_key not in referenced_keys:
                unused.append(data_key)

        if unused:
            return RuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                severity=self.severity,
                category=self.category,
                message=(
                    f"发现 {len(unused)} 个未使用的 data key: {', '.join(unused)}。"
                    "这些 key 定义了值但未被任何步骤引用，可能是冗余数据或步骤遗漏。"
                ),
                suggestion="移除未使用的 data key，或确认是否遗漏了对应的步骤",
                evidence={
                    "unused_keys": unused,
                    "total_data_keys": len(data),
                    "checkable_count": checkable_count,
                    "referenced_keys": sorted(referenced_keys),
                },
                passed=False,
            )

        return RuleResult(
            rule_id=self.rule_id,
            rule_name=self.rule_name,
            severity=self.severity,
            category=self.category,
            message=(
                f"已检查 {checkable_count} 个可检查 data key（共 {len(data)} 个），"
                f"无未使用项"
            ),
            evidence={
                "unused_keys": [],
                "total_data_keys": len(data),
                "checkable_count": checkable_count,
                "referenced_keys": sorted(referenced_keys),
            },
            passed=True,
        )

