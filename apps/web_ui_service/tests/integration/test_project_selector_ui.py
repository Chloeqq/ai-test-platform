from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers.ui import router as ui_router
from app.routers.ui_assets_pages import router as ui_assets_pages_router
from app.routers.ui_governance_pages import router as ui_governance_pages_router
from app.routers.ui_operations_pages import router as ui_operations_pages_router


def _assert_react_shell(client: TestClient, path: str) -> None:
    response = client.get(path)
    assert response.status_code == 200
    html = response.text
    assert "/static/react/assets/main.css" in html
    assert "/static/react/assets/main.js" in html


def test_cases_and_workbench_generate_include_shared_project_selector_support() -> None:
    app = FastAPI()
    app.include_router(ui_assets_pages_router)
    app.include_router(ui_operations_pages_router)
    app.include_router(ui_governance_pages_router)
    client = TestClient(app)

    try:
        cases_resp = client.get("/cases", follow_redirects=False)
        assert cases_resp.status_code == 307
        assert cases_resp.headers.get("location", "").startswith("/react/cases")
        _assert_react_shell(client, "/react/cases")

        generate_resp = client.get("/ai-generation", follow_redirects=False)
        assert generate_resp.status_code == 307
        assert generate_resp.headers.get("location", "").startswith("/react/ai-generation")

        _assert_react_shell(client, "/react/ai-generation")

        workbench_resp = client.get("/execution/workbench", follow_redirects=False)
        assert workbench_resp.status_code == 307
        assert workbench_resp.headers.get("location", "").startswith("/react/execution/workbench")
        _assert_react_shell(client, "/react/execution/workbench")

        history_resp = client.get("/ai-generation/history", follow_redirects=False)
        assert history_resp.status_code == 307
        assert history_resp.headers.get("location", "").startswith("/react/ai-generation/history")

        _assert_react_shell(client, "/react/ai-generation/history")

        prompts_resp = client.get("/ai-generation/prompts", follow_redirects=False)
        assert prompts_resp.status_code == 307
        assert prompts_resp.headers.get("location", "").startswith("/react/ai-generation/prompts")

        plans_resp = client.get("/execution/plans", follow_redirects=False)
        assert plans_resp.status_code == 307
        assert plans_resp.headers.get("location", "").startswith("/react/execution/plans")

        flaky_resp = client.get("/quality/flaky", follow_redirects=False)
        assert flaky_resp.status_code == 307
        assert flaky_resp.headers.get("location", "").startswith("/react/quality/flaky")

        defects_resp = client.get("/defects", follow_redirects=False)
        assert defects_resp.status_code == 307
        assert defects_resp.headers.get("location", "").startswith("/react/defects")

        for legacy_path, react_prefix in [
            ("/cases/review", "/react/cases/review"),
            ("/cases/versions", "/react/cases/versions"),
            ("/cases/tags", "/react/cases/tags"),
            ("/assets/api-contracts", "/react/assets/api-contracts"),
            ("/assets/data-templates", "/react/assets/data-templates"),
            ("/system/environments", "/react/system/environments"),
            ("/system/nodes", "/react/system/nodes"),
            ("/system/integrations", "/react/system/integrations"),
            ("/system/roles", "/react/system/roles"),
        ]:
            redirect_resp = client.get(legacy_path, follow_redirects=False)
            assert redirect_resp.status_code == 307
            assert redirect_resp.headers.get("location", "").startswith(react_prefix)
            _assert_react_shell(client, react_prefix)

        runs_resp = client.get("/execution/runs", follow_redirects=False)
        assert runs_resp.status_code == 307
        assert runs_resp.headers.get("location", "").startswith("/react/execution/runs")

        _assert_react_shell(client, "/react/execution/runs")

        results_resp = client.get("/execution/results", follow_redirects=False)
        assert results_resp.status_code == 307
        assert results_resp.headers.get("location", "").startswith("/react/execution/results")

        failures_resp = client.get("/execution/results/failures?case_id=foo", follow_redirects=False)
        assert failures_resp.status_code == 307
        assert failures_resp.headers.get("location", "").startswith("/react/execution/results/failures?case_id=foo")

        _assert_react_shell(client, "/react/execution/results")
    finally:
        client.close()


def test_case_detail_page_redirects_to_react_detail() -> None:
    app = FastAPI()
    app.include_router(ui_assets_pages_router)
    app.include_router(ui_operations_pages_router)
    client = TestClient(app)

    try:
        detail_resp = client.get("/cases/atp-web-ret-query-sm-ai-0001", follow_redirects=False)
        assert detail_resp.status_code == 307
        assert detail_resp.headers.get("location", "").startswith("/react/cases/atp-web-ret-query-sm-ai-0001")
        _assert_react_shell(client, "/react/cases/atp-web-ret-query-sm-ai-0001")
    finally:
        client.close()


def test_ui_router_registers_each_primary_page_family_once() -> None:
    app = FastAPI()
    app.include_router(ui_router)

    route_counts: dict[str, int] = {}
    for route in app.routes:
        path = getattr(route, "path", None)
        if path is None:
            continue
        route_counts[path] = route_counts.get(path, 0) + 1

    assert route_counts["/cases"] == 1
    assert route_counts["/assets/cases"] == 1
    assert route_counts["/execution/workbench"] == 1
    assert route_counts["/ai-generation"] == 1
    assert route_counts["/ai-generation/history"] == 1
    assert route_counts["/ai-generation/prompts"] == 1
    assert route_counts["/execution/results"] == 1


def test_ui_router_rejects_deprecated_workbench_aliases() -> None:
    app = FastAPI()
    app.include_router(ui_router)
    client = TestClient(app)

    try:
        for path in [
            "/workbench",
            "/workbench/generate",
            "/workbench/history",
            "/workbench/preview",
            "/ai-orchestration",
            "/ai/prompt-management",
            "/report",
            "/reports/101",
        ]:
            assert client.get(path).status_code == 404
    finally:
        client.close()


def test_ui_router_redirects_dashboard_to_react() -> None:
    app = FastAPI()
    app.include_router(ui_router)
    client = TestClient(app)

    try:
        response = client.get("/dashboard", follow_redirects=False)
        assert response.status_code == 307
        assert response.headers.get("location", "").startswith("/react/dashboard")

        login_resp = client.get("/login?next=/execution/runs", follow_redirects=False)
        assert login_resp.status_code == 307
        assert login_resp.headers.get("location", "").startswith("/react/login?next=%2Fexecution%2Fruns")

        unsafe_login_resp = client.get("/login?next=//evil.example", follow_redirects=False)
        assert unsafe_login_resp.status_code == 307
        assert unsafe_login_resp.headers.get("location", "").startswith("/react/login?next=%2Fai-generation")
    finally:
        client.close()
