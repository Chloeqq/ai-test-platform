from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError, expect


class LoginPage:
    def __init__(self, page: Page):
        self.page = page

    def goto(self, base_url: str) -> None:
        self.page.goto(base_url, wait_until="domcontentloaded", timeout=30000)
        self.page.wait_for_load_state("domcontentloaded")

    def login(self, username: str, password: str) -> None:
        self.page.get_by_placeholder("请输入用户名").fill(username)
        self.page.get_by_placeholder("请输入密码").fill(password)

        login_button = self.page.get_by_role("button", name="登录").first
        def submit(force: bool = False) -> None:
            login_button.click(timeout=5000, force=force)

        try:
            submit(force=False)
        except PlaywrightTimeoutError:
            try:
                submit(force=True)
            except PlaywrightTimeoutError:
                self.page.get_by_role("button", name="登录").first.evaluate("el => el.click()")

        try:
            self.page.wait_for_load_state("networkidle", timeout=5000)
        except Exception:
            pass

        self.page.wait_for_timeout(1200)

        if "#/login" in self.page.url:
            raise AssertionError(f"Login did not redirect away from login page: {self.page.url}")

        self.assert_login_success()

    def assert_login_success(self) -> None:
        expect(self.page.get_by_role("menuitem", name="首页").first).to_be_visible(timeout=10000)

    def dump_page_text(self) -> None:
        print(self.page.locator("body").inner_text())
