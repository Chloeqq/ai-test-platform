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
    page.goto(normalized_url, wait_until="commit", timeout=30000)
    try:
        page.wait_for_load_state("domcontentloaded", timeout=3000)
    except Exception:
        # In headed noVNC runs, Vite/Vue dev overlays can keep lifecycle events
        # flaky. Concrete element actions below are the reliable readiness gate.
        pass
    try:
        page.wait_for_load_state("load", timeout=3000)
    except Exception:
        # SPA/dev-server pages can keep requests open; element actions below
        # will still wait for the concrete target controls.
        pass
