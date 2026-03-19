import pytest

from pages.login_page import LoginPage


pytestmark = [pytest.mark.e2e, pytest.mark.smoke]


def test_login_smoke(page, base_url, test_username, test_password):
    login_page = LoginPage(page)

    login_page.goto(base_url)
    login_page.login(test_username, test_password)
    login_page.assert_login_success()
