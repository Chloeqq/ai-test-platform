from playwright.sync_api import Page, expect


class ProductPage:
    def __init__(self, page: Page):
        self.page = page

    def goto_product_menu(self) -> None:
        self.page.get_by_role("menuitem", name="商品").click()

    def assert_product_page_loaded(self) -> None:
        expect(self.page.get_by_role("menuitem", name="商品列表")).to_be_visible(timeout=10000)