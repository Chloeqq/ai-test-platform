"""规则共享工具函数。"""

from __future__ import annotations

import re
from typing import Any, Callable

# 匹配 {{ variable_name }} 模板
_VAR_TEMPLATE_RE = re.compile(r"^\{\{\s*([A-Za-z_][A-Za-z0-9_.-]*)\s*\}\}$")

# Step check function type
_StepCheckFn = Callable[[list[dict[str, Any]]], bool]

# Structured precondition types (shared with generate_pipeline_precondition)
PRECONDITION_TYPES: frozenset[str] = frozenset({
    "login", "account_state", "sql", "api_call",
})


def normalized(value: Any) -> str:
    """标准化字符串。"""
    return str(value or "").strip().lower()


def is_template(value: Any) -> bool:
    """检查值是否为 {{var}} 模板。"""
    return isinstance(value, str) and bool(_VAR_TEMPLATE_RE.match(value))


def template_key(value: str) -> str:
    """从 {{var}} 中提取变量名。"""
    m = _VAR_TEMPLATE_RE.match(value)
    return m.group(1) if m else ""


def extract_element_code(target: Any) -> str:
    """从 target 中提取 element code。支持 'element:xxx' 格式。返回空字符串表示无引用。"""
    if isinstance(target, str) and target.startswith("element:"):
        return target[len("element:"):].strip()
    return ""


# ── Shared _CHECKS lambdas (used by RULE_012 and RULE_015) ──────────────

def has_assert_for_keywords(keywords: tuple[str, ...]) -> _StepCheckFn:
    """返回检查函数：步骤中是否有断言且 target/expected 含指定语义关键词。"""
    def check(steps: list[dict[str, Any]]) -> bool:
        return any(
            isinstance(s, dict)
            and normalized(s.get("action")) in {"assert_text", "assert_visible"}
            and any(
                kw in normalized(s.get("target", ""))
                or kw in normalized(s.get("expected", ""))
                for kw in keywords
            )
            for s in steps
        )
    return check


def has_assert_for_block_intercept() -> _StepCheckFn:
    """返回检查函数：步骤中是否有针对拒绝/阻断语义的断言。"""
    return has_assert_for_keywords(
        ("block", "intercept", "forbidden", "拒绝", "拦截", "禁止", "无权")
    )


def has_assert_for_error_message() -> _StepCheckFn:
    """返回检查函数：步骤中是否有针对错误提示语义的断言。"""
    return has_assert_for_keywords(
        ("error", "toast", "message", "错误", "提示", "失败", "invalid")
    )
