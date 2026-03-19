from playwright.sync_api import expect


def _single_locator(locator):
    try:
        if locator.count() > 1:
            return locator.first
    except Exception:
        return locator
    return locator


def wait_for_action(page, locator, step, context, **kwargs):
    expect(_single_locator(locator)).to_be_visible(timeout=10000)
