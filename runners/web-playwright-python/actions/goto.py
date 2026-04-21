from runner.url_utils import normalize_url_for_runner
from runner.variable_resolver import resolve_variables


def goto_action(page, locator, step, context, **kwargs):
    raw_url = step.get("url")
    if raw_url in (None, ""):
        raw_url = step.get("value")
    if raw_url in (None, ""):
        raw_url = step.get("target_url")
    if raw_url in (None, ""):
        raw_url = kwargs.get("base_url")

    if raw_url in (None, ""):
        raise ValueError("goto action requires one of: url, value, target_url, or base_url")

    resolved_url = resolve_variables(str(raw_url), context)
    normalized_url = normalize_url_for_runner(
        resolved_url,
        base_url=str(kwargs.get("base_url", "")),
    )
    page.goto(normalized_url, wait_until="networkidle")
