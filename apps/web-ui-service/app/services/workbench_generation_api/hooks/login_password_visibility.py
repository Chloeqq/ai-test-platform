"""登录页密码可见性切换 Hook。

处理登录页专属逻辑：
- 密码可见性切换后补充 assert_attribute 断言验证 input[type]
- 前置条件"密码已切换为明文/密文"时补 UI 建立步骤
"""

from __future__ import annotations

from typing import Any

from shared_backend.step_fields import (
    ACTION_INPUT, ACTION_CLICK, ACTION_ASSERT_ATTRIBUTE,
)

from .. import constants as _c
from .base import PageHook


class LoginPasswordVisibilityHook(PageHook):
    """登录页密码可见性切换钩子。"""

    @property
    def page_code(self) -> str:
        return "login"

    # ── 前置条件 setup ──────────────────────────────────────────────────

    def setup_precondition_steps(self, precondition: str) -> list[dict[str, Any]]:
        return _precondition_setup(precondition)

    # ── click 后断言 ────────────────────────────────────────────────────

    def post_click_assertions(
        self, element_code: str, expected: str
    ) -> list[dict[str, Any]]:
        if element_code != _c.LOGIN_PASSWORD_TOGGLE_CODE:
            return []
        step = _assertion_step(expected)
        if step is None:
            return []
        return [step]


# ── 模块级函数（从原 save_test_point_assets_service.py 迁移）─────────────

def _resolve_visibility_state(expected: str) -> str | None:
    """从预期文本推断密码框的目标 type 属性值。

    规则：取"明文"/"密文"最后出现的位置判断目标态；
    两个词都没出现则退回到 token 集合匹配。
    无法判断返回 None。
    """
    from shared_backend.type_utils import str_value as _normalized_text
    normalized = _normalized_text(expected)
    plain_pos = normalized.rfind("明文")
    masked_pos = normalized.rfind("密文")
    if plain_pos < 0 and masked_pos < 0:
        if any(token in normalized for token in _c.PLAINTEXT_TOKENS):
            return _c.PASSWORD_VISIBILITY_TEXT
        elif any(token in normalized for token in _c.MASKED_TOKENS):
            return _c.PASSWORD_VISIBILITY_PASSWORD
        return None
    return _c.PASSWORD_VISIBILITY_TEXT if plain_pos > masked_pos else _c.PASSWORD_VISIBILITY_PASSWORD


def _assertion_step(expected: str) -> dict[str, Any] | None:
    """生成校验密码输入框 type 属性的断言步骤。"""
    expected_type = _resolve_visibility_state(expected)
    if expected_type is None:
        return None
    return {
        "action": ACTION_ASSERT_ATTRIBUTE,
        "target": f"{_c.ELEMENT_PREFIX}{_c.LOGIN_PASSWORD_INPUT_CODE}",
        "target_name": _c.LOGIN_PASSWORD_INPUT_NAME,
        "attribute": _c.ASSERT_ATTR_TYPE,
        "value": expected_type,
        "raw_text": expected,
    }


def _precondition_setup(precondition: str) -> list[dict[str, Any]]:
    """为密码可见性前置条件生成 UI 建立步骤。

    前置条件如"密码已切换为明文" → 先输入密码 + 必要时点击眼睛图标。
    """
    from shared_backend.type_utils import str_value as _normalized_text
    normalized = _normalized_text(precondition)
    if not any(token in normalized for token in _c.PASSWORD_VISIBILITY_TOKENS):
        return []

    target_state = _resolve_visibility_state(precondition)
    if target_state is None:
        return []

    setup: list[dict[str, Any]] = [
        {
            "action": ACTION_INPUT,
            "target": f"{_c.ELEMENT_PREFIX}{_c.LOGIN_PASSWORD_INPUT_CODE}",
            "target_name": _c.LOGIN_PASSWORD_INPUT_NAME,
            "data_ref": _c.PASSWORD_DATA_REF,
            "value": _c.DEFAULT_TEST_PASSWORD,
            "raw_text": _c.RAW_TEXT_PRERCOND_INPUT,
        }
    ]
    if target_state == _c.PASSWORD_VISIBILITY_TEXT:
        setup.append(
            {
                "action": ACTION_CLICK,
                "target": f"{_c.ELEMENT_PREFIX}{_c.LOGIN_PASSWORD_TOGGLE_CODE}",
                "target_name": _c.LOGIN_PASSWORD_TOGGLE_NAME,
                "raw_text": _c.RAW_TEXT_PRERCOND_TOGGLE,
            }
        )
    return setup
