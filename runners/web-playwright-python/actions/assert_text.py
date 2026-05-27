from __future__ import annotations

from playwright.sync_api import expect

from runner.variable_resolver import resolve_variables


def _single_locator(locator):
    try:
        if locator.count() > 1:
            return locator.first
    except Exception:
        return locator
    return locator


def assert_text_action(page, locator, step, context, **kwargs):
    if locator is None:
        raise ValueError("assert_text action requires a resolved locator")

    expected_text = step.get("value")
    if expected_text in (None, ""):
        raise ValueError("assert_text action requires a value")

    expected_text = resolve_variables(expected_text, context)
    expect(_single_locator(locator)).to_contain_text(str(expected_text), timeout=10000)
