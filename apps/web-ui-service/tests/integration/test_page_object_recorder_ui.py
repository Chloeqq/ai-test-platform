from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers.ui_assets_pages import router as ui_assets_pages_router
from app.routers.ui_operations_pages import router as ui_operations_pages_router


def test_page_object_recorder_ui_page_and_entry_link() -> None:
    app = FastAPI()
    app.include_router(ui_assets_pages_router)
    app.include_router(ui_operations_pages_router)
    client = TestClient(app)

    try:
        recorder_resp = client.get("/assets/page-objects/recorder", follow_redirects=False)
        assert recorder_resp.status_code == 307
        assert recorder_resp.headers.get("location", "").startswith("/react/assets/page-objects/recorder")

        recorder_react_resp = client.get("/react/assets/page-objects/recorder")
        assert recorder_react_resp.status_code == 200
        recorder_react_html = recorder_react_resp.text
        assert "/static/react/assets/main.css" in recorder_react_html
        assert "/static/react/assets/main.js" in recorder_react_html

        list_resp = client.get("/assets/page-objects", follow_redirects=False)
        assert list_resp.status_code == 307
        assert list_resp.headers.get("location", "").startswith("/react/assets/page-objects")

        list_react_resp = client.get("/react/assets/page-objects")
        assert list_react_resp.status_code == 200
        list_react_html = list_react_resp.text
        assert "/static/react/assets/main.css" in list_react_html
        assert "/static/react/assets/main.js" in list_react_html
    finally:
        client.close()
