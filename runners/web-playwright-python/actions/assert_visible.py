from playwright.sync_api import expect


def assert_visible_action(page, locator, step, context, **kwargs):

    expect(locator).to_be_visible(timeout=10000)