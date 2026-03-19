import re

from playwright.sync_api import expect

from runner.variable_resolver import resolve_variables
from runner.url_utils import normalize_url_for_runner


def assert_url_action(page, locator, step, context, **kwargs):
    expected_url = step.get("value")

    if expected_url in (None, ""):
        raise ValueError("assert_url action requires a value")

    expected_url = resolve_variables(expected_url, context)
    expected_url = normalize_url_for_runner(str(expected_url), base_url=str(kwargs.get("base_url", "")))
    url_pattern = re.compile(rf".*{re.escape(str(expected_url))}.*")
    expect(page).to_have_url(url_pattern, timeout=10000)
