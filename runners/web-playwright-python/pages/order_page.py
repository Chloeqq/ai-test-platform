from playwright.sync_api import Page, expect


class OrderPage:
    def __init__(self, page: Page):
        self.page = page

    def goto_order_menu(self) -> None:
        self.page.get_by_role("menuitem", name="订单").click()

    def assert_order_page_loaded(self) -> None:
        expect(self.page.get_by_role("menuitem", name="订单列表")).to_be_visible(timeout=10000)