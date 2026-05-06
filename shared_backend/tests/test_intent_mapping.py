from __future__ import annotations

import pytest

from shared_backend.element_binding import build_element_alias_map
from shared_backend.intent_mapping import resolve_explicit_step


def test_resolve_explicit_step_maps_exact_alias_to_code() -> None:
    alias_map = build_element_alias_map(
        {
            "elements": {
                "login_button": {"selector": "登录", "element_name": "登录按钮", "aliases": ["登录"]},
                "home_menu": {"selector": "首页", "element_name": "首页菜单", "aliases": ["首页"]},
            }
        }
    )

    action, target, value = resolve_explicit_step(
        steps_hint=["click:登录按钮"],
        page="login",
        page_element_alias_map=alias_map,
    )

    assert action == "click"
    assert target == "login_button"
    assert value is None


def test_resolve_explicit_step_requires_explicit_target_for_click() -> None:
    with pytest.raises(ValueError, match="explicit target"):
        resolve_explicit_step(
            steps_hint=["click"],
            page="login",
            page_element_alias_map=build_element_alias_map({"elements": {"login_button": {"selector": "登录", "element_name": "登录按钮"}}}),
        )


def test_resolve_explicit_step_does_not_guess_from_title() -> None:
    with pytest.raises(ValueError, match="unsupported explicit step hint"):
        resolve_explicit_step(
            steps_hint=["whatever"],
            page="login",
            page_element_alias_map=build_element_alias_map({"elements": {"login_button": {"selector": "登录", "element_name": "登录按钮"}}}),
        )


def test_resolve_explicit_step_requires_explicit_route_for_goto() -> None:
    with pytest.raises(ValueError, match="explicit route"):
        resolve_explicit_step(
            steps_hint=["goto"],
            page="login",
            page_element_alias_map=build_element_alias_map({"elements": {"login_button": {"selector": "登录", "element_name": "登录按钮"}}}),
        )


def test_resolve_explicit_step_supports_assert_metric_alias() -> None:
    alias_map = build_element_alias_map(
        {
            "elements": {
                "weekly_sales_metric_label": {
                    "selector": "本周销售总额",
                    "element_name": "本周销售总额",
                    "aliases": ["销售总额"],
                }
            }
        }
    )

    action, target, value = resolve_explicit_step(
        steps_hint=["assert_number:销售总额>=1000"],
        page="home",
        page_element_alias_map=alias_map,
    )

    assert action == "assert_metric"
    assert target == "weekly_sales_metric_label"
    assert value == ">=1000"
