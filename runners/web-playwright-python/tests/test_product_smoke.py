import pytest

from pages.login_page import LoginPage
from pages.product_page import ProductPage


pytestmark = [pytest.mark.e2e, pytest.mark.smoke]


def test_product_smoke(page, base_url, test_username, test_password):
    login_page = LoginPage(page)
    product_page = ProductPage(page)

    login_page.goto(base_url)
    login_page.login(test_username, test_password)
    login_page.assert_login_success()

    product_page.goto_product_menu()
    product_page.assert_product_page_loaded()
