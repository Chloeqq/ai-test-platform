"""跨模块共享的类型安全工具函数。"""
from __future__ import annotations

from typing import Any


def dict_value(value: Any) -> dict[str, Any]:
    """安全获取 dict 值，非 dict 返回空 dict。"""
    return value if isinstance(value, dict) else {}


def list_value(value: Any) -> list[Any]:
    """安全获取 list 值，非 list 返回空 list。"""
    return value if isinstance(value, list) else []


def int_value(value: Any, *, default: int = 0) -> int:
    """安全获取 int 值，转换失败返回 default。"""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def float_value(value: Any, *, default: float = 0.0) -> float:
    """安全获取 float 值，转换失败返回 default。"""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def str_value(value: Any, *, default: str = "") -> str:
    """安全获取 stripped 字符串。"""
    return str(value or "").strip() or default


def dedup_keep_order(items: list[str]) -> list[str]:
    """去重但保持原始顺序。"""
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result


def normalized_key(value: Any) -> str:
    """将值规范化为仅含字母数字的 key（用于 alias/element 匹配）。"""
    text = str_value(value).lower()
    return "".join(ch for ch in text if ch.isalnum())


def bounded_score(value: int | None, *, min_val: int = 0, max_val: int = 100) -> int:
    """将分数限制在 [min_val, max_val] 范围内。"""
    if value is None:
        return min_val
    return max(min_val, min(int(value), max_val))


def json_dict(value: Any) -> dict[str, Any]:
    """JSON-safe dict 转换。"""
    return value if isinstance(value, dict) else {}


def normalize_project_code(value: Any) -> str:
    """简单版 project_code 标准化：strip + lowercase，无长度校验。"""
    return str(value or "").strip().lower()


def normalize_project_code_strict(value: Any, *, min_len: int = 2, max_len: int = 20) -> str:
    """严格版 project_code 标准化：只保留字母数字，加长度校验。"""
    import re
    normalized = re.sub(r"[^a-zA-Z0-9]+", "", str(value or "").strip()).lower()
    if len(normalized) < min_len or len(normalized) > max_len:
        raise ValueError(f"project_code must be {min_len}-{max_len} letters or digits")
    return normalized


def json_list(value: Any) -> list[Any]:
    """JSON-safe list 转换。"""
    return value if isinstance(value, list) else []


def now_iso() -> str:
    """返回当前 UTC 时间 ISO 字符串。"""
    from datetime import datetime
    from shared_backend.datetime_compat import UTC
    return datetime.now(UTC).isoformat()
