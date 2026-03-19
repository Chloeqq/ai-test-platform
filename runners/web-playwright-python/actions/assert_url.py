from playwright.sync_api import expect

from runner.variable_resolver import resolve_variables


def assert_url_action(page, locator, step, context, **kwargs):
    expected_url = step.get("value")

    if expected_url in (None, ""):
        raise ValueError("assert_url action requires a value")

    expected_url = resolve_variables(expected_url, context)
    expect(page).to_have_url(
        lambda url: expected_url in url,
        timeout=10000,
    )
