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
