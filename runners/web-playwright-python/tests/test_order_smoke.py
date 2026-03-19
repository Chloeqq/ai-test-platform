import pytest

from pages.login_page import LoginPage
from pages.order_page import OrderPage


pytestmark = [pytest.mark.e2e, pytest.mark.smoke]


def test_order_smoke(page, base_url, test_username, test_password):
    login_page = LoginPage(page)
    order_page = OrderPage(page)

    login_page.goto(base_url)
    login_page.login(test_username, test_password)
    login_page.assert_login_success()

    order_page.goto_order_menu()
    order_page.assert_order_page_loaded()
