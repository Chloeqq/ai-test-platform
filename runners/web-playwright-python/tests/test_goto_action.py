from actions.goto import goto_action


class FakePage:
    def __init__(self, *, fail_load: bool = False):
        self.fail_load = fail_load
        self.goto_calls = []
        self.load_state_calls = []

    def goto(self, url, **kwargs):
        self.goto_calls.append((url, kwargs))

    def wait_for_load_state(self, state, **kwargs):
        self.load_state_calls.append((state, kwargs))
        if self.fail_load:
            raise TimeoutError("load timeout")


def test_goto_action_uses_commit_for_spa_pages():
    page = FakePage()

    goto_action(
        page,
        locator=None,
        step={"value": "http://localhost:5174/#/login"},
        context={},
        base_url="http://localhost:8013/login#/login",
    )

    assert page.goto_calls == [
        (
            "http://host.docker.internal:5174/#/login",
            {"wait_until": "commit", "timeout": 30000},
        )
    ]
    assert page.load_state_calls == [
        ("domcontentloaded", {"timeout": 3000}),
        ("load", {"timeout": 3000}),
    ]


def test_goto_action_keeps_running_when_load_state_never_settles():
    page = FakePage(fail_load=True)

    goto_action(
        page,
        locator=None,
        step={"value": "http://localhost:5174/#/login"},
        context={},
        base_url="http://localhost:8013/login#/login",
    )

    assert page.goto_calls
    assert page.load_state_calls == [
        ("domcontentloaded", {"timeout": 3000}),
        ("load", {"timeout": 3000}),
    ]
