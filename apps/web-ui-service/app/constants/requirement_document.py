"""需求文档解析状态常量（单一事实源，避免字面量散落在 model/service/router）。

状态流转：PENDING → PARSED | PARTIAL | FAILED
- PENDING：已存档、尚未解析（落库初始态）
- PARSED ：解析成功且提取到文本
- PARTIAL：存档成功但未提取到任何文本内容
- FAILED ：解析抛错（原始文件仍保留，可后续重试）

注：Alembic 迁移不引用本模块（迁移是历史快照，须自包含），其 server_default
仍写字面量 "pending"，与 ParseStatus.PENDING 保持一致。
"""
from __future__ import annotations

from typing import Final


class ParseStatus:
    PENDING: Final[str] = "pending"
    PARSED: Final[str] = "parsed"
    PARTIAL: Final[str] = "partial"
    FAILED: Final[str] = "failed"


# 全部合法取值（校验/枚举用）。
PARSE_STATUSES: Final[frozenset[str]] = frozenset(
    {ParseStatus.PENDING, ParseStatus.PARSED, ParseStatus.PARTIAL, ParseStatus.FAILED}
)