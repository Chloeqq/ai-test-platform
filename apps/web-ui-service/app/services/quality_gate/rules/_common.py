"""规则共享工具函数。

RULE_002 和 RULE_010 共用，避免重复定义。
"""

from __future__ import annotations

import re
from typing import Any

# 匹配 {{ variable_name }} 模板
_VAR_TEMPLATE_RE = re.compile(r"^\{\{\s*([A-Za-z_][A-Za-z0-9_.-]*)\s*\}\}$")


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
    """从 target 中提取 element code。支持 'element:xxx' 格式。"""
    if isinstance(target, str) and target.startswith("element:"):
        return target[len("element:"):]
    return ""
