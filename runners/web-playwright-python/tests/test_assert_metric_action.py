from __future__ import annotations

import pytest

from actions.assert_metric import assert_metric_action


class _FakeLocator:
    def __init__(self, text: str, *, parent: "_FakeLocator | None" = None) -> None:
        self._text = text
        self._parent = parent

    def count(self) -> int:
        return 1

    @property
    def first(self) -> "_FakeLocator":
        return self

    def text_content(self) -> str:
        return self._text

    def inner_text(self) -> str:
        return self._text

    def locator(self, query: str) -> "_FakeLocator":
        if query == "xpath=.." and self._parent is not None:
            return self._parent
        raise ValueError("no parent")


def test_assert_metric_extracts_value_from_parent_text() -> None:
    container = _FakeLocator("本周销售总额 12345")
    label = _FakeLocator("本周销售总额", parent=container)

    assert_metric_action(
        page=None,
        locator=label,
        step={"value": ">=10000", "metric_label": "本周销售总额"},
        context={},
    )


def test_assert_metric_supports_regex_and_numeric_type_rule() -> None:
    container = _FakeLocator("客单价: 88.50 元")
    label = _FakeLocator("客单价", parent=container)

    assert_metric_action(
        page=None,
        locator=label,
        step={
            "metric_rule": "regex:^\\d+\\.\\d{2}$",
            "extract_regex": r"客单价:\s*([0-9]+\.[0-9]{2})",
            "metric_label": "客单价",
        },
        context={},
    )


def test_assert_metric_raises_when_rule_not_met() -> None:
    container = _FakeLocator("本周订单数 8")
    label = _FakeLocator("本周订单数", parent=container)

    with pytest.raises(AssertionError, match="assert_metric failed"):
        assert_metric_action(
            page=None,
            locator=label,
            step={"rule": ">10", "metric_label": "本周订单数"},
            context={},
        )
