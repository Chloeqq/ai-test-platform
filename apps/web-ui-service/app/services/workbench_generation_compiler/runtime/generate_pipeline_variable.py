"""V3.0: $test_data.xxx.yyy 两级变量解析 — 编译器接受新格式,内部转 {{var}}。"""

from __future__ import annotations

import re as _re
from typing import Any

_TEST_DATA_REF_RE = _re.compile(
    r"^\$test_data\.([A-Za-z_][A-Za-z0-9_.-]*)\.([A-Za-z_][A-Za-z0-9_.-]*)$"
)


def _is_test_data_ref(value: Any) -> bool:
    """检查值是否为 $test_data.xxx.yyy 格式。"""
    return isinstance(value, str) and bool(_TEST_DATA_REF_RE.match(value.strip()))


def _parse_test_data_ref(value: str) -> tuple[str, str] | None:
    """解析 $test_data.xxx.yyy → (entry, field)。

    例: $test_data.user_001.username → ("user_001", "username")
    """
    if not isinstance(value, str):
        return None
    m = _TEST_DATA_REF_RE.match(value.strip())
    if not m:
        return None
    return m.group(1), m.group(2)
