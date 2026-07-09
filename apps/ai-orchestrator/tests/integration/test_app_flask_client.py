import importlib.util
import sys
import asyncio
from types import ModuleType
from pathlib import Path

import pytest


pytestmark = [pytest.mark.integration]


PROJECT_ROOT = Path(__file__).resolve().parents[4]
SRC_ROOT = PROJECT_ROOT / "apps" / "ai-orchestrator" / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


def _load_orchestrator_app_module() -> ModuleType:
    module_name = "_ai_orchestrator_app_test_client"
    existing = sys.modules.get(module_name)
    if isinstance(existing, ModuleType):
        return existing
    spec = importlib.util.spec_from_file_location(module_name, SRC_ROOT / "app.py")
    if spec is None or spec.loader is None:
        raise ImportError("unable to load ai-orchestrator app module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


_APP_MODULE = _load_orchestrator_app_module()
asgi_app = _APP_MODULE.app
create_app = _APP_MODULE.create_app


class FakeService:
    def get_latest_report(self):
        return {
            "report": {
                "case_id": "tc-product-999",
                "status": "passed",
                "summary": "Latest fake report",
            },
            "report_json_path": "/tmp/tc-product-999.report.json",
            "report_markdown_path": "/tmp/tc-product-999.report.md",
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

    def get_llm_health(self, *, probe: bool = True):
        return {
            "status": "ok",
            "force_llm_mode": True,
            "probe": {"enabled": probe, "attempted": probe, "ok": True},
        }

    def parse_requirement(self, **kwargs):
        return {
            "version": "RequirementSpecV1",
            "source_type": kwargs.get("source", "manual"),
            "requirement": kwargs.get("requirement", ""),
            "page": kwargs.get("page", ""),
            "raw_requirement": kwargs.get("requirement", ""),
            "normalized_requirement": str(kwargs.get("requirement", "")).strip(),
            "parse_confidence": 0.99,
            "priority": "P1",
            "source_inputs": [
                {
                    "source_id": "input.manual.001",
                    "source_type": kwargs.get("source", "manual"),
                    "content_preview": str(kwargs.get("requirement", ""))[:120],
                    "metadata": {},
                }
            ],
            "input_sources": kwargs.get("input_sources", []),
            "entities": [],
            "test_intents": [],
            "ambiguities": [],
            "business_rules": [],
            "coverage_matrix": [],
            "dependency_graph": [],
            "historical_patterns": [],
            "change_impact": {},
            "design_input": kwargs.get("requirement", ""),
            "parser_runtime": {
                "agent": "requirement-parser-agent",
                "prompt_version": "requirement-parser.prompt.test",
                "model": "fake",
                "instructions_version": "test",
                "mode": "llm",
                "source_summary": {
                    "source_count": 1,
                    "source_types": [kwargs.get("source", "manual")],
                    "has_multisource_inputs": False,
                },
                "llm_trace": {
                    "attempted": True,
                    "succeeded": True,
                    "reason_code": "llm_parse",
                    "latency_ms": 1,
                    "overlay_key_count": 1,
                    "total_tokens": None,
                },
                "page_resolution": {
                    "candidate_page": kwargs.get("page", ""),
                    "selected_page": kwargs.get("page", ""),
                    "source_types": [kwargs.get("source", "manual")],
                    "candidate_details": [],
                },
                "trace_id": "trace-001",
                "ai_trace": {"trace_id": "trace-001"},
            },
            "quality_gate": {
                "version": "RequirementQualityGateV1",
                "stage": "parse",
                "gate_enabled": True,
                "decision": "allow",
                "metrics": {},
                "blockers": [],
            },
        }

    def render_requirement_spec_markdown(self, requirement_spec):
        return f"# {requirement_spec.get('page', '-')}\n"


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


def test_flask_client_llm_health_returns_probe_result(flask_client):
    response = flask_client.get("/health/llm?probe=false")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "ok"
    assert payload["probe"]["enabled"] is False


def test_flask_client_console_returns_html(flask_client):
    response = flask_client.get("/console")

    assert response.status_code == 200
    assert "text/html" in response.content_type
    assert "Scaffold Console" in response.get_data(as_text=True)


def test_flask_client_latest_report_returns_summary_preview(flask_client):
    response = flask_client.get("/reports/latest")

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["report"]["case_id"] == "tc-product-999"
    assert payload["report_summary_preview"]["total_failed_cases"] == 0


def test_flask_client_requirement_parse_returns_envelope(flask_client):
    response = flask_client.post(
        "/requirements/parse",
        json={"requirement": "支持按商品名称查询", "page": "product"},
    )

    payload = response.get_json()
    assert response.status_code == 201
    assert payload["requirement_spec"]["page"] == "product"
    assert payload["requirement_analysis_markdown"].startswith("# product")
    assert payload["output_contract"]["machine_schema"] == "RequirementSpecV1"


def test_flask_client_rejects_non_json_post(flask_client):
    response = flask_client.post(
        "/healing/preview",
        data="page=product",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    payload = response.get_json()
    assert response.status_code == 415
    assert payload["error"]["code"] == "unsupported_media_type"


def test_asgi_adapter_health_returns_ok() -> None:
    messages: list[dict[str, object]] = []
    body_sent = False

    async def receive() -> dict[str, object]:
        nonlocal body_sent
        if not body_sent:
            body_sent = True
            return {"type": "http.request", "body": b"", "more_body": False}
        return {"type": "http.disconnect"}

    async def send(message: dict[str, object]) -> None:
        messages.append(message)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/health",
        "raw_path": b"/health",
        "query_string": b"",
        "headers": [],
        "client": ("127.0.0.1", 12345),
        "server": ("127.0.0.1", 8000),
    }

    asyncio.run(asgi_app(scope, receive, send))

    assert messages[0]["type"] == "http.response.start"
    assert messages[0]["status"] == 200
    assert messages[1]["type"] == "http.response.body"
    assert messages[1]["body"] == b'{"status":"ok"}\n'
