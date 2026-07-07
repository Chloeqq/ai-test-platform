"""规则共享工具函数。"""

from __future__ import annotations

import re
from typing import Any, Callable

# 结构化 precondition type 集合的唯一事实源在 shared_backend，此处 re-export
# 以兼容现有 `from ._common import PRECONDITION_TYPES` 调用点。
from shared_backend.quality_gate import PRECONDITION_TYPES  # noqa: F401

# 匹配 {{ variable_name }} 模板
_VAR_TEMPLATE_RE = re.compile(r"^\{\{\s*([A-Za-z_][A-Za-z0-9_.-]*)\s*\}\}$")

# Step check function type
_StepCheckFn = Callable[[list[dict[str, Any]]], bool]

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
    """返回检查函数：步骤中是否有断言且 target/expected/expected_result 含指定语义关键词。"""
    def check(steps: list[dict[str, Any]]) -> bool:
        return any(
            isinstance(s, dict)
            and normalized(s.get("action")) in {"assert_text", "assert_visible"}
            and any(
                kw in normalized(s.get("target", ""))
                or kw in normalized(s.get("expected", ""))
                or kw in normalized(s.get("expected_result", ""))
                for kw in keywords
            )
            for s in steps
        )
    return check


def has_assert_for_block_intercept() -> _StepCheckFn:
    """返回检查函数：步骤中是否有针对拒绝/阻断语义的断言。

    assert_url 在拦截/跳转场景中是合理断言（验证页面未跳转=被拦截）。
    """
    def check(steps: list[dict[str, Any]]) -> bool:
        return any(
            isinstance(s, dict)
            and normalized(s.get("action")) in {"assert_visible", "assert_text", "assert_url"}
            and any(
                kw in normalized(s.get("target", ""))
                or kw in normalized(s.get("expected", ""))
                or kw in normalized(s.get("expected_result", ""))
                or kw in normalized(str(s.get("value", "")))
                for kw in ("block", "intercept", "forbidden", "拒绝", "拦截", "禁止", "无权", "未登录")
            )
            for s in steps
        )
    return check


def has_assert_for_error_message() -> _StepCheckFn:
    """返回检查函数：步骤中是否有针对错误提示语义的断言。"""
    return has_assert_for_keywords(
        ("error", "toast", "message", "错误", "提示", "失败", "invalid")
    )
