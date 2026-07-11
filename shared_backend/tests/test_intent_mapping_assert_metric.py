from __future__ import annotations

import pytest

from shared_backend.element_binding import build_element_alias_map
from shared_backend.intent_mapping import resolve_explicit_step


def _alias_map() -> dict[str, str]:
    return build_element_alias_map(
        {
            "elements": {
                "login-count": {
                    "selector": "login-count",
                    "element_name": "登录次数",
                }
            }
        }
    )


def test_resolve_explicit_step_preserves_non_empty_assert_metric_rule() -> None:
    action, target, rule = resolve_explicit_step(
        steps_hint=["assert_metric:login-count=positive_integer"],
        page="login",
        page_element_alias_map=_alias_map(),
    )

    assert action == "assert_metric"
    assert target == "login-count"
    assert rule == "positive_integer"


def test_resolve_explicit_step_rejects_empty_assert_metric_rule() -> None:
    with pytest.raises(ValueError, match="assert_metric step requires explicit rule"):
        resolve_explicit_step(
            steps_hint=["assert_metric:login-count="],
            page="login",
            page_element_alias_map=_alias_map(),
        )
