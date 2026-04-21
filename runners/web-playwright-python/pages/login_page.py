from __future__ import annotations

import re

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError, expect


class LoginPage:
    def __init__(self, page: Page):
        self.page = page

    def goto(self, base_url: str) -> None:
        self.page.goto(base_url, wait_until="domcontentloaded", timeout=30000)
        self.page.wait_for_load_state("domcontentloaded")

    def fill_credentials(self, username: str, password: str) -> None:
        self.page.get_by_placeholder("请输入用户名").fill(username)
        self.page.get_by_placeholder("请输入密码").fill(password)

    def click_login_button(self) -> None:
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

    def login(self, username: str, password: str) -> None:
        self.fill_credentials(username, password)
        self.click_login_button()

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

    def assert_text_matches_any(self, patterns: list[str | re.Pattern], *, timeout: float = 8000) -> None:
        """Assert at least one pattern appears in visible page text (form error, toast, or message)."""
        rx = [re.compile(p) if isinstance(p, str) else p for p in patterns]
        per = max(2000, int(timeout) // max(1, len(rx)))
        last_err: AssertionError | None = None
        for r in rx:
            try:
                expect(self.page.locator("body")).to_contain_text(r, timeout=per)
                return
            except AssertionError as exc:
                last_err = exc
        raise AssertionError(f"no validation message matched any of {patterns!r}") from last_err

    def dump_page_text(self) -> None:
        print(self.page.locator("body").inner_text())
