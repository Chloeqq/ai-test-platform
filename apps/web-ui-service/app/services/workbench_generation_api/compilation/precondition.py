"""前置条件推断 — 为缺失前置条件的候选测试点补齐业务级前置条件。"""

from __future__ import annotations

from typing import Any

from shared_backend.type_utils import str_value as _normalized_text

from .. import constants as _c


def fallback_precondition(
    candidate: dict[str, Any], *, point_type: str, expected: str
) -> str:
    """补齐业务级前置条件；不补账号密码、不补环境地址。"""
    precondition = _normalized_text(candidate.get("precondition"))
    if precondition:
        return precondition
    merged = " ".join(
        _normalized_text(candidate.get(key))
        for key in ("title", "summary", "expected", "expected_result")
    )
    if any(token in merged for token in _c.LOGGED_IN_TOKENS):
        return _c.DEFAULT_PRECONDITION_LOGGED_IN
    if any(token in merged for token in _c.NOT_LOGGED_IN_TOKENS):
        return _c.DEFAULT_PRECONDITION_NOT_LOGGED_IN
    if point_type in _c.PRECONDITION_APPLICABLE_POINT_TYPES or "登录" in merged or expected:
        return _c.DEFAULT_PRECONDITION_LOGIN_PAGE
    return _c.FALLBACK_PRECONDITION
