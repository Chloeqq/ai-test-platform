import json
import sys
import threading
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[4]
SRC_ROOT = PROJECT_ROOT / "apps" / "ai-orchestrator" / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from app import create_server
from orchestrator_service import OrchestratorValidationError, RunnerExecutionError


pytestmark = [pytest.mark.integration]


class FakeService:
    def __init__(self):
        self.calls = []
        self.healing_calls = []
        self.error = None

    def orchestrate(
        self,
        requirement: str,
        page: str,
        execute: bool = False,
        source: str = "manual",
        mode: str = "generate_only",
    ):
        self.calls.append(
            {
                "requirement": requirement,
                "page": page,
                "execute": execute,
                "source": source,
                "mode": mode,
            }
        )
        if self.error:
            raise self.error

        return {
            "case": {
                "id": "TC-PRODUCT-999",
                "title": "Fake case",
            },
            "test_points": {
                "page": "product",
                "requirement": [requirement],
                "points": [
                    {
                        "key": "product-01",
                        "point_type": "precondition",
                        "description": "Use the shared login entry step.",
                        "action": "login",
                    },
                    {
                        "key": "product-02",
                        "point_type": "navigation",
                        "description": "Navigate with target 'product_menu'.",
                        "action": "click",
                        "target": "product_menu",
                    },
                ],
            },
            "execution_record": {
                "run_id": "TC-PRODUCT-999:2026-03-17T00:00:00+00:00",
                "case_id": "TC-PRODUCT-999",
                "project": "default",
                "source": source,
                "mode": mode,
                "status": "passed" if execute else "generated",
                "started_at": "2026-03-17T00:00:00+00:00",
                "finished_at": "2026-03-17T00:00:01+00:00" if execute else "",
                "step_summary": {
                    "page": "product",
                    "requirement_count": 1,
                    "total_steps": 2,
                    "action_types": ["click", "login"],
                },
                "evidence_index": {
                    "total_files": 1 if execute else 0,
                    "artifact_categories": {
                        "screenshots": 0,
                        "html_pages": 0,
                        "meta_files": 0,
                        "analysis_files": 0,
                        "suggestion_files": 0,
                        "self_healing_result_files": 1 if execute else 0,
                        "videos": 0,
                        "other_files": 0,
                    },
                    "runner_exit_code": 0 if execute else None,
                    "execution_requested": execute,
                },
            },
            "case_path": "/tmp/TC-PRODUCT-999.yaml",
            "execution_requested": execute,
            "runner_exit_code": 0 if execute else None,
            "runner_stdout": "ok" if execute else "",
            "runner_stderr": "",
            "report": {
                "status": "passed" if execute else "generated",
                "summary": "Fake report summary",
                "case_id": "TC-PRODUCT-999",
                "case_title": "Fake case",
                "page": "product",
                "case_path": "/tmp/TC-PRODUCT-999.yaml",
                "execution_requested": execute,
                "source": source,
                "request_context": {
                    "page": "product",
                    "mode": mode,
                    "source": source,
                    "execution_requested": execute,
                },
                "execution_record": {
                    "run_id": "TC-PRODUCT-999:2026-03-17T00:00:00+00:00",
                    "case_id": "TC-PRODUCT-999",
                    "project": "default",
                    "source": source,
                    "mode": mode,
                    "status": "passed" if execute else "generated",
                    "started_at": "2026-03-17T00:00:00+00:00",
                    "finished_at": "2026-03-17T00:00:01+00:00" if execute else "",
                    "step_summary": {
                        "page": "product",
                        "requirement_count": 1,
                        "total_steps": 2,
                        "action_types": ["click", "login"],
                    },
                    "evidence_index": {
                        "total_files": 1 if execute else 0,
                        "artifact_categories": {
                            "screenshots": 0,
                            "html_pages": 0,
                            "meta_files": 0,
                            "analysis_files": 0,
                            "suggestion_files": 0,
                            "self_healing_result_files": 1 if execute else 0,
                            "videos": 0,
                            "other_files": 0,
                        },
                        "runner_exit_code": 0 if execute else None,
                        "execution_requested": execute,
                    },
                },
                "started_at": "2026-03-17T00:00:00+00:00",
                "finished_at": "2026-03-17T00:00:01+00:00",
                "runner_exit_code": 0 if execute else None,
                "metrics": {"passed": 1 if execute else 0, "failed": 0, "skipped": 0, "errors": 0},
                "pytest_results": {
                    "collected": 1 if execute else None,
                    "passed": 1 if execute else 0,
                    "failed": 0,
                    "skipped": 0,
                    "errors": 0,
                    "runner_exit_code": 0 if execute else None,
                    "duration_seconds": 0.12 if execute else None,
                    "has_stderr": False,
                },
                "failure_reason": "",
                "self_healing_enabled": True,
                "self_healing_attempted": execute,
                "failure_analysis": {
                    "summary": "No failure analysis needed because the run did not fail.",
                    "failure_category": "unknown",
                    "likely_cause": "",
                    "risk_level": "low",
                    "recommended_action": "No immediate failure action is required.",
                    "confidence": 1.0,
                    "evidence_used": [],
                },
                "self_healing_advice": {
                    "summary": "No self-healing action is required because the run did not fail.",
                    "suggestion_type": "no_change",
                    "suggested_changes": ["Keep the current YAML and page-object unchanged."],
                    "rationale": "The run passed, so only a no-op advisory is returned.",
                    "confidence": 1.0,
                    "safe_to_apply_manually": True,
                },
                "self_healing_suggestion_preview": {
                    "summary": "No suggestion file preview available.",
                    "advice_type": "no_change",
                    "target": "",
                    "suggestion": "",
                    "confidence": 0.0,
                    "fix_candidates": [],
                },
                "self_healing_execution_preview": {
                    "status": "success",
                    "reason": "Patch applied and rerun succeeded.",
                    "attempts_used": 1,
                    "healed": True,
                    "rolled_back": False,
                    "confidence": 0.82,
                    "plan_path": "/tmp/self_healing_patch_plan.json",
                    "result_path": "/tmp/self_healing_result.json",
                },
                "evidence": {
                    "screenshots": [],
                    "html_pages": [],
                    "meta_files": [],
                    "analysis_files": [],
                    "suggestion_files": [],
                    "self_healing_result_files": ["/tmp/self_healing_result.json"],
                    "videos": [],
                    "other_files": [],
                    "total_files": 1,
                },
                "runner_stdout_excerpt": "ok" if execute else "",
                "runner_stderr_excerpt": "",
            },
            "report_json_path": "/tmp/TC-PRODUCT-999.report.json",
            "report_markdown_path": "/tmp/TC-PRODUCT-999.report.md",
            "report_summary_path": "/tmp/report_summary.txt" if execute else "",
        }

    @staticmethod
    def serialize_result(result):
        return result

    def get_latest_report(self):
        return {
            "report": {
                "case_id": "TC-PRODUCT-999",
                "status": "passed",
                "summary": "Latest fake report",
                "execution_record": {
                    "run_id": "TC-PRODUCT-999:2026-03-17T00:00:00+00:00",
                    "case_id": "TC-PRODUCT-999",
                    "project": "default",
                    "source": "manual",
                    "mode": "generate_and_run",
                    "status": "passed",
                    "started_at": "2026-03-17T00:00:00+00:00",
                    "finished_at": "2026-03-17T00:00:01+00:00",
                    "step_summary": {"page": "product", "requirement_count": 1, "total_steps": 2, "action_types": ["click", "login"]},
                    "evidence_index": {"total_files": 1, "artifact_categories": {"self_healing_result_files": 1}, "runner_exit_code": 0, "execution_requested": True},
                },
                "self_healing_enabled": True,
                "self_healing_attempted": True,
                "self_healing_execution_preview": {
                    "status": "success",
                    "reason": "Patch applied and rerun succeeded.",
                    "attempts_used": 1,
                    "healed": True,
                    "rolled_back": False,
                    "confidence": 0.82,
                    "plan_path": "/tmp/self_healing_patch_plan.json",
                    "result_path": "/tmp/self_healing_result.json",
                },
            },
            "execution_record": {
                "run_id": "TC-PRODUCT-999:2026-03-17T00:00:00+00:00",
                "case_id": "TC-PRODUCT-999",
                "project": "default",
                "source": "manual",
                "mode": "generate_and_run",
                "status": "passed",
                "started_at": "2026-03-17T00:00:00+00:00",
                "finished_at": "2026-03-17T00:00:01+00:00",
                "step_summary": {"page": "product", "requirement_count": 1, "total_steps": 2, "action_types": ["click", "login"]},
                "evidence_index": {"total_files": 1, "artifact_categories": {"self_healing_result_files": 1}, "runner_exit_code": 0, "execution_requested": True},
            },
            "report_json_path": "/tmp/TC-PRODUCT-999.report.json",
            "report_markdown_path": "/tmp/TC-PRODUCT-999.report.md",
            "report_summary_path": "/tmp/report_summary.txt",
            "report_summary_preview": {
                "total_failed_cases": 2,
                "environment_failures": 1,
                "business_failures": 1,
                "high_risk_failures": 1,
                "actionable_self_healing_cases": 1,
                "environment_failure_cases": ["TC-LOGIN-001"],
                "actionable_self_healing_case_details": [
                    {
                        "case_id": "TC-PRODUCT-999",
                        "target": "product_list_title",
                        "advice_type": "assertion_update",
                    }
                ],
            },
        }

    def get_report(self, case_id: str):
        if case_id == "missing":
            raise OrchestratorValidationError("Execution report not found for case_id: missing")
        return {
            "report": {
                "case_id": case_id,
                "status": "passed",
                "summary": "Report by case id",
                "execution_record": {
                    "run_id": f"{case_id}:2026-03-17T00:00:00+00:00",
                    "case_id": case_id,
                    "project": "default",
                    "source": "manual",
                    "mode": "generate_and_run",
                    "status": "passed",
                    "started_at": "2026-03-17T00:00:00+00:00",
                    "finished_at": "2026-03-17T00:00:01+00:00",
                    "step_summary": {"page": "product", "requirement_count": 1, "total_steps": 2, "action_types": ["click", "login"]},
                    "evidence_index": {"total_files": 1, "artifact_categories": {"self_healing_result_files": 1}, "runner_exit_code": 0, "execution_requested": True},
                },
                "self_healing_enabled": True,
                "self_healing_attempted": True,
                "self_healing_execution_preview": {
                    "status": "success",
                    "reason": "Patch applied and rerun succeeded.",
                    "attempts_used": 1,
                    "healed": True,
                    "rolled_back": False,
                    "confidence": 0.82,
                    "plan_path": "/tmp/self_healing_patch_plan.json",
                    "result_path": "/tmp/self_healing_result.json",
                },
                "evidence": {
                    "self_healing_result_files": ["/tmp/self_healing_result.json"],
                },
            },
            "execution_record": {
                "run_id": f"{case_id}:2026-03-17T00:00:00+00:00",
                "case_id": case_id,
                "project": "default",
                "source": "manual",
                "mode": "generate_and_run",
                "status": "passed",
                "started_at": "2026-03-17T00:00:00+00:00",
                "finished_at": "2026-03-17T00:00:01+00:00",
                "step_summary": {"page": "product", "requirement_count": 1, "total_steps": 2, "action_types": ["click", "login"]},
                "evidence_index": {"total_files": 1, "artifact_categories": {"self_healing_result_files": 1}, "runner_exit_code": 0, "execution_requested": True},
            },
            "report_json_path": f"/tmp/{case_id}.report.json",
            "report_markdown_path": f"/tmp/{case_id}.report.md",
            "report_summary_path": "/tmp/report_summary.txt",
            "report_summary_preview": {
                "total_failed_cases": 2,
                "environment_failures": 1,
                "business_failures": 1,
                "high_risk_failures": 1,
                "actionable_self_healing_cases": 1,
                "environment_failure_cases": ["TC-LOGIN-001"],
                "actionable_self_healing_case_details": [
                    {
                        "case_id": "TC-PRODUCT-999",
                        "target": "product_list_title",
                        "advice_type": "assertion_update",
                    }
                ],
            },
        }

    def preview_self_healing_advice(self, page: str, case=None, failure_reason: str = "", failure_analysis=None):
        self.healing_calls.append(
            {
                "page": page,
                "case": case,
                "failure_reason": failure_reason,
                "failure_analysis": failure_analysis,
            }
        )
        if not page.strip():
            raise OrchestratorValidationError("page must not be empty")
        return {
            "summary": "Preview a manual assertion update.",
            "suggestion_type": "assertion_update",
            "suggested_changes": [
                "Check whether product_list_title is still the correct stable assertion target."
            ],
            "rationale": "The preview endpoint only returns advice and does not modify files.",
            "confidence": 0.82,
            "safe_to_apply_manually": True,
        }


class FakeAssetService:
    def __init__(self):
        self.page_object_calls = []
        self.element_calls = []
        self.sync_calls = []
        self.scaffold_calls = []
        self.template_list_calls = 0
        self.template_detail_calls = []

    def create_page_object(self, page: str, description: str = ""):
        self.page_object_calls.append({"page": page, "description": description})
        return {
            "page_object": {"page": page, "description": description, "elements": {}},
            "path": f"/tmp/{page}.page-object.yaml",
        }

    def add_page_element(self, page: str, element_name: str, locator_type: str, locator_value: str, role=None, description=None):
        self.element_calls.append(
            {
                "page": page,
                "name": element_name,
                "locator_type": locator_type,
                "locator_value": locator_value,
                "role": role,
                "description": description,
            }
        )
        return {
            "page_object": {
                "page": page,
                "elements": {
                    element_name: {
                        "locator_type": locator_type,
                        "locator_value": locator_value,
                    }
                },
            },
            "path": f"/tmp/{page}.page-object.yaml",
        }

    def sync_test_case(self, file_path: str, menu_target=None, assert_target=None):
        self.sync_calls.append(
            {
                "file": file_path,
                "menu_target": menu_target,
                "assert_target": assert_target,
            }
        )
        return {
            "test_case": {
                "id": "TC-PRODUCT-001",
                "execution": {"page": "product"},
            },
            "path": file_path,
        }

    def scaffold_page_assets(
        self,
        page: str,
        title: str,
        requirement: str,
        description: str = "",
        priority: str = "P1",
        menu_label=None,
        assert_label=None,
        template=None,
        elements=None,
    ):
        self.scaffold_calls.append(
            {
                "page": page,
                "title": title,
                "requirement": requirement,
                "description": description,
                "priority": priority,
                "menu_label": menu_label,
                "assert_label": assert_label,
                "template": template,
                "elements": elements,
            }
        )
        return {
            "page_object": {
                "page": page,
                "elements": {
                    "catalog_search_input": {
                        "locator_type": "css",
                        "locator_value": "input[name='keyword']",
                    }
                } if elements else {},
            },
            "page_object_path": f"/tmp/{page}.page-object.yaml",
            "test_case": {
                "id": f"TC-{page.upper()}-001",
                "title": title,
                "execution": {
                    "steps": [
                        {"action": "login"},
                        {"action": "click", "target": "catalog_search_entry"},
                        {"action": "wait_for", "target": "catalog_results_panel"},
                        {"action": "assert_visible", "target": "catalog_results_panel"},
                    ]
                },
            } if elements else {"id": f"TC-{page.upper()}-001", "title": title},
            "test_case_path": f"/tmp/TC-{page.upper()}-001.yaml",
        }

    def list_scaffold_templates(self):
        self.template_list_calls += 1
        return {
            "templates": [
                {
                    "name": "catalog",
                    "summary": "商品目录/搜索结果类页面骨架",
                    "page_type": "catalog",
                    "recommended_title": "商品目录",
                    "recommended_requirement": "商品目录页面展示",
                    "elements_count": 3,
                    "elements": [],
                }
            ]
        }

    def get_scaffold_template(self, template_name: str):
        if template_name == "unknown":
            raise OrchestratorValidationError("Unknown scaffold template: unknown")
        self.template_detail_calls.append(template_name)
        return {
            "template": {
                "name": template_name,
                "summary": "商品目录/搜索结果类页面骨架",
                "page_type": "catalog",
                "recommended_title": "商品目录",
                "recommended_requirement": "商品目录页面展示",
                "elements_count": 3,
                "elements": [
                    {
                        "name": "catalog_search_entry",
                        "locator_type": "role",
                        "role": "menuitem",
                        "locator_value": "商品目录查询",
                        "smoke_role": "menu",
                    }
                ],
            }
        }


@pytest.fixture
def orchestrator_server():
    fake_service = FakeService()
    fake_asset_service = FakeAssetService()
    server = create_server(
        host="127.0.0.1",
        port=0,
        service=fake_service,
        asset_service=fake_asset_service,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address

    yield {
        "service": fake_service,
        "asset_service": fake_asset_service,
        "base_url": f"http://{host}:{port}",
    }

    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


def _request_json(base_url: str, method: str, path: str, payload: dict):
    body = json.dumps(payload).encode("utf-8")
    return _request_raw(
        base_url=base_url,
        method=method,
        path=path,
        body=body,
        content_type="application/json",
    )


def _request_raw(base_url: str, method: str, path: str, body: bytes, content_type: str):
    request = Request(
        url=f"{base_url}{path}",
        data=body,
        headers={"Content-Type": content_type},
        method=method,
    )
    try:
        with urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def _request_text(base_url: str, path: str):
    request = Request(url=f"{base_url}{path}", method="GET")
    with urlopen(request, timeout=5) as response:
        return response.status, response.headers.get("Content-Type", ""), response.read().decode("utf-8")


def test_get_console_returns_html(orchestrator_server):
    status, content_type, body = _request_text(
        orchestrator_server["base_url"],
        "/console",
    )

    assert status == 200
    assert "text/html" in content_type
    assert "Scaffold Console" in body


def test_get_console_script_returns_javascript(orchestrator_server):
    status, content_type, body = _request_text(
        orchestrator_server["base_url"],
        "/console/app.js",
    )

    assert status == 200
    assert "application/javascript" in content_type
    assert "loadTemplates" in body


def test_post_orchestrate_returns_201_and_payload(orchestrator_server):
    status, payload = _request_json(
        orchestrator_server["base_url"],
        "POST",
        "/orchestrate",
        {"requirement": "验证商品搜索功能", "page": "product", "execute": True},
    )

    assert status == 201
    assert payload["case"]["id"] == "TC-PRODUCT-999"
    assert payload["test_points"]["page"] == "product"
    assert payload["test_points"]["points"][0]["action"] == "login"
    assert payload["execution_requested"] is True
    assert payload["execution_record"]["source"] == "manual"
    assert payload["execution_record"]["mode"] == "generate_and_run"
    assert payload["execution_record"]["step_summary"]["total_steps"] == 2
    assert payload["report"]["status"] == "passed"
    assert payload["report"]["source"] == "manual"
    assert payload["report"]["request_context"]["mode"] == "generate_and_run"
    assert payload["report"]["execution_record"]["status"] == "passed"
    assert payload["report"]["pytest_results"]["passed"] == 1
    assert payload["report"]["self_healing_advice"]["suggestion_type"] == "no_change"
    assert payload["report_json_path"].endswith(".report.json")
    assert payload["report_summary_path"].endswith("report_summary.txt")
    assert orchestrator_server["service"].calls[0]["page"] == "product"


def test_post_orchestrate_supports_source_field(orchestrator_server):
    status, payload = _request_json(
        orchestrator_server["base_url"],
        "POST",
        "/orchestrate",
        {"requirement": "验证商品搜索功能", "page": "product", "source": "regression"},
    )

    assert status == 201
    assert payload["report"]["source"] == "regression"
    assert payload["report"]["request_context"]["source"] == "regression"
    assert payload["execution_record"]["source"] == "regression"
    assert orchestrator_server["service"].calls[-1]["source"] == "regression"


def test_post_orchestrate_supports_explicit_generate_only_mode(orchestrator_server):
    status, payload = _request_json(
        orchestrator_server["base_url"],
        "POST",
        "/orchestrate",
        {"requirement": "验证商品搜索功能", "page": "product", "execute": True, "mode": "generate_only"},
    )

    assert status == 201
    assert payload["execution_requested"] is False
    assert payload["test_points"]["page"] == "product"
    assert payload["report"]["request_context"]["mode"] == "generate_only"
    assert orchestrator_server["service"].calls[-1]["execute"] is False


def test_post_orchestrate_supports_explicit_generate_and_run_mode(orchestrator_server):
    status, payload = _request_json(
        orchestrator_server["base_url"],
        "POST",
        "/orchestrate",
        {"requirement": "验证商品搜索功能", "page": "product", "execute": False, "mode": "generate_and_run"},
    )

    assert status == 201
    assert payload["execution_requested"] is True
    assert payload["report"]["request_context"]["mode"] == "generate_and_run"
    assert orchestrator_server["service"].calls[-1]["execute"] is True


def test_post_orchestrate_rejects_unknown_mode(orchestrator_server):
    status, payload = _request_json(
        orchestrator_server["base_url"],
        "POST",
        "/orchestrate",
        {"requirement": "验证商品搜索功能", "page": "product", "mode": "rewrite_everything"},
    )

    assert status == 422
    assert payload["error"]["code"] == "validation_error"


def test_post_healing_preview_returns_200_and_payload(orchestrator_server):
    status, payload = _request_json(
        orchestrator_server["base_url"],
        "POST",
        "/healing/preview",
        {
            "page": "product",
            "failure_reason": "expected product list title to be visible",
            "failure_analysis": {
                "summary": "UI assertion failed on product page.",
                "failure_category": "assertion",
                "likely_cause": "The expected product list title was not rendered.",
                "risk_level": "high",
                "recommended_action": "Review the stable assertion target manually.",
                "confidence": 0.84,
                "evidence_used": ["stdout"],
            },
        },
    )

    assert status == 200
    assert payload["self_healing_advice"]["suggestion_type"] == "assertion_update"
    assert payload["self_healing_advice"]["safe_to_apply_manually"] is True
    assert orchestrator_server["service"].healing_calls[0]["page"] == "product"


def test_post_healing_preview_maps_validation_errors(orchestrator_server):
    status, payload = _request_json(
        orchestrator_server["base_url"],
        "POST",
        "/healing/preview",
        {"page": " "},
    )

    assert status == 422
    assert payload["error"]["code"] == "validation_error"


def test_post_orchestrate_rejects_invalid_json(orchestrator_server):
    status, payload = _request_raw(
        orchestrator_server["base_url"],
        "POST",
        "/orchestrate",
        body=b"{invalid",
        content_type="application/json",
    )

    assert status == 400
    assert payload["error"]["code"] == "invalid_json"


def test_post_orchestrate_requires_application_json(orchestrator_server):
    status, payload = _request_raw(
        orchestrator_server["base_url"],
        "POST",
        "/orchestrate",
        body=b"requirement=test",
        content_type="text/plain",
    )

    assert status == 415
    assert payload["error"]["code"] == "unsupported_media_type"


def test_post_orchestrate_maps_runner_failures_to_502(orchestrator_server):
    orchestrator_server["service"].error = RunnerExecutionError(
        "Runner execution failed",
        details={"runner_exit_code": 1},
    )

    status, payload = _request_json(
        orchestrator_server["base_url"],
        "POST",
        "/orchestrate",
        {"requirement": "验证商品搜索功能", "page": "product"},
    )

    assert status == 502
    assert payload["error"]["code"] == "runner_failed"
    assert payload["error"]["details"]["runner_exit_code"] == 1


def test_post_orchestrate_returns_404_for_unknown_route(orchestrator_server):
    status, payload = _request_json(
        orchestrator_server["base_url"],
        "POST",
        "/unknown",
        {"requirement": "验证商品搜索功能", "page": "product"},
    )

    assert status == 404
    assert payload["error"]["code"] == "not_found"


def test_get_scaffold_templates_returns_200(orchestrator_server):
    status, payload = _request_raw(
        orchestrator_server["base_url"],
        "GET",
        "/assets/scaffold/templates",
        body=b"",
        content_type="application/json",
    )

    assert status == 200
    assert payload["templates"][0]["name"] == "catalog"
    assert orchestrator_server["asset_service"].template_list_calls == 1


def test_get_latest_report_returns_200(orchestrator_server):
    status, payload = _request_raw(
        orchestrator_server["base_url"],
        "GET",
        "/reports/latest",
        body=b"",
        content_type="application/json",
    )

    assert status == 200
    assert payload["report"]["case_id"] == "TC-PRODUCT-999"
    assert payload["execution_record"]["case_id"] == "TC-PRODUCT-999"
    assert payload["report_json_path"].endswith(".report.json")
    assert payload["report_summary_path"].endswith("report_summary.txt")
    assert payload["report_summary_preview"]["total_failed_cases"] == 2
    assert payload["report_summary_preview"]["actionable_self_healing_cases"] == 1
    assert payload["report_summary_preview"]["environment_failure_cases"] == ["TC-LOGIN-001"]
    assert payload["report_summary_preview"]["actionable_self_healing_case_details"][0]["target"] == "product_list_title"
    assert payload["report"]["self_healing_execution_preview"]["status"] == "success"
    assert payload["report"]["self_healing_enabled"] is True


def test_get_report_by_case_id_returns_200(orchestrator_server):
    status, payload = _request_raw(
        orchestrator_server["base_url"],
        "GET",
        "/reports/TC-PRODUCT-999",
        body=b"",
        content_type="application/json",
    )

    assert status == 200
    assert payload["report"]["case_id"] == "TC-PRODUCT-999"
    assert payload["execution_record"]["mode"] == "generate_and_run"
    assert payload["report_summary_path"].endswith("report_summary.txt")
    assert payload["report_summary_preview"]["environment_failures"] == 1
    assert payload["report_summary_preview"]["actionable_self_healing_case_details"][0]["advice_type"] == "assertion_update"
    assert payload["report"]["evidence"]["self_healing_result_files"][0].endswith("self_healing_result.json")
    assert payload["report"]["self_healing_attempted"] is True


def test_get_report_by_case_id_maps_validation_errors(orchestrator_server):
    status, payload = _request_raw(
        orchestrator_server["base_url"],
        "GET",
        "/reports/missing",
        body=b"",
        content_type="application/json",
    )

    assert status == 422
    assert payload["error"]["code"] == "validation_error"


def test_get_scaffold_template_detail_returns_200(orchestrator_server):
    status, payload = _request_raw(
        orchestrator_server["base_url"],
        "GET",
        "/assets/scaffold/templates/catalog",
        body=b"",
        content_type="application/json",
    )

    assert status == 200
    assert payload["template"]["name"] == "catalog"
    assert orchestrator_server["asset_service"].template_detail_calls == ["catalog"]


def test_get_scaffold_template_detail_maps_validation_errors(orchestrator_server):
    status, payload = _request_raw(
        orchestrator_server["base_url"],
        "GET",
        "/assets/scaffold/templates/unknown",
        body=b"",
        content_type="application/json",
    )

    assert status == 422
    assert payload["error"]["code"] == "validation_error"


def test_post_create_page_object_returns_201(orchestrator_server):
    status, payload = _request_json(
        orchestrator_server["base_url"],
        "POST",
        "/assets/page-objects",
        {"page": "catalog", "description": "商品目录页"},
    )

    assert status == 201
    assert payload["page_object"]["page"] == "catalog"
    assert orchestrator_server["asset_service"].page_object_calls[0]["page"] == "catalog"


def test_post_add_page_object_element_returns_201(orchestrator_server):
    status, payload = _request_json(
        orchestrator_server["base_url"],
        "POST",
        "/assets/page-objects/catalog/elements",
        {
            "name": "catalog_menu",
            "locator_type": "role",
            "locator_value": "商品目录",
            "role": "menuitem",
        },
    )

    assert status == 201
    assert "catalog_menu" in payload["page_object"]["elements"]
    assert orchestrator_server["asset_service"].element_calls[0]["page"] == "catalog"


def test_post_sync_test_case_returns_200(orchestrator_server):
    status, payload = _request_json(
        orchestrator_server["base_url"],
        "POST",
        "/assets/test-cases/sync",
        {"file": "assets/test-cases/smoke/product-smoke.yaml"},
    )

    assert status == 200
    assert payload["test_case"]["id"] == "TC-PRODUCT-001"
    assert orchestrator_server["asset_service"].sync_calls[0]["file"] == "assets/test-cases/smoke/product-smoke.yaml"


def test_post_scaffold_assets_returns_201(orchestrator_server):
    status, payload = _request_json(
        orchestrator_server["base_url"],
        "POST",
        "/assets/scaffold",
        {
            "page": "catalog",
            "title": "商品目录",
            "requirement": "商品目录页面展示",
            "description": "创建目录页骨架",
        },
    )

    assert status == 201
    assert payload["page_object"]["page"] == "catalog"
    assert payload["test_case"]["id"] == "TC-CATALOG-001"
    assert orchestrator_server["asset_service"].scaffold_calls[0]["page"] == "catalog"


def test_post_scaffold_assets_accepts_element_templates(orchestrator_server):
    status, payload = _request_json(
        orchestrator_server["base_url"],
        "POST",
        "/assets/scaffold",
        {
            "page": "catalog",
            "title": "商品目录",
            "requirement": "商品目录页面展示",
            "elements": [
                {
                    "name": "catalog_search_input",
                    "locator_type": "css",
                    "locator_value": "input[name='keyword']",
                    "description": "搜索输入框",
                },
                {
                    "name": "catalog_search_entry",
                    "locator_type": "role",
                    "role": "menuitem",
                    "locator_value": "商品目录查询",
                    "smoke_role": "menu",
                },
                {
                    "name": "catalog_results_panel",
                    "locator_type": "css",
                    "locator_value": ".catalog-results",
                    "smoke_role": "assert",
                }
            ],
        },
    )

    assert status == 201
    assert "catalog_search_input" in payload["page_object"]["elements"]
    assert orchestrator_server["asset_service"].scaffold_calls[0]["elements"][0]["name"] == "catalog_search_input"
    assert payload["test_case"]["execution"]["steps"][1]["target"] == "catalog_search_entry"
    assert payload["test_case"]["execution"]["steps"][2]["target"] == "catalog_results_panel"


def test_post_scaffold_assets_accepts_template_name(orchestrator_server):
    status, _payload = _request_json(
        orchestrator_server["base_url"],
        "POST",
        "/assets/scaffold",
        {
            "page": "catalog",
            "title": "商品目录",
            "requirement": "商品目录页面展示",
            "template": "catalog",
        },
    )

    assert status == 201
    assert orchestrator_server["asset_service"].scaffold_calls[0]["template"] == "catalog"
