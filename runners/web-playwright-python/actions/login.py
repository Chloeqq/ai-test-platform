from pages.login_page import LoginPage


def login_action(page, locator, step, context, **kwargs):

    username = kwargs.get("username")
    password = kwargs.get("password")
    base_url = kwargs.get("base_url")

    login_page = LoginPage(page)

    login_page.goto(base_url)
    login_page.login(username, password)
    login_page.assert_login_success()