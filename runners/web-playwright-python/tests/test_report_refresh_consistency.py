from __future__ import annotations

import os
import time
from urllib import error as url_error
from urllib import parse as url_parse
from urllib import request as url_request

import pytest
from playwright.sync_api import Page


pytestmark = [pytest.mark.integration]


def _env_enabled(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _is_reachable(url: str, timeout: float = 3.0) -> bool:
    req = url_request.Request(url=url, method="GET")
    try:
        with url_request.urlopen(req, timeout=timeout) as resp:
            return int(getattr(resp, "status", 0) or 0) < 500
    except (url_error.URLError, TimeoutError, OSError):
        return False


def _wait_frame_src_change(page: Page, previous_src: str, timeout_seconds: float = 30.0) -> str:
    start = time.time()
    while time.time() - start < timeout_seconds:
        current = page.locator("#rp-allure-frame").get_attribute("src") or ""
        if current and current != previous_src:
            return current
        page.wait_for_timeout(200)
    raise AssertionError("allure frame src did not change after refresh")


def _extract_query_value(url: str, key: str) -> str:
    if not url:
        return ""
    query = url_parse.urlparse(url).query
    values = url_parse.parse_qs(query).get(key, [])
    return str(values[0]).strip() if values else ""


def test_report_allure_refresh_updates_frame_version(page: Page) -> None:
    if not _env_enabled("WEB_UI_REPORT_REFRESH_E2E", default=False):
        pytest.skip("set WEB_UI_REPORT_REFRESH_E2E=1 to enable browser-level report refresh consistency check")

    web_ui_base = os.getenv("WEB_UI_BASE_URL", "http://127.0.0.1:8013").rstrip("/")
    report_url = f"{web_ui_base}/report/allure"
    if not _is_reachable(report_url):
        pytest.skip(f"web-ui-service is not reachable: {report_url}")

    page.goto(report_url, wait_until="domcontentloaded", timeout=60000)
    page.locator("#rp-allure-refresh").wait_for(timeout=20000)
    page.locator("#rp-allure-frame").wait_for(timeout=20000)

    initial_src = page.locator("#rp-allure-frame").get_attribute("src") or ""
    assert initial_src, "allure frame src should not be empty after page load"
    initial_nonce = _extract_query_value(initial_src, "nonce")
    assert initial_nonce, "allure frame src should contain nonce query parameter"

    page.click("#rp-allure-refresh")
    page.wait_for_timeout(500)
    status_text = page.locator("#rp-allure-status").inner_text(timeout=30000)
    assert "失败" not in status_text, f"refresh status indicates failure: {status_text}"

    refreshed_src = _wait_frame_src_change(page, initial_src)
    refreshed_nonce = _extract_query_value(refreshed_src, "nonce")
    assert refreshed_nonce and refreshed_nonce != initial_nonce
    assert _extract_query_value(refreshed_src, "v"), "allure frame src should contain version query parameter"

    open_href = page.locator("#rp-allure-open").get_attribute("href") or ""
    assert open_href == refreshed_src, "open link should stay in sync with iframe src"
