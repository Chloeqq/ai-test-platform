import sys
from pathlib import Path

import pytest


pytestmark = [pytest.mark.integration]


PROJECT_ROOT = Path(__file__).resolve().parents[4]
SRC_ROOT = PROJECT_ROOT / "apps" / "ai-orchestrator" / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from app import create_app


class FakeService:
    def get_latest_report(self):
        return {
            "report": {
                "case_id": "TC-PRODUCT-999",
                "status": "passed",
                "summary": "Latest fake report",
            },
            "report_json_path": "/tmp/TC-PRODUCT-999.report.json",
            "report_markdown_path": "/tmp/TC-PRODUCT-999.report.md",
            "report_summary_path": "/tmp/report_summary.txt",
            "report_summary_preview": {
                "total_failed_cases": 0,
                "environment_failures": 0,
                "business_failures": 0,
                "high_risk_failures": 0,
                "actionable_self_healing_cases": 0,
                "environment_failure_cases": [],
                "actionable_self_healing_case_details": [],
            },
        }


class FakeAssetService:
    def list_scaffold_templates(self):
        return {
            "templates": [
                {
                    "name": "catalog",
                    "summary": "商品目录/搜索结果类页面骨架",
                }
            ]
        }


@pytest.fixture
def flask_client():
    app = create_app(service=FakeService(), asset_service=FakeAssetService())
    app.config["TESTING"] = True
    return app.test_client()


def test_flask_client_health_returns_ok(flask_client):
    response = flask_client.get("/health")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_flask_client_console_returns_html(flask_client):
    response = flask_client.get("/console")

    assert response.status_code == 200
    assert "text/html" in response.content_type
    assert "Scaffold Console" in response.get_data(as_text=True)


def test_flask_client_latest_report_returns_summary_preview(flask_client):
    response = flask_client.get("/reports/latest")

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["report"]["case_id"] == "TC-PRODUCT-999"
    assert payload["report_summary_preview"]["total_failed_cases"] == 0


def test_flask_client_rejects_non_json_post(flask_client):
    response = flask_client.post(
        "/healing/preview",
        data="page=product",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    payload = response.get_json()
    assert response.status_code == 415
    assert payload["error"]["code"] == "unsupported_media_type"
