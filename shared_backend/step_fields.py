"""execution.steps 字段名的唯一事实源。

背景：项目里至少 6 处独立维护"按固定字段列表重建 step 字典"的代码——每处
都是各自硬编码一份字段名，新增 DSL 字段（如 assert_attribute 的
attribute）必须同步改全部位置，但没有任何机制强制这一点。2026-06-29
debug 密码可见性切换用例时，正是因为 5 处里漏改了 1 处（
test_case_service.py 的 _productize_workbench_steps_for_script），
导致用例能生成、quality gate 也通过，但实际执行时 schema 校验失败——
从生成到发现问题中间隔了好几层，定位成本很高。

这个模块把字段列表集中到一处。各处仍然各自决定"具体怎么构造 dict"
（有的用 allowed_keys 元组配合 `in` 判断，有的是显式字面量），但字段
名称本身只在这里定义一份，新增字段时只改这一处，其余地方导入即可。
shared_backend/tests/test_step_field_consistency.py 用一个包含全部字段
的 step 跑过每个已知的重建函数，断言没有字段被静默丢弃。
"""
from __future__ import annotations

# DSL execution.steps 当前支持的全部字段（跨 action 类型的并集）。
# 新增字段时只改这里，然后跑 test_step_field_consistency.py 确认全部
# 重建函数都已同步。
STEP_FIELD_NAMES: frozenset[str] = frozenset(
    {
        "action",
        "target",
        "target_name",
        "value",
        "expected",
        "expected_result",
        "description",
        "page",
        "selector",
        "locator_type",
        "locator_value",
        "role",
        "intent_id",
        "element_code",
        "count",
        "metric_rule",
        "rule",
        "extract_regex",
        "metric_label",
        "attribute",
        "data_ref",
        "raw_text",
        "source_point_key",
        "traceability",
    }
)
