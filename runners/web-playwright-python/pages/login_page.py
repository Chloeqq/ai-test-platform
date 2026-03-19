from playwright.sync_api import Page, expect


class LoginPage:
    def __init__(self, page: Page):
        self.page = page

    def goto(self, base_url: str) -> None:
        self.page.goto(base_url)
        self.page.wait_for_load_state("domcontentloaded")

    def login(self, username: str, password: str) -> None:
        self.page.get_by_placeholder("请输入用户名").fill(username)
        self.page.get_by_placeholder("请输入密码").fill(password)

        with self.page.expect_response(
            lambda resp: "/admin/login" in resp.url or "/login" in resp.url,
            timeout=10000
        ) as response_info:
            self.page.get_by_role("button", name="登录").click()

        response = response_info.value
        body = response.json()

        assert response.status == 200, f"Login response http status not 200: {response.status}"
        assert body["code"] == 200, f"Login failed: {body}"

    def assert_login_success(self) -> None:
        expect(self.page.get_by_role("menuitem", name="首页").first).to_be_visible(timeout=10000)

    def dump_page_text(self) -> None:
        print(self.page.locator("body").inner_text())