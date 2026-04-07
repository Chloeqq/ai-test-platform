from __future__ import annotations

from runner.locator_resolver import resolve_locator


class _FakePage:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...], dict[str, object]]] = []

    def get_by_placeholder(self, value: object) -> tuple[str, object]:
        self.calls.append(("get_by_placeholder", (value,), {}))
        return ("placeholder", value)

    def get_by_text(self, value: object) -> tuple[str, object]:
        self.calls.append(("get_by_text", (value,), {}))
        return ("text", value)

    def locator(self, value: object) -> tuple[str, object]:
        self.calls.append(("locator", (value,), {}))
        return ("locator", value)

    def get_by_role(self, role: object, *, name: object) -> tuple[str, object, object]:
        self.calls.append(("get_by_role", (role,), {"name": name}))
        return ("role", role, name)

    def get_by_test_id(self, value: object) -> tuple[str, object]:
        self.calls.append(("get_by_test_id", (value,), {}))
        return ("test_id", value)


def test_resolve_locator_supports_extended_locator_types() -> None:
    page = _FakePage()

    assert resolve_locator(page, {"locator_type": "id", "locator_value": "username"}) == ("locator", "#username")
    assert resolve_locator(page, {"locator_type": "name", "locator_value": "account"}) == (
        "locator",
        '[name="account"]',
    )
    assert resolve_locator(page, {"locator_type": "xpath", "locator_value": "//button[@id='submit']"}) == (
        "locator",
        "xpath=//button[@id='submit']",
    )
    assert resolve_locator(page, {"locator_type": "data-testid", "locator_value": "submit-btn"}) == (
        "test_id",
        "submit-btn",
    )


def test_resolve_locator_role_requires_role_field() -> None:
    page = _FakePage()
    try:
        resolve_locator(page, {"locator_type": "role", "locator_value": "提交"})
    except ValueError as exc:
        assert "role locator requires role field" in str(exc)
    else:
        raise AssertionError("expected ValueError for role locator without role")
