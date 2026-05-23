import pytest

from runner.action_registry import ACTION_DEFINITIONS
from runner.yaml_executor import YamlExecutor


class FakeLocator:
    def __init__(self):
        self.fills = []
        self.clicks = 0

    def fill(self, value):
        self.fills.append(value)

    def click(self):
        self.clicks += 1


class FakePage:
    def __init__(self):
        self.locators = []
        self.roles = []
        self.fake_locator = FakeLocator()

    def locator(self, value):
        self.locators.append(value)
        return self.fake_locator

    def get_by_role(self, role, name):
        self.roles.append((role, name))
        return self.fake_locator


def test_executor_accepts_input_action_and_locator_value_alias():
    page = FakePage()
    executor = YamlExecutor(page=page, username="admin", password="macro123", base_url="http://localhost:8013/login#/login")

    executor.execute(
        {
            "execution": {
                "page": "login",
                "steps": [
                    {
                        "action": "input",
                        "target": "element:username_input",
                        "locator_type": "css",
                        "locator_value": "input[name='username']",
                        "value": "admin",
                    }
                ],
            }
        }
    )

    assert page.locators == ["input[name='username']"]
    assert page.fake_locator.fills == ["admin"]


def test_executor_infers_button_role_for_role_click_without_explicit_role():
    page = FakePage()
    executor = YamlExecutor(page=page, username="admin", password="macro123", base_url="http://localhost:8013/login#/login")

    executor.execute(
        {
            "execution": {
                "page": "login",
                "steps": [
                    {
                        "action": "click",
                        "target": "element:login_button",
                        "locator_type": "role",
                        "locator_value": "登录",
                    }
                ],
            }
        }
    )

    assert page.roles == [("button", "登录")]
    assert page.fake_locator.clicks == 1


def test_ai_generated_automated_case_requires_executable_assertion():
    page = FakePage()
    executor = YamlExecutor(page=page, username="admin", password="macro", base_url="http://localhost:5174/#/login")

    with pytest.raises(AssertionError, match="Executable assertion is required"):
        executor.execute(
            {
                "id": "mall-web-login-auth-fn-ai-0001",
                "status": "automated",
                "tags": ["ai-generated"],
                "expected_result": "页面跳转至平台工作台首页",
                "execution": {
                    "page": "login",
                    "steps": [
                        {
                            "action": "input",
                            "target": "element:username_input",
                            "locator_type": "css",
                            "locator_value": "input[name='username']",
                            "value": "test001",
                        }
                    ],
                },
            }
        )


def test_top_level_assertions_satisfy_ai_generated_assertion_gate(monkeypatch):
    page = FakePage()
    executed_assertions = []

    def fake_assert_url_action(page, locator, step, context, **kwargs):
        executed_assertions.append(step["value"])

    monkeypatch.setitem(
        ACTION_DEFINITIONS,
        "assert_url",
        {"handler": fake_assert_url_action, "requires_target": False},
    )
    executor = YamlExecutor(page=page, username="admin", password="macro", base_url="http://localhost:5174/#/login")

    executor.execute(
        {
            "id": "mall-web-login-auth-fn-ai-0001",
            "status": "automated",
            "tags": ["ai-generated"],
            "execution": {
                "page": "login",
                "steps": [
                    {
                        "action": "input",
                        "target": "element:username_input",
                        "locator_type": "css",
                        "locator_value": "input[name='username']",
                        "value": "admin",
                    }
                ],
            },
            "assertions": [
                {
                    "action": "assert_url",
                    "value": "/#/home",
                    "expected_result": "登录后进入首页",
                }
            ],
        }
    )

    assert executed_assertions == ["/#/home"]
