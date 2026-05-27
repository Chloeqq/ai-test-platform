from actions import assert_text as assert_text_module
from actions.assert_text import assert_text_action


class FakeLocator:
    def __init__(self, count_value: int = 1):
        self.count_value = count_value
        self.first = self

    def count(self):
        return self.count_value


class FakeExpectation:
    def __init__(self, calls: list[tuple[str, int]]):
        self.calls = calls

    def to_contain_text(self, value, timeout):
        self.calls.append((value, timeout))


def test_assert_text_contains_resolved_value(monkeypatch):
    calls: list[tuple[str, int]] = []

    def fake_expect(locator):
        return FakeExpectation(calls)

    monkeypatch.setattr(assert_text_module, "expect", fake_expect)

    assert_text_action(
        page=None,
        locator=FakeLocator(count_value=2),
        step={"action": "assert_text", "value": "欢迎 {{username}}"},
        context={"username": "admin"},
    )

    assert calls == [("欢迎 admin", 10000)]


def test_assert_text_requires_value():
    try:
        assert_text_action(
            page=None,
            locator=FakeLocator(),
            step={"action": "assert_text"},
            context={},
        )
    except ValueError as exc:
        assert "requires a value" in str(exc)
    else:
        raise AssertionError("assert_text_action should reject missing value")
