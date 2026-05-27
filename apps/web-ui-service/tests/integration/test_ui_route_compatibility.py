from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient


WEB_UI_ROOT = Path(__file__).resolve().parents[2]
if str(WEB_UI_ROOT) not in sys.path:
    sys.path.insert(0, str(WEB_UI_ROOT))
existing_app = sys.modules.get("app")
if existing_app is not None and not getattr(existing_app, "__path__", None):
    sys.modules.pop("app", None)

from app.main import app  # noqa: E402


def test_legacy_report_redirect_preserves_execution_id() -> None:
    client = TestClient(app)

    response = client.get("/report/123", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "/reports/123"


def test_report_failures_route_is_not_shadowed_by_legacy_redirect() -> None:
    client = TestClient(app)

    response = client.get("/report/failures", follow_redirects=False)

    assert response.status_code == 200
    assert 'id="report-failures-shell"' in response.text


def test_canonical_routes_render_same_ui_shells() -> None:
    client = TestClient(app)

    expectations = {
        "/dashboard": 'id="dashboard-shell"',
        "/cases": 'id="cases-shell"',
        "/cases/review": 'id="management-console-shell"',
        "/ai-generation": 'id="workbench-generate-shell"',
        "/ai-generation/history": 'id="workbench-history-shell"',
        "/execution/workbench": 'id="workbench-shell"',
        "/execution/runs": "执行中心 - 执行任务",
        "/execution/results": 'id="report-overview-shell"',
        "/quality/failure-clusters": 'id="cluster-shell"',
        "/quality/gates": 'id="gate-console-shell"',
        "/system/roles": 'id="management-console-shell"',
    }

    for path, anchor in expectations.items():
        response = client.get(path, follow_redirects=False)
        assert response.status_code == 200
        assert anchor in response.text


def test_legacy_ui_aliases_still_work() -> None:
    client = TestClient(app)

    render_aliases = {
        "/workbench/generate": 'id="workbench-generate-shell"',
        "/workbench/history": 'id="workbench-history-shell"',
        "/workbench": 'id="workbench-shell"',
        "/assets/cases/review": 'id="management-console-shell"',
        "/quality/clusters": 'id="cluster-shell"',
        "/gate": 'id="gate-console-shell"',
    }

    for path, anchor in render_aliases.items():
        response = client.get(path, follow_redirects=False)
        assert response.status_code == 200
        assert anchor in response.text
