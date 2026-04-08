from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers.ui_assets_pages import router as ui_assets_pages_router
from app.routers.ui_operations_pages import router as ui_operations_pages_router


def test_cases_and_workbench_generate_include_shared_project_selector_support() -> None:
    app = FastAPI()
    app.include_router(ui_assets_pages_router)
    app.include_router(ui_operations_pages_router)
    client = TestClient(app)

    try:
        cases_resp = client.get("/cases")
        assert cases_resp.status_code == 200
        cases_html = cases_resp.text
        assert "/static/projects_api.js" in cases_html
        assert "/static/project_manager_dialog.js" in cases_html
        assert "/static/project_selector_support.js" in cases_html
        assert 'id="btn-create-project"' in cases_html
        assert 'id="filter-project-code"' in cases_html

        generate_resp = client.get("/ai-generation")
        assert generate_resp.status_code == 200
        generate_html = generate_resp.text
        assert "/static/projects_api.js" in generate_html
        assert "/static/project_manager_dialog.js" in generate_html
        assert "/static/project_selector_support.js" in generate_html
        assert 'id="gen-create-project"' in generate_html
        assert 'id="gen-project"' in generate_html

        workbench_resp = client.get("/execution/workbench")
        assert workbench_resp.status_code == 200
        workbench_html = workbench_resp.text
        assert "/static/projects_api.js" in workbench_html
        assert "/static/project_manager_dialog.js" in workbench_html
        assert "/static/project_selector_support.js" in workbench_html
        assert 'id="wb-manage-project"' in workbench_html
        assert 'id="wb-project-governance-note"' in workbench_html

        history_resp = client.get("/ai-generation/history")
        assert history_resp.status_code == 200
        history_html = history_resp.text
        assert "/static/projects_api.js" in history_html
        assert "/static/project_manager_dialog.js" in history_html
        assert "/static/project_selector_support.js" in history_html
        assert 'id="wb-history-project"' in history_html
        assert 'id="wb-history-manage-project"' in history_html

        runs_resp = client.get("/execution/runs")
        assert runs_resp.status_code == 200
        runs_html = runs_resp.text
        assert "/static/projects_api.js" in runs_html
        assert "/static/project_manager_dialog.js" in runs_html
        assert "/static/project_selector_support.js" in runs_html
        assert 'id="er-filter-project"' in runs_html
        assert 'id="er-manage-project"' in runs_html
    finally:
        client.close()


def test_case_detail_page_includes_governance_note_placeholder() -> None:
    app = FastAPI()
    app.include_router(ui_assets_pages_router)
    client = TestClient(app)

    try:
        detail_resp = client.get("/cases/atp-web-ret-query-sm-ai-0001")
        assert detail_resp.status_code == 200
        detail_html = detail_resp.text
        assert 'id="case-detail-governance-note"' in detail_html
        assert "/static/case_detail.js" in detail_html
    finally:
        client.close()
