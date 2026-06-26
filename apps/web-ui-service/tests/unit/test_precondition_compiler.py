"""Tests for the V2.0 precondition compiler.

覆盖：登录步骤动态生成（含元素缺失时的兜底）、身份数据池路由约定、
未知 precondition 类型报错。这些是 dev 分支新改动但此前零覆盖的代码路径。
"""
from __future__ import annotations

import pytest

from app.services.workbench_generation_compiler.runtime.generate_pipeline_precondition import (
    compile_preconditions,
    route_identity_data_to_pool,
)
from shared_backend.execution_compiler import ExecutionCompilerError


def _login_elements() -> dict[str, dict[str, str]]:
    return {
        "username_input": {"element_name": "用户名输入框", "locator_type": "css", "locator_value": "#user"},
        "password_input": {"element_name": "密码输入框", "locator_type": "css", "locator_value": "#pass"},
        "login_button": {"element_name": "登录按钮", "locator_type": "css", "locator_value": "#submit"},
        "home_menu": {"element_name": "首页菜单", "locator_type": "data-testid", "locator_value": "home"},
    }


def _login_product_yaml() -> dict:
    return {
        "preconditions": [
            {"type": "login", "data_ref": {"username": "username", "password": "password"}}
        ],
        "data": {
            "username": {"source_type": "inline", "value": "admin"},
            "password": {"source_type": "inline", "value": "secret"},
        },
        "execution": {"variables": {}, "steps": []},
    }


# ── route_identity_data_to_pool ──────────────────────────────────────────────

def test_route_identity_flips_inline_to_pool_with_convention() -> None:
    data = {
        "username": {"source_type": "inline", "value": "admin"},
        "password": {"source_type": "inline", "value": "secret"},
    }
    route_identity_data_to_pool(data, page="login", state="locked")
    assert data["username"] == {"source_type": "pool", "pool_name": "login", "key": "username_locked"}
    assert data["password"] == {"source_type": "pool", "pool_name": "login", "key": "password_locked"}


def test_route_identity_empty_page_falls_back_to_login() -> None:
    data = {"username": {"source_type": "inline", "value": "admin"}}
    route_identity_data_to_pool(data, page="", state="disabled")
    assert data["username"]["pool_name"] == "login"
    assert data["username"]["key"] == "username_disabled"


def test_route_identity_noop_when_state_empty() -> None:
    data = {"username": {"source_type": "inline", "value": "admin"}}
    route_identity_data_to_pool(data, page="login", state="")
    assert data["username"] == {"source_type": "inline", "value": "admin"}


def test_route_identity_leaves_non_identity_and_non_inline_untouched() -> None:
    data = {
        "amount": {"source_type": "inline", "value": "100"},            # 非身份键
        "username": {"source_type": "pool", "pool_name": "x", "key": "y"},  # 已是 pool
    }
    route_identity_data_to_pool(data, page="login", state="locked")
    assert data["amount"] == {"source_type": "inline", "value": "100"}
    assert data["username"] == {"source_type": "pool", "pool_name": "x", "key": "y"}


# ── compile_preconditions: login ─────────────────────────────────────────────

def test_login_compiles_full_step_sequence() -> None:
    product_yaml = _login_product_yaml()
    steps = compile_preconditions(
        product_yaml=product_yaml,
        page_object={"page": "login", "elements": _login_elements()},
    )
    assert [s["action"] for s in steps] == ["input", "input", "click", "assert_visible"]
    # 凭据变量已写入 execution.variables，Runner 才能解析 {{login_username}}
    assert product_yaml["execution"]["variables"]["login_username"] == "{{username}}"
    assert product_yaml["execution"]["variables"]["login_password"] == "{{password}}"
    # locator 信息从 page_object 复制
    assert steps[0]["locator_type"] == "css"
    assert steps[0]["locator_value"] == "#user"


def test_login_missing_home_menu_keeps_assert_with_fallback_locator() -> None:
    """home_menu 是登录成功的唯一验证 — 元素缺失时必须退回默认 locator，不能跳过。"""
    elements = _login_elements()
    del elements["home_menu"]
    steps = compile_preconditions(
        product_yaml=_login_product_yaml(),
        page_object={"page": "login", "elements": elements},
    )
    assert_steps = [s for s in steps if s["action"] == "assert_visible"]
    assert len(assert_steps) == 1, "登录成功断言不能被静默丢弃"
    assert assert_steps[0]["locator_type"] == "data-testid"
    assert assert_steps[0]["locator_value"] == "home-page"


def test_login_missing_input_element_skips_only_that_step() -> None:
    elements = _login_elements()
    del elements["username_input"]
    steps = compile_preconditions(
        product_yaml=_login_product_yaml(),
        page_object={"page": "login", "elements": elements},
    )
    actions = [s["action"] for s in steps]
    # username 的 input 被跳过，但 password input / click / assert 仍在
    assert actions == ["input", "click", "assert_visible"]


# ── compile_preconditions: account_state & validation ────────────────────────

def test_account_state_routes_identity_data_to_pool() -> None:
    product_yaml = {
        "preconditions": [{"type": "account_state", "state": "locked"}],
        "data": {"username": {"source_type": "inline", "value": "admin"}},
        "execution": {"variables": {}, "steps": []},
    }
    compile_preconditions(
        product_yaml=product_yaml,
        page_object={"page": "login", "elements": {}},
    )
    assert product_yaml["data"]["username"] == {
        "source_type": "pool", "pool_name": "login", "key": "username_locked",
    }


def test_unknown_precondition_type_raises() -> None:
    with pytest.raises(ExecutionCompilerError) as exc:
        compile_preconditions(
            product_yaml={"preconditions": [{"type": "teleport"}]},
            page_object={"page": "login", "elements": {}},
        )
    assert exc.value.code == "v2_0_unknown_precondition_type"


def test_reserved_precondition_type_raises_not_implemented() -> None:
    """api_call 已进入契约但无编译分支 — 必须硬失败，不能静默返回空步骤。"""
    with pytest.raises(ExecutionCompilerError) as exc:
        compile_preconditions(
            product_yaml={"preconditions": [{"type": "api_call"}]},
            page_object={"page": "login", "elements": {}},
        )
    assert exc.value.code == "v2_0_precondition_not_implemented"


def test_no_preconditions_returns_empty() -> None:
    assert compile_preconditions(product_yaml={}, page_object={}) == []
