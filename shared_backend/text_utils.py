"""跨模块共享的文本处理工具。

被 2 个以上模块使用的文本匹配、否定检测、错误文案提取等工具函数，
统一放在这里。当前使用方：
- apps/web_ui_service/.../save_test_point_assets_service.py
- apps/web_ui_service/.../generate_pipeline_precondition.py
- 质量门禁规则（未来）
"""
from __future__ import annotations

import re

from .type_utils import str_value as _normalized_text

# ── 否定检测 ────────────────────────────────────────────────────────────────

NEGATION_WORDS: tuple[str, ...] = (
    "未", "不", "没有", "不会", "禁止", "无法", "不能",
)


def has_negation_before(text: str, targets: tuple[str, ...], *, window: int = 6) -> bool:
    """检查 text 中每个 target 前面 window 字内是否有否定词。

    例如:
        has_negation_before("未跳转回登录页", ("登录页",))  → True
        has_negation_before("自动跳转到登录页", ("登录页",))  → False
    """
    for target in targets:
        idx = text.find(target)
        if idx < 0:
            continue
        before = text[:idx]
        w = before[-window:] if len(before) >= window else before
        if any(nw in w for nw in NEGATION_WORDS):
            return True
    return False


# ── 错误文案提取 ────────────────────────────────────────────────────────────

# 匹配中英文引号内的文本
QUOTED_TEXT_PATTERN: str = r"[\"\"''](.*?)[\"\"'']"


def extract_error_message(expected_text: str, *, max_len: int = 80) -> str:
    """从预期结果文本中提取引号内的错误提示文案。

    输入: "页面提示'请输入账号'" 或 '页面提示"请输入账号"'
    输出: "请输入账号"
    无法提取时返回原文本的前 max_len 个字符。
    """
    expected_text = _normalized_text(expected_text)
    # 匹配引号内文案
    quoted = re.findall(QUOTED_TEXT_PATTERN, expected_text)
    if quoted:
        return quoted[0].strip()
    # 匹配 "提示：" 后面的部分
    for sep in ("提示：", "提示:", "显示：", "显示:", "错误：", "错误:"):
        if sep in expected_text:
            return expected_text.split(sep, 1)[1].strip()[:max_len]
    return expected_text.strip()[:max_len]
