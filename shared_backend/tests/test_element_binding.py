from __future__ import annotations

import pytest

from shared_backend.element_binding import build_element_alias_map, resolve_involved_element_codes


def test_build_element_alias_map_resolves_common_login_aliases() -> None:
    page_object = {
        "elements": {
            "login_button": {"selector": "登录", "type": "role", "role": "button", "name": "登录按钮", "aliases": ["登录"]},
            "username_input": {
                "selector": "请输入用户名",
                "type": "role",
                "role": "textbox",
                "name": "用户名输入框",
                "aliases": ["账号输入框"],
            },
        }
    }

    alias_map = build_element_alias_map(page_object)

    assert alias_map["登录按钮"] == "login_button"
    assert alias_map["账号输入框"] == "username_input"


def test_resolve_involved_element_codes_returns_canonical_codes() -> None:
    page_object = {
        "elements": {
            "login_button": {"selector": "登录", "type": "role", "role": "button", "name": "登录按钮", "aliases": ["登录"]},
            "username_input": {
                "selector": "请输入用户名",
                "type": "role",
                "role": "textbox",
                "name": "用户名输入框",
                "aliases": ["账号输入框"],
            },
        }
    }

    codes, unknown = resolve_involved_element_codes(["账号输入框", "登录按钮"], page_object)

    assert codes == ["username_input", "login_button"]
    assert unknown == []


def test_build_element_alias_map_derives_role_suffix_aliases() -> None:
    page_object = {
        "elements": {
            "login_btn_auto": {"selector": "登录", "type": "role", "role": "button", "name": "录制元素1"},
            "username_auto": {"selector": "用户名", "type": "role", "role": "textbox", "name": "录制元素2"},
        }
    }

    alias_map = build_element_alias_map(page_object)

    assert alias_map["登录按钮"] == "login_btn_auto"
    assert alias_map["用户名输入框"] == "username_auto"


def test_build_element_alias_map_allows_same_code_to_repeat_alias() -> None:
    aliases = build_element_alias_map(
        {
            "elements": {
                "login-submit-btn": {
                    "selector": "login-submit-btn",
                    "element_name": "登录按钮",
                    "aliases": ["登录按钮"],
                }
            }
        }
    )

    assert aliases["登录按钮"] == "login-submit-btn"


def test_build_element_alias_map_rejects_alias_used_by_different_codes() -> None:
    with pytest.raises(ValueError, match="duplicate element alias"):
        build_element_alias_map(
            {
                "elements": {
                    "login-submit-btn": {"aliases": ["提交"]},
                    "register-submit-btn": {"aliases": ["提交"]},
                }
            }
        )
