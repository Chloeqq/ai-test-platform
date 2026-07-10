"""ID 生成工具 — 跨模块共享的标识符生成函数。"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

__all__ = [
    "generate_case_id",
    "generate_run_id",
    "generate_item_id",
    "generate_result_id",
    "generate_dataset_id",
    "hash_text_slug",
]


def _short_hex(length: int = 8) -> str:
    return uuid.uuid4().hex[:length]


def generate_case_id() -> str:
    """生成测试用例 ID：case-xxxxxxxxxxxx"""
    return f"case-{_short_hex(12)}"


def generate_run_id() -> str:
    """生成评测运行 ID：run-YYYYMMDD-HHMMSS-xxxxxx"""
    ts = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    return f"run-{ts}-{_short_hex(6)}"


def generate_item_id(index: int) -> str:
    """生成评测条目 ID：it-001, it-002, ..."""
    return f"it-{index:03d}"


def generate_result_id() -> str:
    """生成评测结果 ID：res-xxxxxxxxxxxx"""
    return f"res-{_short_hex(12)}"


def generate_dataset_id(task_type: str) -> str:
    """生成数据集 ID：de-<task_type>-xxxxxx"""
    safe_type = task_type.replace("_", "-")[:30]
    return f"de-{safe_type}-{_short_hex(6)}"


def hash_text_slug(text: str) -> str:
    """对文本做 MD5 截断，生成短标识。"""
    import hashlib
    return hashlib.md5(text.encode()).hexdigest()[:8]
