from __future__ import annotations

import json
import os
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4

import pytest
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import expect, sync_playwright


WEB_UI_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = WEB_UI_ROOT.parents[1]


def _reserve_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen(1)
        return int(sock.getsockname()[1])


def _request_json(url: str, *, method: str = "GET", payload: dict[str, object] | None = None) -> dict[str, object]:
    body = None
    headers: dict[str, str] = {}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(url=url, data=body, method=method, headers=headers)
    with urlopen(request, timeout=10) as response:  # nosec B310
        return json.loads(response.read().decode("utf-8"))


def _wait_for_server(base_url: str, process: subprocess.Popen[str], *, timeout_seconds: float = 30.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error = ""
    while time.monotonic() < deadline:
        if process.poll() is not None:
            output = process.stdout.read() if process.stdout else ""
            raise RuntimeError(f"web-ui-service exited before ready: {output}")
        try:
            with urlopen(f"{base_url}/cases", timeout=2) as response:  # nosec B310
                body = response.read().decode("utf-8")
                if response.status == 200 and 'id="cases-shell"' in body:
                    return
        except (HTTPError, URLError, TimeoutError, ValueError) as exc:
            last_error = str(exc)
        time.sleep(0.5)
    output = process.stdout.read() if process.stdout else ""
    raise RuntimeError(f"web-ui-service did not become ready: {last_error}\n{output}")


@contextmanager
def _run_web_ui_server():
    with tempfile.TemporaryDirectory(prefix="cases-browser-") as temp_dir:
        db_path = Path(temp_dir) / "cases-browser.db"
        port = _reserve_free_port()
        env = os.environ.copy()
        env.update(
            {
                "APP_ENV": "test",
                "DATABASE_URL": f"sqlite:///{db_path}",
                "DATABASE_AUTO_CREATE_TABLES": "1",
                "REDIS_ENABLED": "0",
                "ORCHESTRATOR_URL": "",
                "PYTHONPATH": str(REPO_ROOT),
            }
        )
        process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)],
            cwd=WEB_UI_ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        base_url = f"http://127.0.0.1:{port}"
        try:
            _wait_for_server(base_url, process)
            yield base_url, db_path
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


def _create_case(
    base_url: str,
    *,
    name: str,
    product_line: str,
    module: str,
    creator: str,
    status: str,
    test_type: str,
) -> int:
    payload = _request_json(
        f"{base_url}/api/test-cases",
        method="POST",
        payload={
            "mode": "manual",
            "name": name,
            "product_line": product_line,
            "module": module,
            "priority": "P1",
            "test_type": test_type,
            "tags": ["browser", "cases"],
            "markers": ["smoke"],
            "creator": creator,
            "pytest_path": "tests/ui/browser/test_cases.py",
            "status": status,
            "script_code": "def test_browser_case():\n    assert True\n",
            "requirement": "",
            "data_config": {"enabled": False, "parameters": [], "rows": []},
        },
    )
    item = payload.get("item")
    if not isinstance(item, dict) or "id" not in item:
        raise RuntimeError("create case response missing item.id")
    return int(item["id"])


def _set_last_result(db_path: Path, case_id: int, result: str) -> None:
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "UPDATE test_cases SET last_execution_result = ? WHERE id = ?",
            (result, case_id),
        )
        connection.commit()


@pytest.mark.e2e
def test_cases_page_browser_flow_supports_search_context_actions() -> None:
    token = uuid4().hex[:8]
    product_line = f"E2E产品线-{token}"
    api_module = f"E2E模块API-{token}"
    ui_module = f"E2E模块UI-{token}"
    api_name = f"E2E-{token}-API"
    ui_name = f"E2E-{token}-UI"

    with _run_web_ui_server() as (base_url, db_path):
        api_case_id = _create_case(
            base_url,
            name=api_name,
            product_line=product_line,
            module=api_module,
            creator="qa-team",
            status="active",
            test_type="api",
        )
        ui_case_id = _create_case(
            base_url,
            name=ui_name,
            product_line=product_line,
            module=ui_module,
            creator="owner-ui",
            status="inactive",
            test_type="ui",
        )
        _set_last_result(db_path, api_case_id, "failed")
        _set_last_result(db_path, ui_case_id, "passed")

        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except PlaywrightError as exc:  # pragma: no cover - environment guard
                pytest.skip(f"Playwright browser unavailable: {exc}")

            try:
                page = browser.new_page()
                page.goto(f"{base_url}/cases", wait_until="networkidle", timeout=60000)

                page.locator("#search-input").fill(f"{token} 类型:api 状态:启用 创建人:qa 结果:失败")
                page.locator("#btn-search").click()

                search_context = page.locator("#cases-search-context")
                table_body = page.locator("#cases-table-body")

                expect(search_context).to_be_visible()
                expect(search_context).to_contain_text("当前搜索上下文")
                expect(search_context).to_contain_text("测试类型")
                expect(search_context).to_contain_text("状态")
                expect(search_context).to_contain_text("执行结果")
                expect(table_body).to_contain_text(api_name)
                expect(table_body).not_to_contain_text(ui_name)

                page.locator('[data-remove-key="creator"]').click()
                expect(page.locator("#search-input")).to_have_value(f"{token} 类型:api 状态:启用 结果:失败")
                expect(search_context).not_to_contain_text("创建人")
                expect(table_body).to_contain_text(api_name)
                expect(table_body).not_to_contain_text(ui_name)

                page.locator('[data-remove-key="status"]').click()
                expect(page.locator("#search-input")).to_have_value(f"{token} 类型:api 结果:失败")
                expect(search_context).not_to_contain_text("状态")
                expect(table_body).to_contain_text(api_name)
                expect(table_body).not_to_contain_text(ui_name)

                page.locator('[data-remove-key="last_result"]').click()
                expect(page.locator("#search-input")).to_have_value(f"{token} 类型:api")
                expect(search_context).not_to_contain_text("执行结果")
                expect(table_body).to_contain_text(api_name)
                expect(table_body).not_to_contain_text(ui_name)

                page.locator(f'[data-tree-action="module"][data-module="{api_module}"]').click()
                expect(search_context).to_contain_text(product_line)
                expect(search_context).to_contain_text(api_module)

                page.locator('[data-remove-key="product_line"]').click()
                expect(search_context).not_to_contain_text(product_line)
                expect(search_context).not_to_contain_text(api_module)

                page.locator("[data-clear-all-context]").click()
                expect(page.locator("#search-input")).to_have_value("")
                expect(search_context).to_have_attribute("hidden", "")
                expect(search_context).to_be_empty()
            finally:
                browser.close()
