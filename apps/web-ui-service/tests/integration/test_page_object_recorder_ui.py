from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers.ui_assets_pages import router as ui_assets_pages_router


def test_page_object_recorder_ui_page_and_entry_link() -> None:
    app = FastAPI()
    app.include_router(ui_assets_pages_router)
    client = TestClient(app)

    try:
        recorder_resp = client.get("/assets/page-objects/recorder")
        assert recorder_resp.status_code == 200
        recorder_html = recorder_resp.text
        assert "页面对象录制" in recorder_html
        assert "/static/page_object_recorder.js" in recorder_html
        assert "/static/projects_api.js" in recorder_html
        assert "/static/project_manager_dialog.js" in recorder_html
        assert "/static/project_selector_support.js" in recorder_html
        assert 'id="rec-manage-project"' in recorder_html
        assert 'id="rec-project-code"' in recorder_html
        assert 'id="rec-create-case"' in recorder_html
        assert 'id="rec-clean-orphan"' in recorder_html

        list_resp = client.get("/assets/page-objects")
        assert list_resp.status_code == 200
        list_html = list_resp.text
        assert "/assets/page-objects/recorder" in list_html
        assert "页面对象列表" in list_html
        assert "/static/page_objects.js" in list_html
        assert "/static/projects_api.js" in list_html
        assert "/static/project_manager_dialog.js" in list_html
        assert "/static/project_selector_support.js" in list_html
        assert 'id="po-manage-project"' in list_html
    finally:
        client.close()
