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


def assert_attribute_action(page, locator, step, context, **kwargs):
    if locator is None:
        raise ValueError("assert_attribute action requires a resolved locator")

    attribute = step.get("attribute")
    if not attribute:
        raise ValueError("assert_attribute action requires an attribute name")

    expected_value = step.get("value")
    if expected_value in (None, ""):
        raise ValueError("assert_attribute action requires a value")

    expected_value = resolve_variables(expected_value, context)
    expect(_single_locator(locator)).to_have_attribute(str(attribute), str(expected_value), timeout=10000)
