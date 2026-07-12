"""统一 Token 估算。CJK chars/1.6 + others/4.0，阈值 env 可配。

所有数据来自 env 配置（无硬编码），供 web-ui-service 和 ai-orchestrator 共用。
"""
from __future__ import annotations

import os
import re
from typing import Any

# CJK 统一范围：基础区 + Ext-A + Ext-B+（`requirement_parse_support` 的精确正则）
_CJK_PATTERN = re.compile(r"[㐀-鿿豈-﫿\U00020000-\U0002ffff]")

# 默认阈值（env 可覆盖）
_DEFAULT_WARN_TOKENS = 8000
_DEFAULT_BLOCK_TOKENS = 16000
_CJK_RATIO = 1.6   # 约 1.6 个 CJK 字符 ≈ 1 token
_OTHER_RATIO = 4.0  # 约 4 个英文字符 ≈ 1 token


def _env_int(key: str, default: int) -> int:
    val = os.getenv(key, "").strip()
    if not val:
        return default
    try:
        return max(1, int(val))
    except ValueError:
        return default


def estimate_tokens(
    text: str,
    *,
    warn_tokens: int | None = None,
    block_tokens: int | None = None,
) -> dict[str, Any]:
    """估算输入 token 规模，返回 {tokens, char_count, cjk_count, level, warn_tokens, block_tokens, message}。

    参数:
        text: 待估算文本
        warn_tokens: 覆盖 env REQUIREMENT_SCOPE_WARN_TOKENS（None=从 env 读取）
        block_tokens: 覆盖 env REQUIREMENT_SCOPE_BLOCK_TOKENS（None=从 env 读取）
    """
    content = text or ""
    char_count = len(content)
    cjk_count = len(_CJK_PATTERN.findall(content))
    other_count = max(0, char_count - cjk_count)
    estimated = int(round(cjk_count / _CJK_RATIO + other_count / _OTHER_RATIO))

    w = warn_tokens if warn_tokens is not None else _env_int("REQUIREMENT_SCOPE_WARN_TOKENS", _DEFAULT_WARN_TOKENS)
    b = block_tokens if block_tokens is not None else _env_int("REQUIREMENT_SCOPE_BLOCK_TOKENS", _DEFAULT_BLOCK_TOKENS)
    if b <= w:
        b = w * 2

    if estimated >= b:
        level = "block"
        message = (
            f"预估输入约 {estimated} tokens（{char_count} 字），已超上限 {b}，"
            f"请缩小需求范围或拆分文档后再生成"
        )
    elif estimated >= w:
        level = "warn"
        message = (
            f"预估输入约 {estimated} tokens（{char_count} 字），内容较多，"
            f"建议缩小范围或降低目标数量，避免生成被截断"
        )
    else:
        level = "ok"
        message = f"预估输入约 {estimated} tokens（{char_count} 字），可正常生成"

    return {
        "estimated_tokens": estimated,
        "char_count": char_count,
        "cjk_count": cjk_count,
        "level": level,
        "warn_tokens": w,
        "block_tokens": b,
        "message": message,
    }
