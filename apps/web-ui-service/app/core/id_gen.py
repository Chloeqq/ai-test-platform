"""ID 生成工具 — 跨模块共享的标识符生成函数。"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

__all__ = [
    "REQUIREMENT_ID_PATTERN",
    "REQUIREMENT_VERSION_ID_PATTERN",
    "TEST_ASSET_ID_PATTERN",
    "TEST_ASSET_VERSION_ID_PATTERN",
    "TEST_ASSET_SOURCE_ID_PATTERN",
    "generate_case_id",
    "generate_run_id",
    "generate_item_id",
    "generate_result_id",
    "generate_dataset_id",
    "generate_requirement_id",
    "generate_requirement_version_id",
    "generate_test_asset_id",
    "generate_test_asset_version_id",
    "generate_test_asset_source_id",
    "hash_text_slug",
]


REQUIREMENT_ID_PATTERN = r"^req_[0-9a-f]{32}$"
REQUIREMENT_VERSION_ID_PATTERN = r"^reqv_[0-9a-f]{32}$"
TEST_ASSET_ID_PATTERN = r"^ta_[0-9a-f]{32}$"
TEST_ASSET_VERSION_ID_PATTERN = r"^tav_[0-9a-f]{32}$"
TEST_ASSET_SOURCE_ID_PATTERN = r"^tas_[0-9a-f]{32}$"


def _short_hex(length: int = 8) -> str:
    return uuid.uuid4().hex[:length]


def _generate_prefixed_uuid(prefix: str) -> str:
    """生成带领域前缀的完整 UUID4 hex 公共业务 ID。"""
    return f"{prefix}_{uuid.uuid4().hex}"


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


def generate_requirement_id() -> str:
    """生成需求公共 ID：req_<uuid4hex32>。"""
    return _generate_prefixed_uuid("req")


def generate_requirement_version_id() -> str:
    """生成需求版本公共 ID：reqv_<uuid4hex32>。"""
    return _generate_prefixed_uuid("reqv")


def generate_test_asset_id() -> str:
    """生成测试资产公共 ID：ta_<uuid4hex32>。"""
    return _generate_prefixed_uuid("ta")


def generate_test_asset_version_id() -> str:
    """生成测试资产版本公共 ID：tav_<uuid4hex32>。"""
    return _generate_prefixed_uuid("tav")


def generate_test_asset_source_id() -> str:
    """生成测试资产来源公共 ID：tas_<uuid4hex32>。"""
    return _generate_prefixed_uuid("tas")


def hash_text_slug(text: str) -> str:
    """对文本做 MD5 截断，生成短标识。"""
    import hashlib
    return hashlib.md5(text.encode()).hexdigest()[:8]
