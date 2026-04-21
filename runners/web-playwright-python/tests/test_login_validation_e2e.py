"""登录页业务规则 E2E（需本地前端与 BASE_URL /账号环境变量）。

用法示例::

    cd runners/web-playwright-python
    source .venv/bin/activate
    export BASE_URL='http://localhost:5173/#/login'
    export TEST_USERNAME='你的账号'
    export TEST_PASSWORD='你的密码'
    # 可选：未登录不可访问的落地页（默认把 BASE_URL 里的 #/login 换成 #/）
    export E2E_PROTECTED_URL='http://localhost:5173/#/pms/product'
    pytest tests/test_login_validation_e2e.py -m e2e -v
"""

from __future__ import annotations

import os

import pytest
from playwright.sync_api import expect

from pages.login_page import LoginPage

pytestmark = [pytest.mark.e2e]


def _default_protected_url(base_url: str) -> str:
    if "#/login" in base_url:
        return base_url.replace("#/login", "#/")
    return base_url.rstrip("/") + "/#/"


@pytest.fixture(scope="session")
def protected_url(base_url: str) -> str:
    override = os.getenv("E2E_PROTECTED_URL", "").strip()
    if override:
        return override
    return _default_protected_url(base_url)


def test_correct_credentials_login_success(page, base_url, test_username, test_password):
    """正确账号密码可登录成功。"""
    login = LoginPage(page)
    login.goto(base_url)
    login.login(test_username, test_password)


def test_unauthenticated_redirect_or_blocked_from_home(page, base_url, protected_url):
    """未登录不能访问首页（或受保护路由）：应出现登录表单（或跳转到登录页）。"""
    login = LoginPage(page)
    login.goto(base_url)
    page.evaluate("() => { localStorage.clear(); sessionStorage.clear(); }")
    page.context.clear_cookies()

    page.goto(protected_url, wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(1500)

    expect(page.get_by_placeholder("请输入用户名")).to_be_visible(timeout=10000)


def test_empty_username_or_password_shows_message(page, base_url):
    """用户名或密码为空需要提示。"""
    login = LoginPage(page)
    login.goto(base_url)
    page.get_by_placeholder("请输入用户名").fill("")
    page.get_by_placeholder("请输入密码").fill("")
    login.click_login_button()
    page.wait_for_timeout(800)
    login.assert_text_matches_any(
        [
            r"请输入用户名",
            r"请输入密码",
            r"不能为空",
            r"必填",
            r"用户名为空",
            r"密码为空",
        ],
        timeout=8000,
    )


def test_wrong_password_shows_message(page, base_url, test_username):
    """账号密码错误需要提示。"""
    login = LoginPage(page)
    login.goto(base_url)
    login.fill_credentials(test_username, "__wrong_password_not_exist__")
    login.click_login_button()
    page.wait_for_timeout(1500)
    login.assert_text_matches_any(
        [
            r"密码错误",
            r"账号或密码",
            r"用户名或密码",
            r"登录失败",
            r"不正确",
            r"验证失败",
            r"错误",
        ],
        timeout=10000,
    )


def test_username_length_exceeded_shows_message(page, base_url, test_password):
    """用户名长度超限需要提示（默认尝试 300 个字符，可按应用调整）。"""
    login = LoginPage(page)
    login.goto(base_url)
    long_name = "a" * int(os.getenv("E2E_LONG_USERNAME_LEN", "300"))
    page.get_by_placeholder("请输入用户名").fill(long_name)
    page.get_by_placeholder("请输入密码").fill(test_password)
    login.click_login_button()
    page.wait_for_timeout(800)
    login.assert_text_matches_any(
        [
            r"长度",
            r"字符",
            r"超限",
            r"最多",
            r"不超过",
            r"超出",
            r"限{1,3}制",
            r"max",
        ],
        timeout=8000,
    )
