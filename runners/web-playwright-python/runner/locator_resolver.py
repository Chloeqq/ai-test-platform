# mypy: ignore-errors

from playwright.sync_api import Page


def resolve_locator(page: Page, element: dict):
    locator_type = element.get("locator_type")
    locator_value = element.get("locator_value")
    role = element.get("role")

    if locator_type == "placeholder":
        return page.get_by_placeholder(locator_value)

    if locator_type == "text":
        return page.get_by_text(locator_value)

    if locator_type == "css":
        return page.locator(locator_value)

    if locator_type == "id":
        return page.locator(f"#{locator_value}")

    if locator_type == "name":
        return page.locator(f'[name="{locator_value}"]')

    if locator_type == "xpath":
        return page.locator(f"xpath={locator_value}")

    if locator_type == "data-testid":
        return page.get_by_test_id(locator_value)

    if locator_type == "role":
        if not role:
            raise ValueError("role locator requires role field")
        return page.get_by_role(role, name=locator_value)

    raise ValueError(f"Unsupported locator_type: {locator_type}")
