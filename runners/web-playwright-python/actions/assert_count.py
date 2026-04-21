from __future__ import annotations

from playwright.sync_api import expect


def assert_count_action(page, locator, step, context, **kwargs):
    if locator is None:
        raise ValueError("assert_count action requires a resolved locator")

    raw_count = step.get("count")
    if raw_count is None:
        raw_count = step.get("value")
    if raw_count is None:
        raise ValueError("assert_count action requires count/value")
    try:
        expected_count = int(raw_count)
    except Exception as exc:
        raise ValueError(f"assert_count requires integer count, got: {raw_count}") from exc

    expect(locator).to_have_count(expected_count, timeout=10000)
