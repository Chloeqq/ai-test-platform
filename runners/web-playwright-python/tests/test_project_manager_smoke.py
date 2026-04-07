from __future__ import annotations

import json
from urllib.parse import urlsplit
from uuid import uuid4

import pytest
from playwright.sync_api import Page, expect


pytestmark = [pytest.mark.e2e, pytest.mark.smoke]


def _resolve_origin(base_url: str) -> str:
    parsed = urlsplit(str(base_url or "").strip())
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}"
    raise AssertionError(f"invalid base_url: {base_url}")


def _fetch_token(page: Page, *, origin: str, username: str, password: str) -> str:
    response = page.request.post(
        f"{origin}/api/auth/login",
        headers={"Content-Type": "application/json"},
        data=json.dumps({"username": username, "password": password}),
    )
    assert response.ok, f"login failed: status={response.status} body={response.text()}"
    payload = response.json()
    token = str(payload.get("access_token") or "").strip()
    assert token, "empty access_token from /api/auth/login"
    return token


def _open_cases_page(page: Page, *, origin: str, token: str) -> None:
    page.add_init_script(
        f"window.localStorage.setItem('ai_test_platform.access_token', {json.dumps(token)});"
    )
    page.goto(f"{origin}/cases?sort_dir=desc&sort_key=updated_at", wait_until="networkidle", timeout=30000)
    expect(page.locator("#btn-create-project")).to_be_visible()


def _open_project_manager(page: Page):
    page.click("#btn-create-project")
    dialog = page.locator("#project-manager-dialog")
    expect(dialog).to_be_visible()
    return dialog


def _wait_dialog_closed(page: Page) -> None:
    page.wait_for_function(
        """
        () => {
          const dialog = document.getElementById('project-manager-dialog');
          return Boolean(dialog) && !dialog.open;
        }
        """
    )


def _list_projects(page: Page, *, origin: str) -> list[dict]:
    response = page.request.get(f"{origin}/api/test-projects")
    assert response.ok, f"list projects failed: status={response.status}"
    payload = response.json()
    items = payload.get("items")
    assert isinstance(items, list), f"unexpected payload: {payload}"
    return [item for item in items if isinstance(item, dict)]


def test_project_manager_dialog_smoke(page: Page, base_url: str, test_username: str, test_password: str) -> None:
    origin = _resolve_origin(base_url)
    token = _fetch_token(page, origin=origin, username=test_username, password=test_password)
    project_code = f"pm{uuid4().hex[:6]}"
    project_name = f"Playwright Smoke {project_code}"
    updated_name = f"{project_name} Updated"

    try:
        _open_cases_page(page, origin=origin, token=token)

        _open_project_manager(page)
        page.click("#project-manager-new")
        page.fill("#project-manager-code", project_code)
        page.fill("#project-manager-name", project_name)
        page.fill("#project-manager-description", "created by playwright smoke")
        page.click("#project-manager-save")
        _wait_dialog_closed(page)

        created = next((item for item in _list_projects(page, origin=origin) if item.get("project_code") == project_code), None)
        assert created is not None, f"project not created: {project_code}"
        assert str(created.get("project_name") or "").strip() == project_name

        _open_project_manager(page)
        page.select_option("#project-manager-select", project_code)
        page.fill("#project-manager-name", updated_name)
        page.select_option("#project-manager-status", "inactive")
        page.click("#project-manager-save")
        _wait_dialog_closed(page)

        updated = next((item for item in _list_projects(page, origin=origin) if item.get("project_code") == project_code), None)
        assert updated is not None, f"project missing after update: {project_code}"
        assert str(updated.get("project_name") or "").strip() == updated_name
        assert str(updated.get("status") or "").strip() == "inactive"

        _open_project_manager(page)
        page.select_option("#project-manager-select", project_code)
        page.once("dialog", lambda dialog: dialog.accept())
        page.click("#project-manager-delete")
        expect(page.locator("#project-manager-message")).to_contain_text("已删除")

        deleted = next((item for item in _list_projects(page, origin=origin) if item.get("project_code") == project_code), None)
        assert deleted is None, f"project still exists after delete: {project_code}"
    finally:
        cleanup_response = page.request.delete(f"{origin}/api/test-projects/{project_code}")
        if cleanup_response.status not in {200, 404}:
            raise AssertionError(
                f"cleanup delete failed for {project_code}: "
                f"status={cleanup_response.status} body={cleanup_response.text()}"
            )
