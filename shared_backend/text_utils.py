"""跨模块共享的文本处理工具。

被 2 个以上模块使用的文本匹配、否定检测、错误文案提取等工具函数，
统一放在这里。当前使用方：
- apps/web-ui-service/.../save_test_point_assets_service.py
- apps/web-ui-service/.../generate_pipeline_precondition.py
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


# ── 输入值提取 ────────────────────────────────────────────────────────────────

def extract_input_value(
    text: str,
    *,
    empty_tokens: tuple[str, ...] = (),
    space_token: str = "",
    input_value_pattern: str = "",
) -> tuple[bool, Any]:
    """从步骤自然语言中提取明确写出的输入值。

    不猜测未明确写出的值（如账号、密码、边界值）——那些由 steps_hint 或数据池提供。

    返回: (has_value, value)。has_value=False 表示未提取到值。

    匹配顺序：
    1. 空值 token（如"清空"/"留空"） → value=""
    2. 空格 token（如"空格"） → value=" "
    3. 引号内文本 → 提取第一对引号内的内容
    4. 正则模式（如匹配"输入xxx"后面的值）
    5. 未匹配 → (False, None)
    """
    normalized = _normalized_text(text)
    if empty_tokens and any(token in normalized for token in empty_tokens):
        return True, ""
    if space_token and space_token in normalized:
        return True, " "
    quoted = re.search(QUOTED_TEXT_PATTERN, normalized)
    if quoted is not None:
        return True, quoted.group(1)
    if input_value_pattern:
        matched = re.search(input_value_pattern, normalized)
        if matched is not None:
            return True, matched.group(1)
    return False, None
