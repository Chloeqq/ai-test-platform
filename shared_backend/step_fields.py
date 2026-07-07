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


# ── DSL Action 常量（唯一事实源）────────────────────────────────────────────
# 项目里至少 3 处各自定义 action 字符串（execution_compiler、intent_mapping、
# save_test_point_assets_service），新增 action 类型时必须同步改全部位置。
# 以下常量是唯一事实源，所有模块统一从这里导入。

ACTION_INPUT = "input"
ACTION_CLICK = "click"
ACTION_GOTO = "goto"
ACTION_ASSERT_VISIBLE = "assert_visible"
ACTION_ASSERT_TEXT = "assert_text"
ACTION_ASSERT_URL = "assert_url"
ACTION_ASSERT_ATTRIBUTE = "assert_attribute"
ACTION_ASSERT_METRIC = "assert_metric"
ACTION_WAIT = "wait_for"
ACTION_LOGIN = "login"
ACTION_CANDIDATE = "candidate_step"

# 所有可执行的 DSL action（用于 includes 校验）
ALL_DSL_ACTIONS: frozenset[str] = frozenset({
    ACTION_INPUT,
    ACTION_CLICK,
    ACTION_GOTO,
    ACTION_ASSERT_VISIBLE,
    ACTION_ASSERT_TEXT,
    ACTION_ASSERT_URL,
    ACTION_ASSERT_ATTRIBUTE,
    ACTION_ASSERT_METRIC,
    ACTION_WAIT,
    ACTION_LOGIN,
})


# ── steps_hint 协议常量 ──────────────────────────────────────────────────────
# 格式: "action:target=value"
#   - action 和 target 之间用 HINT_SEP_ACTION 分隔
#   - target 和 value 之间用 HINT_SEP_VALUE 分隔
#   - intent_mapping.py 还支持 HINT_SEP_ALT 作为备用分隔符
# 生成 steps_hint 统一用 format_steps_hint()，不要各自拼接字符串。

HINT_SEP_ACTION = ":"
HINT_SEP_VALUE = "="
HINT_SEP_ALT: tuple[str, ...] = ("::", "=>", "|")

# hint_value_map 解析时视为 input 动作的候选名
HINT_INPUT_ACTIONS: frozenset[str] = frozenset({"input", "fill"})


def format_steps_hint(action: str, target: str = "", value: str = "") -> str:
    """统一生成 steps_hint 字符串，避免各处自己拼接。

    >>> format_steps_hint("input", "用户名输入框", "")
    "input:用户名输入框="
    >>> format_steps_hint("click", "登录按钮")
    "click:登录按钮"
    >>> format_steps_hint("assert_text", "login_button", "请输入账号")
    "assert_text:login_button=请输入账号"
    """
    if not target:
        return action
    if not value:
        return f"{action}{HINT_SEP_ACTION}{target}"
    return f"{action}{HINT_SEP_ACTION}{target}{HINT_SEP_VALUE}{value}"
