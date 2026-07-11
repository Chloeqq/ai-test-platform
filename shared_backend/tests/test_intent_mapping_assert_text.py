from __future__ import annotations

import pytest

from shared_backend.element_binding import build_element_alias_map
from shared_backend.intent_mapping import resolve_explicit_step


def test_resolve_explicit_step_preserves_non_empty_assert_text_value() -> None:
    alias_map = build_element_alias_map(
        {
            "elements": {
                "login-error-tip": {
                    "selector": "login-error-tip",
                    "element_name": "登录错误提示",
                }
            }
        }
    )

    action, target, value = resolve_explicit_step(
        steps_hint=["assert_text:login-error-tip=请输入正确的用户名"],
        page="login",
        page_element_alias_map=alias_map,
    )

    assert action == "assert_text"
    assert target == "login-error-tip"
    assert value == "请输入正确的用户名"


def test_resolve_explicit_step_rejects_empty_assert_text_value() -> None:
    alias_map = build_element_alias_map(
        {
            "elements": {
                "login-error-tip": {
                    "selector": "login-error-tip",
                    "element_name": "登录错误提示",
                }
            }
        }
    )

    with pytest.raises(ValueError, match="assert_text step requires explicit expected value"):
        resolve_explicit_step(
            steps_hint=["assert_text:login-error-tip="],
            page="login",
            page_element_alias_map=alias_map,
        )
