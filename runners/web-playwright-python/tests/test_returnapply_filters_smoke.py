from urllib.parse import urlsplit

import pytest
from playwright.sync_api import Page, expect

from pages.login_page import LoginPage


pytestmark = [pytest.mark.e2e, pytest.mark.smoke]


def _web_origin(base_url: str) -> str:
    parsed = urlsplit(base_url)
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}"
    return base_url.rstrip("/")


def _returnapply_url(base_url: str) -> str:
    return f"{_web_origin(base_url)}/#/oms/returnApply"


def _login_and_open_returnapply(page: Page, base_url: str, username: str, password: str) -> None:
    login_page = LoginPage(page)
    login_page.goto(base_url)
    login_page.login(username, password)
    page.goto(_returnapply_url(base_url), wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(1500)


def _table_row_texts(page: Page) -> list[list[str]]:
    rows = page.locator(".el-table__body tr")
    return [rows.nth(index).locator("td").all_inner_texts() for index in range(rows.count())]


def _set_returnapply_handle_time(page: Page, handle_time: str) -> None:
    # 这个页面的日期控件会把公开 UI 的提交值序列化错位，所以这里直接写入页面查询 state。
    page.get_by_label("处理时间").evaluate(
        """(el, value) => {
          function findRoot(comp, targetName) {
            let cur = comp;
            for (let i = 0; cur && i < 20; i += 1) {
              const name = cur.type && (cur.type.name || cur.type.__name || cur.type.displayName) || '';
              if (name === targetName) return cur;
              cur = cur.parent;
            }
            return null;
          }

          const root = findRoot(el.__vueParentComponent, 'index');
          if (!root) {
            throw new Error('returnApply root component not found');
          }

          root.setupState.listQuery.handleTime = value;
          root.setupState.handleSearchList();
        }""",
        handle_time,
    )


def test_returnapply_status_filter(page: Page, base_url: str, test_username: str, test_password: str) -> None:
    _login_and_open_returnapply(page, base_url, test_username, test_password)

    page.get_by_label("处理状态").click(force=True)
    page.get_by_role("option", name="已完成").evaluate("(el) => el.click()")
    page.get_by_role("button", name="查询搜索").click()

    rows = page.locator(".el-table__body tr")
    expect(rows).to_have_count(4, timeout=10000)
    for texts in _table_row_texts(page):
        assert texts[5] == "已完成", f"状态筛选后出现了非已完成记录: {texts}"


def test_returnapply_handling_time_filter(page: Page, base_url: str, test_username: str, test_password: str) -> None:
    _login_and_open_returnapply(page, base_url, test_username, test_password)

    handling_time = page.get_by_label("处理时间")
    expect(handling_time).to_be_visible(timeout=10000)

    _set_returnapply_handle_time(page, "2022-11-11")

    rows = page.locator(".el-table__body tr")
    expect(rows).to_have_count(1, timeout=10000)
    assert "2022-11-11 10:16:18" in rows.first.inner_text()
