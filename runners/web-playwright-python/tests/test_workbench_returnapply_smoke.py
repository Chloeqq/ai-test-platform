import os
import re
from urllib.parse import parse_qs, urlparse

import pytest
from playwright.sync_api import Page, expect


pytestmark = [pytest.mark.e2e, pytest.mark.smoke]


def _web_ui_origin() -> str:
    raw = os.getenv("WEB_UI_BASE_URL", "http://127.0.0.1:8013").strip()
    parsed = urlparse(raw)
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}"
    return raw.rstrip("/")


def test_returnapply_sample_browser_flow(page: Page) -> None:
    origin = _web_ui_origin()

    page.goto(f"{origin}/workbench/generate", wait_until="networkidle", timeout=60000)
    expect(page.locator("#gen-returnflow-panel")).to_be_visible(timeout=10000)
    expect(page.locator("#gen-load-returnapply")).to_be_visible(timeout=10000)

    page.get_by_role("button", name="载入 returnApply 样板").click()

    expect(page.locator("#gen-page")).to_have_value("returnapply", timeout=10000)
    expect(page.locator("#gen-title")).to_have_value("returnApply 样板回归", timeout=10000)
    expect(page.locator("#gen-priority")).to_have_value("P1", timeout=10000)
    expect(page.locator("#gen-source")).to_have_value("regression", timeout=10000)
    expect(page.locator("#gen-tags")).to_have_value("ai-generated,smoke,returnapply", timeout=10000)
    expect(page.locator("#gen-page-urls")).to_have_value("http://localhost:5173/#/oms/returnApply", timeout=10000)
    expect(page.locator("#gen-requirement")).to_have_value(
        re.compile(r".*回流到工作台查看结果.*"),
        timeout=10000,
    )

    page.get_by_role("button", name="仅生成用例").click()
    expect(page.locator("#gen-result")).to_contain_text("生成成功", timeout=120000)

    workbench_href = page.locator("#gen-open-workbench").get_attribute("href") or ""
    assert "case_id=" in workbench_href, f"工作台回流链接未携带 case_id: {workbench_href}"
    case_id = parse_qs(urlparse(workbench_href).query).get("case_id", [""])[0]
    assert case_id, f"无法从工作台回流链接解析 case_id: {workbench_href}"

    page.locator("#gen-open-workbench").click()
    expect(page).to_have_url(re.compile(r".*/workbench(\?.*)?$"), timeout=60000)
    expect(page.locator("#wb-current-case")).to_contain_text(case_id, timeout=60000)
    expect(page.locator("#wb-yaml-editor")).to_have_value(re.compile(rf".*id:\s*{re.escape(case_id)}.*"), timeout=60000)
