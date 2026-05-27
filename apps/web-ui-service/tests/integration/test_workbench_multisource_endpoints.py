from __future__ import annotations

import json
import sys
from datetime_compat import UTC
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient


WEB_UI_ROOT = Path(__file__).resolve().parents[2]
if str(WEB_UI_ROOT) not in sys.path:
    sys.path.insert(0, str(WEB_UI_ROOT))
existing_app = sys.modules.get("app")
if existing_app is not None and not getattr(existing_app, "__path__", None):
    sys.modules.pop("app", None)

from app.main import app  # noqa: E402
from app.core.security import create_access_token  # noqa: E402
from app.routers import dashboard as dashboard_router  # noqa: E402
from app.routers import legacy_workbench as workbench  # noqa: E402
from shared_backend.case_ids import normalize_case_id  # noqa: E402


pytestmark = [pytest.mark.integration]


def cid(value: str) -> str:
    return normalize_case_id(value)


def test_case_dictionary_endpoint_exposes_platform_dictionary() -> None:
    client = TestClient(app)
    response = client.get("/api/workbench/case-dictionaries")

    assert response.status_code == 200
    payload = response.json()["items"]
    assert any(item["code"] == "ret" for item in payload["page"])
    assert any(item["code"] == "query" for item in payload["module"])
    assert any(item["code"] == "fb" for item in payload["source"])


def test_preview_test_points_supports_multisource_without_requirement(monkeypatch: Any) -> None:
    captured: dict[str, Any] = {}

    monkeypatch.setattr(workbench, "_ensure_dirs", lambda: None)

    def fake_parse(**kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return {
            "requirement_spec": {
                "page": "product",
                "priority": "P1",
                "parse_confidence": 0.91,
                "quality_gate": {
                    "version": "RequirementQualityGateV1",
                    "stage": "parse",
                    "decision": "allow",
                    "metrics": {
                        "parse_confidence": 0.91,
                        "test_intent_count": 3,
                        "coverage_gap_ratio": 0.1,
                    },
                    "blockers": [],
                },
                "test_intents": [
                    {"intent_type": "functional", "summary": "列表展示"},
                    {"intent_type": "functional", "summary": "搜索筛选"},
                    {"intent_type": "negative", "summary": "空数据提示"},
                ],
                "ambiguities": [{"field": "排序规则", "reason": "需求未明确"}],
                "business_rules": [{"name": "商品状态过滤", "severity": "high"}],
                "change_impact": {
                    "impact_score": 37,
                    "changed_areas": ["api_contract", "business_rule"],
                    "risk_signals": [{"code": "auth_scope", "severity": "high"}],
                    "top_factor": {"factor": "api_contract", "weight": 14},
                    "recommended_regression_scope": ["api_contract_regression", "business_rule_regression"],
                },
                "parser_runtime": {
                    "source_summary": {
                        "source_count": 2,
                        "source_types": ["openapi", "prd"],
                    }
                },
            }
        }

    monkeypatch.setattr(workbench, "_run_orchestrator_parse", fake_parse)

    client = TestClient(app)
    response = client.post(
        "/api/workbench/preview-test-points",
        json={
            "project": "default",
            "page": "",
            "requirement": "",
            "source": "manual",
            "openapi_spec": {"openapi": "3.0.0", "paths": {"/products": {"get": {}}}},
            "prd_text": "商品列表页支持按名称查询",
        },
    )

    assert response.status_code == 200
    payload = response.json()["item"]
    assert payload["page"] == "product"
    assert payload["intent_count"] == 3
    assert payload["intent_type_distribution"]["functional"] == 2
    assert payload["intent_type_distribution"]["negative"] == 1
    assert payload["ambiguity_count"] == 1
    assert payload["rule_count"] == 1
    assert payload["source_count"] == 2
    assert payload["source_types"] == ["openapi", "prd"]
    assert payload["change_impact"]["impact_score"] == 37
    assert payload["change_impact"]["changed_areas"] == ["api_contract", "business_rule"]
    assert payload["change_impact"]["risk_signal_count"] == 1
    assert payload["change_impact"]["top_factor"]["factor"] == "api_contract"
    assert payload["change_impact"]["recommended_regression_scope"] == ["api_contract_regression", "business_rule_regression"]
    assert payload["quality_gate"]["decision"] == "allow"
    assert "# 需求测试点分析" in payload["requirement_analysis_markdown"]
    assert payload["output_contract"]["machine_schema"] == "RequirementSpecV1"
    assert captured["requirement"].startswith("多输入源需求驱动的页面核心流程验证")
    assert captured["prd_text"] == "商品列表页支持按名称查询"
    assert isinstance(captured["openapi_spec"], dict)


def test_preview_test_points_supports_page_only_without_requirement(monkeypatch: Any) -> None:
    captured: dict[str, Any] = {}

    monkeypatch.setattr(workbench, "_ensure_dirs", lambda: None)

    def fake_parse(**kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return {
            "requirement_spec": {
                "page": "product",
                "priority": "P1",
                "parse_confidence": 0.82,
                "quality_gate": {
                    "version": "RequirementQualityGateV1",
                    "stage": "parse",
                    "decision": "allow",
                    "metrics": {
                        "parse_confidence": 0.82,
                        "test_intent_count": 2,
                        "coverage_gap_ratio": 0.0,
                    },
                    "blockers": [],
                },
                "test_intents": [
                    {"intent_type": "functional", "summary": "页面可访问"},
                    {"intent_type": "functional", "summary": "关键区域可见"},
                ],
                "ambiguities": [],
                "business_rules": [],
            }
        }

    monkeypatch.setattr(workbench, "_run_orchestrator_parse", fake_parse)

    client = TestClient(app)
    response = client.post(
        "/api/workbench/preview-test-points",
        json={
            "project": "default",
            "page": "product",
            "requirement": "",
            "source": "manual",
        },
    )

    assert response.status_code == 200
    payload = response.json()["item"]
    assert payload["page"] == "product"
    assert payload["intent_count"] == 2
    assert payload["quality_gate"]["decision"] == "allow"
    assert captured["requirement"].startswith("自动生成的页面测试目标")
    assert captured["page"] == "product"


def test_generate_supports_multisource_without_requirement(monkeypatch: Any) -> None:
    captured: dict[str, Any] = {}

    monkeypatch.setattr(workbench, "_ensure_dirs", lambda: None)

    def fake_generate(**kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return {
            "case": {
                "version": "v4",
                "id": "tc-product-001",
                "title": "Product List Smoke",
                "module": "product",
                "execution": {
                    "runner": "playwright",
                    "page": "product",
                    "variables": {},
                    "steps": [{"action": "login"}],
                },
            },
            "requirement_spec": {
                "page": "product",
                "quality_gate": {
                    "version": "RequirementQualityGateV1",
                    "stage": "orchestrate",
                    "decision": "allow",
                    "metrics": {"parse_confidence": 0.9, "test_intent_count": 1, "coverage_gap_ratio": 0.0},
                    "blockers": [],
                },
            },
        }

    monkeypatch.setattr(workbench, "_run_orchestrator_generate", fake_generate)
    monkeypatch.setattr(workbench, "_write_case_yaml", lambda *_args, **_kwargs: "id: tc-product-001\n")
    monkeypatch.setattr(workbench, "_save_case_state", lambda *_args, **_kwargs: {"version": 1})
    monkeypatch.setattr(workbench, "_append_history", lambda *_args, **_kwargs: None)

    client = TestClient(app)
    response = client.post(
        "/api/workbench/generate",
        json={
            "project": "default",
            "page": "",
            "requirement": "",
            "title": "",
            "case_id": "",
            "priority": "P1",
            "tags": ["ai-generated"],
            "source": "manual",
            "openapi_spec": {"openapi": "3.0.0", "paths": {"/products": {"get": {}}}},
        },
    )

    assert response.status_code == 201
    data = response.json()["item"]
    assert data["case_id"] == cid("tc-product-001")
    assert data["page"] == "product"
    assert not data["orchestrator_fallback_reason"]
    assert data["orchestrator_design_fallback_used"] is False
    assert data["quality_gate"]["decision"] == "allow"
    assert captured["requirement"].startswith("多输入源需求驱动的页面核心流程验证")
    assert isinstance(captured["openapi_spec"], dict)


def test_generate_surfaces_orchestrator_design_fallback(monkeypatch: Any) -> None:
    monkeypatch.setattr(workbench, "_ensure_dirs", lambda: None)
    monkeypatch.setattr(
        workbench,
        "_run_orchestrator_generate",
        lambda **_kwargs: {
            "case": {
                "version": "v4",
                "id": "tc-product-fallback",
                "title": "SMOKE-PRODUCT-FALLBACK",
                "module": "product",
                "tags": ["ai-generated", "fallback"],
                "execution": {
                    "runner": "playwright",
                    "page": "product",
                    "variables": {},
                    "steps": [{"action": "login"}],
                },
            },
            "design_generation": {
                "generator": "test-design-agent",
                "fallback_used": True,
                "fallback_reason": "invalid yaml from test-design-agent",
            },
            "requirement_spec": {"page": "product"},
        },
    )
    monkeypatch.setattr(workbench, "_write_case_yaml", lambda *_args, **_kwargs: "id: tc-product-FALLBACK\n")
    monkeypatch.setattr(workbench, "_save_case_state", lambda *_args, **_kwargs: {"version": 1})
    monkeypatch.setattr(workbench, "_append_history", lambda *_args, **_kwargs: None)

    client = TestClient(app)
    response = client.post(
        "/api/workbench/generate",
        json={
            "project": "default",
            "page": "product",
            "requirement": "商品列表页面验证",
            "source": "manual",
        },
    )

    assert response.status_code == 201
    payload = response.json()["item"]
    assert payload["orchestrator_design_fallback_used"] is True
    assert "invalid yaml" in payload["orchestrator_fallback_reason"]


def test_generate_blocks_when_orchestrator_requirement_quality_gate_blocks(monkeypatch: Any) -> None:
    monkeypatch.setattr(workbench, "_ensure_dirs", lambda: None)

    def fake_generate(**_kwargs: Any) -> dict[str, Any]:
        raise workbench.HTTPException(
            status_code=422,
            detail={
                "code": "validation_error",
                "message": "requirement quality gate blocked orchestration",
                "details": {
                    "quality_gate": {
                        "version": "RequirementQualityGateV1",
                        "stage": "orchestrate",
                        "decision": "block",
                        "metrics": {"parse_confidence": 0.21, "test_intent_count": 0, "coverage_gap_ratio": 0.9},
                        "blockers": [{"code": "low_parse_confidence", "message": "parse confidence too low"}],
                    }
                },
            },
        )

    monkeypatch.setattr(workbench, "_run_orchestrator_generate", fake_generate)

    def fail_write_case_yaml(*_args: Any, **_kwargs: Any) -> str:
        raise AssertionError("fallback yaml should not be written when quality gate blocks generation")

    monkeypatch.setattr(workbench, "_write_case_yaml", fail_write_case_yaml)
    monkeypatch.setattr(workbench, "_save_case_state", lambda *_args, **_kwargs: {"version": 1})
    monkeypatch.setattr(workbench, "_append_history", lambda *_args, **_kwargs: None)

    client = TestClient(app)
    response = client.post(
        "/api/workbench/generate",
        json={
            "project": "default",
            "page": "product",
            "requirement": "模糊需求",
            "source": "manual",
        },
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["code"] == "requirement_quality_gate_blocked"
    assert detail["quality_gate"]["decision"] == "block"


def test_auto_run_supports_multisource_without_requirement(monkeypatch: Any) -> None:
    captured_requests: list[dict[str, Any]] = []

    monkeypatch.setattr(workbench, "_ensure_dirs", lambda: None)
    monkeypatch.setattr(
        workbench,
        "_extract_page_surface",
        lambda resolved_page_url: {
            "url": resolved_page_url,
            "title": "Mock Surface",
            "elements": [
                {"name": "search_input", "locator_type": "css", "locator_value": "input[placeholder*='商品']"},
            ],
        },
    )
    monkeypatch.setattr(workbench, "_enhance_page_object_from_surface", lambda page, _surface: Path(f"/tmp/{page}.page-object.yaml"))
    monkeypatch.setattr(
        workbench,
        "_build_requirement_steps",
        lambda requirement, page, page_url, _surface: (
            [
                {"action": "login"},
                {"action": "click", "target": f"{page}_menu"},
                {"action": "wait_for", "target": page},
            ],
            {"status": "full", "required_coverage": ["navigation", "assert_visible"], "missing_coverage": []},
        ),
    )

    def fake_generate(**kwargs: Any) -> dict[str, Any]:
        captured_requests.append(kwargs)
        page = kwargs["page"]
        return {
            "case": {
                "version": "v4",
                "id": f"tc-{page}-auto",
                "title": f"{page} auto run",
                "module": page,
                "execution": {
                    "runner": "playwright",
                    "page": page,
                    "variables": {},
                    "steps": [{"action": "login"}],
                },
            },
            "case_path": f"assets/test-cases/ai-generated/TC-{page.upper()}-AUTO.yaml",
            "test_points": {"test_intents": [{"intent_type": "functional"}]},
            "requirement_spec": {"page": page},
        }

    monkeypatch.setattr(workbench, "_run_orchestrator_generate", fake_generate)
    monkeypatch.setattr(workbench, "_write_case_yaml", lambda *_args, **_kwargs: "id: TC-AUTO\n")
    monkeypatch.setattr(workbench, "_read_case_yaml", lambda *_args, **_kwargs: ({"id": "TC-AUTO"}, "id: TC-AUTO\n"))
    monkeypatch.setattr(workbench, "_save_case_state", lambda *_args, **_kwargs: {"version": 1})
    monkeypatch.setattr(
        workbench,
        "_steps_to_points",
        lambda page, requirement, _steps: {
            "version": "TestPointPlanV1",
            "source_type": "generated",
            "page": page,
            "requirement": requirement,
            "test_intents": [{"intent_type": "functional", "summary": "核心流程"}],
        },
    )
    monkeypatch.setattr(workbench, "_save_test_point_plan", lambda **_kwargs: Path("/tmp/test-point-plan.json"))
    monkeypatch.setattr(workbench, "_append_history", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(workbench, "_start_run", lambda **_kwargs: {"run_id": "RUN-1", "status": "running"})
    monkeypatch.setattr(workbench, "_wait_run_terminal", lambda run_id, timeout_seconds: ({"run_id": run_id, "status": "passed"}, False))
    monkeypatch.setattr(workbench, "_update_job", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(workbench, "_update_runtime_run", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(workbench, "report_allure_refresh", lambda: {"refreshed": True})

    client = TestClient(app)
    response = client.post(
        "/api/workbench/auto-run",
        json={
            "project": "default",
            "requirement": "",
            "page_urls": [
                "http://localhost:5173/#/pms/product",
                "http://localhost:5173/#/oms/order",
            ],
            "source": "manual",
            "openapi_spec": {"openapi": "3.0.0", "paths": {"/products": {"get": {}}, "/orders": {"get": {}}}},
            "wait_seconds": 30,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["summary"]["total"] == 2
    assert body["summary"]["passed"] == 2
    assert len(body["items"]) == 2
    assert body["allure"]["refresh"]["refreshed"] is True
    for item in body["items"]:
        assert item["test_points"]["version"] == "TestPointPlanV1"
        assert item["test_points"]["schema_version"] == "test-point-plan.v1"
        assert "confidence" in item["test_points"]
        assert "requires_review" in item["test_points"]
        assert "review_summary" in item["test_points"]
        assert item["review_state"]["model_versions"]["page_surface"] == "PageSurfaceV1"
        assert item["review_state"]["model_versions"]["page_semantic"] == "PageSemanticModelV1"
        assert item["review_state"]["model_versions"]["page_object"] == "PageObjectDraftV1"
        assert item["review_state"]["model_versions"]["test_points"] == "TestPointPlanV1"
        assert item["page_semantic"]["version"] == "PageSemanticModelV1"
        assert item["page_semantic"]["schema_version"] == "page-semantic-model.v1"
        assert item["page_semantic_summary"]["page_type"] in {"list", "form", "hybrid", "dialog", "dialog_form", "unknown"}
        assert "confidence" in item["page_semantic_summary"]
        assert item["page_object_summary"]["status"] == "full"
        assert "confidence" in item["page_object_summary"]
        assert "requires_review" in item["page_object_summary"]
        assert "required_elements" in item["page_object_summary"]
        assert item["page_object"]["coverage"]["status"] == "full"
        assert item["page_object"]["version"] == "PageObjectDraftV1"
        assert item["page_object"]["schema_version"] == "page-object-draft.v1"
        assert item["page_surface"]["version"] == "PageSurfaceV1"
        assert item["page_surface"]["schema_version"] == "page-surface.v1"
        assert item["page_surface"]["page"] in {"product", "order"}
        assert "page_surface_summary" in item
        assert "confidence" in item["page_surface_summary"]
    assert len(captured_requests) == 2
    for request_payload in captured_requests:
        assert request_payload["requirement"].startswith("多输入源需求驱动的页面核心流程验证")
        assert request_payload["page"] in {"product", "order"}


def test_auto_run_supports_url_only_without_requirement(monkeypatch: Any) -> None:
    captured_requests: list[dict[str, Any]] = []

    monkeypatch.setattr(workbench, "_ensure_dirs", lambda: None)
    monkeypatch.setattr(
        workbench,
        "_extract_page_surface",
        lambda resolved_page_url: {
            "url": resolved_page_url,
            "title": "Mock Surface",
            "has_table": True,
        },
    )
    monkeypatch.setattr(workbench, "_enhance_page_object_from_surface", lambda page, _surface: Path(f"/tmp/{page}.page-object.yaml"))
    monkeypatch.setattr(
        workbench,
        "_build_requirement_steps",
        lambda requirement, page, page_url, _surface: (
            [
                {"action": "login"},
                {"action": "goto", "value": page_url},
                {"action": "assert_visible", "target": f"{page}_table"},
            ],
            {"status": "full", "required_coverage": ["navigation", "assert_visible"], "missing_coverage": []},
        ),
    )

    def fake_generate(**kwargs: Any) -> dict[str, Any]:
        captured_requests.append(kwargs)
        page = kwargs["page"]
        return {
            "case": {
                "version": "v4",
                "id": f"tc-{page}-auto",
                "title": f"{page} auto run",
                "module": page,
                "execution": {
                    "runner": "playwright",
                    "page": page,
                    "variables": {},
                    "steps": [{"action": "login"}],
                },
            },
            "case_path": f"assets/test-cases/ai-generated/TC-{page.upper()}-AUTO.yaml",
            "test_points": {"points": [{"key": "intent-01", "action": "assert_visible"}]},
            "requirement_spec": {"page": page},
        }

    monkeypatch.setattr(workbench, "_run_orchestrator_generate", fake_generate)
    monkeypatch.setattr(workbench, "_write_case_yaml", lambda *_args, **_kwargs: "id: TC-AUTO\n")
    monkeypatch.setattr(workbench, "_read_case_yaml", lambda *_args, **_kwargs: ({"id": "TC-AUTO"}, "id: TC-AUTO\n"))
    monkeypatch.setattr(workbench, "_save_case_state", lambda *_args, **_kwargs: {"version": 1})
    monkeypatch.setattr(workbench, "_save_test_point_plan", lambda **_kwargs: Path("/tmp/test-point-plan.json"))
    monkeypatch.setattr(workbench, "_append_history", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(workbench, "_start_run", lambda **_kwargs: {"run_id": "RUN-URL", "status": "running"})
    monkeypatch.setattr(workbench, "_wait_run_terminal", lambda run_id, timeout_seconds: ({"run_id": run_id, "status": "passed"}, False))
    monkeypatch.setattr(workbench, "_update_job", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(workbench, "_update_runtime_run", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(workbench, "report_allure_refresh", lambda: {"refreshed": True})

    client = TestClient(app)
    response = client.post(
        "/api/workbench/auto-run",
        json={
            "project": "default",
            "requirement": "",
            "page_urls": ["http://localhost:5173/#/pms/product"],
            "source": "manual",
            "wait_seconds": 30,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["summary"]["total"] == 1
    assert body["summary"]["passed"] == 1
    assert body["items"][0]["page_surface"]["version"] == "PageSurfaceV1"
    assert body["items"][0]["page_surface"]["page"] == "product"
    assert body["items"][0]["page_surface"]["requested_url"] == "http://localhost:5173/#/pms/product"
    assert body["items"][0]["page_object"]["version"] == "PageObjectDraftV1"
    assert body["items"][0]["page_object"]["page"] == "product"
    assert body["items"][0]["page_semantic"]["version"] == "PageSemanticModelV1"
    assert body["items"][0]["page_semantic_summary"]["business_domain"] == "product"
    assert body["items"][0]["test_points"]["confidence"] >= 0
    assert body["items"][0]["test_points"]["review_summary"]["total_points"] >= 1
    assert "page_surface_summary" in body["items"][0]
    assert captured_requests
    assert captured_requests[0]["requirement"].startswith("自动生成的页面测试目标")
    assert "目标 URL" in captured_requests[0]["requirement"]
    assert captured_requests[0]["page"] == "product"


def test_auto_run_returns_review_state_for_low_confidence_points(monkeypatch: Any) -> None:
    monkeypatch.setattr(workbench, "_ensure_dirs", lambda: None)
    monkeypatch.setattr(
        workbench,
        "_extract_page_surface",
        lambda resolved_page_url: {
            "url": resolved_page_url,
            "page_title": "商品列表",
            "has_table": True,
            "search_placeholder": "商品名称",
            "query_button_text": "查询",
            "element_candidates": [
                {
                    "key": "pagination",
                    "label": "分页控件",
                    "locator_type": "css",
                    "locator_value": ".el-pagination",
                    "confidence": 0.42,
                    "warnings": ["定位器不唯一"],
                    "requires_review": True,
                }
            ],
            "confidence_summary": {
                "confidence": 0.66,
                "warnings": [],
                "low_confidence_count": 1,
                "low_confidence_items": [
                    {
                        "key": "pagination",
                        "label": "分页控件",
                        "locator_type": "css",
                        "locator_value": ".el-pagination",
                        "confidence": 0.42,
                        "warnings": ["定位器不唯一"],
                    }
                ],
                "requires_review": True,
            },
        },
    )
    monkeypatch.setattr(workbench, "_enhance_page_object_from_surface", lambda page, _surface: Path(f"/tmp/{page}.page-object.yaml"))
    monkeypatch.setattr(
        workbench,
        "_build_requirement_steps",
        lambda requirement, page, page_url, _surface: (
            [
                {"action": "login"},
                {"action": "goto", "value": page_url},
                {"action": "click", "target": "pagination"},
            ],
            {"status": "full", "required_coverage": ["navigation"], "missing_coverage": []},
        ),
    )
    monkeypatch.setattr(
        workbench,
        "_run_orchestrator_generate",
        lambda **kwargs: {
            "case": {
                "version": "v4",
                "id": f"tc-{kwargs['page']}-review",
                "title": "review case",
                "module": kwargs["page"],
                "execution": {
                    "runner": "playwright",
                    "page": kwargs["page"],
                    "variables": {},
                    "steps": [{"action": "login"}],
                },
            },
            "case_path": "assets/test-cases/ai-generated/tc-product-REVIEW.yaml",
            "test_points": {
                "points": [
                    {
                        "key": "tp-01",
                        "action": "click",
                        "target": "pagination",
                        "description": "验证分页可以切换",
                        "confidence": 0.48,
                        "warnings": ["依赖分页控件"],
                        "requires_review": True,
                    }
                ]
            },
            "requirement_spec": {"page": kwargs["page"]},
        },
    )
    monkeypatch.setattr(workbench, "_write_case_yaml", lambda *_args, **_kwargs: "id: tc-product-REVIEW\n")
    monkeypatch.setattr(workbench, "_read_case_yaml", lambda *_args, **_kwargs: ({"id": "tc-product-REVIEW"}, "id: tc-product-REVIEW\n"))
    monkeypatch.setattr(workbench, "_save_case_state", lambda *_args, **_kwargs: {"version": 1})
    monkeypatch.setattr(workbench, "_save_test_point_plan", lambda **_kwargs: Path("/tmp/test-point-plan.json"))
    monkeypatch.setattr(workbench, "_append_history", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(workbench, "_review_decisions_for_run", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(
        workbench,
        "_run_orchestrator_risk",
        lambda **_kwargs: (_ for _ in ()).throw(workbench.HTTPException(status_code=502, detail="risk orchestrator unavailable")),
    )
    monkeypatch.setattr(workbench, "_start_run", lambda **_kwargs: {"run_id": "RUN-REVIEW", "status": "running"})
    monkeypatch.setattr(workbench, "_wait_run_terminal", lambda run_id, timeout_seconds: ({"run_id": run_id, "status": "passed"}, False))
    monkeypatch.setattr(workbench, "_update_job", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(workbench, "_update_runtime_run", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(workbench, "report_allure_refresh", lambda: {"refreshed": True})

    client = TestClient(app)
    response = client.post(
        "/api/workbench/auto-run",
        json={
            "project": "default",
            "requirement": "",
            "page_urls": ["http://localhost:5173/#/pms/product"],
            "source": "manual",
            "wait_seconds": 30,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["summary"]["pending_reviews"] == 3
    assert body["summary"]["gate_manual_review"] == 1
    assert body["summary"]["gate_blocked"] == 0
    item = body["items"][0]
    assert item["risk_report"]["version"] == "RiskReportV1"
    assert item["risk_report"]["gate_decision"] == "manual_review"
    assert item["risk_report"]["requires_review"] is True
    assert item["risk_report"]["factors"]
    assert item["risk_report"]["factor_summary"]["factor_count"] >= 1
    assert item["risk_report"]["factor_summary"]["top_factor"]["factor"] == "execution_status"
    assert item["risk_report"]["metadata"]["factor_count"] >= 1
    assert item["risk_report"]["metadata"]["consumed_models"]["page_surface"] == "PageSurfaceV1"
    assert item["risk_report"]["metadata"]["consumed_models"]["page_semantic"] == "PageSemanticModelV1"
    assert item["risk_report"]["metadata"]["consumed_models"]["page_object"] == "PageObjectDraftV1"
    assert item["risk_report"]["metadata"]["consumed_models"]["test_points"] == "TestPointPlanV1"
    assert item["risk_report"]["metadata"]["semantic_page_type"] == "list"
    assert item["risk_report"]["metadata"]["semantic_business_domain"] == "product"
    assert any("page_semantic=type:list,domain:product" in row for row in item["risk_report"]["evidence"])
    assert item["review_state"]["requires_review"] is True
    assert item["test_points"]["review_summary"]["skip_suggestion_count"] == 1
    assert item["test_points"]["dependent_elements"] == ["pagination"]
    assert item["test_points"]["points"][0]["dependent_elements"] == ["pagination"]
    assert item["review_state"]["model_versions"]["page_surface"] == "PageSurfaceV1"
    assert item["review_state"]["model_versions"]["page_object"] == "PageObjectDraftV1"
    assert item["review_state"]["model_versions"]["test_points"] == "TestPointPlanV1"
    assert item["review_state"]["element"]["status"] == "pending"
    assert item["review_state"]["element"]["candidate_count"] == 1
    assert item["review_state"]["test_point"]["status"] == "pending"
    assert item["review_state"]["test_point"]["candidate_count"] == 1
    assert item["review_state"]["risk"]["status"] == "pending"
    assert item["review_state"]["risk"]["candidate_count"] == 1
    assert item["execution_gate"]["version"] == "ExecutionGateV1"
    assert item["execution_gate"]["decision"] == "manual_review"
    assert item["execution_gate"]["requires_review"] is True
    assert item["execution_gate"]["metrics"]["dependency_review_points"] == 1
    assert item["execution_gate"]["metrics"]["low_confidence_dependency_points"] == 1
    assert item["execution_gate"]["metrics"]["dependency_skip_points"] == 1
    assert any("低置信度元素影响测试点 1 个" in row for row in item["execution_gate"]["evidence"])
    assert item["test_points"]["points"][0]["suggestion"] == "skip"
    assert item["test_points"]["points"][0]["review_reason"]
    assert item["test_points"]["points"][0]["dependency_review"]["propagated"] is True
    assert item["test_points"]["points"][0]["dependency_review"]["low_confidence_dependency_count"] == 1


def test_auto_run_prefers_orchestrator_risk_report(monkeypatch: Any) -> None:
    monkeypatch.setattr(workbench, "_ensure_dirs", lambda: None)
    monkeypatch.setattr(
        workbench,
        "_extract_page_surface",
        lambda resolved_page_url: {
            "url": resolved_page_url,
            "page_title": "订单列表",
            "has_table": True,
            "confidence_summary": {
                "confidence": 0.92,
                "warnings": [],
                "low_confidence_count": 0,
                "low_confidence_items": [],
                "requires_review": False,
            },
        },
    )
    monkeypatch.setattr(workbench, "_enhance_page_object_from_surface", lambda page, _surface: Path(f"/tmp/{page}.page-object.yaml"))
    monkeypatch.setattr(
        workbench,
        "_build_requirement_steps",
        lambda requirement, page, page_url, _surface: (
            [
                {"action": "login"},
                {"action": "goto", "value": page_url},
                {"action": "assert_visible", "target": f"{page}_table"},
            ],
            {"status": "full", "required_coverage": ["navigation"], "missing_coverage": []},
        ),
    )
    monkeypatch.setattr(
        workbench,
        "_run_orchestrator_generate",
        lambda **kwargs: {
            "case": {
                "version": "v4",
                "id": "tc-order-risk",
                "title": "order risk",
                "module": kwargs["page"],
                "execution": {
                    "runner": "playwright",
                    "page": kwargs["page"],
                    "variables": {},
                    "steps": [{"action": "login"}],
                },
            },
            "case_path": "assets/test-cases/ai-generated/TC-ORDER-RISK.yaml",
            "test_points": {"points": [{"key": "tp-01", "action": "assert_visible", "target": "order_table", "confidence": 0.9}]},
            "requirement_spec": {"page": kwargs["page"], "priority": "P0", "quality_gate": {"decision": "allow", "stage": "orchestrate", "blockers": []}},
        },
    )
    monkeypatch.setattr(
        workbench,
        "_run_orchestrator_risk",
        lambda **_kwargs: {
            "risk_report": {
                "version": "RiskReportV1",
                "risk_score": 28,
                "risk_level": "low",
                "gate_decision": "allow",
                "recommendation": "风险可控，可放行并持续观察趋势。",
                "factors": [
                    {"factor": "business_priority", "score": 22, "reason": "priority=P1"},
                    {"factor": "execution_status", "score": 6, "reason": "status=passed"},
                ],
                "metadata": {"provider": "agent"},
            }
        },
    )
    monkeypatch.setattr(workbench, "_write_case_yaml", lambda *_args, **_kwargs: "id: TC-ORDER-RISK\n")
    monkeypatch.setattr(workbench, "_read_case_yaml", lambda *_args, **_kwargs: ({"id": "TC-ORDER-RISK"}, "id: TC-ORDER-RISK\n"))
    monkeypatch.setattr(workbench, "_save_case_state", lambda *_args, **_kwargs: {"version": 1})
    monkeypatch.setattr(workbench, "_save_test_point_plan", lambda **_kwargs: Path("/tmp/test-point-plan.json"))
    monkeypatch.setattr(workbench, "_append_history", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(workbench, "_review_decisions_for_run", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(workbench, "_start_run", lambda **_kwargs: {"run_id": "RUN-RISK-AGENT", "status": "running"})
    monkeypatch.setattr(
        workbench,
        "_find_run_item",
        lambda _run_id: {
            "run_id": "RUN-RISK-AGENT",
            "case_id": "TC-ORDER-RISK",
            "started_at": "2026-03-20T10:00:00+00:00",
            "finished_at": "2026-03-20T10:00:15+00:00",
            "execution_record": {
                "version": "ExecutionRecordV1",
                "run_id": "RUN-RISK-AGENT",
                "case_id": "TC-ORDER-RISK",
                "project": "default",
                "source": "auto-run",
                "mode": "generate_and_run",
                "status": "passed",
                "started_at": "2026-03-20T10:00:00+00:00",
                "finished_at": "2026-03-20T10:00:15+00:00",
                "step_summary": {"page": "order", "requirement_count": 1, "total_steps": 3, "action_types": ["login", "goto", "assert_visible"]},
                "evidence_index": {"total_files": 0, "artifact_categories": {}, "runner_exit_code": 0, "execution_requested": True},
            },
        },
    )
    monkeypatch.setattr(workbench, "_wait_run_terminal", lambda run_id, timeout_seconds: ({"run_id": run_id, "status": "passed"}, False))
    monkeypatch.setattr(workbench, "_update_job", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(workbench, "_update_runtime_run", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(workbench, "report_allure_refresh", lambda: {"refreshed": True})

    client = TestClient(app)
    response = client.post(
        "/api/workbench/auto-run",
        json={
            "project": "default",
            "requirement": "",
            "page_urls": ["http://localhost:5173/#/oms/order"],
            "source": "manual",
            "wait_seconds": 30,
        },
    )

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["risk_report"]["source"] == "risk-evaluation-agent"
    assert item["risk_report"]["gate_decision"] == "allow"
    assert item["risk_report"]["confidence"] >= 0.8
    assert item["risk_report"]["evidence"]
    assert item["risk_report"]["factors"][0]["factor"] == "business_priority"
    assert item["risk_report"]["factors"][0]["source"] == "risk-evaluation-agent"
    assert item["risk_report"]["factor_summary"]["factor_count"] == 2
    assert item["risk_report"]["factor_summary"]["top_factor"]["factor"] == "business_priority"
    assert item["risk_report"]["metadata"]["factor_count"] == 2
    assert item["risk_report"]["metadata"]["consumed_models"]["page_semantic"] == "PageSemanticModelV1"
    assert item["risk_report"]["metadata"]["semantic_page_type"] == "list"
    assert item["risk_report"]["metadata"]["semantic_business_domain"] == "order"
    assert any("page_semantic=type:list,domain:order" in row for row in item["risk_report"]["evidence"])


def test_save_review_persists_confirmation(monkeypatch: Any, tmp_path: Path) -> None:
    review_file = tmp_path / "review-decisions.json"
    history_events: list[dict[str, Any]] = []
    access_token = create_access_token(subject="1", username="betty", role="admin")

    monkeypatch.setattr(workbench, "REVIEW_DECISIONS_FILE", review_file)
    monkeypatch.setattr(workbench, "_ensure_dirs", lambda: review_file.parent.mkdir(parents=True, exist_ok=True))
    monkeypatch.setattr(workbench, "_append_history", lambda entry: history_events.append(entry))

    client = TestClient(app)
    response = client.post(
        "/api/workbench/reviews",
        headers={"Authorization": f"Bearer {access_token}"},
        json={
            "project": "default",
            "run_id": "RUN-123",
            "case_id": "tc-product-001",
            "page": "product",
            "review_type": "test_point",
            "status": "confirmed",
            "items": [
                {
                    "key": "tp-01",
                    "label": "验证分页可以切换",
                    "confidence": 0.48,
                    "warnings": ["依赖分页控件"],
                    "action": "click",
                    "target": "pagination",
                    "suggestion": "skip",
                    "review_reason": "需要人工确认后执行",
                    "dependent_elements": ["pagination"],
                    "dependency_review": {
                        "mode": "rule_first_surface",
                        "propagated": True,
                        "dependent_elements": ["pagination"],
                        "matched_elements": ["pagination"],
                        "low_confidence_dependencies": [
                            {
                                "key": "pagination",
                                "label": "分页控件",
                                "confidence": 0.48,
                                "warnings": ["定位器不唯一"],
                            }
                        ],
                        "missing_dependencies": [],
                        "evidence": ["低置信度依赖元素：分页控件(48%)"],
                    },
                }
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["summary"]["review_type"] == "test_point"
    assert body["summary"]["status"] == "confirmed"
    saved = json.loads(review_file.read_text(encoding="utf-8"))
    assert len(saved) == 1
    assert saved[0]["run_id"] == "RUN-123"
    assert saved[0]["page"] == "product"
    assert saved[0]["confirmed_by"] == "betty"
    assert saved[0]["confirmed_by_role"] == "admin"
    assert saved[0]["items"][0]["key"] == "tp-01"
    assert saved[0]["items"][0]["suggestion"] == "skip"
    assert saved[0]["items"][0]["dependent_elements"] == ["pagination"]
    assert saved[0]["items"][0]["dependency_review"]["propagated"] is True
    assert saved[0]["items"][0]["dependency_review"]["evidence"]
    assert len(history_events) == 1
    assert history_events[0]["action"] == "review_confirmed"
    assert history_events[0]["review_type"] == "test_point"
    assert history_events[0]["run_id"] == "RUN-123"
    assert history_events[0]["page"] == "product"
    assert history_events[0]["confirmed_by"] == "betty"
    assert history_events[0]["actor_display"] == "betty (admin)"
    assert history_events[0]["review_item_count"] == 1
    assert history_events[0]["detail_summary"] == "test_point 确认 1 项"
    review_state = workbench._build_run_review_state_from_decisions(project="default", run_id="RUN-123", page="product")
    assert review_state["test_point"]["confirmed_by"] == "betty"
    assert review_state["test_point"]["confirmed_by_role"] == "admin"
    assert review_state["test_point"]["actor_display"] == "betty (admin)"


def test_save_review_accepts_risk_confirmation(monkeypatch: Any, tmp_path: Path) -> None:
    review_file = tmp_path / "review-decisions.json"
    calibration_file = tmp_path / "failure-source-calibrations.json"
    history_events: list[dict[str, Any]] = []

    monkeypatch.setattr(workbench, "REVIEW_DECISIONS_FILE", review_file)
    monkeypatch.setattr(workbench, "FAILURE_SOURCE_CALIBRATIONS_FILE", calibration_file)
    monkeypatch.setattr(workbench, "_ensure_dirs", lambda: review_file.parent.mkdir(parents=True, exist_ok=True))
    monkeypatch.setattr(workbench, "_append_history", lambda entry: history_events.append(entry))
    monkeypatch.setattr(
        workbench,
        "_resolve_run_failure_snapshot",
        lambda _run_id: {
            "analysis": {
                "failure_source": "case_design",
                "failure_source_reason": "断言预期与页面现状不一致",
                "failure_source_confidence": 0.81,
                "requires_manual_review": True,
                "source_evidence": [{"signal": "token", "value": "assertion", "origin": "stdout", "supports": "case_design"}],
            }
        },
    )

    client = TestClient(app)
    response = client.post(
        "/api/workbench/reviews",
        headers={"X-User-Name": "reviewer-a", "X-User-Role": "qa"},
        json={
            "project": "default",
            "run_id": "RUN-RISK",
            "case_id": "tc-product-002",
            "page": "product",
            "review_type": "risk",
            "status": "confirmed",
            "items": [
                {
                    "key": "risk_decision",
                    "label": "风险决策确认",
                    "confidence": 0.9,
                    "warnings": ["执行状态=coverage_gap，基础风险分=72"],
                    "gate_decision": "manual_review",
                    "risk_level": "medium",
                    "risk_score": 58,
                }
            ],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["review_type"] == "risk"
    assert payload["summary"]["confirmed_by"] == "reviewer-a"
    assert payload["summary"]["confirmed_by_role"] == "qa"
    assert payload["calibration_sample"]["human_decision"] == "accepted"
    assert payload["calibration_sample"]["confirmed_failure_source"] == "case_design"
    saved = json.loads(review_file.read_text(encoding="utf-8"))
    assert saved[0]["review_type"] == "risk"
    assert saved[0]["items"][0]["key"] == "risk_decision"
    assert saved[0]["confirmed_by"] == "reviewer-a"
    assert saved[0]["confirmed_by_source"] == "x-user-name"
    calibration_items = json.loads(calibration_file.read_text(encoding="utf-8"))
    assert calibration_items[0]["predicted_failure_source"] == "case_design"
    assert calibration_items[0]["confirmed_failure_source"] == "case_design"
    assert calibration_items[0]["usable_for_training"] is True
    assert calibration_items[0]["predicted_source_evidence"][0]["supports"] == "case_design"
    assert history_events[-1]["action"] == "failure_source_calibration_recorded"


def test_save_review_records_corrected_failure_source_feedback(monkeypatch: Any, tmp_path: Path) -> None:
    review_file = tmp_path / "review-decisions.json"
    calibration_file = tmp_path / "failure-source-calibrations.json"

    monkeypatch.setattr(workbench, "REVIEW_DECISIONS_FILE", review_file)
    monkeypatch.setattr(workbench, "FAILURE_SOURCE_CALIBRATIONS_FILE", calibration_file)
    monkeypatch.setattr(workbench, "_ensure_dirs", lambda: review_file.parent.mkdir(parents=True, exist_ok=True))
    monkeypatch.setattr(
        workbench,
        "_resolve_run_failure_snapshot",
        lambda _run_id: {
            "analysis": {
                "failure_source": "page_object",
                "failure_source_reason": "旧定位器疑似漂移",
                "failure_source_confidence": 0.9,
                "requires_manual_review": False,
                "source_evidence": [{"signal": "token", "value": "selector", "origin": "stdout", "supports": "page_object"}],
            }
        },
    )

    client = TestClient(app)
    response = client.post(
        "/api/workbench/reviews",
        headers={"X-User-Name": "reviewer-b", "X-User-Role": "qa"},
        json={
            "project": "default",
            "run_id": "RUN-CORRECTED",
            "case_id": "tc-product-004",
            "page": "product",
            "review_type": "test_point",
            "status": "confirmed",
            "items": [{"key": "tp-risk", "label": "人工复核失败来源", "confidence": 0.95}],
            "failure_source_feedback": {
                "decision": "corrected",
                "corrected_failure_source": "app_bug",
                "reason": "接口 500 才是根因，页面定位只是连带现象",
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["calibration_sample"]["human_decision"] == "corrected"
    assert payload["calibration_sample"]["confirmed_failure_source"] == "app_bug"
    calibration_items = json.loads(calibration_file.read_text(encoding="utf-8"))
    assert calibration_items[0]["review_type"] == "test_point"
    assert calibration_items[0]["predicted_failure_source"] == "page_object"
    assert calibration_items[0]["confirmed_failure_source"] == "app_bug"
    assert calibration_items[0]["feedback_reason"] == "接口 500 才是根因，页面定位只是连带现象"
    assert calibration_items[0]["usable_for_training"] is True


def test_save_review_rejects_anonymous_confirmation(monkeypatch: Any, tmp_path: Path) -> None:
    review_file = tmp_path / "review-decisions.json"
    history_events: list[dict[str, Any]] = []

    monkeypatch.setattr(workbench, "REVIEW_DECISIONS_FILE", review_file)
    monkeypatch.setattr(workbench, "_ensure_dirs", lambda: review_file.parent.mkdir(parents=True, exist_ok=True))
    monkeypatch.setattr(workbench, "_append_history", lambda entry: history_events.append(entry))

    client = TestClient(app)
    response = client.post(
        "/api/workbench/reviews",
        json={
            "project": "default",
            "run_id": "RUN-ANON",
            "case_id": "tc-product-003",
            "page": "product",
            "review_type": "element",
            "status": "confirmed",
            "items": [
                {
                    "key": "pagination",
                    "label": "分页控件",
                    "confidence": 0.45,
                    "warnings": ["定位器不唯一"],
                    "locator_type": "css",
                    "locator_value": ".pagination",
                }
            ],
        },
    )

    assert response.status_code == 401
    detail = response.json()["detail"]
    assert detail["code"] == "review_auth_required"
    assert "请先登录" in detail["message"]
    assert not review_file.exists()
    assert len(history_events) == 1
    assert history_events[0]["action"] == "review_rejected_auth"
    assert history_events[0]["status"] == "rejected"
    assert history_events[0]["confirmed_by"] == "anonymous"
    assert history_events[0]["note"] == "review_auth_required"


def test_save_execution_gate_decision_persists_audit_record(monkeypatch: Any, tmp_path: Path) -> None:
    gate_file = tmp_path / "execution-gate-decisions.json"
    history_events: list[dict[str, Any]] = []
    access_token = create_access_token(subject="2", username="gate-owner", role="qa-lead")

    monkeypatch.setattr(workbench, "EXECUTION_GATE_DECISIONS_FILE", gate_file)
    monkeypatch.setattr(workbench, "_ensure_dirs", lambda: gate_file.parent.mkdir(parents=True, exist_ok=True))
    monkeypatch.setattr(workbench, "_append_history", lambda entry: history_events.append(entry))
    monkeypatch.setattr(
        workbench,
        "_find_run_item",
        lambda _run_id: {
            "run_id": "RUN-GATE-1",
            "project": "default",
            "page": "product",
            "execution_gate": {
                "version": "ExecutionGateV1",
                "page": "product",
                "decision": "manual_review",
                "effective_decision": "manual_review",
                "decision_source": "system",
                "requires_review": True,
                "blockers": ["存在依赖元素未识别的测试点 1 个。"],
                "warnings": ["存在待确认测试点 1 个。"],
                "evidence": [
                    "页面分析未识别依赖元素影响测试点 1 个，达到阻断阈值 1。",
                    "测试点层存在待确认项 1 个。",
                ],
                "metrics": {"missing_dependency_points": 1, "pending_test_points": 1},
                "config_snapshot": {"block_missing_dependency_points_threshold": 1},
            },
        },
    )

    client = TestClient(app)
    response = client.post(
        "/api/workbench/execution-gate/decisions",
        headers={"Authorization": f"Bearer {access_token}"},
        json={
            "project": "default",
            "run_id": "RUN-GATE-1",
            "case_id": "tc-product-001",
            "page": "product",
            "decision": "block",
            "note": "分页控件定位不稳定，先阻断。",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["summary"]["decision"] == "block"
    assert body["summary"]["decided_by"] == "gate-owner"
    saved = json.loads(gate_file.read_text(encoding="utf-8"))
    assert len(saved) == 1
    assert saved[0]["run_id"] == "RUN-GATE-1"
    assert saved[0]["decision"] == "block"
    assert saved[0]["decided_by"] == "gate-owner"
    assert len(history_events) == 1
    assert history_events[0]["action"] == "execution_gate_decided"
    assert "执行门禁人工决策：block" in history_events[0]["detail_summary"]
    assert "存在依赖元素未识别的测试点 1 个。" in history_events[0]["gate_reason_summary"]
    assert history_events[0]["matched_rules"][0]["level"] == "blocker"
    assert history_events[0]["metrics"]["missing_dependency_points"] == 1
    assert history_events[0]["config_snapshot"]["block_missing_dependency_points_threshold"] == 1


def test_save_execution_gate_decision_rejects_unprivileged_block(monkeypatch: Any, tmp_path: Path) -> None:
    gate_file = tmp_path / "execution-gate-decisions.json"
    history_events: list[dict[str, Any]] = []
    access_token = create_access_token(subject="3", username="viewer-a", role="viewer")

    monkeypatch.setattr(workbench, "EXECUTION_GATE_DECISIONS_FILE", gate_file)
    monkeypatch.setattr(workbench, "_ensure_dirs", lambda: gate_file.parent.mkdir(parents=True, exist_ok=True))
    monkeypatch.setattr(workbench, "_append_history", lambda entry: history_events.append(entry))

    client = TestClient(app)
    response = client.post(
        "/api/workbench/execution-gate/decisions",
        headers={"Authorization": f"Bearer {access_token}"},
        json={
            "project": "default",
            "run_id": "RUN-GATE-UNPRIV",
            "case_id": "tc-product-001",
            "page": "product",
            "decision": "block",
            "note": "没有权限也尝试阻断。",
        },
    )

    assert response.status_code == 403
    detail = response.json()["detail"]
    assert detail["code"] == "execution_gate_decision_forbidden"
    assert "无权执行门禁决策" in detail["message"]
    assert not gate_file.exists()
    assert len(history_events) == 1
    assert history_events[0]["action"] == "execution_gate_decision_rejected_permission"
    assert history_events[0]["status"] == "rejected"


def test_execution_gate_approve_rejects_anonymous_and_persists_audit(monkeypatch: Any, tmp_path: Path) -> None:
    gate_file = tmp_path / "execution-gate-decisions.json"
    history_events: list[dict[str, Any]] = []

    monkeypatch.setattr(workbench, "EXECUTION_GATE_DECISIONS_FILE", gate_file)
    monkeypatch.setattr(workbench, "_ensure_dirs", lambda: gate_file.parent.mkdir(parents=True, exist_ok=True))
    monkeypatch.setattr(workbench, "_append_history", lambda entry: history_events.append(entry))

    client = TestClient(app)
    response = client.post(
        "/api/workbench/execution-gate/decisions/approve",
        json={
            "project": "default",
            "run_id": "RUN-GATE-APPROVE-AUTH",
            "page": "product",
            "note": "匿名尝试二次审批。",
        },
    )

    assert response.status_code == 401
    detail = response.json()["detail"]
    assert detail["code"] == "review_auth_required"
    assert "请先登录" in detail["message"]
    assert len(history_events) == 1
    assert history_events[0]["action"] == "execution_gate_approve_rejected_auth"
    assert history_events[0]["status"] == "rejected"
    assert history_events[0]["confirmed_by"] == "anonymous"
    assert history_events[0]["note"] == "review_auth_required"


def test_execution_gate_revoke_rejects_anonymous_and_persists_audit(monkeypatch: Any, tmp_path: Path) -> None:
    gate_file = tmp_path / "execution-gate-decisions.json"
    history_events: list[dict[str, Any]] = []

    monkeypatch.setattr(workbench, "EXECUTION_GATE_DECISIONS_FILE", gate_file)
    monkeypatch.setattr(workbench, "_ensure_dirs", lambda: gate_file.parent.mkdir(parents=True, exist_ok=True))
    monkeypatch.setattr(workbench, "_append_history", lambda entry: history_events.append(entry))

    client = TestClient(app)
    response = client.post(
        "/api/workbench/execution-gate/decisions/revoke",
        json={
            "project": "default",
            "run_id": "RUN-GATE-REVOKE-AUTH",
            "page": "product",
            "note": "匿名尝试撤销。",
        },
    )

    assert response.status_code == 401
    detail = response.json()["detail"]
    assert detail["code"] == "review_auth_required"
    assert "请先登录" in detail["message"]
    assert len(history_events) == 1
    assert history_events[0]["action"] == "execution_gate_revoke_rejected_auth"
    assert history_events[0]["status"] == "rejected"
    assert history_events[0]["confirmed_by"] == "anonymous"
    assert history_events[0]["note"] == "review_auth_required"


def test_execution_gate_second_approval_and_revoke_flow(monkeypatch: Any, tmp_path: Path) -> None:
    gate_file = tmp_path / "execution-gate-decisions.json"
    history_events: list[dict[str, Any]] = []
    gate_owner_token = create_access_token(subject="4", username="gate-owner", role="qa-lead")
    admin_token = create_access_token(subject="1", username="betty", role="admin")

    monkeypatch.setattr(workbench, "EXECUTION_GATE_DECISIONS_FILE", gate_file)
    monkeypatch.setattr(workbench, "_ensure_dirs", lambda: gate_file.parent.mkdir(parents=True, exist_ok=True))
    monkeypatch.setattr(workbench, "_append_history", lambda entry: history_events.append(entry))
    monkeypatch.setattr(workbench.SETTINGS, "execution_gate_dual_approval_enabled", True, raising=False)
    monkeypatch.setattr(
        workbench,
        "_find_run_item",
        lambda _run_id: {
            "run_id": "RUN-GATE-2",
            "project": "default",
            "page": "product",
            "execution_gate": {
                "version": "ExecutionGateV1",
                "page": "product",
                "decision": "block",
                "effective_decision": "block",
                "decision_source": "system",
                "requires_review": True,
                "blockers": ["存在依赖元素未识别的测试点 1 个。"],
                "warnings": ["存在受低置信度元素影响的测试点 1 个。"],
                "evidence": [
                    "页面分析未识别依赖元素影响测试点 1 个，达到阻断阈值 1。",
                    "低置信度元素影响测试点 1 个。",
                ],
                "metrics": {"missing_dependency_points": 1, "low_confidence_dependency_points": 1},
                "config_snapshot": {"block_missing_dependency_points_threshold": 1},
            },
        },
    )

    client = TestClient(app)
    create_response = client.post(
        "/api/workbench/execution-gate/decisions",
        headers={"Authorization": f"Bearer {gate_owner_token}"},
        json={
            "project": "default",
            "run_id": "RUN-GATE-2",
            "case_id": "tc-product-001",
            "page": "product",
            "decision": "block",
            "note": "分页控件定位不稳定，先阻断。",
        },
    )
    assert create_response.status_code == 200
    created = create_response.json()["item"]
    assert created["approval_status"] == "pending_second_approval"
    assert created["record_status"] == "active"

    saved = json.loads(gate_file.read_text(encoding="utf-8"))
    assert saved[0]["approval_status"] == "pending_second_approval"
    assert saved[0]["record_status"] == "active"

    approve_response = client.post(
        "/api/workbench/execution-gate/decisions/approve",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "project": "default",
            "run_id": "RUN-GATE-2",
            "page": "product",
            "note": "复核通过，可以继续执行。",
        },
    )
    assert approve_response.status_code == 200
    approved = approve_response.json()["item"]
    assert approved["approval_status"] == "approved"
    assert approved["second_approver"] == "betty"
    assert approved["second_approver_role"] == "admin"

    saved = json.loads(gate_file.read_text(encoding="utf-8"))
    assert saved[0]["approval_status"] == "approved"
    assert saved[0]["second_approver"] == "betty"
    assert saved[0]["second_approver_role"] == "admin"

    revoke_response = client.post(
        "/api/workbench/execution-gate/decisions/revoke",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "project": "default",
            "run_id": "RUN-GATE-2",
            "page": "product",
            "note": "后续发现门禁条件变化，撤销本次决策。",
        },
    )
    assert revoke_response.status_code == 200
    revoked = revoke_response.json()["item"]
    assert revoked["record_status"] == "revoked"
    assert revoked["revoked_by"] == "betty"
    assert revoked["revoked_by_role"] == "admin"

    saved = json.loads(gate_file.read_text(encoding="utf-8"))
    assert saved[0]["record_status"] == "revoked"
    assert saved[0]["revoked_by"] == "betty"
    assert len(history_events) == 3
    assert history_events[0]["action"] == "execution_gate_decided"
    assert history_events[1]["action"] == "execution_gate_approved"
    assert history_events[2]["action"] == "execution_gate_revoked"
    assert "存在依赖元素未识别的测试点 1 个。" in history_events[1]["gate_reason_summary"]
    assert history_events[2]["matched_rules"][0]["message"] == "存在依赖元素未识别的测试点 1 个。"


def test_runs_endpoint_surfaces_manual_execution_gate_decision(monkeypatch: Any) -> None:
    monkeypatch.setattr(workbench, "_ensure_dirs", lambda: None)

    def fake_read_json_list(path: Path) -> list[dict[str, Any]]:
        if path == workbench.RUNTIME_RUNS_FILE:
            return [
                {
                    "run_id": "run-gate-2",
                    "project": "default",
                    "case_id": "tc-product-002",
                    "page": "product",
                    "status": "passed",
                    "execution_gate": {
                        "version": "ExecutionGateV1",
                        "page": "product",
                        "decision": "manual_review",
                        "requires_review": True,
                        "blockers": [],
                        "warnings": ["存在待确认测试点 1 个。"],
                        "evidence": ["测试点层存在待确认项 1 个。"],
                        "metrics": {"pending_test_points": 1},
                        "config_snapshot": {"warn_on_pending_test_points": True},
                    },
                }
            ]
        if path == workbench.EXECUTION_GATE_DECISIONS_FILE:
            return [
                {
                    "project": "default",
                    "run_id": "run-gate-2",
                    "case_id": "tc-product-002",
                    "page": "product",
                    "decision": "allow",
                    "note": "人工放行，本次仅冒烟验证。",
                    "decided_by": "betty",
                    "decided_by_role": "admin",
                    "updated_at": "2026-03-21T09:00:00+00:00",
                }
            ]
        if path == workbench.HISTORY_FILE:
            return [
                {
                    "timestamp": "2026-03-21T09:00:00+00:00",
                    "action": "execution_gate_decided",
                    "run_id": "run-gate-2",
                    "page": "product",
                    "review_type": "execution_gate",
                    "status": "confirmed",
                    "actor_display": "betty (admin)",
                    "detail_summary": "执行门禁人工决策：allow（存在待确认测试点 1 个。）",
                    "decision": "allow",
                    "approval_status": "approved",
                    "record_status": "active",
                    "gate_reason_summary": "存在待确认测试点 1 个。",
                    "matched_rules": [{"level": "warning", "message": "存在待确认测试点 1 个。"}],
                    "evidence": ["测试点层存在待确认项 1 个。"],
                    "metrics": {"pending_test_points": 1},
                    "config_snapshot": {"warn_on_pending_test_points": True},
                }
            ]
        return []

    monkeypatch.setattr(workbench, "_read_json_list", fake_read_json_list)

    client = TestClient(app)
    response = client.get("/api/workbench/runs/run-gate-2")

    assert response.status_code == 200
    item = response.json()["item"]
    gate = item["execution_gate"]
    assert gate["decision"] == "manual_review"
    assert gate["effective_decision"] == "allow"
    assert gate["decision_source"] == "manual_override"
    assert gate["approval_status"] == "approved"
    assert gate["record_status"] == "active"
    assert gate["manual_decision"]["decision"] == "allow"
    assert gate["manual_decision"]["decided_by"] == "betty"
    assert item["review_audit_timeline"][0]["review_type"] == "execution_gate"
    assert item["review_audit_timeline"][0]["gate_reason_summary"] == "存在待确认测试点 1 个。"
    assert item["review_audit_timeline"][0]["matched_rules"][0]["level"] == "warning"


def test_runs_endpoint_surfaces_pending_and_revoked_execution_gate_decisions(monkeypatch: Any) -> None:
    monkeypatch.setattr(workbench, "_ensure_dirs", lambda: None)
    monkeypatch.setattr(workbench, "_get_job", lambda _run_id: None)

    def fake_read_json_list(path: Path) -> list[dict[str, Any]]:
        if path == workbench.RUNTIME_RUNS_FILE:
            return [
                {
                    "run_id": "run-gate-3",
                    "project": "default",
                    "case_id": "tc-product-003",
                    "page": "product",
                    "source": "manual",
                    "status": "passed",
                    "execution_gate": {
                        "version": "ExecutionGateV1",
                        "page": "product",
                        "decision": "allow",
                        "effective_decision": "allow",
                        "requires_review": False,
                        "blockers": [],
                        "warnings": [],
                        "metrics": {},
                    },
                },
                {
                    "run_id": "run-gate-4",
                    "project": "default",
                    "case_id": "tc-product-004",
                    "page": "product",
                    "source": "manual",
                    "status": "passed",
                    "execution_gate": {
                        "version": "ExecutionGateV1",
                        "page": "product",
                        "decision": "manual_review",
                        "effective_decision": "manual_review",
                        "requires_review": True,
                        "blockers": [],
                        "warnings": ["存在待确认测试点 1 个。"],
                        "metrics": {},
                    },
                },
            ]
        if path == workbench.EXECUTION_GATE_DECISIONS_FILE:
            return [
                {
                    "project": "default",
                    "run_id": "run-gate-3",
                    "case_id": "tc-product-003",
                    "page": "product",
                    "decision": "block",
                    "approval_status": "pending_second_approval",
                    "record_status": "active",
                    "note": "待二次审批。",
                    "decided_by": "gate-owner",
                    "decided_by_role": "qa-lead",
                    "updated_at": "2026-03-21T09:05:00+00:00",
                },
                {
                    "project": "default",
                    "run_id": "run-gate-4",
                    "case_id": "tc-product-004",
                    "page": "product",
                    "decision": "block",
                    "approval_status": "approved",
                    "record_status": "revoked",
                    "note": "已撤销。",
                    "decided_by": "gate-owner",
                    "decided_by_role": "qa-lead",
                    "revoked_by": "betty",
                    "revoked_by_role": "admin",
                    "revoked_at": "2026-03-21T09:10:00+00:00",
                    "updated_at": "2026-03-21T09:10:00+00:00",
                },
            ]
        return []

    monkeypatch.setattr(workbench, "_read_json_list", fake_read_json_list)

    client = TestClient(app)

    response = client.get("/api/workbench/runs/run-gate-3")
    assert response.status_code == 200
    item = response.json()["item"]
    gate = item["execution_gate"]
    assert gate["decision"] == "allow"
    assert gate["effective_decision"] == "allow"
    assert gate["decision_source"] == "manual_pending_second_approval"
    assert gate["approval_status"] == "pending_second_approval"
    assert gate["record_status"] == "active"
    assert gate["manual_decision"]["decision"] == "block"
    assert gate["manual_decision"]["approval_status"] == "pending_second_approval"

    response = client.get("/api/workbench/runs/run-gate-4")
    assert response.status_code == 200
    item = response.json()["item"]
    gate = item["execution_gate"]
    assert gate["decision"] == "manual_review"
    assert gate["effective_decision"] == "manual_review"
    assert gate["decision_source"] == "manual_revoked"
    assert gate["approval_status"] == "approved"
    assert gate["record_status"] == "revoked"
    assert gate["manual_decision"]["record_status"] == "revoked"
    assert gate["manual_decision"]["revoked_by"] == "betty"


def test_workbench_history_supports_audit_filters(monkeypatch: Any) -> None:
    history = [
        {
            "timestamp": "2026-03-20T10:00:00+00:00",
            "action": "review_confirmed",
            "case_id": "tc-product-001",
            "page": "product",
            "confirmed_by": "betty",
            "actor_display": "betty (admin)",
            "status": "confirmed",
        },
        {
            "timestamp": "2026-03-20T10:05:00+00:00",
            "action": "review_rejected_auth",
            "case_id": "tc-product-002",
            "page": "product",
            "confirmed_by": "anonymous",
            "actor_display": "anonymous",
            "status": "rejected",
        },
        {
            "timestamp": "2026-03-20T10:10:00+00:00",
            "action": "execution_gate_decided",
            "case_id": "tc-product-003",
            "page": "product",
            "confirmed_by": "betty",
            "actor_display": "betty (admin)",
            "status": "confirmed",
            "gate_reason_summary": "存在待确认测试点 1 个。",
            "matched_rules": [{"level": "warning", "message": "存在待确认测试点 1 个。"}],
            "evidence": ["测试点层存在待确认项 1 个。"],
        },
        {
            "timestamp": "2026-03-20T10:12:00+00:00",
            "action": "execution_gate_approve_rejected_auth",
            "case_id": "",
            "page": "product",
            "confirmed_by": "anonymous",
            "actor_display": "anonymous",
            "status": "rejected",
            "detail_summary": "执行门禁二次审批被拒绝：未登录或身份不可追溯",
            "note": "review_auth_required",
        },
    ]
    monkeypatch.setattr(workbench, "_read_json_list", lambda path: history if path == workbench.HISTORY_FILE else [])

    client = TestClient(app)

    response = client.get("/api/workbench/history?action=review_confirmed")
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["action"] == "review_confirmed"

    response = client.get("/api/workbench/history?status=rejected")
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 2
    assert all(item["status"] == "rejected" for item in items)

    response = client.get("/api/workbench/history?actor=betty")
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 2
    assert items[0]["confirmed_by"] == "betty"

    response = client.get("/api/workbench/history?action=execution_gate_decided")
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["gate_reason_summary"] == "存在待确认测试点 1 个。"
    assert items[0]["matched_rules"][0]["level"] == "warning"
    assert items[0]["evidence"][0] == "测试点层存在待确认项 1 个。"

    response = client.get("/api/workbench/history?action=execution_gate_approve_rejected_auth")
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["status"] == "rejected"
    assert items[0]["note"] == "review_auth_required"


def test_workbench_history_supports_keyword_sort_and_pagination(monkeypatch: Any) -> None:
    history = [
        {
            "timestamp": "2026-03-20T10:00:00+00:00",
            "action": "review_confirmed",
            "run_id": "run-order-2",
            "case_id": "TC-ORDER-002",
            "page": "order",
            "actor_display": "betty (admin)",
            "status": "confirmed",
        },
        {
            "timestamp": "2026-03-20T09:55:00+00:00",
            "action": "execution_gate_approved",
            "run_id": "run-order-1",
            "case_id": "TC-ORDER-001",
            "page": "order",
            "actor_display": "betty (admin)",
            "status": "confirmed",
        },
        {
            "timestamp": "2026-03-20T09:40:00+00:00",
            "action": "review_confirmed",
            "run_id": "run-product-1",
            "case_id": "TC-PRODUCT-001",
            "page": "product",
            "actor_display": "alice (qa)",
            "status": "rejected",
        },
    ]
    monkeypatch.setattr(workbench, "_read_json_list", lambda path: history if path == workbench.HISTORY_FILE else [])
    monkeypatch.setattr(workbench, "_resolve_run_failure_snapshot", lambda _run_id: {})
    monkeypatch.setattr(workbench, "_resolve_run_governance_snapshot", lambda _run_id: {})

    client = TestClient(app)
    response = client.get("/api/workbench/history?keyword=order&sort=action_asc&page=1&page_size=1")

    assert response.status_code == 200
    payload = response.json()
    assert payload["pagination"]["page"] == 1
    assert payload["pagination"]["page_size"] == 1
    assert payload["pagination"]["total_items"] == 2
    assert payload["pagination"]["total_pages"] == 2
    assert payload["summary"]["total_items"] == 2
    assert payload["summary"]["top_action"] == {"value": "execution_gate_approved", "count": 1}
    assert payload["items"][0]["run_id"] == "run-order-1"

    response = client.get("/api/workbench/history?keyword=order&sort=action_asc&page=2&page_size=1")
    assert response.status_code == 200
    payload = response.json()
    assert payload["pagination"]["page"] == 2
    assert len(payload["items"]) == 1
    assert payload["items"][0]["run_id"] == "run-order-2"


def test_workbench_history_enriches_failure_source_from_run_snapshot(monkeypatch: Any) -> None:
    history = [
        {
            "timestamp": "2026-03-20T10:00:00+00:00",
            "action": "review_confirmed",
            "run_id": "run-failure-1",
            "case_id": "tc-product-001",
            "page": "product",
            "confirmed_by": "betty",
            "actor_display": "betty (admin)",
            "status": "confirmed",
        }
    ]
    monkeypatch.setattr(workbench, "_read_json_list", lambda path: history if path == workbench.HISTORY_FILE else [])
    monkeypatch.setattr(
        workbench,
        "_resolve_run_failure_snapshot",
        lambda _run_id: {
            "analysis": {
                "failure_source": "page_object",
                "failure_source_reason": "定位器与页面元素不再匹配",
                "source_evidence": [{"signal": "token", "value": "locator", "origin": "stdout", "supports": "page_object"}],
                "requires_manual_review": False,
            }
        },
    )

    client = TestClient(app)
    response = client.get("/api/workbench/history")

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["failure_source"] == "page_object"
    assert items[0]["failure_source_reason"] == "定位器与页面元素不再匹配"
    assert items[0]["source_evidence"][0]["supports"] == "page_object"
    assert items[0]["requires_manual_review"] is False
    assert "失败来源=page_object" in items[0]["detail_summary"]


def test_workbench_history_enriches_risk_and_self_healing_from_run_snapshot(monkeypatch: Any) -> None:
    history = [
        {
            "timestamp": "2026-03-20T10:00:00+00:00",
            "action": "self_heal",
            "run_id": "run-governance-1",
            "case_id": "tc-product-001",
            "page": "product",
            "status": "rejected",
        }
    ]
    monkeypatch.setattr(workbench, "_read_json_list", lambda path: history if path == workbench.HISTORY_FILE else [])
    monkeypatch.setattr(workbench, "_resolve_run_failure_snapshot", lambda _run_id: {})
    monkeypatch.setattr(
        workbench,
        "_resolve_run_governance_snapshot",
        lambda _run_id: {
            "risk_summary": {
                "risk_level": "medium",
                "gate_decision": "manual_review",
                "requires_review": True,
                "risk_score": 58,
                "factor_count": 3,
                "top_factor": {
                    "factor": "pending_review_sections",
                    "score": 10,
                    "reason": "仍有 2 个确认分组待处理",
                    "category": "review",
                },
                "provider": "orchestrator",
                "source": "risk-evaluation-agent",
            },
            "self_healing_summary": {
                "attempted": True,
                "result_file_count": 1,
                "status": "rejected",
                "healed": False,
                "rolled_back": False,
                "reason": "Advice type 'assertion_update' is outside deterministic auto-healing boundary.",
                "boundary": {
                    "version": "SelfHealingBoundaryV1",
                    "allowed": False,
                    "advice_type": "assertion_update",
                    "reason": "Advice type 'assertion_update' is outside deterministic auto-healing boundary.",
                },
            },
        },
    )

    client = TestClient(app)
    response = client.get("/api/workbench/history")

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["risk_summary"]["risk_level"] == "medium"
    assert items[0]["risk_summary"]["top_factor"]["factor"] == "pending_review_sections"
    assert items[0]["self_healing_summary"]["status"] == "rejected"
    assert items[0]["self_healing_summary"]["boundary"]["allowed"] is False
    assert "manual_review" in items[0]["detail_summary"]


def test_workbench_history_filters_by_risk_gate_and_self_healing_status(monkeypatch: Any) -> None:
    history = [
        {
            "timestamp": "2026-03-20T10:00:00+00:00",
            "action": "self_heal",
            "run_id": "run-governance-allow",
            "case_id": "TC-ALLOW-001",
            "page": "product",
            "status": "confirmed",
        },
        {
            "timestamp": "2026-03-20T10:05:00+00:00",
            "action": "self_heal",
            "run_id": "run-governance-review",
            "case_id": "TC-REVIEW-001",
            "page": "product",
            "status": "rejected",
        },
    ]
    monkeypatch.setattr(workbench, "_read_json_list", lambda path: history if path == workbench.HISTORY_FILE else [])
    monkeypatch.setattr(workbench, "_resolve_run_failure_snapshot", lambda _run_id: {})
    monkeypatch.setattr(
        workbench,
        "_resolve_run_governance_snapshot",
        lambda run_id: {
            "risk_summary": {
                "risk_level": "low" if run_id == "run-governance-allow" else "medium",
                "gate_decision": "allow" if run_id == "run-governance-allow" else "manual_review",
                "requires_review": run_id != "run-governance-allow",
                "risk_score": 22 if run_id == "run-governance-allow" else 58,
                "factor_count": 1,
                "top_factor": {"factor": "execution_status", "score": 22, "reason": "status=passed", "category": "execution"},
                "provider": "orchestrator",
                "source": "risk-evaluation-agent",
            },
            "self_healing_summary": {
                "attempted": True,
                "result_file_count": 1,
                "status": "success" if run_id == "run-governance-allow" else "rejected",
                "healed": run_id == "run-governance-allow",
                "rolled_back": False,
                "reason": "ok" if run_id == "run-governance-allow" else "boundary rejected",
                "boundary": {
                    "version": "SelfHealingBoundaryV1",
                    "allowed": run_id == "run-governance-allow",
                    "advice_type": "locator_update" if run_id == "run-governance-allow" else "assertion_update",
                    "reason": "ok" if run_id == "run-governance-allow" else "boundary rejected",
                },
            },
        },
    )

    client = TestClient(app)

    response = client.get("/api/workbench/history?risk_gate_decision=manual_review")
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["run_id"] == "run-governance-review"

    response = client.get("/api/workbench/history?self_healing_status=success")
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["run_id"] == "run-governance-allow"


def test_workbench_history_returns_governance_summary_counts(monkeypatch: Any) -> None:
    history = [
        {
            "timestamp": "2026-03-20T10:00:00+00:00",
            "action": "self_heal",
            "run_id": "run-governance-allow",
            "case_id": "TC-ALLOW-001",
            "page": "product",
            "status": "confirmed",
        },
        {
            "timestamp": "2026-03-20T10:05:00+00:00",
            "action": "self_heal",
            "run_id": "run-governance-review",
            "case_id": "TC-REVIEW-001",
            "page": "product",
            "status": "rejected",
        },
        {
            "timestamp": "2026-03-20T10:10:00+00:00",
            "action": "self_heal",
            "run_id": "run-governance-block",
            "case_id": "TC-BLOCK-001",
            "page": "product",
            "status": "rejected",
        },
    ]
    monkeypatch.setattr(workbench, "_read_json_list", lambda path: history if path == workbench.HISTORY_FILE else [])
    monkeypatch.setattr(workbench, "_resolve_run_failure_snapshot", lambda _run_id: {})
    monkeypatch.setattr(
        workbench,
        "_resolve_run_governance_snapshot",
        lambda run_id: {
            "risk_summary": {
                "risk_level": "low" if run_id == "run-governance-allow" else ("medium" if run_id == "run-governance-review" else "high"),
                "gate_decision": "allow" if run_id == "run-governance-allow" else ("manual_review" if run_id == "run-governance-review" else "block"),
                "requires_review": run_id != "run-governance-allow",
                "risk_score": 22 if run_id == "run-governance-allow" else (58 if run_id == "run-governance-review" else 86),
                "factor_count": 1,
                "top_factor": {"factor": "execution_status", "score": 22, "reason": "status", "category": "execution"},
                "provider": "orchestrator",
                "source": "risk-evaluation-agent",
            },
            "self_healing_summary": {
                "attempted": True,
                "result_file_count": 1,
                "status": "success" if run_id == "run-governance-allow" else ("rejected" if run_id == "run-governance-review" else "rollback"),
                "healed": run_id == "run-governance-allow",
                "rolled_back": run_id == "run-governance-block",
                "reason": "ok" if run_id == "run-governance-allow" else ("boundary rejected" if run_id == "run-governance-review" else "rollback applied"),
                "boundary": {
                    "version": "SelfHealingBoundaryV1",
                    "allowed": run_id != "run-governance-review",
                    "advice_type": "locator_update" if run_id == "run-governance-allow" else ("assertion_update" if run_id == "run-governance-review" else "wait_strategy"),
                    "reason": "ok" if run_id == "run-governance-allow" else ("boundary rejected" if run_id == "run-governance-review" else "rollback applied"),
                },
            },
        },
    )

    client = TestClient(app)
    response = client.get("/api/workbench/history")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["items"]) == 3
    assert payload["summary"]["total_items"] == 3
    assert payload["summary"]["risk_gate_counts"] == {"allow": 1, "manual_review": 1, "block": 1}
    assert payload["summary"]["self_healing_status_counts"] == {"success": 1, "rejected": 1, "rollback": 1}
    assert payload["summary"]["risk_requires_review_count"] == 2
    assert payload["summary"]["boundary_rejected_count"] == 1
    assert payload["summary"]["top_risk_gate"] == {"value": "allow", "count": 1}

    response = client.get("/api/workbench/history?risk_gate_decision=allow&self_healing_status=success")
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["run_id"] == "run-governance-allow"


def test_ui_pages_load_platform_auth_bootstrap() -> None:
    client = TestClient(app)

    expected_notice_ids = {
        "/execution/workbench": 'id="wb-auth-notice"',
        "/ai-generation": 'id="gen-auth-notice"',
        "/ai-generation/history": 'id="wb-history-auth-notice"',
        "/ai-generation/preview": 'id="gen-auth-notice"',
    }
    expected_timeline_ids = {
        "/execution/workbench": 'id="wb-audit-timeline"',
        "/ai-generation": None,
        "/ai-generation/history": None,
        "/ai-generation/preview": None,
    }
    expected_generate_button = {
        "/ai-generation": 'id="gen-confirm-generate"',
        "/ai-generation/preview": 'id="gen-confirm-generate"',
    }
    expected_returnapply_button = {
        "/ai-generation": 'id="gen-load-returnapply"',
    }
    expected_returnflow_panel = {
        "/ai-generation": 'id="gen-returnflow-panel"',
    }
    for path in ("/execution/workbench", "/ai-generation", "/ai-generation/history", "/ai-generation/preview"):
        response = client.get(path)
        assert response.status_code == 200
        body = response.text
        assert '/static/platform_auth.js' in body
        assert 'id="platform-user-box"' in body
        assert 'id="platform-user-name"' in body
        assert 'id="platform-user-avatar"' in body
        if expected_notice_ids[path]:
            assert expected_notice_ids[path] in body
        timeline_id = expected_timeline_ids[path]
        if timeline_id:
            assert timeline_id in body
        if expected_generate_button.get(path):
            assert expected_generate_button[path] in body
        if expected_returnapply_button.get(path):
            assert expected_returnapply_button[path] in body
        if expected_returnflow_panel.get(path):
            assert expected_returnflow_panel[path] in body


def test_preview_route_redirects_back_to_ai_generation_wizard() -> None:
    client = TestClient(app)

    response = client.get("/ai-generation/preview", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "/ai-generation?step=3"


def test_dashboard_keeps_homepage_focus_without_generation_shortcuts() -> None:
    client = TestClient(app)
    response = client.get("/")

    assert response.status_code == 200
    body = response.text
    assert "平台概览" in body
    assert "本周重点" in body
    assert "待处理事项" in body
    assert "快速进入" not in body
    assert 'href="/ai-generation?sample=returnapply"' not in body


def test_dashboard_routes_detail_work_back_to_corresponding_pages() -> None:
    client = TestClient(app)
    response = client.get("/")

    assert response.status_code == 200
    body = response.text
    assert 'id="governance-actions-list"' in body
    assert 'id="manager-headline"' in body
    assert 'id="manager-highlights-list"' in body
    assert 'id="pending-issues-list"' in body
    assert 'id="trend-svg"' in body
    assert 'href="/execution/runs"' in body
    assert 'href="/quality/trends"' in body
    assert 'href="/quality/flaky"' in body
    assert 'href="/quality/failure-clusters"' in body
    assert 'href="/quality/gates"' in body
    assert 'id="governance-top-risks-list"' not in body
    assert 'id="governance-strategy-list"' not in body
    assert 'id="governance-insights-list"' not in body
    assert 'id="governance-trend-svg"' not in body


def test_ui_management_pages_render_real_shells() -> None:
    client = TestClient(app)

    expectations = {
        "/assets/test-points": 'id="tp-assets-shell"',
        "/assets/test-points/tc-product-001": 'id="tp-asset-detail-shell"',
        "/assets/test-points/tc-product-001/matrix": 'id="tp-matrix-shell"',
        "/quality/gates": 'id="gate-console-shell"',
        "/quality/trends": 'id="quality-trends-shell"',
        "/quality/flaky": 'id="quality-flaky-shell"',
        "/settings/scheduler": 'id="scheduler-shell"',
        "/defects": 'id="defects-shell"',
    }

    for path, anchor in expectations.items():
        response = client.get(path)
        assert response.status_code == 200
        body = response.text
        assert anchor in body
        assert '/static/platform_auth.js' in body
        assert "当前为平台导航骨架页" not in body


def test_dashboard_navigation_matches_task_flow_ia() -> None:
    client = TestClient(app)
    response = client.get("/")

    assert response.status_code == 200
    body = response.text
    assert "用例中心" in body
    assert "AI生成" in body
    assert "执行中心" in body
    assert "质量分析" in body
    assert "资产与配置" in body
    assert "系统管理" in body
    assert "待审核用例" in body
    assert "用例版本" in body
    assert "Prompt 管理" in body
    assert "测试计划" in body
    assert "权限与角色" in body


def test_ui_new_navigation_routes_render_management_console() -> None:
    client = TestClient(app)
    expectations = {
        "/cases/review": "待审核用例",
        "/cases/versions": "用例版本",
        "/cases/tags": "标签管理",
        "/ai-generation/prompts": "Prompt 管理",
        "/execution/plans": "测试计划",
        "/assets/page-objects": "页面对象",
        "/assets/api-contracts": "API契约",
        "/assets/data-templates": "数据模板",
        "/system/environments": "环境管理",
        "/system/nodes": "节点管理",
        "/system/integrations": "集成配置",
        "/system/roles": "权限与角色",
    }
    for path, title in expectations.items():
        response = client.get(path)
        assert response.status_code == 200
        body = response.text
        assert 'id="management-console-shell"' in body
        assert title in body
        assert "页面职责" in body
        assert 'id="management-console-search"' in body
        assert 'id="management-console-footer"' in body


def test_ai_orchestration_redirects_to_generate_entry() -> None:
    client = TestClient(app)
    response = client.get("/ai-orchestration", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/ai-generation"


def test_ui_list_pages_render_shared_toolbar_and_footer() -> None:
    client = TestClient(app)
    checks = {
        "/ai-generation/history": ['id="wb-history-refresh"', 'id="wb-history-footer"', 'id="wb-history-selection-bar"', 'id="wb-history-advanced-filters"'],
        "/execution/runs": ['id="execution-runs-shell"', 'id="er-refresh"', 'id="er-footer"', 'id="er-selection-bar"', 'id="er-advanced-filters"'],
        "/quality/flaky": ['id="qf-refresh"', 'id="qf-footer"', 'id="qf-selection-bar"', 'id="qf-advanced-filters"'],
        "/assets/test-points": ['id="tp-assets-refresh"', 'id="tp-assets-footer"', 'id="tp-assets-selection-bar"', 'id="tp-assets-advanced-filters"'],
        "/defects": ['id="def-refresh"', 'id="def-footer"', 'id="def-selection-bar"', 'id="def-filter-system"'],
        "/quality/failure-clusters": ['id="cluster-refresh"', 'id="cluster-footer"', 'id="cluster-selection-bar"', 'id="cluster-advanced-filters"'],
        "/quality/trends": ['id="qt-refresh"', 'id="qt-footer"', 'id="qt-last-updated"', 'id="qt-advanced-filters"'],
        "/settings/scheduler": ['id="sch-refresh"', 'id="sch-footer"', 'id="sch-last-updated"', 'id="sch-advanced-filters"'],
        "/quality/gates": ['id="gate-history-refresh"', 'id="gate-history-footer"', 'id="gate-last-updated"', 'id="gate-advanced-filters"'],
    }
    for path, anchors in checks.items():
        response = client.get(path)
        assert response.status_code == 200
        body = response.text
        for anchor in anchors:
            assert anchor in body


def test_cases_page_removes_duplicate_ai_entry_and_uses_archive_language() -> None:
    client = TestClient(app)
    response = client.get("/cases")
    assert response.status_code == 200
    body = response.text
    assert 'id="cases-shell"' in body
    assert 'id="cases-tree-shell"' in body
    assert 'id="cases-table-shell"' in body
    assert 'id="cases-selection-bar"' in body
    assert 'id="cases-footer"' in body
    assert 'id="cases-last-updated"' in body
    assert 'id="cases-tree"' in body
    assert 'id="cases-table-body"' in body
    assert 'id="cases-search-context"' in body
    assert 'id="search-input"' in body
    assert 'id="filter-product-line"' in body
    assert 'id="filter-module"' in body
    assert "手动新建草稿" in body
    assert "重置搜索" in body
    assert "批量废弃" in body
    assert "类型:api" in body
    assert 'href="/ai-generation"' in body
    assert 'id="cases-view-tabs"' not in body
    assert 'id="filter-status"' not in body
    assert 'id="filter-priority"' not in body
    assert 'id="filter-test-type"' not in body
    assert 'id="filter-tag"' not in body
    assert 'id="filter-creator"' not in body
    assert 'id="filter-result"' not in body
    assert 'id="btn-apply-filters"' not in body
    assert "更多筛选" not in body
    assert "AI生成（从需求解析）" not in body
    assert "脑图" not in body
    assert "批量删除" not in body


def test_dashboard_governance_aggregates_management_signals(monkeypatch: Any) -> None:
    monkeypatch.setattr(
        dashboard_router,
        "_load_governance_quality_gate_summary",
        lambda limit=2000: {
            "summary_24h": {
                "total_events": 12,
                "blocked_events": 5,
                "block_rate": 0.417,
                "top_alert_code": "REQQG_CONFIDENCE_LOW",
                "top_alert_count": 3,
            },
            "blocker_distribution": [{"alert_code": "REQQG_CONFIDENCE_LOW", "count": 3}],
            "recent_blocked": [{"case_id": "tc-product-001"}],
        },
    )
    monkeypatch.setattr(
        dashboard_router,
        "_load_governance_task_snapshot",
        lambda limit=200: {
            "items": [],
            "summary": {
                "total_tasks": 8,
                "manifest_backfill_candidate_count": 2,
                "no_manifest_task_count": 3,
                "multisource_task_count": 5,
                "traceability_gap_task_count": 2,
                "strict_mode_status_counts": {"blocked": 2, "caution": 1, "ready": 5},
                "strict_mode_ready_task_count": 5,
                "strict_mode_caution_task_count": 1,
                "strict_mode_blocked_task_count": 2,
                "multisource_source_type_counts": {"openapi": 3, "prd": 2, "git_diff": 1},
                "strict_mode_readiness": {
                    "score": 0.58,
                    "status": "caution",
                    "reason": "manifest-first 已占主导，但仍有 compat/runtime 回退需要清理。",
                    "can_disable_compat_builder": False,
                },
                "governance_risk_counts": {"critical": 1, "high": 2, "medium": 1, "low": 4},
                "governance_risk_top_items": [
                    {
                        "task_id": "task-critical-1",
                        "run_id": "run-001",
                        "page": "product",
                        "queue_status": "failed",
                        "manifest_action": "backfill_manifest",
                        "governance_risk_level": "critical",
                        "governance_risk_score": 7,
                        "governance_risk_reason": "缺少稳定 execution record 且存在门禁阻断。",
                        "source_count": 3,
                        "source_types": ["openapi", "prd", "git_diff"],
                        "traceability_completeness": 0.67,
                        "has_traceability_gap": True,
                        "changed_areas": ["api_contract", "business_rule"],
                    }
                ],
            },
        },
    )
    monkeypatch.setattr(
        dashboard_router,
        "_load_governance_failure_clusters",
        lambda limit=200, max_clusters=8: {
            "total_failed_reports": 9,
            "total_clusters": 2,
            "clusters": [
                {
                    "cluster_id": "cluster-hot-1",
                    "failure_class": "selector_drift",
                    "queue": "frontend",
                    "severity": "S1",
                    "occurrence_count": 5,
                    "requires_manual_review_count": 2,
                    "manual_review_ratio": 0.4,
                    "latest_case_id": "tc-product-001",
                },
                {
                    "cluster_id": "cluster-hot-2",
                    "failure_class": "environment",
                    "queue": "infra",
                    "severity": "S2",
                    "occurrence_count": 4,
                    "requires_manual_review_count": 0,
                    "manual_review_ratio": 0.0,
                    "latest_case_id": "TC-ORDER-002",
                },
            ],
        },
    )
    monkeypatch.setattr(
        dashboard_router,
        "_load_governance_trend",
        lambda quality_gate_summary=None, days=14: {
            "items": [
                {
                    "date": "2026-03-20",
                    "history_events": 4,
                    "quality_gate_allow": 1,
                    "quality_gate_block": 2,
                    "quality_gate_total": 3,
                    "risk_blocked_runs": 1,
                    "review_required_runs": 2,
                    "self_healing_attention_runs": 0,
                    "pressure_score": 41,
                },
                {
                    "date": "2026-03-21",
                    "history_events": 5,
                    "quality_gate_allow": 2,
                    "quality_gate_block": 3,
                    "quality_gate_total": 5,
                    "risk_blocked_runs": 2,
                    "review_required_runs": 1,
                    "self_healing_attention_runs": 1,
                    "pressure_score": 55,
                },
            ],
            "summary_7d": {
                "quality_gate_blocked": 5,
                "risk_blocked_runs": 3,
                "review_required_runs": 3,
                "self_healing_attention_runs": 1,
                "average_pressure_score": 48.0,
                "max_pressure_score": 55,
                "direction": "worsening",
                "pressure_delta": 12.0,
            },
        },
    )
    monkeypatch.setattr(
        dashboard_router,
        "_load_governance_flaky_snapshot",
        lambda _db: {
            "top_flaky": [
                {
                    "case_id": 101,
                    "name": "商品列表 smoke",
                    "module": "product",
                    "flaky_rate": 48.5,
                    "total_runs": 9,
                    "unstable_runs": 4,
                }
            ]
        },
    )

    client = TestClient(app)
    response = client.get("/api/dashboard/governance")

    assert response.status_code == 200
    payload = response.json()
    assert payload["degraded"] is False
    assert payload["summary"]["high_risk_task_count"] == 3
    assert payload["summary"]["critical_risk_task_count"] == 1
    assert payload["summary"]["failure_cluster_count"] == 2
    assert payload["summary"]["manual_review_cluster_count"] == 1
    assert payload["summary"]["multisource_task_count"] == 5
    assert payload["summary"]["traceability_gap_task_count"] == 2
    assert payload["summary"]["strict_mode_status_counts"]["blocked"] == 2
    assert payload["summary"]["strict_mode_ready_task_count"] == 5
    assert payload["summary"]["strict_mode_blocked_task_count"] == 2
    assert payload["summary"]["multisource_source_type_counts"]["openapi"] == 3
    assert payload["summary"]["links"]["high_risk_tasks"].startswith("/execution/runs?")
    assert "traceability_gap=1" in payload["summary"]["links"]["high_risk_tasks"]
    assert payload["summary"]["links"]["manual_review_clusters"].startswith("/quality/failure-clusters?")
    assert payload["quality_gate"]["summary_24h"]["top_alert_code"] == "REQQG_CONFIDENCE_LOW"
    assert payload["failure_clusters"]["top_clusters"][0]["cluster_id"] == "cluster-hot-1"
    assert payload["failure_clusters"]["analysis"]["focus_cluster"]["cluster_id"] == "cluster-hot-1"
    assert payload["trend_14d"][0]["quality_gate_block"] == 2
    assert payload["trend_summary_7d"]["direction"] == "worsening"
    assert payload["trend_summary_7d"]["links"]["quality_gate_blocked"].startswith("/quality/failure-clusters?")
    assert "window=7d" in payload["trend_summary_7d"]["links"]["risk_blocked_runs"]
    assert payload["top_governance_risks"][0]["task_id"] == "task-critical-1"
    assert payload["top_governance_risks"][0]["source_count"] == 3
    assert payload["top_governance_risks"][0]["traceability_completeness"] == 0.67
    assert payload["top_governance_risks"][0]["gate_recommendation"] == "block"
    assert payload["top_governance_risks"][0]["risk_score_breakdown"]["model_version"] == "governance-risk-v2"
    assert payload["top_governance_risks"][0]["risk_score_breakdown"]["components"]["multisource_score"] == 12
    assert payload["top_governance_risks"][0]["href"].startswith("/execution/runs?")
    assert "risk_levels=critical" in payload["top_governance_risks"][0]["href"]
    assert payload["action_items"]
    assert payload["action_items"][0]["href"].startswith("/execution/runs?")
    assert payload["execution_strategy"]["recommended_pack"]
    assert payload["execution_strategy"]["gate_recommendation"] == "block"
    assert payload["flaky_analysis"]["linked_count"] == 1
    assert payload["flaky_analysis"]["items"][0]["stability_score"] == 52
    assert payload["failure_clusters"]["analysis"]["focus_cluster"]["risk_overlap_count"] >= 1
    assert payload["metric_definitions"]["block_rate_24h"]
    assert payload["metric_definitions"]["multisource_task_count"]
    assert payload["metric_definitions"]["traceability_gap_task_count"]
    assert payload["metric_definitions"]["strict_mode_blocked_task_count"]
    assert payload["metric_definitions"]["strict_manifest_policy"]
    assert payload["metric_definitions"]["recommended_regression_pack"]
    assert payload["manager_summary"]["release_readiness"]
    assert payload["manager_summary"]["top_theme"]
    assert payload["manager_summary"]["highlights"]
    assert payload["risk"]["level"] in {"中", "高"}
    assert payload["risk"]["score_breakdown"]["model_version"] == "governance-score-v2"
    assert payload["summary"]["strict_mode_readiness"]["status"] == "caution"
    assert payload["summary"]["strict_mode_readiness"]["can_disable_compat_builder"] is False
    assert payload["summary"]["strict_manifest_policy"]["mode"] == "caution"
    assert payload["summary"]["strict_manifest_policy"]["blocked_task_count"] == 2
    assert any(item["title"] == "提升 strict-mode readiness" for item in payload["action_items"])


def test_execution_page_renders_active_filter_context() -> None:
    client = TestClient(app)
    response = client.get("/execution/runs?risk_levels=critical,high&traceability_gap=1&changed_area=api_contract")

    assert response.status_code == 200
    body = response.text
    assert "当前筛选上下文" in body
    assert "风险级别" in body
    assert "critical / high" in body
    assert "追溯缺口" in body
    assert "变更影响" in body


def test_quality_clusters_page_renders_active_filter_context() -> None:
    client = TestClient(app)
    response = client.get("/quality/failure-clusters?alert_code=REQQG_CONFIDENCE_LOW&manual_review=1&cluster_id=cluster-hot-1")

    assert response.status_code == 200
    body = response.text
    assert "当前筛选上下文" in body
    assert "门禁告警码" in body
    assert "REQQG_CONFIDENCE_LOW" in body
    assert "仅人工复核" in body
    assert "cluster-hot-1" in body


def test_dashboard_governance_surfaces_degraded_sources(monkeypatch: Any) -> None:
    def raise_quality_gate(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        raise RuntimeError("quality gate unavailable")

    monkeypatch.setattr(dashboard_router, "_load_governance_quality_gate_summary", raise_quality_gate)
    monkeypatch.setattr(
        dashboard_router,
        "_load_governance_task_snapshot",
        lambda limit=200: {"items": [], "summary": {"total_tasks": 0, "governance_risk_counts": {}}},
    )
    monkeypatch.setattr(
        dashboard_router,
        "_load_governance_failure_clusters",
        lambda limit=200, max_clusters=8: {"total_failed_reports": 0, "total_clusters": 0, "clusters": []},
    )
    monkeypatch.setattr(
        dashboard_router,
        "_load_governance_trend",
        lambda quality_gate_summary=None, days=14: {"items": [], "summary_7d": {}},
    )
    monkeypatch.setattr(dashboard_router, "_load_governance_flaky_snapshot", lambda _db: {"top_flaky": []})

    client = TestClient(app)
    response = client.get("/api/dashboard/governance")

    assert response.status_code == 200
    payload = response.json()
    assert payload["degraded"] is True
    assert "quality_gate" in payload["degraded_sources"]
    assert payload["summary"]["high_risk_task_count"] == 0
    assert payload["quality_gate"]["summary_24h"] == {}


def test_dashboard_governance_trend_builder_aggregates_quality_gate_and_run_governance() -> None:
    now = datetime(2026, 4, 2, 9, 0, 0, tzinfo=UTC)
    history_items = [
        {"timestamp": "2026-04-01T10:00:00+00:00", "run_id": "run-1", "action": "generate_case"},
        {"timestamp": "2026-04-01T11:00:00+00:00", "run_id": "run-2", "action": "auto_run"},
        {"timestamp": "2026-03-31T08:00:00+00:00", "run_id": "run-3", "action": "rerun_case"},
    ]

    def resolve_governance(run_id: str) -> dict[str, Any]:
        mapping = {
            "run-1": {
                "risk_summary": {"gate_decision": "block", "requires_review": True},
                "self_healing_summary": {"status": "rejected", "boundary": {"allowed": False}},
            },
            "run-2": {
                "risk_summary": {"gate_decision": "allow", "requires_review": True},
                "self_healing_summary": {"status": "healed", "boundary": {"allowed": True}},
            },
            "run-3": {
                "risk_summary": {"gate_decision": "block", "requires_review": False},
                "self_healing_summary": {"status": "rolled_back", "boundary": {"allowed": False}},
            },
        }
        return mapping.get(run_id, {})

    payload = dashboard_router.workbench_governance_service.build_governance_trend(
        history_items=history_items,
        resolve_governance_snapshot=resolve_governance,
        quality_gate_summary={
            "decision_trend": [
                {"date": "2026-03-31", "allow": 1, "block": 2},
                {"date": "2026-04-01", "allow": 0, "block": 3},
            ]
        },
        now=now,
        days=7,
    )

    assert len(payload["items"]) == 7
    day_0331 = next(item for item in payload["items"] if item["date"] == "2026-03-31")
    day_0401 = next(item for item in payload["items"] if item["date"] == "2026-04-01")
    assert day_0331["quality_gate_block"] == 2
    assert day_0331["risk_blocked_runs"] == 1
    assert day_0331["self_healing_attention_runs"] == 1
    assert day_0401["quality_gate_block"] == 3
    assert day_0401["review_required_runs"] == 2
    assert payload["summary_7d"]["quality_gate_blocked"] == 5
    assert payload["summary_7d"]["risk_blocked_runs"] == 2


def test_generate_page_includes_returnapply_returnflow_hint() -> None:
    client = TestClient(app)
    response = client.get("/ai-generation?sample=returnapply")

    assert response.status_code == 200
    body = response.text
    assert 'id="gen-returnflow-panel"' in body
    assert "AI生成主流程" in body
    assert "去用例中心审核" in body


def test_login_page_loads_form_and_scripts() -> None:
    client = TestClient(app)
    response = client.get("/login?next=/workbench/history")

    assert response.status_code == 200
    body = response.text
    assert 'id="login-shell"' in body
    assert 'data-next-path="/workbench/history"' in body
    assert 'id="login-form"' in body
    assert 'id="login-username"' in body
    assert 'id="login-password"' in body
    assert '/static/platform_auth.js' in body
    assert '/static/login.js' in body


def test_generate_supports_page_only_without_requirement(monkeypatch: Any) -> None:
    captured: dict[str, Any] = {}

    monkeypatch.setattr(workbench, "_ensure_dirs", lambda: None)

    def fake_generate(**kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return {
            "case": {
                "version": "v4",
                "id": "tc-product-url-only",
                "title": "Product URL Only Smoke",
                "module": "product",
                "execution": {
                    "runner": "playwright",
                    "page": "product",
                    "variables": {},
                    "steps": [{"action": "login"}],
                },
            },
            "requirement_spec": {
                "page": "product",
                "quality_gate": {
                    "version": "RequirementQualityGateV1",
                    "stage": "orchestrate",
                    "decision": "allow",
                    "metrics": {"parse_confidence": 0.8, "test_intent_count": 1, "coverage_gap_ratio": 0.0},
                    "blockers": [],
                },
            },
        }

    monkeypatch.setattr(workbench, "_run_orchestrator_generate", fake_generate)
    monkeypatch.setattr(workbench, "_write_case_yaml", lambda *_args, **_kwargs: "id: tc-product-URL-ONLY\n")
    monkeypatch.setattr(workbench, "_save_case_state", lambda *_args, **_kwargs: {"version": 1})
    monkeypatch.setattr(workbench, "_append_history", lambda *_args, **_kwargs: None)

    client = TestClient(app)
    response = client.post(
        "/api/workbench/generate",
        json={
            "project": "default",
            "page": "product",
            "requirement": "",
            "source": "manual",
        },
    )

    assert response.status_code == 201
    item = response.json()["item"]
    assert item["page"] == "product"
    assert item["quality_gate"]["decision"] == "allow"
    assert captured["requirement"].startswith("自动生成的页面测试目标")
    assert captured["page"] == "product"


def test_quality_gate_summary_aggregates_alert_codes(monkeypatch: Any) -> None:
    monkeypatch.setattr(workbench, "_ensure_dirs", lambda: None)
    history = [
        {
            "timestamp": "2026-03-20T10:00:00+00:00",
            "action": "generate_case_blocked_by_quality_gate",
            "case_id": "tc-product-001",
            "page": "product",
            "quality_gate": {
                "version": "RequirementQualityGateV1",
                "stage": "orchestrate",
                "decision": "block",
                "blockers": [
                    {
                        "code": "low_parse_confidence",
                        "category": "quality",
                        "severity": "high",
                        "alert_code": "REQQG_CONFIDENCE_LOW",
                    },
                    {
                        "code": "insufficient_test_intents",
                        "category": "coverage",
                        "severity": "high",
                        "alert_code": "REQQG_INTENTS_LOW",
                    },
                ],
            },
        },
        {
            "timestamp": "2026-03-20T11:00:00+00:00",
            "action": "generate_case",
            "case_id": "tc-product-002",
            "quality_gate": {
                "version": "RequirementQualityGateV1",
                "stage": "orchestrate",
                "decision": "allow",
                "blockers": [],
            },
        },
        {
            "timestamp": "2026-03-20T12:00:00+00:00",
            "action": "auto_generate_case_blocked_by_quality_gate",
            "case_id": "TC-ORDER-001",
            "page": "order",
            "quality_gate": {
                "version": "RequirementQualityGateV1",
                "stage": "orchestrate",
                "decision": "block",
                "blockers": [
                    {
                        "code": "low_parse_confidence",
                        "category": "quality",
                        "severity": "high",
                        "alert_code": "REQQG_CONFIDENCE_LOW",
                    }
                ],
            },
        },
    ]

    monkeypatch.setattr(workbench, "_read_json_list", lambda path: history if path == workbench.HISTORY_FILE else [])

    client = TestClient(app)
    response = client.get("/api/workbench/quality-gates/summary?limit=100")

    assert response.status_code == 200
    item = response.json()["item"]
    assert item["total_events"] == 3
    assert item["blocked_events"] == 2
    assert item["allow_events"] == 1
    assert item["block_rate"] == 0.667
    assert item["blocker_distribution"][0]["alert_code"] == "REQQG_CONFIDENCE_LOW"
    assert item["blocker_distribution"][0]["count"] == 2
    assert item["alert_details"][0]["alert_code"] == "REQQG_CONFIDENCE_LOW"
    assert item["alert_details"][0]["remediation"]["title"]
    assert item["alert_details"][0]["samples"]
    assert item["recent_blocked"][0]["blocker_alert_codes"]
    assert "summary_24h" in item
    assert "top_page" in item["summary_24h"]
    assert "decision_trend_24h" in item
    assert len(item["decision_trend_24h"]) == 24


def test_quality_gate_summary_supports_alert_code_and_page_filters(monkeypatch: Any) -> None:
    monkeypatch.setattr(workbench, "_ensure_dirs", lambda: None)
    history = [
        {
            "timestamp": "2026-03-20T10:00:00+00:00",
            "action": "generate_case_blocked_by_quality_gate",
            "case_id": "tc-product-001",
            "page": "product",
            "quality_gate": {
                "version": "RequirementQualityGateV1",
                "stage": "orchestrate",
                "decision": "block",
                "blockers": [{"code": "low_parse_confidence", "alert_code": "REQQG_CONFIDENCE_LOW"}],
            },
        },
        {
            "timestamp": "2026-03-20T11:00:00+00:00",
            "action": "generate_case_blocked_by_quality_gate",
            "case_id": "TC-ORDER-001",
            "page": "order",
            "quality_gate": {
                "version": "RequirementQualityGateV1",
                "stage": "orchestrate",
                "decision": "block",
                "blockers": [{"code": "insufficient_test_intents", "alert_code": "REQQG_INTENTS_LOW"}],
            },
        },
    ]
    monkeypatch.setattr(workbench, "_read_json_list", lambda path: history if path == workbench.HISTORY_FILE else [])

    client = TestClient(app)
    response = client.get("/api/workbench/quality-gates/summary?limit=100&alert_code=REQQG_CONFIDENCE_LOW&page=product")

    assert response.status_code == 200
    item = response.json()["item"]
    assert item["total_events"] == 1
    assert item["blocked_events"] == 1
    assert item["blocker_distribution"][0]["alert_code"] == "REQQG_CONFIDENCE_LOW"
    assert item["summary_24h"]["top_page"] == "product"


def test_auto_run_marks_generate_failed_when_quality_gate_blocks(monkeypatch: Any) -> None:
    monkeypatch.setattr(workbench, "_ensure_dirs", lambda: None)
    monkeypatch.setattr(workbench, "_extract_page_surface", lambda _url: {"title": "Mock"})
    monkeypatch.setattr(workbench, "_enhance_page_object_from_surface", lambda page, _surface: Path(f"/tmp/{page}.page-object.yaml"))
    monkeypatch.setattr(
        workbench,
        "_build_requirement_steps",
        lambda requirement, page, page_url, _surface: (
            [{"action": "goto", "value": page_url}],
            {"status": "full", "required_coverage": [], "missing_coverage": []},
        ),
    )
    monkeypatch.setattr(workbench, "_append_history", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(workbench, "_save_test_point_plan", lambda **_kwargs: Path("/tmp/unused-plan.json"))
    monkeypatch.setattr(workbench, "report_allure_refresh", lambda: {"refreshed": True})

    def fake_generate(**_kwargs: Any) -> dict[str, Any]:
        raise workbench.HTTPException(
            status_code=422,
            detail={
                "message": "requirement quality gate blocked orchestration",
                "details": {
                    "quality_gate": {
                        "version": "RequirementQualityGateV1",
                        "stage": "orchestrate",
                        "decision": "block",
                        "blockers": [{"code": "low_parse_confidence", "alert_code": "REQQG_CONFIDENCE_LOW"}],
                    }
                },
            },
        )

    monkeypatch.setattr(workbench, "_run_orchestrator_generate", fake_generate)
    monkeypatch.setattr(workbench, "_start_run", lambda **_kwargs: (_ for _ in ()).throw(AssertionError("runner should not start")))

    client = TestClient(app)
    response = client.post(
        "/api/workbench/auto-run",
        json={
            "project": "default",
            "requirement": "模糊需求",
            "page_urls": ["http://localhost:5173/#/pms/product"],
            "source": "manual",
            "wait_seconds": 30,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["total"] == 1
    assert payload["summary"]["generate_failed"] == 1
    item = payload["items"][0]
    assert item["status"] == "generate_failed"
    assert item["run_id"] == ""
    assert item["quality_gate"]["decision"] == "block"
    assert item["page_object_summary"]["status"] == "full"
    assert "page_surface_summary" in item
    assert "required_elements" in item["page_object_summary"]


def test_auto_run_marks_coverage_gap_when_page_object_missing_required(monkeypatch: Any) -> None:
    monkeypatch.setattr(workbench, "_ensure_dirs", lambda: None)
    monkeypatch.setattr(workbench, "_extract_page_surface", lambda _url: {"title": "Mock"})
    monkeypatch.setattr(workbench, "_enhance_page_object_from_surface", lambda page, _surface: Path(f"/tmp/{page}.page-object.yaml"))
    monkeypatch.setattr(
        workbench,
        "_build_requirement_steps",
        lambda requirement, page, page_url, _surface: (
            [{"action": "goto", "value": page_url}],
            {"status": "full", "required_coverage": [], "missing_coverage": []},
        ),
    )
    monkeypatch.setattr(
        workbench,
        "_build_page_object_quality",
        lambda page, requirement, surface, page_object_path: {
            "path": str(page_object_path),
            "summary": {
                "status": "partial",
                "total_elements": 2,
                "required_elements": ["login_button", "search_input"],
                "required_count": 2,
                "missing_required": ["search_input"],
                "missing_required_count": 1,
                "added_from_surface": [],
                "added_from_surface_count": 0,
                "defaults_used": ["login_button"],
                "defaults_used_count": 1,
            },
            "coverage": {
                "status": "partial",
                "missing_required": ["search_input"],
                "next_actions": ["补充 page object 元素：search_input"],
            },
            "missing_elements": ["search_input"],
            "next_actions": ["补充 page object 元素：search_input"],
        },
    )
    monkeypatch.setattr(workbench, "_append_history", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(workbench, "_save_test_point_plan", lambda **_kwargs: Path("/tmp/test-point-plan.json"))
    monkeypatch.setattr(workbench, "report_allure_refresh", lambda: {"refreshed": True})

    monkeypatch.setattr(
        workbench,
        "_run_orchestrator_generate",
        lambda **_kwargs: {
            "case": {
                "version": "v4",
                "id": "tc-product-auto",
                "title": "product auto run",
                "module": "product",
                "execution": {
                    "runner": "playwright",
                    "page": "product",
                    "variables": {},
                    "steps": [{"action": "goto", "value": "/#/pms/product"}],
                },
            },
            "case_path": "assets/test-cases/ai-generated/tc-product-AUTO.yaml",
            "test_points": {"test_intents": [{"intent_type": "functional"}]},
            "requirement_spec": {"page": "product"},
        },
    )
    monkeypatch.setattr(workbench, "_write_case_yaml", lambda *_args, **_kwargs: "id: TC-AUTO\n")
    monkeypatch.setattr(workbench, "_read_case_yaml", lambda *_args, **_kwargs: ({"id": "TC-AUTO"}, "id: TC-AUTO\n"))
    monkeypatch.setattr(workbench, "_save_case_state", lambda *_args, **_kwargs: {"version": 1})
    monkeypatch.setattr(
        workbench,
        "_steps_to_points",
        lambda page, requirement, _steps: {
            "version": "TestPointPlanV1",
            "source_type": "generated",
            "page": page,
            "requirement": requirement,
            "test_intents": [{"intent_type": "functional", "summary": "核心流程"}],
        },
    )
    monkeypatch.setattr(workbench, "_start_run", lambda **_kwargs: {"run_id": "RUN-PARTIAL", "status": "running"})
    monkeypatch.setattr(
        workbench,
        "_wait_run_terminal",
        lambda run_id, timeout_seconds: ({"run_id": run_id, "status": "passed"}, False),
    )
    monkeypatch.setattr(workbench, "_update_job", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(workbench, "_update_runtime_run", lambda *_args, **_kwargs: None)

    client = TestClient(app)
    response = client.post(
        "/api/workbench/auto-run",
        json={
            "project": "default",
            "requirement": "校验搜索输入能力",
            "page_urls": ["http://localhost:5173/#/pms/product"],
            "source": "manual",
            "wait_seconds": 30,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["summary"]["coverage_gap"] == 1
    item = body["items"][0]
    assert item["status"] == "coverage_gap"
    assert item["page_object_summary"]["status"] == "partial"
    assert item["page_object_summary"]["missing_required_count"] == 1
    assert item["page_object"]["version"] == "PageObjectDraftV1"
    assert item["page_object"]["schema_version"] == "page-object-draft.v1"
    assert "confidence" in item["test_points"]
    assert "search_input" in item["page_object"]["missing_elements"]


def test_auto_run_rejects_private_host_not_in_allowlist(monkeypatch: Any) -> None:
    monkeypatch.setattr(workbench, "_ensure_dirs", lambda: None)
    monkeypatch.setattr(workbench.SETTINGS, "page_surface_allow_private_hosts", False)
    monkeypatch.setattr(workbench.SETTINGS, "page_surface_allowed_hosts", ["localhost", "127.0.0.1", "::1"])

    client = TestClient(app)
    response = client.post(
        "/api/workbench/auto-run",
        json={
            "project": "default",
            "requirement": "探测页面",
            "page_urls": ["http://169.254.169.254/latest/meta-data"],
            "source": "manual",
            "wait_seconds": 30,
        },
    )

    assert response.status_code == 422
    assert "blocked by SSRF policy" in response.json()["detail"]


def test_build_page_object_quality_includes_surface_diagnostics(tmp_path: Path) -> None:
    page_object_path = tmp_path / "product.page-object.yaml"
    page_object_path.write_text(
        json.dumps(
            {
                "page": "product",
                "elements": {
                    "login_button": {"locator_type": "role", "role": "button", "locator_value": "登录"},
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    quality = workbench._build_page_object_quality(
        page="product",
        requirement="校验商品搜索能力",
        surface={
            "page_title": "商品列表",
            "has_table": True,
            "auth_state": {
                "login_attempted": True,
                "login_success": False,
                "redirected_to_login": True,
            },
            "load_state": {
                "marker_selector": "",
                "selector_wait_status": "timeout",
                "route_mismatch": True,
                "requested_route": "/pms/product",
                "final_route": "/login",
            },
            "analysis": {
                "surface_health": "warn",
            },
            "iframe_count": 2,
            "loading_mask_count": 1,
            "dialog_titles": ["编辑商品"],
            "frame_surface": {
                "accessible_count": 1,
                "blocked_count": 1,
                "frames": [
                    {
                        "url": "http://localhost:5173/frame",
                        "title": "frame-1",
                        "field_placeholders": ["服务单号"],
                        "button_texts": ["查询"],
                        "title_candidates": ["退货申请"],
                    }
                ],
            },
        },
        page_object_path=page_object_path,
    )

    assert quality["version"] == "PageObjectDraftV1"
    assert quality["schema_version"] == "page-object-draft.v1"
    assert quality["page"] == "product"
    assert quality["element_count"] >= 1
    assert isinstance(quality["element_inventory"], list)
    assert quality["summary"]["surface_health"] == "warn"
    assert "dialog_title" in quality["summary"]["inferred_candidates"]
    assert "frame_search_input" in quality["summary"]["inferred_candidates"]
    assert quality["summary"]["auth_state"]["redirected_to_login"] is True
    assert quality["summary"]["load_state"]["selector_wait_status"] == "timeout"
    assert quality["summary"]["iframe_count"] == 2
    assert quality["summary"]["loading_mask_count"] == 1
    assert quality["summary"]["dialog_titles"] == ["编辑商品"]
    assert quality["summary"]["frame_surface"]["accessible_count"] == 1
    assert quality["summary"]["confidence"] >= 0
    assert "warnings" in quality["summary"]
    assert "requires_review" in quality["summary"]
    assert quality["low_confidence_items"]
    assert any("登录页" in item for item in quality["next_actions"])
    assert any("登录状态不稳定" in item for item in quality["next_actions"])
    assert any("稳定 DOM 标记" in item for item in quality["next_actions"])
    assert any("最终停留路由与预期不一致" in item for item in quality["next_actions"])
    assert any("iframe" in item for item in quality["next_actions"])
    assert any("可访问 iframe" in item for item in quality["next_actions"])
    assert any("无法直接访问" in item for item in quality["next_actions"])
    assert any("加载态遮罩" in item for item in quality["next_actions"])
    assert any("编辑商品" in item for item in quality["next_actions"])


def test_normalize_page_object_draft_promotes_legacy_payload_to_v1_contract() -> None:
    normalized = workbench._normalize_page_object_draft(
        {
            "path": "/tmp/product.page-object.yaml",
            "elements": {
                "login_button": {"locator_type": "role", "role": "button", "locator_value": "登录"},
                "search_input": {"locator_type": "placeholder", "locator_value": "商品名称"},
            },
            "summary": {
                "status": "partial",
                "total_elements": 2,
                "required_elements": ["login_button", "search_input", "search_button"],
                "required_count": 3,
                "missing_required": ["search_button"],
                "missing_required_count": 1,
                "inferred_candidates": ["search_input", "search_button"],
                "inferred_candidate_count": 2,
                "added_from_surface": ["search_input"],
                "added_from_surface_count": 1,
                "defaults_used": ["login_button"],
                "defaults_used_count": 1,
                "surface_health": "warn",
                "confidence": 0.68,
                "warnings": ["存在缺失的必需元素。"],
                "low_confidence_items": [
                    {
                        "key": "search_button",
                        "label": "查询按钮",
                        "confidence": 0.0,
                        "warnings": ["缺少对应的页面分析元素候选。"],
                        "reason": "missing_surface_candidate",
                    }
                ],
                "requires_review": True,
            },
            "coverage": {
                "status": "partial",
                "missing_required": ["search_button"],
                "next_actions": ["补充 page object 元素：search_button"],
                "confidence": 0.68,
                "warnings": ["存在缺失的必需元素。"],
                "requires_review": True,
            },
            "missing_elements": ["search_button"],
            "next_actions": ["补充 page object 元素：search_button"],
            "confidence": 0.68,
            "warnings": ["存在缺失的必需元素。"],
            "requires_review": True,
        },
        page="product",
        path="/tmp/product.page-object.yaml",
    )

    assert normalized["version"] == "PageObjectDraftV1"
    assert normalized["schema_version"] == "page-object-draft.v1"
    assert normalized["page"] == "product"
    assert normalized["path"] == "/tmp/product.page-object.yaml"
    assert normalized["element_count"] == 2
    assert normalized["summary"]["missing_required_count"] == 1
    assert normalized["coverage"]["status"] == "partial"
    assert normalized["missing_elements"] == ["search_button"]
    assert normalized["requires_review"] is True
    inventory = {item["key"]: item for item in normalized["element_inventory"]}
    assert inventory["login_button"]["source_hint"] == "default_match"
    assert inventory["search_input"]["source_hint"] == "surface_inferred"


def test_steps_to_points_includes_dependent_elements_and_review_summary() -> None:
    plan = workbench._steps_to_points(
        "product",
        "验证分页切换能力",
        [
            {"action": "login"},
            {"action": "click", "target": "pagination"},
            {"action": "assert_visible", "target": "product_table"},
        ],
    )

    assert plan["version"] == "TestPointPlanV1"
    assert plan["schema_version"] == "test-point-plan.v1"
    assert plan["review_summary"]["review_suggestion_count"] == 1
    assert "pagination" in plan["dependent_elements"]
    assert plan["points"][1]["dependent_elements"] == ["pagination"]
    assert plan["points"][1]["suggestion"] == "review"


def test_normalize_test_point_plan_promotes_legacy_payload_to_v1_contract() -> None:
    normalized = workbench._normalize_test_point_plan_payload(
        {
            "version": "test-point-plan.v1",
            "project": "default",
            "case_id": "tc-product-001",
            "page": "product",
            "page_url": "http://localhost:5173/#/pms/product",
            "source_type": "requirement_intents",
            "requirement": "验证分页切换能力",
            "points": [
                {
                    "key": "tp-01",
                    "action": "click",
                    "target": "pagination",
                    "description": "验证分页可以切换",
                    "confidence": 0.48,
                    "warnings": ["依赖分页控件"],
                    "suggestion": "skip",
                    "review_reason": "需要人工确认后执行",
                    "dependency_review": {
                        "mode": "rule_first_surface",
                        "propagated": True,
                        "dependent_elements": ["pagination"],
                        "matched_elements": ["pagination"],
                        "low_confidence_dependencies": [
                            {
                                "key": "pagination",
                                "label": "分页控件",
                                "confidence": 0.48,
                                "warnings": ["定位器不唯一"],
                            }
                        ],
                        "missing_dependencies": [],
                        "evidence": ["低置信度依赖元素：分页控件(48%)"],
                    },
                },
                {
                    "key": "tp-02",
                    "action": "assert_visible",
                    "target": "product_table",
                    "description": "验证列表正常展示",
                    "confidence": 0.9,
                    "suggestion": "execute",
                },
            ],
            "coverage": {
                "status": "partial",
                "required_coverage": ["navigation", "assert_visible"],
                "missing_coverage": ["pagination"],
                "notes": ["分页依赖元素低置信度"],
            },
        }
    )

    assert normalized["version"] == "TestPointPlanV1"
    assert normalized["schema_version"] == "test-point-plan.v1"
    assert normalized["point_count"] == 2
    assert normalized["dependent_elements"] == ["pagination", "product_table"]
    assert normalized["review_summary"]["skip_suggestion_count"] == 1
    assert normalized["review_summary"]["execute_suggestion_count"] == 1
    assert normalized["review_summary"]["dependency_review_count"] == 1
    assert normalized["review_summary"]["low_confidence_dependency_point_count"] == 1


def test_save_test_point_plan_updates_asset_snapshot(monkeypatch: Any, tmp_path: Path) -> None:
    monkeypatch.setattr(workbench, "TEST_POINTS_ROOT", tmp_path / "test-points")

    case_path = tmp_path / "cases" / "tc-product-TP-001.yaml"
    case_path.parent.mkdir(parents=True, exist_ok=True)
    case_path.write_text("id: tc-product-TP-001\n", encoding="utf-8")
    page_object_path = tmp_path / "page-objects" / "product.page-object.yaml"
    page_object_path.parent.mkdir(parents=True, exist_ok=True)
    page_object_path.write_text("page: product\n", encoding="utf-8")

    plan_path = workbench._save_test_point_plan(
        project="default",
        case_id="tc-product-TP-001",
        page="product",
        page_url="http://localhost:5173/#/pms/product",
        requirement="验证商品列表查询",
        plan={
            "version": "TestPointPlanV1",
            "priority": "P0",
            "source_type": "requirement_intents",
            "points": [
                {
                    "key": "tp-01",
                    "point_type": "navigation",
                    "description": "打开商品列表",
                    "action": "click",
                    "target": "product_menu",
                },
                {
                    "key": "tp-02",
                    "point_type": "assertion",
                    "description": "验证商品表格出现",
                    "action": "assert_visible",
                    "target": "product_table",
                },
                {
                    "key": "tp-03",
                    "point_type": "input",
                    "description": "搜索关键字超长边界校验",
                    "action": "fill",
                    "target": "search_input",
                    "value": "aaaaaaaaaaaaaaaaaaaaa",
                    "field_key": "keyword",
                    "technique_type": "boundary",
                    "technique_source": "over_max_length",
                    "technique_confidence": 0.89,
                    "execution_scope": "design_only",
                },
            ],
            "coverage": {"status": "full"},
            "review_summary": {
                "pending_review_count": 1,
                "mainline_point_count": 2,
                "design_only_point_count": 1,
                "technique_distribution": {"normal": 2, "boundary": 1},
            },
            "dependent_elements": ["product_table"],
            "confidence": 0.82,
            "requires_review": True,
            "warnings": ["存在 1 个待确认测试点"],
        },
        case_path=case_path,
        page_object_path=page_object_path,
    )

    assert plan_path.exists()
    asset_path = tmp_path / "test-points" / "default" / f"{cid('tc-product-TP-001')}.json"
    assert asset_path.exists()
    asset = json.loads(asset_path.read_text(encoding="utf-8"))
    assert asset["asset_id"] == cid("tc-product-TP-001")
    assert asset["plan_path"] == str(plan_path.resolve())
    assert asset["point_count"] == 3
    assert asset["references"][0]["kind"] == "test_point_plan"
    assert {item["kind"] for item in asset["references"]} >= {"test_point_plan", "case_yaml", "page_object"}
    assert asset["review_summary"]["pending_review_count"] == 1
    assert asset["review_summary"]["design_only_point_count"] == 1
    assert asset["plan"]["points"][2]["execution_scope"] == "design_only"
    assert asset["plan"]["points"][2]["technique_type"] == "boundary"
    assert asset["technique_summary"]["design_only_point_count"] == 1
    assert asset["technique_summary"]["mainline_point_count"] == 2
    assert asset["technique_summary"]["technique_distribution"]["boundary"] == 1
    assert asset["plan"]["version"] == "TestPointPlanV1"


def test_list_test_point_assets_returns_latest_run_snapshot(monkeypatch: Any, tmp_path: Path) -> None:
    monkeypatch.setattr(workbench, "TEST_POINTS_ROOT", tmp_path / "test-points")
    monkeypatch.setattr(workbench, "RUNTIME_RUNS_FILE", tmp_path / "runtime-runs.json")
    monkeypatch.setattr(workbench, "_ensure_dirs", lambda: (tmp_path / "test-points" / "default" / "plans").mkdir(parents=True, exist_ok=True))

    workbench._save_test_point_plan(
        project="default",
        case_id="tc-product-TP-LIST-001",
        page="product",
        page_url="http://localhost:5173/#/pms/product",
        requirement="验证商品列表",
        plan={
            "version": "TestPointPlanV1",
            "source_type": "execution_steps",
            "points": [
                {
                    "key": "tp-01",
                    "point_type": "input",
                    "description": "查询参数最小值校验",
                    "action": "api_request",
                    "target": "product_api",
                    "value": "GET /api/products?pageNo=1",
                    "field_key": "pageNo",
                    "parameter_location": "query",
                    "api_method": "GET",
                    "api_path": "/api/products",
                    "technique_type": "boundary",
                    "technique_source": "min_value",
                    "technique_confidence": 0.9,
                    "execution_scope": "design_only",
                }
            ],
            "coverage": {"status": "full"},
            "review_summary": {
                "pending_review_count": 0,
                "mainline_point_count": 0,
                "design_only_point_count": 1,
                "technique_distribution": {"boundary": 1},
            },
            "confidence": 0.91,
        },
    )

    original_read_json_list = workbench._read_json_list

    def fake_read_json_list(path: Path) -> list[dict[str, Any]]:
        if path == workbench.RUNTIME_RUNS_FILE:
            return [
                {
                    "project": "default",
                    "run_id": "run-tp-list-1",
                    "case_id": "tc-product-TP-LIST-001",
                    "page": "product",
                    "status": "coverage_gap",
                    "started_at": "2026-03-21T10:00:00+00:00",
                    "finished_at": "2026-03-21T10:01:00+00:00",
                    "review_state": {
                        "requires_review": True,
                        "pending_sections": 1,
                        "confirmed_sections": 0,
                        "element": {"status": "not_required"},
                        "test_point": {"status": "pending"},
                        "risk": {"status": "not_required"},
                    },
                    "coverage": {"status": "partial"},
                    "execution_gate": {
                        "decision": "manual_review",
                        "effective_decision": "manual_review",
                        "decision_source": "system",
                        "requires_review": True,
                        "warnings": ["存在待确认测试点 1 个。"],
                        "evidence": ["测试点层存在待确认项 1 个。"],
                    },
                }
            ]
        return original_read_json_list(path)

    monkeypatch.setattr(workbench, "_read_json_list", fake_read_json_list)

    client = TestClient(app)
    response = client.get("/api/workbench/test-point-assets?page=product")

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["asset_id"] == cid("tc-product-TP-LIST-001")
    assert items[0]["latest_run"]["run_id"] == "run-tp-list-1"
    assert items[0]["latest_run"]["status"] == "coverage_gap"
    assert items[0]["coverage"]["status"] == "full"
    assert items[0]["semantic_summary"]["page_type"] == "list"
    assert items[0]["semantic_summary"]["business_domain"] == "product"
    assert items[0]["traceability_summary"]["coverage"]["asset_status"] == "full"
    assert items[0]["traceability_summary"]["coverage"]["latest_run_status"] == "partial"
    assert items[0]["traceability_summary"]["review"]["test_point_status"] == "pending"
    assert items[0]["traceability_summary"]["gate"]["effective_decision"] == "manual_review"
    assert items[0]["traceability_summary"]["semantic"]["source"] == "asset_plan"
    assert items[0]["technique_summary"]["design_only_point_count"] == 1
    assert items[0]["traceability_summary"]["technique"]["mainline_ready"] is False
    assert items[0]["traceability_summary"]["technique"]["technique_distribution"]["boundary"] == 1
    assert items[0]["selection_summary"]["selection_state"] == "needs_review"
    assert items[0]["selection_summary"]["ready_for_regression"] is False
    assert "仅有 design_only 设计点" in items[0]["selection_summary"]["reasons"][0] or any("仅有 design_only 设计点" in reason for reason in items[0]["selection_summary"]["reasons"])
    assert response.json()["selection_summary"]["needs_review_count"] == 1


def test_list_test_point_assets_supports_selection_filters(monkeypatch: Any, tmp_path: Path) -> None:
    monkeypatch.setattr(workbench, "TEST_POINTS_ROOT", tmp_path / "test-points")
    monkeypatch.setattr(workbench, "RUNTIME_RUNS_FILE", tmp_path / "runtime-runs.json")
    monkeypatch.setattr(workbench, "_ensure_dirs", lambda: (tmp_path / "test-points" / "default" / "plans").mkdir(parents=True, exist_ok=True))

    workbench._save_test_point_plan(
        project="default",
        case_id="tc-product-READY-001",
        page="product",
        page_url="http://localhost:5173/#/pms/product",
        requirement="验证商品列表基础功能",
        plan={
            "version": "TestPointPlanV1",
            "source_type": "execution_steps",
            "points": [{"key": "tp-01", "point_type": "assertion", "description": "验证商品表格", "action": "assert_visible", "target": "product_table"}],
            "coverage": {"status": "full"},
            "review_summary": {"pending_review_count": 0},
            "confidence": 0.94,
        },
    )
    workbench._save_test_point_plan(
        project="default",
        case_id="tc-product-BLOCKED-001",
        page="product",
        page_url="http://localhost:5173/#/pms/product",
        requirement="验证高风险阻断场景",
        plan={
            "version": "TestPointPlanV1",
            "source_type": "requirement_intents",
            "points": [{"key": "tp-02", "point_type": "assertion", "description": "验证分页", "action": "assert_visible", "target": "pagination"}],
            "coverage": {"status": "partial"},
            "review_summary": {"pending_review_count": 1},
            "confidence": 0.55,
            "requires_review": True,
        },
    )

    monkeypatch.setattr(
        workbench,
        "_read_json_list",
        lambda path: [
            {
                "project": "default",
                "run_id": "run-ready-1",
                "case_id": "tc-product-READY-001",
                "page": "product",
                "status": "passed",
                "review_state": {
                    "requires_review": False,
                    "pending_sections": 0,
                    "confirmed_sections": 1,
                    "element": {"status": "not_required"},
                    "test_point": {"status": "confirmed"},
                    "risk": {"status": "not_required"},
                },
                "coverage": {"status": "full", "missing_count": 0},
                "execution_gate": {
                    "decision": "allow",
                    "effective_decision": "allow",
                    "decision_source": "system",
                    "requires_review": False,
                    "warnings": [],
                    "evidence": [],
                },
                "risk_report": {"risk_level": "low", "gate_decision": "allow", "requires_review": False},
            },
            {
                "project": "default",
                "run_id": "run-blocked-1",
                "case_id": "tc-product-BLOCKED-001",
                "page": "product",
                "status": "failed",
                "review_state": {
                    "requires_review": True,
                    "pending_sections": 1,
                    "confirmed_sections": 0,
                    "element": {"status": "pending"},
                    "test_point": {"status": "pending"},
                    "risk": {"status": "pending"},
                },
                "coverage": {"status": "partial", "missing": ["pagination"], "missing_count": 1},
                "execution_gate": {
                    "decision": "block",
                    "effective_decision": "block",
                    "decision_source": "system",
                    "requires_review": True,
                    "blockers": ["存在依赖元素未识别的测试点 1 个。"],
                    "warnings": [],
                    "evidence": ["页面分析未识别依赖元素影响测试点 1 个，达到阻断阈值 1。"],
                },
                "risk_report": {"risk_level": "high", "gate_decision": "block", "requires_review": True},
            },
        ] if path == workbench.RUNTIME_RUNS_FILE else [],
    )

    client = TestClient(app)
    filtered = client.get("/api/workbench/test-point-assets?page=product&selection_state=ready&gate_decision=allow&review_status=confirmed&coverage_status=full")

    assert filtered.status_code == 200
    filtered_payload = filtered.json()
    assert [item["asset_id"] for item in filtered_payload["items"]] == [cid("tc-product-READY-001")]
    assert filtered_payload["items"][0]["selection_summary"]["selection_state"] == "ready"
    assert filtered_payload["selection_summary"]["ready_count"] == 1
    assert filtered_payload["selection_summary"]["blocked_count"] == 0
    assert filtered_payload["selection_summary"]["filter_snapshot"]["selection_state"] == "ready"
    assert filtered_payload["coverage_summary"]["total_assets"] == 1
    assert filtered_payload["coverage_summary"]["coverage_status_counts"]["full"] == 1
    assert filtered_payload["coverage_summary"]["selection_state_counts"]["ready"] == 1
    assert filtered_payload["coverage_summary"]["regression_ready_point_count"] == 1

    blocked = client.get("/api/workbench/test-point-assets?page=product&selection_state=blocked")

    assert blocked.status_code == 200
    blocked_payload = blocked.json()
    assert [item["asset_id"] for item in blocked_payload["items"]] == [cid("tc-product-BLOCKED-001")]
    assert blocked_payload["items"][0]["selection_summary"]["reasons"][0]
    assert blocked_payload["selection_summary"]["blocked_count"] == 1


def test_test_point_asset_coverage_summary_endpoint_aggregates_asset_dimension(monkeypatch: Any, tmp_path: Path) -> None:
    monkeypatch.setattr(workbench, "TEST_POINTS_ROOT", tmp_path / "test-points")
    monkeypatch.setattr(workbench, "RUNTIME_RUNS_FILE", tmp_path / "runtime-runs.json")
    monkeypatch.setattr(workbench, "_ensure_dirs", lambda: (tmp_path / "test-points" / "default" / "plans").mkdir(parents=True, exist_ok=True))

    workbench._save_test_point_plan(
        project="default",
        case_id="tc-product-COVERAGE-001",
        page="product",
        page_url="http://localhost:5173/#/pms/product",
        requirement="验证商品列表回归",
        plan={
            "version": "TestPointPlanV1",
            "source_type": "execution_steps",
            "points": [
                {"key": "tp-01", "point_type": "assertion", "description": "验证表格", "action": "assert_visible", "target": "product_table"},
                {"key": "tp-02", "point_type": "assertion", "description": "验证搜索", "action": "assert_visible", "target": "search_input"},
            ],
            "coverage": {"status": "full"},
            "review_summary": {"pending_review_count": 0},
            "confidence": 0.95,
        },
    )
    workbench._save_test_point_plan(
        project="default",
        case_id="tc-product-COVERAGE-002",
        page="product",
        page_url="http://localhost:5173/#/pms/product",
        requirement="验证商品分页回归",
        plan={
            "version": "TestPointPlanV1",
            "source_type": "requirement_intents",
            "points": [{"key": "tp-03", "point_type": "assertion", "description": "验证分页", "action": "assert_visible", "target": "pagination"}],
            "coverage": {"status": "partial"},
            "review_summary": {"pending_review_count": 1},
            "confidence": 0.52,
            "requires_review": True,
        },
    )

    monkeypatch.setattr(
        workbench,
        "_read_json_list",
        lambda path: [
            {
                "project": "default",
                "run_id": "run-coverage-1",
                "case_id": "tc-product-COVERAGE-001",
                "page": "product",
                "status": "passed",
                "review_state": {
                    "requires_review": False,
                    "pending_sections": 0,
                    "confirmed_sections": 1,
                    "element": {"status": "not_required"},
                    "test_point": {"status": "confirmed"},
                    "risk": {"status": "not_required"},
                },
                "coverage": {"status": "full", "missing_count": 0},
                "execution_gate": {
                    "decision": "allow",
                    "effective_decision": "allow",
                    "decision_source": "system",
                    "requires_review": False,
                    "warnings": [],
                    "evidence": [],
                },
                "risk_report": {"risk_level": "low", "gate_decision": "allow", "requires_review": False},
            },
            {
                "project": "default",
                "run_id": "run-coverage-2",
                "case_id": "tc-product-COVERAGE-002",
                "page": "product",
                "status": "coverage_gap",
                "review_state": {
                    "requires_review": True,
                    "pending_sections": 1,
                    "confirmed_sections": 0,
                    "element": {"status": "pending"},
                    "test_point": {"status": "pending"},
                    "risk": {"status": "pending"},
                },
                "coverage": {"status": "partial", "missing": ["pagination"], "missing_count": 1},
                "execution_gate": {
                    "decision": "manual_review",
                    "effective_decision": "manual_review",
                    "decision_source": "system",
                    "requires_review": True,
                    "warnings": ["存在待确认测试点 1 个。"],
                    "evidence": ["测试点层存在待确认项 1 个。"],
                },
                "risk_report": {"risk_level": "medium", "gate_decision": "manual_review", "requires_review": True},
            },
        ] if path == workbench.RUNTIME_RUNS_FILE else [],
    )

    client = TestClient(app)
    response = client.get("/api/workbench/test-point-assets/coverage-summary?page=product")

    assert response.status_code == 200
    item = response.json()["item"]
    assert item["total_assets"] == 2
    assert item["total_points"] == 3
    assert item["regression_ready_asset_count"] == 1
    assert item["regression_ready_point_count"] == 2
    assert item["coverage_status_counts"]["full"] == 1
    assert item["coverage_status_counts"]["partial"] == 1
    assert item["latest_run_coverage_status_counts"]["full"] == 1
    assert item["latest_run_coverage_status_counts"]["partial"] == 1
    assert item["selection_state_counts"]["ready"] == 1
    assert item["selection_state_counts"]["needs_review"] == 1
    assert item["page_counts"]["product"] == 2
    assert item["source_type_counts"]["execution_steps"] == 1
    assert item["source_type_counts"]["requirement_intents"] == 1
    assert item["filter_snapshot"]["page"] == "product"


def test_get_test_point_asset_returns_detail_with_plan_and_references(monkeypatch: Any, tmp_path: Path) -> None:
    monkeypatch.setattr(workbench, "TEST_POINTS_ROOT", tmp_path / "test-points")
    monkeypatch.setattr(workbench, "RUNTIME_RUNS_FILE", tmp_path / "runtime-runs.json")
    monkeypatch.setattr(workbench, "_ensure_dirs", lambda: (tmp_path / "test-points" / "default" / "plans").mkdir(parents=True, exist_ok=True))

    plan_path = workbench._save_test_point_plan(
        project="default",
        case_id="tc-product-TP-DETAIL-001",
        page="product",
        page_url="http://localhost:5173/#/pms/product",
        requirement="验证商品分页",
        plan={
            "version": "TestPointPlanV1",
            "source_type": "requirement_intents",
            "points": [
                {
                    "key": "tp-01",
                    "point_type": "assertion",
                    "description": "验证分页展示",
                    "action": "assert_visible",
                    "target": "pagination",
                }
            ],
            "coverage": {"status": "partial", "missing": ["page_size"]},
            "review_summary": {
                "pending_review_count": 1,
                "mainline_point_count": 1,
                "design_only_point_count": 0,
                "technique_distribution": {"normal": 1},
            },
            "dependent_elements": ["pagination"],
            "confidence": 0.58,
            "requires_review": True,
        },
    )

    monkeypatch.setattr(
        workbench,
        "_read_json_list",
        lambda path: [
            {
                "project": "default",
                "run_id": "run-tp-detail-1",
                "case_id": "tc-product-TP-DETAIL-001",
                "page": "product",
                "status": "passed",
                "started_at": "2026-03-21T11:00:00+00:00",
                "finished_at": "2026-03-21T11:03:00+00:00",
                "review_state": {
                    "requires_review": False,
                    "pending_sections": 0,
                    "confirmed_sections": 1,
                    "element": {"status": "not_required"},
                    "test_point": {
                        "status": "confirmed",
                        "confirmed_by": "betty",
                        "confirmed_by_role": "admin",
                        "actor_display": "betty (admin)",
                        "updated_at": "2026-03-21T11:02:00+00:00",
                    },
                    "risk": {"status": "not_required"},
                },
                "review_audit_summary": {
                    "pending_sections": 0,
                    "confirmed_sections": 1,
                    "latest_actor_display": "betty (admin)",
                    "latest_updated_at": "2026-03-21T11:02:00+00:00",
                },
                "coverage": {"status": "partial", "missing": ["page_size"], "missing_count": 1},
                "execution_gate": {
                    "decision": "manual_review",
                    "effective_decision": "allow",
                    "decision_source": "manual_override",
                    "approval_status": "approved",
                    "record_status": "active",
                    "requires_review": False,
                    "warnings": ["覆盖状态为 partial。"],
                    "evidence": ["覆盖状态=partial。"],
                },
                "risk_report": {
                    "risk_level": "medium",
                    "gate_decision": "manual_review",
                    "requires_review": True,
                },
            }
        ] if path == workbench.RUNTIME_RUNS_FILE else [],
    )

    client = TestClient(app)
    response = client.get(f"/api/workbench/test-point-assets/{cid('tc-product-TP-DETAIL-001')}")

    assert response.status_code == 200
    item = response.json()["item"]
    assert item["asset_id"] == cid("tc-product-TP-DETAIL-001")
    assert item["plan"]["points"][0]["target"] == "pagination"
    assert item["plan_path"] == str(plan_path.resolve())
    assert item["coverage"]["status"] == "partial"
    assert item["dependent_elements"] == ["pagination"]
    assert item["requires_review"] is True
    assert item["semantic_summary"]["page_type"] == "list"
    assert item["semantic_summary"]["requires_review"] is True
    assert item["references"][0]["kind"] == "test_point_plan"
    assert item["latest_run"]["run_id"] == "run-tp-detail-1"
    assert item["traceability_summary"]["review"]["latest_actor_display"] == "betty (admin)"
    assert item["traceability_summary"]["gate"]["decision"] == "manual_review"
    assert "覆盖状态为 partial" in item["traceability_summary"]["gate"]["gate_reason_summary"]
    assert item["traceability_summary"]["risk"]["gate_decision"] == "manual_review"
    assert item["traceability_summary"]["semantic"]["page_type"] == "list"
    assert item["technique_summary"]["mainline_point_count"] == 1
    assert item["traceability_summary"]["technique"]["technique_distribution"]["normal"] == 1
    assert item["selection_summary"]["selection_state"] == "needs_review"
    assert item["selection_summary"]["ready_for_regression"] is False


def test_get_test_point_asset_coverage_matrix_returns_productized_rows(monkeypatch: Any, tmp_path: Path) -> None:
    monkeypatch.setattr(workbench, "TEST_POINTS_ROOT", tmp_path / "test-points")
    monkeypatch.setattr(workbench, "RUNTIME_RUNS_FILE", tmp_path / "runtime-runs.json")
    monkeypatch.setattr(workbench, "_ensure_dirs", lambda: (tmp_path / "test-points" / "default" / "plans").mkdir(parents=True, exist_ok=True))

    workbench._save_test_point_plan(
        project="default",
        case_id="TC-COVERAGE-MATRIX-001",
        page="product",
        page_url="http://localhost:5173/#/pms/product",
        requirement="验证商品列表与分页覆盖关系",
        plan={
            "version": "TestPointPlanV1",
            "source_type": "multisource",
            "points": [
                {
                    "key": "tp-01",
                    "point_type": "assertion",
                    "description": "验证商品表格展示",
                    "action": "assert_visible",
                    "target": "product_table",
                    "metadata": {"traceability": {"source_ids": ["openapi.billing.list"], "intent_ids": ["intent-list"], "origin": "coverage_matrix"}},
                },
                {
                    "key": "tp-02",
                    "point_type": "assertion",
                    "description": "验证分页控件展示",
                    "action": "assert_visible",
                    "target": "pagination",
                    "metadata": {"traceability": {"source_ids": ["jira.OMS-12"], "intent_ids": ["intent-pagination"], "origin": "coverage_matrix"}},
                },
            ],
            "metadata": {
                "coverage_matrix": [
                    {
                        "row_id": "cm-01",
                        "traceability_status": "covered",
                        "source_ids": ["openapi.billing.list"],
                        "intent_ids": ["intent-list"],
                        "point_keys": ["tp-01"],
                        "changed_areas": ["api_contract"],
                        "explanation": "列表接口已被主断言覆盖。",
                    },
                    {
                        "row_id": "cm-02",
                        "traceability_status": "gap",
                        "source_ids": ["jira.OMS-12"],
                        "intent_ids": ["intent-pagination"],
                        "point_keys": ["tp-99"],
                        "changed_areas": ["business_rule"],
                        "explanation": "分页改动尚未映射到有效测试点。",
                    },
                ]
            },
            "coverage": {"status": "partial", "missing": ["pagination"], "missing_count": 1},
            "review_summary": {"pending_review_count": 1},
            "confidence": 0.72,
            "requires_review": True,
        },
    )

    monkeypatch.setattr(
        workbench,
        "_read_json_list",
        lambda path: [
            {
                "project": "default",
                "run_id": "run-matrix-1",
                "case_id": "TC-COVERAGE-MATRIX-001",
                "page": "product",
                "status": "coverage_gap",
                "coverage": {"status": "partial", "missing": ["pagination"], "missing_count": 1},
            }
        ] if path == workbench.RUNTIME_RUNS_FILE else [],
    )

    client = TestClient(app)
    response = client.get(f"/api/workbench/test-point-assets/{cid('TC-COVERAGE-MATRIX-001')}/coverage-matrix")

    assert response.status_code == 200
    item = response.json()["item"]
    assert item["asset_id"] == cid("TC-COVERAGE-MATRIX-001")
    assert item["row_count"] == 2
    assert item["summary"]["covered_count"] == 1
    assert item["summary"]["gap_count"] == 1
    assert item["summary"]["status"] == "gap"
    assert item["summary"]["latest_run_status"] == "partial"
    assert item["summary"]["latest_run_missing_count"] == 1
    assert item["rows"][0]["row_id"] == "cm-01"
    assert item["rows"][0]["traceability_status"] == "covered"
    assert item["rows"][1]["missing_point_keys"] == ["tp-99"]



def test_consume_model_bundle_promotes_nested_models_to_analysis_bundle_contract() -> None:
    bundle = workbench._consume_model_bundle(
        page="product",
        project="default",
        case_id="tc-product-001",
        page_url="http://localhost:5173/#/pms/product",
        page_surface={
            "page": "product",
            "requested_url": "http://localhost:5173/#/pms/product",
            "confidence_summary": {
                "confidence": 0.88,
                "warnings": ["页面存在加载态遮罩"],
                "low_confidence_count": 1,
                "low_confidence_items": [
                    {
                        "key": "pagination",
                        "label": "分页控件",
                        "confidence": 0.42,
                        "locator_type": "css",
                        "locator_value": ".el-pagination",
                        "warnings": ["定位器不唯一"],
                    }
                ],
                "requires_review": True,
            },
            "warnings": ["页面 DOM 尚未完全稳定。"],
            "element_candidates": [
                {
                    "key": "pagination",
                    "label": "分页控件",
                    "locator_type": "css",
                    "locator_value": ".el-pagination",
                    "confidence": 0.42,
                    "warnings": ["定位器不唯一"],
                    "requires_review": True,
                    "source": "rule_inference",
                }
            ],
        },
        page_object={
            "version": "PageObjectDraftV1",
            "schema_version": "page-object-draft.v1",
            "page": "product",
            "path": "/tmp/product.page-object.yaml",
            "summary": {
                "status": "partial",
                "missing_required_count": 1,
                "confidence": 0.63,
                "warnings": ["存在缺失的必需元素。"],
                "requires_review": True,
            },
            "coverage": {
                "status": "partial",
                "missing_required": ["search_button"],
                "warnings": ["存在缺失的必需元素。"],
                "requires_review": True,
            },
            "elements": {
                "login_button": {"locator_type": "role", "role": "button", "locator_value": "登录"},
            },
        },
        test_points={
            "version": "TestPointPlanV1",
            "schema_version": "test-point-plan.v1",
            "project": "default",
            "case_id": "tc-product-001",
            "page": "product",
            "page_url": "http://localhost:5173/#/pms/product",
            "source_type": "execution_steps",
            "requirement": ["验证分页切换能力"],
            "points": [
                {
                    "key": "tp-01",
                    "action": "click",
                    "target": "pagination",
                    "dependent_elements": ["pagination"],
                    "confidence": 0.48,
                    "warnings": ["依赖分页控件"],
                    "suggestion": "skip",
                    "review_reason": "需要人工确认后执行",
                }
            ],
        },
    )

    analysis_bundle = bundle["analysis_bundle"]
    assert analysis_bundle["version"] == "PageAnalysisBundleV1"
    assert analysis_bundle["page"] == "product"
    assert analysis_bundle["model_versions"]["page_surface"] == "PageSurfaceV1"
    assert analysis_bundle["model_versions"]["page_semantic"] == "PageSemanticModelV1"
    assert analysis_bundle["model_versions"]["page_object"] == "PageObjectDraftV1"
    assert analysis_bundle["model_versions"]["test_points"] == "TestPointPlanV1"
    assert analysis_bundle["consumed_models"]["page_surface"] == "PageSurfaceV1"
    assert analysis_bundle["page_semantic_summary"]["page_type"] == "list"
    assert analysis_bundle["page_semantic_summary"]["business_domain"] == "product"
    assert analysis_bundle["requires_review"] is True
    assert analysis_bundle["page_surface_summary"]["low_confidence_count"] == 1
    assert analysis_bundle["page_object_summary"]["missing_required_count"] == 1
    assert analysis_bundle["test_point_summary"]["skip_suggestion_count"] == 1
    assert bundle["page_semantic"]["summary"]["page_type"] == "list"
    assert bundle["page_surface"]["confidence_summary"]["low_confidence_count"] == 1
    assert bundle["page_object"]["summary"]["missing_required_count"] == 1
    assert bundle["test_points"]["review_summary"]["skip_suggestion_count"] == 1


def test_route_signature_prefers_hash_fragment() -> None:
    assert workbench._route_signature("http://localhost:5173/#/pms/product") == "/pms/product"
    assert workbench._route_signature("http://localhost:5173/oms/order") == "/oms/order"


def test_compute_surface_stability_identifies_stable_samples() -> None:
    result = workbench._compute_surface_stability(
        [
            {"field_count": 2, "button_count": 3, "title_count": 1, "loading_mask_count": 1},
            {"field_count": 3, "button_count": 4, "title_count": 1, "loading_mask_count": 0},
            {"field_count": 3, "button_count": 4, "title_count": 1, "loading_mask_count": 0},
        ]
    )

    assert result["stable"] is True
    assert result["status"] == "stable"
    assert result["sample_count"] == 3


def test_compute_surface_stability_identifies_loading_state() -> None:
    result = workbench._compute_surface_stability(
        [
            {"field_count": 1, "button_count": 1, "title_count": 0, "loading_mask_count": 2},
        ]
    )

    assert result["stable"] is False
    assert result["status"] == "loading"


class _FakeFrame:
    def __init__(self, url: str, payload: dict[str, Any] | None = None, fail: bool = False) -> None:
        self.url = url
        self._payload = payload or {}
        self._fail = fail

    def evaluate(self, _script: str) -> dict[str, Any]:
        if self._fail:
            raise RuntimeError("frame blocked")
        return self._payload


class _FakePage:
    def __init__(self, frames: list[Any]) -> None:
        self._frames = frames

    def frames(self) -> list[Any]:
        return self._frames


def test_collect_frame_surface_summarizes_accessible_and_blocked_frames() -> None:
    page = _FakePage(
        [
            _FakeFrame("http://localhost:5173/#/root", {}),
            _FakeFrame(
                "http://localhost:5173/#/embedded",
                {
                    "title": "嵌入页",
                    "field_placeholders": ["服务单号"],
                    "button_texts": ["查询"],
                    "title_candidates": ["退货申请"],
                    "has_table": True,
                    "has_form": False,
                },
            ),
            _FakeFrame("http://cross-origin.example.com/", fail=True),
        ]
    )

    result = workbench._collect_frame_surface(page)

    assert result["accessible_count"] == 1
    assert result["blocked_count"] == 1
    assert result["frames"][0]["field_placeholders"] == ["服务单号"]


def test_normalize_page_surface_promotes_legacy_payload_to_v1_contract() -> None:
    normalized = workbench._normalize_page_surface(
        {
            "url": "http://localhost:5173/#/pms/product",
            "title": "商品管理",
            "page_title": "商品列表",
            "active_menu": "商品列表",
            "search_placeholder": "商品名称",
            "query_button_text": "查询",
            "primary_button_text": "确认",
            "has_table": True,
            "has_form": False,
            "has_dialog": True,
            "dialog_titles": ["编辑商品"],
            "iframe_count": 1,
            "loading_mask_count": 1,
            "body_text_length": 256,
            "frame_surface": {
                "accessible_count": 1,
                "blocked_count": 0,
                "frames": [
                    {
                        "url": "http://localhost:5173/frame",
                        "title": "嵌入页",
                        "field_placeholders": ["服务单号"],
                        "button_texts": ["查询"],
                        "title_candidates": ["退货申请"],
                        "has_table": True,
                        "has_form": False,
                    }
                ],
            },
            "auth_state": {
                "login_attempted": True,
                "login_success": True,
                "redirected_to_login": False,
            },
            "load_state": {
                "marker_selector": ".el-table",
                "selector_wait_status": "matched",
                "requested_route": "/pms/product",
                "final_route": "/pms/product",
                "route_mismatch": False,
                "stability": {"status": "stable", "stable": True, "sample_count": 3},
            },
            "analysis": {
                "field_count": 2,
                "button_count": 3,
                "menu_count": 1,
                "title_candidate_count": 2,
                "surface_health": "ok",
            },
            "element_candidates": [
                {
                    "key": "search_input",
                    "label": "搜索输入框",
                    "locator_type": "placeholder",
                    "locator_value": "商品名称",
                    "confidence": 0.93,
                    "warnings": [],
                    "requires_review": False,
                    "source": "search_placeholder",
                },
                {
                    "key": "pagination",
                    "label": "分页控件",
                    "locator_type": "css",
                    "locator_value": ".el-pagination",
                    "confidence": 0.42,
                    "warnings": ["定位器不唯一"],
                    "requires_review": True,
                    "source": "rule_inference",
                },
            ],
        },
        page="product",
        requested_url="http://localhost:5173/#/pms/product",
    )

    assert normalized["version"] == "PageSurfaceV1"
    assert normalized["schema_version"] == "page-surface.v1"
    assert normalized["page"] == "product"
    assert normalized["requested_url"] == "http://localhost:5173/#/pms/product"
    assert normalized["final_url"] == "http://localhost:5173/#/pms/product"
    assert normalized["url"] == normalized["final_url"]
    assert normalized["structure"]["has_table"] is True
    assert normalized["structure"]["iframe_count"] == 1
    assert normalized["frame_surface"]["accessible_count"] == 1
    assert normalized["load_state"]["stability"]["status"] == "stable"
    assert normalized["confidence_summary"]["low_confidence_count"] == 1
    assert normalized["confidence_summary"]["low_confidence_items"][0]["key"] == "pagination"
    assert normalized["requires_review"] is True
    assert normalized["metadata"]["contract_stage"] == "rule_first_surface"


def test_surface_inferred_elements_includes_dialog_and_frame_candidates() -> None:
    inferred = workbench._surface_inferred_elements(
        "product",
        {
            "page_title": "商品列表",
            "active_menu": "商品列表",
            "query_button_text": "查询",
            "primary_button_text": "确认",
            "search_placeholder": "商品名称",
            "has_table": True,
            "has_form": True,
            "dialog_titles": ["编辑商品"],
            "frame_surface": {
                "accessible_count": 1,
                "frames": [
                    {
                        "field_placeholders": ["服务单号"],
                        "button_texts": ["查询"],
                        "title_candidates": ["退货申请"],
                    }
                ],
            },
        },
    )

    assert inferred["dialog_title"]["locator_value"] == "编辑商品"
    assert inferred["dialog_primary_button"]["locator_value"] == "确认"
    assert inferred["frame_search_input"]["locator_value"] == "服务单号"
    assert inferred["frame_primary_button"]["locator_value"] == "查询"
    assert inferred["product_table"]["locator_value"] == ".el-table"


def test_required_page_elements_include_dialog_and_frame_requirements() -> None:
    required = workbench._required_page_elements(
        "product",
        "通过弹窗编辑商品后，按服务单号查询结果并确认提交",
        {
            "page_title": "商品列表",
            "has_table": True,
            "dialog_titles": ["编辑商品"],
            "frame_surface": {"accessible_count": 1},
        },
    )

    assert "search_input" in required
    assert "frame_search_input" in required
    assert "dialog_title" in required
    assert "dialog_primary_button" in required


def test_inherit_test_point_confidence_from_surface_lowers_confidence_for_low_elements() -> None:
    plan = {
        "version": "TestPointPlanV1",
        "project": "default",
        "case_id": "tc-product-001",
        "page": "product",
        "source_type": "execution_steps",
        "requirement": ["分页验证"],
        "points": [
            {
                "key": "product-01",
                "description": "验证分页切换",
                "action": "click",
                "target": "pagination",
                "dependent_elements": ["pagination"],
                "confidence": 0.86,
                "warnings": [],
                "requires_review": False,
            }
        ],
    }
    surface = {
        "element_candidates": [
            {
                "key": "pagination",
                "label": "分页控件",
                "confidence": 0.41,
                "requires_review": True,
                "warnings": ["定位器不唯一"],
            }
        ]
    }

    inherited = workbench._inherit_test_point_confidence_from_surface(plan=plan, surface=surface)
    reviewed = workbench._annotate_test_point_plan_review(inherited)
    point = reviewed["points"][0]

    assert point["confidence"] <= 0.41
    assert point["requires_review"] is True
    assert point["suggestion"] == "skip"
    assert "依赖元素置信度偏低" in " ".join(point["warnings"])
    assert point["dependency_review"]["propagated"] is True
    assert point["dependency_review"]["low_confidence_dependency_count"] == 1
    assert point["dependency_review"]["missing_dependency_count"] == 0
    assert reviewed["review_summary"]["dependency_review_count"] == 1
    assert reviewed["review_summary"]["low_confidence_dependency_point_count"] == 1
    assert reviewed["review_summary"]["dependency_skip_count"] == 1


def test_surface_snapshot_rules_are_consumed_via_rule_module() -> None:
    surface = workbench._build_surface_result_from_snapshot(
        page_url="http://localhost:5173/#/pms/product",
        payload={
            "url": "http://localhost:5173/#/pms/product",
            "title": "商品管理",
            "fields": [{"placeholder": "商品名称", "name": "name", "cls": "el-input"}],
            "buttons": [{"text": "查询", "cls": "el-button is-primary"}, {"text": "保存", "cls": "el-button"}],
            "menuItems": [{"text": "商品列表", "cls": "el-menu-item is-active"}],
            "titleCandidates": ["商品列表"],
            "hasTable": True,
            "hasForm": False,
            "hasDialog": False,
            "dialogTitles": [],
            "iframeCount": 0,
            "loadingMaskCount": 0,
            "bodyTextLength": 120,
        },
        frame_surface={"frames": [], "accessible_count": 0, "blocked_count": 0},
        login_url="http://localhost:5173/login#/login",
        login_attempted=True,
        login_succeeded=True,
        redirected_to_login=False,
        login_network_idle_reached=True,
        target_network_idle_reached=True,
        marker_selector=".el-table",
        selector_wait_status="matched",
        requested_route="/pms/product",
        final_route="/pms/product",
        route_mismatch=False,
        stability={"status": "stable", "stable": True, "sample_count": 3},
    )

    assert surface["search_placeholder"] == "商品名称"
    assert surface["query_button_text"] == "查询"
    assert surface["primary_button_text"] == "保存"
    assert surface["active_menu"] == "商品列表"
    assert surface["analysis"]["surface_health"] == "ok"
    assert surface["warnings"] == []


def test_runs_endpoint_normalizes_legacy_runtime_entry(monkeypatch: Any) -> None:
    monkeypatch.setattr(workbench, "_ensure_dirs", lambda: None)
    monkeypatch.setattr(workbench, "_read_json_list", lambda _path: [
        {
            "run_id": "run-legacy-1",
            "project": "default",
            "case_id": "tc-product-001",
            "source": "manual",
            "status": "running",
            "created_at": "2026-03-20T10:00:00+00:00",
            "started_at": "2026-03-20T10:00:10+00:00",
            "log_path": "/tmp/run-legacy-1.log",
            "artifacts_dir": "/tmp/run-legacy-1-artifacts",
            "videos_dir": "/tmp/run-legacy-1-videos",
        }
    ])

    client = TestClient(app)
    response = client.get("/api/workbench/runs")

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    entry = items[0]
    assert entry["run_id"] == "run-legacy-1"
    assert entry["execution_record"]["version"] == "ExecutionRecordV1"
    assert entry["execution_record"]["run_id"] == "run-legacy-1"
    assert entry["execution_record"]["status"] == "running"


def test_execution_gate_config_endpoint_returns_rule_snapshot() -> None:
    client = TestClient(app)
    response = client.get("/api/workbench/execution-gate/config")

    assert response.status_code == 200
    item = response.json()["item"]
    assert item["version"] == "ExecutionGateConfigV1"
    assert isinstance(item["block_missing_required_threshold"], int)
    assert isinstance(item["block_on_failed_status"], bool)
    assert isinstance(item["block_on_risk_block"], bool)
    assert isinstance(item["warn_on_pending_reviews"], bool)
    assert isinstance(item["warn_on_low_confidence_elements"], bool)
    assert isinstance(item["warn_on_pending_test_points"], bool)
    assert isinstance(item["block_missing_dependency_points_threshold"], int)
    assert isinstance(item["warn_on_low_confidence_dependency_points"], bool)
    assert isinstance(item["decision_privileged_roles"], list)
    assert isinstance(item["dual_approval_enabled"], bool)
    assert isinstance(item["dual_approval_bypass_roles"], list)
    assert item["policy_baseline"]["version"] == "ExecutionGatePolicyBaselineV1"
    assert "block" in item["policy_baseline"]["system_decision_rules"]
    assert "manual_review" in item["policy_baseline"]["system_decision_rules"]
    assert item["policy_baseline"]["manual_override_boundary"]["authenticated_required"] is True
    assert item["policy_baseline"]["manual_override_boundary"]["manual_review_roles"] == ["any_authenticated_user"]
    assert "decision_maker" in item["policy_baseline"]["manual_override_boundary"]["revoke_boundary"]["allowed_actors"]
    assert item["policy_baseline"]["non_goals"]


def test_execution_gate_policy_baseline_reflects_dual_approval_boundary(monkeypatch: Any) -> None:
    monkeypatch.setattr(workbench.SETTINGS, "execution_gate_dual_approval_enabled", True, raising=False)
    monkeypatch.setattr(
        workbench.SETTINGS,
        "execution_gate_dual_approval_bypass_roles",
        ["admin", "release-manager"],
        raising=False,
    )
    baseline = workbench._execution_gate_policy_baseline()

    assert baseline["manual_override_boundary"]["dual_approval"]["enabled"] is True
    assert baseline["manual_override_boundary"]["dual_approval"]["applies_to"] == ["block"]
    assert baseline["manual_override_boundary"]["dual_approval"]["bypass_roles"] == ["admin", "release-manager"]
    assert "二次审批" in baseline["manual_override_boundary"]["dual_approval"]["rule"]


def test_execution_gate_blocks_when_missing_dependency_points_reach_threshold(monkeypatch: Any) -> None:
    monkeypatch.setattr(workbench.SETTINGS, "execution_gate_block_missing_dependency_points_threshold", 1, raising=False)
    gate = workbench._build_execution_gate(
        page="product",
        final_status="passed",
        coverage={"status": "full"},
        page_surface_summary={"low_confidence_count": 0},
        page_semantic_summary={},
        page_object_summary={"missing_required_count": 0},
        test_points={
            "review_summary": {
                "pending_review_count": 0,
                "skip_suggestion_count": 0,
                "dependency_review_count": 1,
                "low_confidence_dependency_point_count": 0,
                "missing_dependency_point_count": 1,
                "dependency_skip_count": 0,
            }
        },
        review_state={"pending_sections": 0},
        risk_report={},
    )

    assert gate["decision"] == "block"
    assert gate["requires_review"] is True
    assert gate["metrics"]["missing_dependency_points"] == 1
    assert gate["config_snapshot"]["block_missing_dependency_points_threshold"] == 1
    assert any("未识别依赖元素影响测试点 1 个" in item for item in gate["evidence"])


def test_execution_gate_release_acceptance_matrix(monkeypatch: Any) -> None:
    monkeypatch.setattr(workbench.SETTINGS, "execution_gate_block_missing_dependency_points_threshold", 1, raising=False)

    allow_gate = workbench._build_execution_gate(
        page="product",
        final_status="passed",
        coverage={"status": "full"},
        page_surface_summary={"low_confidence_count": 0},
        page_semantic_summary={},
        page_object_summary={"missing_required_count": 0},
        test_points={
            "review_summary": {
                "pending_review_count": 0,
                "skip_suggestion_count": 0,
                "dependency_review_count": 0,
                "low_confidence_dependency_point_count": 0,
                "missing_dependency_point_count": 0,
                "dependency_skip_count": 0,
            }
        },
        review_state={"pending_sections": 0},
        risk_report={"gate_decision": "allow"},
    )
    assert allow_gate["decision"] == "allow"
    assert allow_gate["requires_review"] is False
    assert allow_gate["blockers"] == []
    assert allow_gate["warnings"] == []

    manual_review_gate = workbench._build_execution_gate(
        page="product",
        final_status="passed",
        coverage={"status": "partial"},
        page_surface_summary={"low_confidence_count": 1},
        page_semantic_summary={},
        page_object_summary={"missing_required_count": 0},
        test_points={
            "review_summary": {
                "pending_review_count": 1,
                "skip_suggestion_count": 0,
                "dependency_review_count": 1,
                "low_confidence_dependency_point_count": 1,
                "missing_dependency_point_count": 0,
                "dependency_skip_count": 0,
            }
        },
        review_state={"pending_sections": 1},
        risk_report={"gate_decision": "manual_review"},
    )
    assert manual_review_gate["decision"] == "manual_review"
    assert manual_review_gate["requires_review"] is True
    assert manual_review_gate["blockers"] == []
    assert manual_review_gate["warnings"]
    assert any("低置信度元素" in item for item in manual_review_gate["evidence"])
    assert any("待确认分组" in item for item in manual_review_gate["evidence"])

    block_gate = workbench._build_execution_gate(
        page="product",
        final_status="passed",
        coverage={"status": "full"},
        page_surface_summary={"low_confidence_count": 0},
        page_semantic_summary={},
        page_object_summary={"missing_required_count": 0},
        test_points={
            "review_summary": {
                "pending_review_count": 0,
                "skip_suggestion_count": 0,
                "dependency_review_count": 1,
                "low_confidence_dependency_point_count": 0,
                "missing_dependency_point_count": 1,
                "dependency_skip_count": 0,
            }
        },
        review_state={"pending_sections": 0},
        risk_report={"gate_decision": "allow"},
    )
    assert block_gate["decision"] == "block"
    assert block_gate["requires_review"] is True
    assert any("依赖元素未识别" in item for item in block_gate["blockers"])


def test_execution_gate_consumes_test_point_asset_selection_summary_when_test_points_missing() -> None:
    gate = workbench._build_execution_gate(
        page="product",
        final_status="passed",
        coverage={"status": "full"},
        page_surface_summary={"low_confidence_count": 0},
        page_semantic_summary={},
        page_object_summary={"missing_required_count": 0},
        test_points={},
        review_state={"pending_sections": 0},
        risk_report={"gate_decision": "allow"},
        test_point_asset_context={
            "asset_id": "tc-product-ASSET-GATE-001",
            "review_summary": {"pending_review_count": 1},
            "traceability_summary": {
                "review": {"test_point_status": "pending"},
                "coverage": {"asset_status": "partial"},
            },
            "selection_summary": {
                "selection_state": "needs_review",
                "ready_for_regression": False,
                "effective_gate_decision": "manual_review",
                "reasons": ["测试点资产自身仍要求复核。"],
            },
        },
    )

    assert gate["decision"] == "manual_review"
    assert gate["requires_review"] is True
    assert gate["metrics"]["pending_test_points"] == 1
    assert gate["metrics"]["asset_selection_state"] == "needs_review"
    assert gate["test_point_asset_context"]["asset_id"] == cid("tc-product-ASSET-GATE-001")
    assert gate["test_point_asset_context"]["selection_state"] == "needs_review"
    assert any("测试点资产选择摘要要求人工复核" in item for item in gate["warnings"])


def test_execution_gate_warns_when_page_semantic_requires_review() -> None:
    gate = workbench._build_execution_gate(
        page="product",
        final_status="passed",
        coverage={"status": "full"},
        page_surface_summary={"low_confidence_count": 0},
        page_semantic_summary={
            "page_type": "unknown",
            "business_domain": "generic",
            "primary_goal": "inspect_page",
            "confidence": 0.52,
            "requires_review": True,
        },
        page_object_summary={"missing_required_count": 0},
        test_points={"review_summary": {"pending_review_count": 0}},
        review_state={"pending_sections": 0},
        risk_report={"gate_decision": "allow"},
    )

    assert gate["decision"] == "manual_review"
    assert gate["metrics"]["semantic_requires_review"] is True
    assert gate["metrics"]["semantic_page_type"] == "unknown"
    assert any("页面语义摘要仍要求人工复核" in item for item in gate["warnings"])


def test_test_point_asset_selection_summary_consumes_semantic_review_signal() -> None:
    summary = workbench._build_test_point_asset_selection_summary(
        traceability_summary={
            "coverage": {"asset_status": "full", "latest_run_status": "full"},
            "review": {"pending_sections": 0, "requires_review": False},
            "gate": {"decision": "allow", "effective_decision": "allow"},
            "risk": {"requires_review": False},
            "semantic": {
                "page_type": "unknown",
                "business_domain": "generic",
                "requires_review": True,
            },
        }
    )

    assert summary["selection_state"] == "needs_review"
    assert summary["ready_for_regression"] is False
    assert any("页面语义仍需复核" in item for item in summary["reasons"])


def test_execution_gate_release_acceptance_run_detail_replays_gate_audit(monkeypatch: Any) -> None:
    monkeypatch.setattr(workbench, "_ensure_dirs", lambda: None)
    monkeypatch.setattr(workbench, "_get_job", lambda _run_id: None)

    def fake_read_json_list(path: Path) -> list[dict[str, Any]]:
        if path == workbench.RUNTIME_RUNS_FILE:
            return [
                {
                    "run_id": "run-gate-release-1",
                    "project": "default",
                    "case_id": "tc-product-RELEASE-001",
                    "page": "product",
                    "source": "manual",
                    "status": "passed",
                    "execution_gate": {
                        "version": "ExecutionGateV1",
                        "page": "product",
                        "decision": "manual_review",
                        "effective_decision": "manual_review",
                        "requires_review": True,
                        "blockers": [],
                        "warnings": ["存在待确认测试点 1 个。"],
                        "evidence": ["测试点层存在待确认项 1 个。"],
                        "metrics": {"pending_test_points": 1},
                        "config_snapshot": {"warn_on_pending_test_points": True},
                    },
                }
            ]
        if path == workbench.EXECUTION_GATE_DECISIONS_FILE:
            return [
                {
                    "project": "default",
                    "run_id": "run-gate-release-1",
                    "case_id": "tc-product-RELEASE-001",
                    "page": "product",
                    "decision": "block",
                    "approval_status": "approved",
                    "record_status": "revoked",
                    "note": "门禁条件变化，撤销之前的阻断。",
                    "decided_by": "gate-owner",
                    "decided_by_role": "qa-lead",
                    "second_approver": "betty",
                    "second_approver_role": "admin",
                    "second_approved_at": "2026-03-21T10:01:00+00:00",
                    "revoked_by": "betty",
                    "revoked_by_role": "admin",
                    "revoked_at": "2026-03-21T10:02:00+00:00",
                    "updated_at": "2026-03-21T10:02:00+00:00",
                }
            ]
        if path == workbench.HISTORY_FILE:
            return [
                {
                    "timestamp": "2026-03-21T10:00:00+00:00",
                    "action": "execution_gate_decided",
                    "run_id": "run-gate-release-1",
                    "page": "product",
                    "review_type": "execution_gate",
                    "status": "confirmed",
                    "actor_display": "gate-owner (qa-lead)",
                    "detail_summary": "执行门禁人工决策：block（存在待确认测试点 1 个。）",
                    "decision": "block",
                    "approval_status": "pending_second_approval",
                    "record_status": "active",
                    "gate_reason_summary": "存在待确认测试点 1 个。",
                    "matched_rules": [{"level": "warning", "message": "存在待确认测试点 1 个。"}],
                    "evidence": ["测试点层存在待确认项 1 个。"],
                },
                {
                    "timestamp": "2026-03-21T10:01:00+00:00",
                    "action": "execution_gate_approved",
                    "run_id": "run-gate-release-1",
                    "page": "product",
                    "review_type": "execution_gate",
                    "status": "confirmed",
                    "actor_display": "betty (admin)",
                    "detail_summary": "执行门禁二次审批通过：block（存在待确认测试点 1 个。）",
                    "decision": "block",
                    "approval_status": "approved",
                    "record_status": "active",
                    "gate_reason_summary": "存在待确认测试点 1 个。",
                    "matched_rules": [{"level": "warning", "message": "存在待确认测试点 1 个。"}],
                    "evidence": ["测试点层存在待确认项 1 个。"],
                },
                {
                    "timestamp": "2026-03-21T10:02:00+00:00",
                    "action": "execution_gate_revoked",
                    "run_id": "run-gate-release-1",
                    "page": "product",
                    "review_type": "execution_gate",
                    "status": "confirmed",
                    "actor_display": "betty (admin)",
                    "detail_summary": "执行门禁决策已撤销：block（存在待确认测试点 1 个。）",
                    "decision": "block",
                    "approval_status": "approved",
                    "record_status": "revoked",
                    "gate_reason_summary": "存在待确认测试点 1 个。",
                    "matched_rules": [{"level": "warning", "message": "存在待确认测试点 1 个。"}],
                    "evidence": ["测试点层存在待确认项 1 个。"],
                },
            ]
        return []

    monkeypatch.setattr(workbench, "_read_json_list", fake_read_json_list)

    client = TestClient(app)
    response = client.get("/api/workbench/runs/run-gate-release-1")

    assert response.status_code == 200
    item = response.json()["item"]
    gate = item["execution_gate"]
    assert gate["decision"] == "manual_review"
    assert gate["effective_decision"] == "manual_review"
    assert gate["decision_source"] == "manual_revoked"
    assert gate["manual_decision"]["decision"] == "block"
    assert gate["manual_decision"]["record_status"] == "revoked"
    assert [row["action"] for row in item["review_audit_timeline"]] == [
        "execution_gate_decided",
        "execution_gate_approved",
        "execution_gate_revoked",
    ]
    assert item["review_audit_timeline"][0]["gate_reason_summary"] == "存在待确认测试点 1 个。"
    assert item["review_audit_timeline"][2]["record_status"] == "revoked"


def test_runs_endpoint_surfaces_review_state_from_saved_decisions(monkeypatch: Any) -> None:
    monkeypatch.setattr(workbench, "_ensure_dirs", lambda: None)

    def fake_read_json_list(path: Path) -> list[dict[str, Any]]:
        if path == workbench.RUNTIME_RUNS_FILE:
            return [
                {
                    "run_id": "run-review-1",
                    "project": "default",
                    "case_id": "tc-product-001",
                    "page": "product",
                    "source": "manual",
                    "status": "passed",
                    "started_at": "2026-03-20T10:00:10+00:00",
                    "finished_at": "2026-03-20T10:00:20+00:00",
                    "page_surface": {
                        "version": "PageSurfaceV1",
                        "schema_version": "page-surface.v1",
                        "page": "product",
                        "requested_url": "http://localhost:5173/#/pms/product",
                        "confidence_summary": {
                            "confidence": 0.92,
                            "warnings": [],
                            "low_confidence_count": 0,
                            "low_confidence_items": [],
                            "requires_review": False,
                        },
                        "element_candidates": [],
                    },
                    "page_object": {
                        "version": "PageObjectDraftV1",
                        "schema_version": "page-object-draft.v1",
                        "page": "product",
                        "summary": {"status": "full", "missing_required_count": 0},
                        "coverage": {"status": "full", "missing": [], "missing_count": 0},
                        "elements": [],
                        "required_elements": [],
                        "missing_required": [],
                    },
                    "test_points": {
                        "version": "TestPointPlanV1",
                        "schema_version": "test-point-plan.v1",
                        "project": "default",
                        "case_id": "tc-product-001",
                        "page": "product",
                        "page_url": "http://localhost:5173/#/pms/product",
                        "source_type": "generated",
                        "requirement": "商品列表页面验证",
                        "point_count": 1,
                        "points": [
                            {
                                "key": "tp-01",
                                "description": "验证页面可访问",
                                "action": "assert_visible",
                                "target": "product_table",
                                "confidence": 0.9,
                                "warnings": [],
                                "requires_review": False,
                            }
                        ],
                        "dependent_elements": ["product_table"],
                        "review_summary": {
                            "total_points": 1,
                            "pending_review_count": 0,
                            "skip_suggestion_count": 0,
                            "review_suggestion_count": 0,
                            "dependent_element_count": 1,
                        },
                    },
                    "risk_report": {
                        "version": "RiskReportV1",
                        "risk_score": 22,
                        "risk_level": "low",
                        "gate_decision": "allow",
                        "recommendation": "可发布",
                        "confidence": 0.9,
                        "requires_review": False,
                        "evidence": [],
                        "metadata": {"provider": "legacy"},
                    },
                    "execution_gate": {
                        "version": "ExecutionGateV1",
                        "page": "product",
                        "decision": "allow",
                        "requires_review": False,
                        "blockers": [],
                        "warnings": [],
                        "metrics": {
                            "status": "passed",
                            "coverage_status": "full",
                            "low_confidence_elements": 0,
                            "missing_page_object_elements": 0,
                            "pending_test_points": 0,
                            "skip_suggestions": 0,
                            "pending_review_sections": 0,
                        },
                    },
                    "review_state": {
                        "element": {"status": "pending", "required": True, "candidate_count": 1, "items": []},
                        "test_point": {"status": "pending", "required": False, "candidate_count": 0, "items": []},
                        "requires_review": True,
                        "pending_sections": 1,
                        "confirmed_sections": 0,
                    },
                }
            ]
        if path == workbench.HISTORY_FILE:
            return [
                {
                    "timestamp": "2026-03-20T10:01:10+00:00",
                    "action": "review_confirmed",
                    "run_id": "run-review-1",
                    "page": "product",
                    "review_type": "element",
                    "status": "confirmed",
                    "actor_display": "betty (admin)",
                    "detail_summary": "element 确认 1 项",
                }
            ]
        if path == workbench.REVIEW_DECISIONS_FILE:
            return [
                {
                    "project": "default",
                    "run_id": "run-review-1",
                    "case_id": "tc-product-001",
                    "page": "product",
                    "review_type": "element",
                    "status": "confirmed",
                    "items": [{"key": "pagination", "label": "分页控件", "decision": "confirmed", "confidence": 0.42}],
                    "created_at": "2026-03-20T10:01:00+00:00",
                    "updated_at": "2026-03-20T10:01:10+00:00",
                }
            ]
        return []

    monkeypatch.setattr(workbench, "_read_json_list", fake_read_json_list)

    client = TestClient(app)
    response = client.get("/api/workbench/runs")

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["page"] == "product"
    assert item["review_state"]["element"]["status"] == "confirmed"
    assert item["review_state"]["confirmed_sections"] == 1
    assert item["review_state"]["pending_sections"] == 0
    assert item["review_state"]["model_versions"]["page_surface"] == "PageSurfaceV1"
    assert item["review_state"]["model_versions"]["page_object"] == "PageObjectDraftV1"
    assert item["review_state"]["model_versions"]["test_points"] == "TestPointPlanV1"
    assert item["risk_report"]["metadata"]["consumed_models"]["page_surface"] == "PageSurfaceV1"
    assert item["risk_report"]["metadata"]["consumed_models"]["page_object"] == "PageObjectDraftV1"
    assert item["risk_report"]["metadata"]["consumed_models"]["test_points"] == "TestPointPlanV1"
    assert item["execution_gate"]["version"] == "ExecutionGateV1"
    assert item["execution_gate"]["decision"] == "allow"
    assert item["review_audit_summary"]["confirmed_sections"] == 1
    assert item["review_audit_summary"]["sections"][0]["status"] == "confirmed"
    assert item["review_audit_summary"]["sections"][0]["updated_at"] == "2026-03-20T10:01:10+00:00"
    assert item["review_audit_timeline"][0]["action"] == "review_confirmed"
    assert item["review_audit_timeline"][0]["actor_display"] == "betty (admin)"


def test_runs_endpoint_attaches_test_point_asset_summary(monkeypatch: Any, tmp_path: Path) -> None:
    monkeypatch.setattr(workbench, "TEST_POINTS_ROOT", tmp_path / "test-points")
    monkeypatch.setattr(workbench, "_ensure_dirs", lambda: (tmp_path / "test-points" / "default" / "plans").mkdir(parents=True, exist_ok=True))
    workbench._save_test_point_plan(
        project="default",
        case_id="tc-product-ASSET-001",
        page="product",
        page_url="http://localhost:5173/#/pms/product",
        requirement="验证商品列表",
        plan={
            "version": "TestPointPlanV1",
            "source_type": "execution_steps",
            "points": [{"key": "tp-01", "point_type": "assertion", "description": "验证商品表格", "action": "assert_visible", "target": "product_table"}],
            "review_summary": {"pending_review_count": 0},
            "coverage": {"status": "full"},
            "confidence": 0.93,
        },
    )

    monkeypatch.setattr(
        workbench,
        "_read_json_list",
        lambda path: [
            {
                "run_id": "run-asset-1",
                "project": "default",
                "case_id": "tc-product-ASSET-001",
                "page": "product",
                "status": "passed",
                "review_state": {
                    "requires_review": False,
                    "pending_sections": 0,
                    "confirmed_sections": 1,
                    "element": {"status": "not_required"},
                    "test_point": {
                        "status": "confirmed",
                        "confirmed_by": "betty",
                        "confirmed_by_role": "admin",
                        "actor_display": "betty (admin)",
                        "updated_at": "2026-03-21T12:01:00+00:00",
                    },
                    "risk": {"status": "not_required"},
                },
                "review_audit_summary": {
                    "pending_sections": 0,
                    "confirmed_sections": 1,
                    "latest_actor_display": "betty (admin)",
                    "latest_updated_at": "2026-03-21T12:01:00+00:00",
                },
                "coverage": {"status": "full", "missing_count": 0},
                "execution_gate": {
                    "decision": "allow",
                    "effective_decision": "allow",
                    "decision_source": "system",
                    "requires_review": False,
                    "warnings": [],
                    "evidence": [],
                },
            }
        ] if path == workbench.RUNTIME_RUNS_FILE else [],
    )

    client = TestClient(app)
    response = client.get("/api/workbench/runs")

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["test_point_asset"]["asset_id"] == cid("tc-product-ASSET-001")
    assert item["test_point_asset"]["point_count"] == 1
    assert item["test_point_asset"]["coverage"]["status"] == "full"
    assert item["test_point_asset"]["traceability_summary"]["review"]["test_point_status"] == "confirmed"
    assert item["test_point_asset"]["traceability_summary"]["gate"]["effective_decision"] == "allow"
    assert item["test_point_asset"]["traceability_summary"]["review"]["latest_actor_display"] == "betty (admin)"
    assert item["test_point_asset"]["selection_summary"]["selection_state"] == "ready"
    assert item["test_point_asset"]["selection_summary"]["ready_for_regression"] is True


def test_get_run_attaches_test_point_asset_summary(monkeypatch: Any, tmp_path: Path) -> None:
    monkeypatch.setattr(workbench, "TEST_POINTS_ROOT", tmp_path / "test-points")
    monkeypatch.setattr(workbench, "_ensure_dirs", lambda: (tmp_path / "test-points" / "default" / "plans").mkdir(parents=True, exist_ok=True))
    workbench._save_test_point_plan(
        project="default",
        case_id="tc-product-ASSET-DETAIL-001",
        page="product",
        page_url="http://localhost:5173/#/pms/product",
        requirement="验证商品列表详情",
        plan={
            "version": "TestPointPlanV1",
            "source_type": "requirement_intents",
            "points": [{"key": "tp-01", "point_type": "navigation", "description": "打开商品页", "action": "click", "target": "product_menu"}],
            "review_summary": {"pending_review_count": 1},
            "coverage": {"status": "partial"},
            "confidence": 0.58,
            "requires_review": True,
        },
    )
    monkeypatch.setattr(workbench, "_get_job", lambda _run_id: None)
    monkeypatch.setattr(
        workbench,
        "_read_json_list",
        lambda path: [
            {
                "run_id": "run-asset-detail-1",
                "project": "default",
                "case_id": "tc-product-ASSET-DETAIL-001",
                "page": "product",
                "status": "coverage_gap",
                "review_state": {
                    "requires_review": True,
                    "pending_sections": 1,
                    "confirmed_sections": 0,
                    "element": {"status": "pending"},
                    "test_point": {"status": "pending"},
                    "risk": {"status": "not_required"},
                },
                "coverage": {"status": "partial", "missing": ["product_menu"], "missing_count": 1},
                "execution_gate": {
                    "decision": "manual_review",
                    "effective_decision": "manual_review",
                    "decision_source": "system",
                    "requires_review": True,
                    "warnings": ["存在待确认分组 1 个。"],
                    "evidence": ["当前仍有待确认分组 1 个。"],
                },
            }
        ] if path == workbench.RUNTIME_RUNS_FILE else [],
    )

    client = TestClient(app)
    response = client.get("/api/workbench/runs/run-asset-detail-1")

    assert response.status_code == 200
    item = response.json()["item"]
    assert item["test_point_asset"]["asset_id"] == cid("tc-product-ASSET-DETAIL-001")
    assert item["test_point_asset"]["requires_review"] is True
    assert item["test_point_asset"]["source_type"] == "requirement_intents"
    assert item["test_point_asset"]["traceability_summary"]["coverage"]["latest_run_status"] == "partial"
    assert item["test_point_asset"]["traceability_summary"]["review"]["pending_sections"] == 1
    assert "覆盖状态为 partial" in item["test_point_asset"]["traceability_summary"]["gate"]["gate_reason_summary"]


def test_runs_and_asset_traceability_surface_risk_summary(monkeypatch: Any, tmp_path: Path) -> None:
    monkeypatch.setattr(workbench, "TEST_POINTS_ROOT", tmp_path / "test-points")
    monkeypatch.setattr(workbench, "_ensure_dirs", lambda: (tmp_path / "test-points" / "default" / "plans").mkdir(parents=True, exist_ok=True))
    workbench._save_test_point_plan(
        project="default",
        case_id="TC-RISK-SUMMARY-001",
        page="product",
        page_url="http://localhost:5173/#/pms/product",
        requirement="验证风险摘要透出",
        plan={
            "version": "TestPointPlanV1",
            "source_type": "execution_steps",
            "points": [{"key": "tp-01", "point_type": "assertion", "description": "验证商品表格", "action": "assert_visible", "target": "product_table"}],
            "review_summary": {"pending_review_count": 0},
            "coverage": {"status": "full"},
            "confidence": 0.91,
        },
    )
    monkeypatch.setattr(workbench, "_get_job", lambda _run_id: None)
    monkeypatch.setattr(
        workbench,
        "_read_json_list",
        lambda path: [
            {
                "run_id": "run-risk-summary-1",
                "project": "default",
                "case_id": "TC-RISK-SUMMARY-001",
                "page": "product",
                "status": "passed",
                "review_state": {
                    "requires_review": False,
                    "pending_sections": 0,
                    "confirmed_sections": 1,
                    "element": {"status": "confirmed"},
                    "test_point": {"status": "confirmed"},
                    "risk": {"status": "confirmed"},
                },
                "coverage": {"status": "full", "missing_count": 0},
                "page_semantic_summary": {
                    "page_type": "list",
                    "business_domain": "product",
                    "primary_goal": "query_and_browse",
                    "primary_actions": ["search", "view_results"],
                    "confidence": 0.86,
                    "requires_review": False,
                },
                "risk_report": {
                    "version": "RiskReportV1",
                    "risk_score": 41,
                    "risk_level": "low",
                    "gate_decision": "allow",
                    "requires_review": False,
                    "source": "risk-evaluation-agent",
                    "factor_summary": {
                        "factor_count": 2,
                        "positive_factor_count": 2,
                        "category_counts": {"business": 1, "execution": 1},
                        "top_factor": {
                            "factor": "business_priority",
                            "score": 22,
                            "reason": "priority=P1",
                            "category": "business",
                        },
                        "total_factor_score": 28,
                    },
                    "metadata": {"provider": "orchestrator"},
                },
                "execution_gate": {
                    "decision": "allow",
                    "effective_decision": "allow",
                    "decision_source": "system",
                    "requires_review": False,
                    "warnings": [],
                    "evidence": [],
                },
            }
        ] if path == workbench.RUNTIME_RUNS_FILE else [],
    )

    client = TestClient(app)

    list_response = client.get("/api/workbench/runs")
    assert list_response.status_code == 200
    list_item = list_response.json()["items"][0]
    assert list_item["risk_summary"]["risk_score"] == 41
    assert list_item["risk_summary"]["factor_count"] == 2
    assert list_item["risk_summary"]["top_factor"]["factor"] == "business_priority"
    assert list_item["risk_summary"]["provider"] == "orchestrator"
    assert list_item["page_semantic_summary"]["page_type"] == "list"
    assert list_item["page_semantic_summary"]["primary_goal"] == "query_and_browse"
    assert list_item["test_point_asset"]["traceability_summary"]["risk"]["factor_count"] == 2
    assert list_item["test_point_asset"]["traceability_summary"]["semantic"]["business_domain"] == "product"
    assert list_item["test_point_asset"]["traceability_summary"]["semantic"]["primary_actions"] == ["search", "view_results"]

    detail_response = client.get("/api/workbench/runs/run-risk-summary-1")
    assert detail_response.status_code == 200
    detail_item = detail_response.json()["item"]
    assert detail_item["risk_summary"]["gate_decision"] == "allow"
    assert detail_item["risk_summary"]["factor_count"] == 2
    assert detail_item["risk_summary"]["top_factor"]["score"] == 22
    assert detail_item["page_semantic_summary"]["business_domain"] == "product"
    assert detail_item["test_point_asset"]["traceability_summary"]["risk"]["top_factor"]["factor"] == "business_priority"
    assert detail_item["test_point_asset"]["traceability_summary"]["semantic"]["page_type"] == "list"


def test_workbench_history_enriches_page_semantic_summary_from_run_snapshot(monkeypatch: Any) -> None:
    history = [
        {
            "timestamp": "2026-03-20T10:00:00+00:00",
            "action": "auto_run_completed",
            "run_id": "run-semantic-1",
            "case_id": "TC-SEMANTIC-001",
            "page": "product",
            "status": "confirmed",
        }
    ]
    monkeypatch.setattr(workbench, "_read_json_list", lambda path: history if path == workbench.HISTORY_FILE else [])
    monkeypatch.setattr(workbench, "_resolve_run_failure_snapshot", lambda _run_id: {})
    monkeypatch.setattr(
        workbench,
        "_resolve_run_governance_snapshot",
        lambda _run_id: {
            "risk_summary": {},
            "self_healing_summary": {},
            "page_semantic_summary": {
                "page_type": "list",
                "business_domain": "product",
                "primary_goal": "query_and_browse",
                "primary_actions": ["search", "view_results"],
                "confidence": 0.84,
                "requires_review": False,
            },
        },
    )

    client = TestClient(app)
    response = client.get("/api/workbench/history")

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["page_semantic_summary"]["page_type"] == "list"
    assert items[0]["page_semantic_summary"]["business_domain"] == "product"
    assert "语义=list" in items[0]["detail_summary"]


def test_runs_surface_self_healing_boundary_summary(monkeypatch: Any, tmp_path: Path) -> None:
    artifacts_dir = tmp_path / "run-self-heal-artifacts"
    case_dir = artifacts_dir / "TC-SELF-HEAL-001"
    case_dir.mkdir(parents=True, exist_ok=True)
    (case_dir / "self_healing_result.json").write_text(
        json.dumps(
            {
                "status": "rejected",
                "reason": "Advice type 'assertion_update' is outside deterministic auto-healing boundary.",
                "healed": False,
                "rolled_back": False,
                "plan_path": str(case_dir / "self_healing_patch_plan.json"),
                "boundary": {
                    "version": "SelfHealingBoundaryV1",
                    "allowed": False,
                    "advice_type": "assertion_update",
                    "reason": "Advice type 'assertion_update' is outside deterministic auto-healing boundary. Only locator_update and wait_strategy can be auto-applied.",
                },
            },
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(workbench, "_ensure_dirs", lambda: None)
    monkeypatch.setattr(workbench, "_get_job", lambda _run_id: None)
    monkeypatch.setattr(
        workbench,
        "_read_json_list",
        lambda path: [
            {
                "run_id": "run-self-heal-1",
                "project": "default",
                "case_id": "TC-SELF-HEAL-001",
                "page": "product",
                "source": "rerun",
                "status": "failed",
                "started_at": "2026-03-20T12:30:00+00:00",
                "finished_at": "2026-03-20T12:31:00+00:00",
                "artifacts_dir": str(artifacts_dir),
                "execution_record": {
                    "version": "ExecutionRecordV1",
                    "run_id": "run-self-heal-1",
                    "case_id": "TC-SELF-HEAL-001",
                    "project": "default",
                    "source": "rerun",
                    "mode": "generate_and_run",
                    "status": "failed",
                    "started_at": "2026-03-20T12:30:00+00:00",
                    "finished_at": "2026-03-20T12:31:00+00:00",
                    "step_summary": {"page": "product", "requirement_count": 1, "total_steps": 2, "action_types": ["click", "assert_visible"]},
                    "evidence_index": {
                        "total_files": 2,
                        "artifact_categories": {
                            "screenshots": 0,
                            "html_pages": 0,
                            "meta_files": 0,
                            "analysis_files": 0,
                            "suggestion_files": 1,
                            "execution_record_files": 1,
                            "self_healing_result_files": 1,
                            "videos": 0,
                            "other_files": 0,
                        },
                        "runner_exit_code": 1,
                        "execution_requested": True,
                    },
                },
            }
        ] if path == workbench.RUNTIME_RUNS_FILE else [],
    )

    client = TestClient(app)

    list_response = client.get("/api/workbench/runs")
    assert list_response.status_code == 200
    list_item = list_response.json()["items"][0]
    assert list_item["self_healing_summary"]["attempted"] is True
    assert list_item["self_healing_summary"]["status"] == "rejected"
    assert list_item["self_healing_summary"]["boundary"]["allowed"] is False
    assert list_item["self_healing_summary"]["boundary"]["advice_type"] == "assertion_update"

    detail_response = client.get("/api/workbench/runs/run-self-heal-1")
    assert detail_response.status_code == 200
    detail_item = detail_response.json()["item"]
    assert detail_item["self_healing_summary"]["reason"].startswith("Advice type 'assertion_update'")
    assert detail_item["self_healing_summary"]["result_file_count"] == 1
    assert detail_item["self_healing_summary"]["plan_path"].endswith("self_healing_patch_plan.json")


def test_get_run_builds_execution_gate_from_test_point_asset_when_test_points_missing(monkeypatch: Any, tmp_path: Path) -> None:
    monkeypatch.setattr(workbench, "TEST_POINTS_ROOT", tmp_path / "test-points")
    monkeypatch.setattr(workbench, "_ensure_dirs", lambda: (tmp_path / "test-points" / "default" / "plans").mkdir(parents=True, exist_ok=True))
    workbench._save_test_point_plan(
        project="default",
        case_id="tc-product-ASSET-GATE-FALLBACK-001",
        page="product",
        page_url="http://localhost:5173/#/pms/product",
        requirement="验证测试点资产兜底门禁",
        plan={
            "version": "TestPointPlanV1",
            "source_type": "requirement_intents",
            "points": [{"key": "tp-01", "point_type": "assertion", "description": "验证分页", "action": "assert_visible", "target": "pagination"}],
            "review_summary": {"pending_review_count": 1},
            "coverage": {"status": "partial"},
            "confidence": 0.57,
            "requires_review": True,
        },
    )
    monkeypatch.setattr(workbench, "_get_job", lambda _run_id: None)
    monkeypatch.setattr(
        workbench,
        "_read_json_list",
        lambda path: [
            {
                "run_id": "run-asset-gate-fallback-1",
                "project": "default",
                "case_id": "tc-product-ASSET-GATE-FALLBACK-001",
                "page": "product",
                "status": "passed",
                "coverage": {"status": "partial", "missing": ["pagination"], "missing_count": 1},
                "review_state": {
                    "requires_review": True,
                    "pending_sections": 1,
                    "confirmed_sections": 0,
                    "element": {"status": "pending"},
                    "test_point": {"status": "pending"},
                    "risk": {"status": "not_required"},
                },
                "risk_report": {
                    "risk_level": "medium",
                    "gate_decision": "allow",
                    "requires_review": False,
                },
            }
        ] if path == workbench.RUNTIME_RUNS_FILE else [],
    )

    client = TestClient(app)
    response = client.get("/api/workbench/runs/run-asset-gate-fallback-1")

    assert response.status_code == 200
    item = response.json()["item"]
    assert item["execution_gate"]["decision"] == "manual_review"
    assert item["execution_gate"]["metrics"]["asset_selection_state"] == "needs_review"
    assert item["execution_gate"]["test_point_asset_context"]["asset_id"] == cid("tc-product-ASSET-GATE-FALLBACK-001")
    assert item["execution_gate"]["test_point_asset_context"]["selection_state"] == "needs_review"
    assert any("测试点资产选择摘要" in row for row in item["execution_gate"]["evidence"])


def test_get_run_returns_execution_record_envelope(monkeypatch: Any) -> None:
    monkeypatch.setattr(workbench, "_ensure_dirs", lambda: None)
    monkeypatch.setattr(workbench, "_get_job", lambda _run_id: None)
    monkeypatch.setattr(workbench, "_read_json_list", lambda _path: [
        {
            "run_id": "run-legacy-2",
            "project": "default",
            "case_id": "TC-ORDER-001",
            "source": "rerun",
            "status": "passed",
            "started_at": "2026-03-20T11:00:00+00:00",
            "finished_at": "2026-03-20T11:00:20+00:00",
            "return_code": 0,
            "log_path": "/tmp/run-legacy-2.log",
            "artifacts_dir": "/tmp/run-legacy-2-artifacts",
            "videos_dir": "/tmp/run-legacy-2-videos",
        }
    ])

    client = TestClient(app)
    response = client.get("/api/workbench/runs/run-legacy-2")

    assert response.status_code == 200
    item = response.json()["item"]
    assert item["run_id"] == "run-legacy-2"
    assert item["status"] == "passed"
    assert item["execution_record"]["version"] == "ExecutionRecordV1"
    assert item["execution_record"]["case_id"] == cid("TC-ORDER-001")


def test_list_execution_tasks_returns_unified_task_view(monkeypatch: Any) -> None:
    monkeypatch.setattr(workbench, "_utc_now", lambda: datetime(2026, 3, 21, 12, 0, 0, tzinfo=UTC))
    monkeypatch.setattr(
        workbench,
        "_collect_execution_records_with_meta",
        lambda limit=1000: (
            [
                {
                    "run_id": "run-task-1",
                    "case_id": "tc-product-TASK-001",
                    "status": "queued",
                    "source": "runtime_realtime",
                    "execution_record_path": "",
                    "manifest_path": "",
                    "execution_record": {
                        "version": "ExecutionRecordV1",
                        "run_id": "run-task-1",
                        "case_id": "tc-product-TASK-001",
                        "project": "default",
                        "source": "manual",
                        "mode": "generate_and_run",
                        "status": "queued",
                        "started_at": "2026-03-21T12:00:00+00:00",
                        "finished_at": "",
                        "step_summary": {"page": "product", "total_steps": 2, "action_types": ["login", "assert_visible"]},
                        "evidence_index": {"total_files": 0},
                        "metadata": {
                            "runtime_realtime_supplement": True,
                            "runner": "playwright",
                            "retry_policy": {"enabled": True, "max_retries": 2, "backoff_seconds": 10},
                            "dependencies": ["TC-LOGIN-BASE-001", "TC-LOGIN-BASE-001", "TC-DATA-SEED-001"],
                            "scheduling_hints": {"queue": "default", "expected_total_seconds": 45, "resource_profile": "light"},
                        },
                    },
                },
                {
                    "run_id": "run-task-2",
                    "case_id": "tc-product-TASK-002",
                    "status": "passed",
                    "source": "manifest",
                    "execution_record_path": "/tmp/run-task-2-execution.json",
                    "manifest_path": "/tmp/run-task-2-manifest.json",
                    "execution_record": {
                        "version": "ExecutionRecordV1",
                        "run_id": "run-task-2",
                        "case_id": "tc-product-TASK-002",
                        "project": "default",
                        "source": "manual",
                        "mode": "generate_and_run",
                        "status": "passed",
                        "started_at": "2026-03-21T10:00:00+00:00",
                        "finished_at": "2026-03-21T10:01:00+00:00",
                        "step_summary": {"page": "product", "total_steps": 3, "action_types": ["login", "click", "assert_visible"]},
                        "evidence_index": {"total_files": 4},
                        "metadata": {"runner": "playwright"},
                    },
                },
            ],
            {
                "policy_mode": "compat",
                "health": "healthy",
                "total_visible_records": 2,
                "manifest_record_count": 1,
                "runtime_realtime_count": 1,
            },
        ),
    )

    client = TestClient(app)
    response = client.get("/api/workbench/tasks?queue_status=queued")

    assert response.status_code == 200
    payload = response.json()
    assert [item["task_id"] for item in payload["items"]] == ["run-task-1"]
    assert payload["items"][0]["runner"] == "playwright"
    assert payload["items"][0]["queue_status"] == "queued"
    assert payload["items"][0]["expected_total_seconds"] == 45
    assert payload["items"][0]["evidence_health"]["status"] == "warning"
    assert "runtime" in payload["items"][0]["evidence_health"]["reason"]
    assert payload["items"][0]["evidence_freshness"]["status"] == "live"
    assert payload["items"][0]["evidence_freshness"]["stale"] is False
    assert payload["items"][0]["retry"] == {"enabled": True, "max_retries": 2, "backoff_seconds": 10}
    assert payload["items"][0]["dependency"] == {
        "dependencies": [cid("TC-LOGIN-BASE-001"), cid("TC-DATA-SEED-001")],
        "dependency_count": 2,
        "has_dependencies": True,
    }
    assert payload["items"][0]["manifest_action"] == "await_runtime_flush"
    assert payload["summary"]["total_tasks"] == 1
    assert payload["summary"]["queue_status_counts"]["queued"] == 1
    assert payload["summary"]["evidence_health_counts"]["warning"] == 1
    assert payload["summary"]["manifest_action_counts"]["await_runtime_flush"] == 1
    assert payload["summary"]["manifest_first_task_count"] == 0
    assert payload["summary"]["compat_fallback_task_count"] == 0
    assert payload["summary"]["runtime_supplement_task_count"] == 1
    assert payload["summary"]["has_manifest_task_count"] == 0
    assert payload["summary"]["manifest_first_ratio_visible"] == 0.0
    assert payload["summary"]["runtime_supplement_ratio_visible"] == 1.0
    assert payload["summary"]["execution_meta"]["total_visible_records"] == 2


def test_get_execution_task_returns_detail(monkeypatch: Any) -> None:
    monkeypatch.setattr(workbench, "_utc_now", lambda: datetime(2026, 3, 21, 10, 0, 0, tzinfo=UTC))
    monkeypatch.setattr(
        workbench,
        "_collect_execution_records_with_meta",
        lambda limit=1000: (
            [
                {
                    "run_id": "run-task-detail-1",
                    "case_id": "TC-ORDER-TASK-001",
                    "status": "failed",
                    "source": "manifest",
                    "execution_record_path": "/tmp/run-task-detail-1-execution.json",
                    "manifest_path": "/tmp/run-task-detail-1-manifest.json",
                    "execution_record": {
                        "version": "ExecutionRecordV1",
                        "run_id": "run-task-detail-1",
                        "case_id": "TC-ORDER-TASK-001",
                        "project": "default",
                        "source": "manual",
                        "mode": "generate_and_run",
                        "status": "failed",
                        "started_at": "2026-03-21T09:00:00+00:00",
                        "finished_at": "2026-03-21T09:02:00+00:00",
                        "step_summary": {"page": "order", "total_steps": 4, "action_types": ["login", "goto", "click", "assert_visible"]},
                        "evidence_index": {"total_files": 6},
                        "metadata": {"runner": "playwright"},
                    },
                }
            ],
            {"policy_mode": "strict", "health": "healthy", "total_visible_records": 1},
        ),
    )

    client = TestClient(app)
    response = client.get("/api/workbench/tasks/run-task-detail-1")

    assert response.status_code == 200
    payload = response.json()
    assert payload["item"]["task_id"] == "run-task-detail-1"
    assert payload["item"]["page"] == "order"
    assert payload["item"]["status"] == "failed"
    assert payload["item"]["has_manifest"] is True
    assert payload["item"]["evidence_health"]["status"] == "healthy"
    assert payload["item"]["evidence_health"]["total_files"] == 6
    assert payload["item"]["evidence_freshness"]["status"] == "fresh"
    assert payload["item"]["evidence_freshness"]["source_window_hours"] == 24
    assert payload["item"]["retry"] == {"enabled": False, "max_retries": 0, "backoff_seconds": 0}
    assert payload["item"]["dependency"] == {"dependencies": [], "dependency_count": 0, "has_dependencies": False}
    assert payload["item"]["manifest_action"] == "ok"
    assert payload["meta"]["policy_mode"] == "strict"


def test_list_execution_tasks_summary_surfaces_manifest_and_compat_stats(monkeypatch: Any) -> None:
    monkeypatch.setattr(workbench, "_utc_now", lambda: datetime(2026, 3, 21, 10, 0, 0, tzinfo=UTC))
    monkeypatch.setattr(
        workbench,
        "_collect_execution_records_with_meta",
        lambda limit=1000: (
            [
                {
                    "run_id": "run-task-manifest-1",
                    "case_id": "TC-TASK-001",
                    "status": "passed",
                    "source": "manifest",
                    "execution_record_path": "/tmp/run-task-manifest-1.json",
                    "manifest_path": "/tmp/run-task-manifest-1-manifest.json",
                    "execution_record": {
                        "version": "ExecutionRecordV1",
                        "run_id": "run-task-manifest-1",
                        "case_id": "TC-TASK-001",
                        "project": "default",
                        "status": "passed",
                        "mode": "generate_and_run",
                        "started_at": "2026-03-17T08:00:00+00:00",
                        "finished_at": "2026-03-17T08:01:00+00:00",
                        "step_summary": {"page": "product", "total_steps": 1, "action_types": ["assert_visible"]},
                        "evidence_index": {"total_files": 3},
                        "metadata": {
                            "runner": "playwright",
                            "multisource": {
                                "source_summary": {"source_count": 3, "source_types": ["openapi", "prd", "git_diff"]},
                                "traceability_summary": {
                                    "traceability_completeness": 0.72,
                                    "gap_point_count": 1,
                                    "partial_count": 1,
                                    "orphan_point_count": 0,
                                    "status": "partial",
                                },
                                "change_impact": {
                                    "impact_score": 48,
                                    "changed_areas": ["api_contract", "business_rule"],
                                    "top_factor": {"factor": "api_contract", "weight": 14},
                                    "recommended_regression_scope": ["api_contract_regression"],
                                },
                            },
                            "retry_policy": {"enabled": True, "max_retries": 1, "backoff_seconds": 5},
                            "dependencies": ["TC-SETUP-001"],
                        },
                    },
                },
                {
                    "run_id": "run-task-compat-1",
                    "case_id": "TC-TASK-002",
                    "status": "failed",
                    "source": "compat_scan",
                    "execution_record_path": "/tmp/run-task-compat-1.json",
                    "manifest_path": "",
                    "execution_record": {
                        "version": "ExecutionRecordV1",
                        "run_id": "run-task-compat-1",
                        "case_id": "TC-TASK-002",
                        "project": "default",
                        "status": "failed",
                        "mode": "generate_and_run",
                        "started_at": "2026-03-21T09:00:00+00:00",
                        "finished_at": "2026-03-21T09:02:00+00:00",
                        "step_summary": {"page": "order", "total_steps": 2, "action_types": ["goto", "assert_visible"]},
                        "evidence_index": {"total_files": 2},
                        "metadata": {"runner": "playwright"},
                    },
                },
                {
                    "run_id": "run-task-runtime-1",
                    "case_id": "TC-TASK-003",
                    "status": "running",
                    "source": "runtime_realtime",
                    "execution_record_path": "",
                    "manifest_path": "",
                    "execution_record": {
                        "version": "ExecutionRecordV1",
                        "run_id": "run-task-runtime-1",
                        "case_id": "TC-TASK-003",
                        "project": "default",
                        "status": "running",
                        "mode": "generate_and_run",
                        "started_at": "2026-03-21T09:30:00+00:00",
                        "finished_at": "",
                        "step_summary": {"page": "product", "total_steps": 2, "action_types": ["login", "click"]},
                        "evidence_index": {"total_files": 0},
                        "metadata": {"runner": "playwright", "runtime_realtime_supplement": True},
                    },
                },
            ],
            {
                "policy_mode": "compat",
                "health": "degraded",
                "total_visible_records": 3,
                "manifest_record_count": 1,
                "compat_scan_record_count": 1,
                "runtime_realtime_count": 1,
                "manifest_first_ratio": 0.5,
                "fallback_ratio": 0.5,
                "strict_mode_readiness": {
                    "score": 0.61,
                    "status": "caution",
                    "reason": "manifest-first 已占主导，但仍有 compat/runtime 回退需要清理。",
                },
            },
        ),
    )

    client = TestClient(app)
    response = client.get("/api/workbench/tasks")

    assert response.status_code == 200
    summary = response.json()["summary"]
    assert summary["total_tasks"] == 3
    assert summary["manifest_first_task_count"] == 1
    assert summary["compat_fallback_task_count"] == 1
    assert summary["runtime_supplement_task_count"] == 1
    assert summary["has_manifest_task_count"] == 1
    assert summary["no_manifest_task_count"] == 2
    assert summary["retry_enabled_task_count"] == 1
    assert summary["dependency_task_count"] == 1
    assert summary["manifest_first_ratio_visible"] == 0.333
    assert summary["compat_fallback_ratio_visible"] == 0.333
    assert summary["runtime_supplement_ratio_visible"] == 0.333
    assert summary["retry_enabled_ratio_visible"] == 0.333
    assert summary["dependency_ratio_visible"] == 0.333
    assert summary["evidence_freshness_counts"]["fresh"] == 1
    assert summary["evidence_freshness_counts"]["live"] == 1
    assert summary["evidence_freshness_counts"]["stale"] == 1
    assert summary["manifest_backfill_candidate_count"] == 1
    assert summary["manifest_backfill_freshness_counts"]["fresh"] == 1
    assert summary["manifest_backfill_priority"] == "low"
    assert summary["multisource_task_count"] == 1
    assert summary["traceability_gap_task_count"] == 1
    assert summary["traceability_partial_task_count"] == 1
    assert summary["traceability_orphan_task_count"] == 0
    assert summary["governance_risk_counts"]["critical"] == 1
    assert summary["governance_risk_counts"]["high"] == 1
    assert summary["governance_risk_counts"]["medium"] == 1
    assert summary["governance_risk_priority"] == "critical"
    assert [item["task_id"] for item in summary["governance_risk_top_items"]] == [
        "run-task-compat-1",
        "run-task-runtime-1",
        "run-task-manifest-1",
    ]
    assert summary["governance_risk_top_items"][0]["governance_risk_level"] == "critical"
    assert summary["governance_risk_top_items"][0]["governance_risk_score"] == 6
    assert summary["governance_risk_top_items"][0]["gate_recommendation"] == "block"
    assert summary["governance_risk_top_items"][2]["traceability_status"] == "partial"
    assert summary["governance_risk_top_items"][2]["top_factor"]["factor"] == "api_contract"
    assert summary["governance_risk_top_items"][2]["gate_recommendation"] == "manual_review"
    assert summary["manifest_action_counts"]["ok"] == 1
    assert summary["manifest_action_counts"]["backfill_manifest"] == 1
    assert summary["manifest_action_counts"]["await_runtime_flush"] == 1
    assert summary["recommended_regression_scope_counts"]["api_contract_regression"] == 1
    assert summary["gate_recommendation_counts"]["block"] == 1
    assert summary["gate_recommendation_counts"]["manual_review"] == 2
    assert summary["recommended_regression_pack"] == "broad_regression"
    assert summary["strict_mode_readiness"]["status"] == "caution"
    assert summary["strict_mode_status_counts"]["blocked"] == 1
    assert summary["strict_mode_status_counts"]["caution"] == 1
    assert summary["strict_mode_status_counts"]["ready"] == 1
    assert summary["strict_mode_ready_task_count"] == 1
    assert summary["strict_mode_caution_task_count"] == 1
    assert summary["strict_mode_blocked_task_count"] == 1
    assert summary["strict_mode_can_disable_compat_builder"] is False


def test_list_execution_tasks_supports_strict_mode_status_filter(monkeypatch: Any) -> None:
    monkeypatch.setattr(
        workbench,
        "_collect_execution_records_with_meta",
        lambda limit=1000: (
            [
                {
                    "run_id": "run-task-manifest",
                    "case_id": "TC-READY-001",
                    "status": "passed",
                    "source": "manifest",
                    "execution_record_path": "/tmp/run-task-manifest.json",
                    "manifest_path": "/tmp/run-task-manifest-manifest.json",
                    "execution_record": {
                        "version": "ExecutionRecordV1",
                        "run_id": "run-task-manifest",
                        "case_id": "TC-READY-001",
                        "project": "default",
                        "status": "passed",
                        "mode": "generate_and_run",
                        "started_at": "2026-03-21T08:00:00+00:00",
                        "finished_at": "2026-03-21T08:01:00+00:00",
                        "created_at": "2026-03-21T07:59:50+00:00",
                        "metadata": {"runner": "playwright"},
                    },
                },
                {
                    "run_id": "run-task-compat",
                    "case_id": "TC-BLOCKED-001",
                    "status": "failed",
                    "source": "compat_scan",
                    "execution_record_path": "/tmp/run-task-compat.json",
                    "execution_record": {
                        "version": "ExecutionRecordV1",
                        "run_id": "run-task-compat",
                        "case_id": "TC-BLOCKED-001",
                        "project": "default",
                        "status": "failed",
                        "mode": "generate_and_run",
                        "started_at": "2026-03-21T08:00:00+00:00",
                        "finished_at": "2026-03-21T08:01:00+00:00",
                        "created_at": "2026-03-21T07:59:50+00:00",
                        "metadata": {"runner": "playwright"},
                    },
                },
            ],
            {},
        ),
    )

    client = TestClient(app)
    response = client.get("/api/workbench/tasks?strict_mode_status=blocked")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["items"]) == 1
    assert payload["items"][0]["run_id"] == "run-task-compat"
    assert payload["items"][0]["strict_mode"]["status"] == "blocked"
    assert payload["summary"]["strict_mode_status_counts"]["blocked"] == 1


def test_scheduler_summary_and_dispatch_plan_surface_queue_pressure(monkeypatch: Any) -> None:
    monkeypatch.setattr(
        workbench,
        "_collect_execution_records_with_meta",
        lambda limit=1000: (
            [
                {
                    "run_id": "run-scheduler-queued-1",
                    "case_id": "TC-SCHED-001",
                    "status": "queued",
                    "source": "manifest",
                    "execution_record": {
                        "version": "ExecutionRecordV1",
                        "run_id": "run-scheduler-queued-1",
                        "case_id": "TC-SCHED-001",
                        "project": "default",
                        "status": "queued",
                        "started_at": "2026-03-21T08:00:00+00:00",
                        "metadata": {
                            "runner": "playwright",
                            "scheduling_hints": {"queue": "critical", "expected_total_seconds": 180, "resource_profile": "browser-heavy"},
                        },
                    },
                    "manifest_path": "/tmp/run-scheduler-queued-1-manifest.json",
                    "execution_record_path": "/tmp/run-scheduler-queued-1.json",
                },
                {
                    "run_id": "run-scheduler-queued-2",
                    "case_id": "TC-SCHED-002",
                    "status": "queued",
                    "source": "compat_scan",
                    "execution_record": {
                        "version": "ExecutionRecordV1",
                        "run_id": "run-scheduler-queued-2",
                        "case_id": "TC-SCHED-002",
                        "project": "default",
                        "status": "queued",
                        "started_at": "2026-03-21T08:01:00+00:00",
                        "metadata": {
                            "runner": "api",
                            "scheduling_hints": {"queue": "critical", "expected_total_seconds": 90, "resource_profile": "default"},
                        },
                    },
                    "manifest_path": "",
                    "execution_record_path": "/tmp/run-scheduler-queued-2.json",
                },
                {
                    "run_id": "run-scheduler-running-1",
                    "case_id": "TC-SCHED-003",
                    "status": "running",
                    "source": "runtime_realtime",
                    "execution_record": {
                        "version": "ExecutionRecordV1",
                        "run_id": "run-scheduler-running-1",
                        "case_id": "TC-SCHED-003",
                        "project": "default",
                        "status": "running",
                        "started_at": "2026-03-21T08:02:00+00:00",
                        "metadata": {
                            "runner": "mobile",
                            "scheduling_hints": {"queue": "device", "expected_total_seconds": 240, "resource_profile": "heavy"},
                        },
                    },
                    "manifest_path": "",
                    "execution_record_path": "",
                },
            ],
            {
                "policy_mode": "compat",
                "health": "degraded",
                "strict_mode_readiness": {"status": "blocked"},
            },
        ),
    )

    client = TestClient(app)

    summary_response = client.get("/api/workbench/scheduler/summary")
    assert summary_response.status_code == 200
    summary = summary_response.json()["item"]
    assert summary["total_tasks"] == 3
    assert summary["active_task_count"] == 3
    assert summary["queued_task_count"] == 2
    assert summary["running_task_count"] == 1
    assert summary["queue_distribution"][0]["queue"] == "critical"
    assert summary["queue_distribution"][0]["pressure"] == "medium"
    assert summary["environment_pool_distribution"]["api-sandbox"] == 1
    assert summary["environment_pool_distribution"]["mobile-device-farm"] == 1
    assert summary["recommendations"][0]["title"] == "优先消化排队任务"
    assert any(item["title"] == "避免将 strict-mode blocked 任务推入高优先级队列" for item in summary["recommendations"])

    plan_response = client.get("/api/workbench/scheduler/dispatch-plan")
    assert plan_response.status_code == 200
    dispatch_plan = plan_response.json()["item"]
    assert dispatch_plan["lane_count"] == 2
    assert dispatch_plan["dispatch_lanes"][0]["queue"] == "critical"
    assert dispatch_plan["dispatch_lanes"][0]["task_count"] == 1
    assert dispatch_plan["dispatch_lanes"][0]["runner"] in {"playwright", "api"}
    assert {lane["environment_pool"] for lane in dispatch_plan["dispatch_lanes"]} == {"web-browser-heavy", "api-sandbox"}


def test_list_execution_tasks_supports_evidence_health_and_manifest_action_filters(monkeypatch: Any) -> None:
    monkeypatch.setattr(workbench, "_utc_now", lambda: datetime(2026, 3, 21, 10, 0, 0, tzinfo=UTC))
    monkeypatch.setattr(
        workbench,
        "_collect_execution_records_with_meta",
        lambda limit=1000: (
            [
                {
                    "run_id": "run-task-filter-1",
                    "case_id": "TC-FILTER-001",
                    "status": "passed",
                    "source": "manifest",
                    "execution_record_path": "/tmp/run-task-filter-1.json",
                    "manifest_path": "/tmp/run-task-filter-1-manifest.json",
                    "execution_record": {
                        "version": "ExecutionRecordV1",
                        "run_id": "run-task-filter-1",
                        "case_id": "TC-FILTER-001",
                        "project": "default",
                        "status": "passed",
                        "mode": "generate_and_run",
                        "started_at": "2026-03-21T08:00:00+00:00",
                        "finished_at": "2026-03-21T08:01:00+00:00",
                        "step_summary": {"page": "product", "total_steps": 1, "action_types": ["assert_visible"]},
                        "evidence_index": {"total_files": 2},
                        "metadata": {"runner": "playwright"},
                    },
                },
                {
                    "run_id": "run-task-filter-2",
                    "case_id": "TC-FILTER-002",
                    "status": "failed",
                    "source": "compat_scan",
                    "execution_record_path": "/tmp/run-task-filter-2.json",
                    "manifest_path": "",
                    "execution_record": {
                        "version": "ExecutionRecordV1",
                        "run_id": "run-task-filter-2",
                        "case_id": "TC-FILTER-002",
                        "project": "default",
                        "status": "failed",
                        "mode": "generate_and_run",
                        "started_at": "2026-03-21T09:00:00+00:00",
                        "finished_at": "2026-03-21T09:01:00+00:00",
                        "step_summary": {"page": "order", "total_steps": 1, "action_types": ["assert_visible"]},
                        "evidence_index": {"total_files": 1},
                        "metadata": {
                            "runner": "playwright",
                            "retry_policy": {"enabled": True, "max_retries": 2, "backoff_seconds": 8},
                            "dependencies": ["TC-SETUP-ORDER-001"],
                        },
                    },
                },
            ],
            {"policy_mode": "compat", "health": "degraded", "total_visible_records": 2},
        ),
    )

    client = TestClient(app)
    response = client.get(
        "/api/workbench/tasks?evidence_health_status=degraded&evidence_freshness_status=fresh&manifest_action=backfill_manifest&retry_enabled=true&has_dependencies=true"
    )

    assert response.status_code == 200
    payload = response.json()
    assert [item["task_id"] for item in payload["items"]] == ["run-task-filter-2"]
    assert payload["items"][0]["manifest_action"] == "backfill_manifest"
    assert payload["items"][0]["retry"]["enabled"] is True
    assert payload["items"][0]["dependency"]["has_dependencies"] is True
    assert payload["summary"]["evidence_health_counts"]["degraded"] == 1
    assert payload["summary"]["evidence_freshness_counts"]["fresh"] == 1
    assert payload["summary"]["manifest_action_counts"]["backfill_manifest"] == 1
    assert payload["summary"]["manifest_backfill_candidate_count"] == 1
    assert payload["summary"]["manifest_backfill_freshness_counts"]["fresh"] == 1
    assert payload["summary"]["manifest_backfill_priority"] == "low"
    assert payload["summary"]["governance_risk_counts"]["critical"] == 1
    assert payload["summary"]["governance_risk_priority"] == "critical"
    assert [item["task_id"] for item in payload["summary"]["governance_risk_top_items"]] == ["run-task-filter-2"]
    assert payload["summary"]["governance_risk_top_items"][0]["governance_risk_score"] == 6
    assert payload["summary"]["governance_risk_top_items"][0]["gate_recommendation"] == "block"
    assert payload["summary"]["retry_enabled_task_count"] == 1
    assert payload["summary"]["dependency_task_count"] == 1
    assert payload["summary"]["gate_recommendation_counts"]["block"] == 1
    assert payload["summary"]["recommended_regression_pack"] == "broad_regression"
    assert payload["summary"]["filter_snapshot"]["evidence_health_status"] == "degraded"
    assert payload["summary"]["filter_snapshot"]["evidence_freshness_status"] == "fresh"
    assert payload["summary"]["filter_snapshot"]["manifest_action"] == "backfill_manifest"
    assert payload["summary"]["filter_snapshot"]["retry_enabled"] == "true"
    assert payload["summary"]["filter_snapshot"]["has_dependencies"] == "true"


def test_get_run_prefers_latest_review_decisions_over_stored_runtime_state(monkeypatch: Any) -> None:
    monkeypatch.setattr(workbench, "_ensure_dirs", lambda: None)
    monkeypatch.setattr(workbench, "_get_job", lambda _run_id: None)

    def fake_read_json_list(path: Path) -> list[dict[str, Any]]:
        if path == workbench.RUNTIME_RUNS_FILE:
            return [
                {
                    "run_id": "run-review-2",
                    "project": "default",
                    "case_id": "TC-ORDER-001",
                    "page": "order",
                    "source": "rerun",
                    "status": "passed",
                    "started_at": "2026-03-20T11:00:00+00:00",
                    "finished_at": "2026-03-20T11:00:20+00:00",
                    "review_state": {
                        "element": {"status": "pending", "required": True, "candidate_count": 1, "items": []},
                        "test_point": {"status": "pending", "required": True, "candidate_count": 1, "items": []},
                        "requires_review": True,
                        "pending_sections": 2,
                        "confirmed_sections": 0,
                    },
                }
            ]
        if path == workbench.HISTORY_FILE:
            return [
                {
                    "timestamp": "2026-03-20T11:01:10+00:00",
                    "action": "review_confirmed",
                    "run_id": "run-review-2",
                    "page": "order",
                    "review_type": "element",
                    "status": "confirmed",
                    "actor_display": "betty (admin)",
                    "detail_summary": "element 确认 1 项",
                },
                {
                    "timestamp": "2026-03-20T11:01:20+00:00",
                    "action": "review_confirmed",
                    "run_id": "run-review-2",
                    "page": "order",
                    "review_type": "test_point",
                    "status": "confirmed",
                    "actor_display": "betty (admin)",
                    "detail_summary": "test_point 确认 1 项",
                },
            ]
        if path == workbench.REVIEW_DECISIONS_FILE:
            return [
                {
                    "project": "default",
                    "run_id": "run-review-2",
                    "case_id": "TC-ORDER-001",
                    "page": "order",
                    "review_type": "element",
                    "status": "confirmed",
                    "items": [{"key": "search_input", "label": "搜索框", "decision": "confirmed", "confidence": 0.88}],
                    "created_at": "2026-03-20T11:01:00+00:00",
                    "updated_at": "2026-03-20T11:01:10+00:00",
                },
                {
                    "project": "default",
                    "run_id": "run-review-2",
                    "case_id": "TC-ORDER-001",
                    "page": "order",
                    "review_type": "test_point",
                    "status": "confirmed",
                    "items": [{"key": "tp-01", "label": "查询功能", "decision": "confirmed", "confidence": 0.83}],
                    "created_at": "2026-03-20T11:01:00+00:00",
                    "updated_at": "2026-03-20T11:01:20+00:00",
                },
            ]
        return []

    monkeypatch.setattr(workbench, "_read_json_list", fake_read_json_list)

    client = TestClient(app)
    response = client.get("/api/workbench/runs/run-review-2")

    assert response.status_code == 200
    item = response.json()["item"]
    assert item["review_state"]["element"]["status"] == "confirmed"
    assert item["review_state"]["test_point"]["status"] == "confirmed"
    assert item["review_state"]["confirmed_sections"] == 2
    assert item["review_state"]["pending_sections"] == 0
    assert item["review_audit_summary"]["confirmed_sections"] == 2
    assert item["review_audit_summary"]["latest_updated_at"] == "2026-03-20T11:01:20+00:00"
    assert len(item["review_audit_timeline"]) == 2
    assert item["review_audit_timeline"][1]["review_type"] == "test_point"


def test_get_run_prefers_artifact_execution_record(monkeypatch: Any, tmp_path: Path) -> None:
    artifacts_dir = tmp_path / "run-legacy-2-artifacts"
    case_dir = artifacts_dir / "TC-ORDER-001"
    case_dir.mkdir(parents=True, exist_ok=True)
    manifest_record_path = case_dir / "manifest_execution_record.json"
    legacy_record_path = case_dir / "execution_record.json"
    manifest_record_path.write_text(
        '{"run_id":"run-legacy-2","case_id":"TC-ORDER-001","project":"default","source":"manual","mode":"generate_and_run","status":"failed","started_at":"2026-03-20T11:00:00+00:00","finished_at":"2026-03-20T11:00:30+00:00","step_summary":{"page":"order","requirement_count":1,"total_steps":2,"action_types":["login","assert_visible"]},"evidence_index":{"total_files":3,"artifact_categories":{"screenshots":1,"html_pages":0,"meta_files":0,"analysis_files":1,"suggestion_files":1,"execution_record_files":1,"self_healing_result_files":0,"videos":0,"other_files":0},"runner_exit_code":1,"execution_requested":true}}',
        encoding="utf-8",
    )
    legacy_record_path.write_text(
        '{"run_id":"run-legacy-2","case_id":"TC-ORDER-001","project":"default","source":"manual","mode":"generate_and_run","status":"passed","started_at":"2026-03-20T11:00:00+00:00","finished_at":"2026-03-20T11:00:20+00:00","step_summary":{"page":"order","requirement_count":1,"total_steps":1,"action_types":["login"]},"evidence_index":{"total_files":1,"artifact_categories":{"screenshots":0,"html_pages":0,"meta_files":0,"analysis_files":0,"suggestion_files":0,"execution_record_files":1,"self_healing_result_files":0,"videos":0,"other_files":0},"runner_exit_code":0,"execution_requested":true}}',
        encoding="utf-8",
    )
    (artifacts_dir / "evidence_manifest.json").write_text(
        json.dumps(
            {
                "version": "EvidenceManifestV1",
                "schema_version": "evidence-manifest.v1",
                "total_files": 1,
                "analysis_files": [],
                "suggestion_files": [],
                "execution_record_files": [str(manifest_record_path)],
                "screenshots": [],
                "html_pages": [],
                "meta_files": [],
                "self_healing_result_files": [],
                "videos": [],
                "other_files": [],
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(workbench, "_ensure_dirs", lambda: None)
    monkeypatch.setattr(workbench, "_get_job", lambda _run_id: None)
    monkeypatch.setattr(
        workbench,
        "_read_json_list",
        lambda _path: [
            {
                "run_id": "run-legacy-2",
                "project": "default",
                "case_id": "TC-ORDER-001",
                "source": "rerun",
                "status": "passed",
                "started_at": "2026-03-20T11:00:00+00:00",
                "finished_at": "2026-03-20T11:00:20+00:00",
                "return_code": 0,
                "log_path": "/tmp/run-legacy-2.log",
                "artifacts_dir": str(artifacts_dir),
                "videos_dir": "/tmp/run-legacy-2-videos",
            }
        ],
    )

    client = TestClient(app)
    response = client.get("/api/workbench/runs/run-legacy-2")

    assert response.status_code == 200
    item = response.json()["item"]
    assert item["status"] == "failed"
    assert item["execution_record"]["status"] == "failed"
    assert item["execution_record"]["evidence_index"]["runner_exit_code"] == 1


def test_report_overview_prefers_execution_records(monkeypatch: Any) -> None:
    monkeypatch.setattr(workbench, "_ensure_dirs", lambda: None)
    monkeypatch.setattr(
        workbench,
        "_collect_execution_records_with_meta",
        lambda **_kwargs: (
            [
                {
                    "run_id": "run-1",
                    "case_id": "tc-product-001",
                    "status": "passed",
                    "finished_at": "2026-03-20T10:00:30+00:00",
                    "source": "manifest",
                    "execution_record": {
                        "run_id": "run-1",
                        "case_id": "tc-product-001",
                        "status": "passed",
                        "started_at": "2026-03-20T10:00:00+00:00",
                        "finished_at": "2026-03-20T10:00:30+00:00",
                    },
                },
                {
                    "run_id": "run-2",
                    "case_id": "TC-ORDER-001",
                    "status": "failed",
                    "finished_at": "2026-03-20T11:00:30+00:00",
                    "source": "manifest",
                    "execution_record": {
                        "run_id": "run-2",
                        "case_id": "TC-ORDER-001",
                        "status": "failed",
                        "started_at": "2026-03-20T11:00:00+00:00",
                        "finished_at": "2026-03-20T11:00:30+00:00",
                    },
                },
            ],
            {"manifest_record_count": 2, "runtime_fallback_used": False, "warnings": []},
        ),
    )
    monkeypatch.setattr(workbench, "_collect_failure_entries", lambda: [])
    monkeypatch.setattr(workbench, "_load_defects", lambda: [])

    client = TestClient(app)
    response = client.get("/api/report/overview")

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["total_runs"] == 2
    assert payload["summary"]["passed_runs"] == 1
    assert payload["summary"]["failed_runs"] == 1
    assert payload["execution_meta"]["manifest_record_count"] == 2


def test_report_overview_normalizes_failure_source_and_manual_review(monkeypatch: Any) -> None:
    monkeypatch.setattr(workbench, "_ensure_dirs", lambda: None)
    monkeypatch.setattr(
        workbench,
        "_collect_execution_records_with_meta",
        lambda **_kwargs: ([], {"manifest_record_count": 0, "runtime_fallback_used": False, "warnings": []}),
    )
    monkeypatch.setattr(
        workbench,
        "_collect_failure_entries",
        lambda: [
            {
                "case_id": "tc-product-ERR-001",
                "case_title": "Product Error",
                "finished_at": "2026-03-20T11:00:00+00:00",
                "analysis": {
                    "summary": "失败来源尚未稳定识别",
                    "risk_level": "medium",
                    "failure_source": "",
                    "failure_source_reason": "",
                    "source_evidence": [{"signal": "fallback", "value": "insufficient_evidence", "origin": "report", "supports": "unknown"}],
                    "confidence": "0.52",
                    "requires_manual_review": False,
                },
                "artifact_dir": "/tmp/artifacts/tc-product-ERR-001",
            }
        ],
    )
    monkeypatch.setattr(workbench, "_load_defects", lambda: [])

    client = TestClient(app)
    response = client.get("/api/report/overview")

    assert response.status_code == 200
    items = response.json()["recent_failures"]
    assert len(items) == 1
    assert items[0]["failure_source"] == "unknown"
    assert items[0]["source_evidence"][0]["signal"] == "fallback"
    assert items[0]["requires_manual_review"] is True


def test_report_performance_uses_execution_record_source(monkeypatch: Any) -> None:
    monkeypatch.setattr(workbench, "_ensure_dirs", lambda: None)
    monkeypatch.setattr(
        workbench,
        "_collect_execution_records_with_meta",
        lambda **_kwargs: (
            [
                {
                    "source": "manifest",
                    "execution_record": {
                        "run_id": "run-1",
                        "case_id": "tc-product-001",
                        "status": "passed",
                        "started_at": "2026-03-20T10:00:00+00:00",
                        "finished_at": "2026-03-20T10:00:20+00:00",
                    },
                },
                {
                    "source": "runtime_realtime",
                    "execution_record": {
                        "run_id": "run-2",
                        "case_id": "TC-ORDER-001",
                        "status": "failed",
                        "started_at": "2026-03-20T11:00:00+00:00",
                        "finished_at": "2026-03-20T11:00:40+00:00",
                    },
                },
            ],
            {"runtime_realtime_count": 1, "warnings": []},
        ),
    )

    client = TestClient(app)
    response = client.get("/api/report/performance")

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["sample_count"] == 2
    assert payload["summary"]["max_duration_seconds"] == 40.0
    assert payload["slow_cases"][0]["run_id"] == "run-2"
    assert payload["slow_cases"][0]["source"] == "runtime_realtime"
    assert payload["execution_meta"]["runtime_realtime_count"] == 1


def test_report_failures_exposes_evidence_source(monkeypatch: Any) -> None:
    monkeypatch.setattr(workbench, "_ensure_dirs", lambda: None)
    monkeypatch.setattr(workbench, "_load_defects", lambda: [])
    monkeypatch.setattr(
        workbench,
        "_collect_failure_entries_with_meta",
        lambda: (
            [
                {
                    "case_id": "tc-product-001",
                    "case_title": "Product Smoke",
                    "finished_at": "2026-03-20T10:00:00Z",
                    "analysis": {
                        "summary": "定位失败",
                        "failure_category": "locator",
                        "failure_source": "page_object",
                        "failure_source_reason": "定位器与当前页面元素不再匹配",
                        "source_evidence": [{"signal": "token", "value": "selector", "origin": "stdout", "supports": "page_object"}],
                        "likely_cause": "元素定位变化",
                        "risk_level": "high",
                        "recommended_action": "更新定位器",
                        "confidence": "0.88",
                        "requires_manual_review": False,
                    },
                    "suggestion": {},
                    "artifact_dir": "/tmp/artifacts/tc-product-001",
                    "analysis_path": "/tmp/artifacts/tc-product-001/analysis.txt",
                    "suggestion_path": "",
                    "screenshot_path": "",
                    "html_path": "",
                    "meta_path": "",
                    "video_path": "",
                    "evidence_source": "manifest",
                    "manifest_path": "/tmp/artifacts/evidence_manifest.json",
                },
                {
                    "case_id": "TC-ORDER-001",
                    "case_title": "Order Smoke",
                    "finished_at": "2026-03-20T09:00:00Z",
                    "analysis": {
                        "summary": "断言失败",
                        "failure_category": "assertion",
                        "failure_source": "case_design",
                        "failure_source_reason": "断言预期与当前页面文本不一致",
                        "likely_cause": "文本不匹配",
                        "risk_level": "medium",
                        "recommended_action": "调整断言",
                        "confidence": "0.77",
                        "requires_manual_review": True,
                    },
                    "suggestion": {},
                    "artifact_dir": "/tmp/artifacts/TC-ORDER-001",
                    "analysis_path": "/tmp/artifacts/TC-ORDER-001/analysis.txt",
                    "suggestion_path": "",
                    "screenshot_path": "",
                    "html_path": "",
                    "meta_path": "",
                    "video_path": "",
                    "evidence_source": "compat_scan",
                    "manifest_path": "",
                },
            ],
            {
                "compat_scan_enabled": True,
                "manifest_entry_count": 1,
                "compat_scan_entry_count": 1,
                "compat_scan_used_count": 1,
                "compat_scan_skipped_count": 0,
                "invalid_manifest_count": 0,
                "missing_manifest_count": 1,
            },
        ),
    )

    client = TestClient(app)
    response = client.get("/api/report/failures")

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 2
    assert items[0]["case_id"] == cid("tc-product-001")
    assert items[0]["evidence_source"] == "manifest"
    assert items[0]["failure_source"] == "page_object"
    assert items[0]["source_evidence"][0]["origin"] == "stdout"
    assert items[0]["requires_manual_review"] is False
    assert items[0]["manifest_path"] == "/tmp/artifacts/evidence_manifest.json"
    assert items[1]["case_id"] == cid("TC-ORDER-001")
    assert items[1]["evidence_source"] == "compat_scan"
    assert items[1]["failure_source"] == "case_design"
    assert items[1]["requires_manual_review"] is True
    assert items[1]["manifest_path"] == ""
    meta = response.json()["evidence_meta"]
    assert meta["compat_scan_enabled"] is True
    assert meta["policy_mode"] == "compat"
    assert meta["health"] == "degraded"
    assert meta["manifest_entry_count"] == 1
    assert meta["compat_scan_entry_count"] == 1
    assert meta["manifest_first_ratio"] == 0.5


def test_get_run_analysis_normalizes_latest_failure_source_fields(monkeypatch: Any) -> None:
    monkeypatch.setattr(workbench, "_ensure_dirs", lambda: None)
    monkeypatch.setattr(
        workbench,
        "_get_job",
        lambda _run_id: {
            "run_id": "run-analysis-1",
            "artifacts_dir": "/tmp/non-existent-run-analysis-1",
            "latest_failure": {
                "case_id": "TC-ORDER-001",
                "analysis": {
                    "summary": "失败来源不稳定",
                    "failure_category": "assertion",
                    "failure_source": "",
                    "failure_source_reason": "",
                    "confidence": "0.61",
                    "failure_source_confidence": "0.4",
                    "source_evidence": [{"signal": "fallback", "value": "insufficient_evidence", "origin": "report", "supports": "unknown"}],
                    "requires_manual_review": False,
                },
            },
        },
    )

    client = TestClient(app)
    response = client.get("/api/workbench/runs/run-analysis-1/analysis")

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    analysis = items[0]["analysis"]
    assert analysis["failure_source"] == "unknown"
    assert analysis["failure_source_reason"] == "Failure source reason not available."
    assert analysis["failure_source_confidence"] == 0.4
    assert analysis["source_evidence"][0]["supports"] == "unknown"
    assert analysis["requires_manual_review"] is True
    summary = response.json()["failure_source_summary"]
    assert summary["version"] == "FailureSourceSummaryV1"
    assert summary["total_failures"] == 1
    assert summary["source_counts"]["unknown"] == 1
    assert summary["requires_manual_review_count"] == 1
    assert summary["low_confidence_count"] == 1
    assert summary["average_failure_source_confidence"] == 0.4


def test_parse_analysis_file_supplements_failure_source_fields_from_embedded_json(tmp_path: Path) -> None:
    analysis_path = tmp_path / "analysis.txt"
    analysis_path.write_text(
        "\n".join(
            [
                "Summary: 失败来源不稳定",
                "Failure Category: assertion",
                "Likely Cause: selector changed",
                "Risk Level: high",
                "Recommended Action: manual_review",
                "Confidence: 0.61",
                "",
                json.dumps(
                    {
                        "summary": "失败来源不稳定",
                        "failure_category": "assertion",
                        "failure_source": "page_object",
                        "failure_source_reason": "selector not found in page object",
                        "failure_source_confidence": 0.86,
                        "source_evidence": [
                            {
                                "signal": "selector_not_found",
                                "value": "#submit-button",
                                "origin": "stdout",
                                "supports": "page_object",
                            }
                        ],
                        "requires_manual_review": True,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                "",
            ]
        ),
        encoding="utf-8",
    )

    parsed = workbench._parse_analysis_file(analysis_path)

    assert parsed["failure_source"] == "page_object"
    assert parsed["failure_source_reason"] == "selector not found in page object"
    assert float(parsed["failure_source_confidence"]) == 0.86
    assert isinstance(parsed["source_evidence"], list)
    assert parsed["source_evidence"][0]["supports"] == "page_object"
    assert parsed["requires_manual_review"] is True


def test_collect_failure_entries_strict_mode_disables_compat_scan(monkeypatch: Any, tmp_path: Path) -> None:
    monkeypatch.setattr(workbench.SETTINGS, "evidence_manifest_compat_scan_enabled", False, raising=False)

    runner_root = tmp_path / "runner-root"
    artifact_case_dir = runner_root / "artifacts" / "TC-STRICT-001"
    artifact_case_dir.mkdir(parents=True, exist_ok=True)
    (artifact_case_dir / "analysis.txt").write_text("summary: strict mode fallback disabled\n", encoding="utf-8")

    runs_dir = tmp_path / "runs-root"
    runs_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(workbench, "RUNNER_ROOT", runner_root)
    monkeypatch.setattr(workbench, "WEB_UI_RUNS_DIR", runs_dir)

    entries, meta = workbench._collect_failure_entries_with_meta()

    assert entries == []
    assert meta["compat_scan_enabled"] is False
    assert meta["policy_mode"] == "strict"
    assert meta["missing_manifest_count"] >= 1
    assert meta["compat_scan_skipped_count"] >= 1
    assert meta["compat_scan_entry_count"] == 0


def test_report_endpoints_set_no_store_headers(monkeypatch: Any) -> None:
    monkeypatch.setattr(workbench, "_ensure_dirs", lambda: None)
    monkeypatch.setattr(workbench, "_collect_execution_records_with_meta", lambda **_kwargs: ([], {}))
    monkeypatch.setattr(workbench, "_collect_failure_entries", lambda: [])
    monkeypatch.setattr(workbench, "_collect_failure_entries_with_meta", lambda: ([], {}))
    monkeypatch.setattr(workbench, "_load_defects", lambda: [])
    monkeypatch.setattr(workbench, "_read_allure_summary", lambda: {})
    monkeypatch.setattr(workbench, "_ensure_allure_snapshot", lambda _version: "/allure/index.html")

    client = TestClient(app)
    endpoints = [
        "/api/report/overview",
        "/api/report/failures",
        "/api/report/context",
        "/api/report/performance",
        "/api/report/allure",
    ]
    for path in endpoints:
        response = client.get(path)
        assert response.status_code == 200
        assert "no-store" in response.headers.get("Cache-Control", "")
        assert response.headers.get("Pragma") == "no-cache"


def test_workbench_cases_endpoint_returns_pagination_metadata(monkeypatch: Any, tmp_path: Path) -> None:
    state_root = tmp_path / "state"
    project_dir = state_root / "default"
    project_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(workbench, "TEST_POINTS_ROOT", state_root)
    monkeypatch.setattr(workbench, "AI_CASES_ROOT", tmp_path / "ai-generated")
    monkeypatch.setattr(workbench, "_ensure_dirs", lambda: None)

    for index in range(5):
        case_id = f"tc-product-00{index + 1}"
        updated_at = f"2026-03-22T12:{59 - index:02d}:00+00:00"
        (project_dir / f"{case_id}.json").write_text(
            json.dumps(
                {
                    "asset_id": case_id,
                    "title": f"Case {index + 1}",
                    "page": "product",
                    "priority": "P1",
                    "updated_at": updated_at,
                }
            ),
            encoding="utf-8",
        )

    client = TestClient(app)
    response = client.get("/api/workbench/cases", params={"project": "default", "page": 2, "page_size": 2})

    assert response.status_code == 200
    payload = response.json()
    assert payload["pagination"]["page"] == 2
    assert payload["pagination"]["page_size"] == 2
    assert payload["pagination"]["total_items"] == 5
    assert payload["pagination"]["total_pages"] == 3
    assert payload["pagination"]["has_prev"] is True
    assert payload["pagination"]["has_next"] is True
    assert [item["case_id"] for item in payload["items"]] == [cid("tc-product-003"), cid("tc-product-004")]


def test_workbench_cases_endpoint_focuses_on_case_id(monkeypatch: Any, tmp_path: Path) -> None:
    state_root = tmp_path / "state"
    project_dir = state_root / "default"
    project_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(workbench, "TEST_POINTS_ROOT", state_root)
    monkeypatch.setattr(workbench, "AI_CASES_ROOT", tmp_path / "ai-generated")
    monkeypatch.setattr(workbench, "_ensure_dirs", lambda: None)

    for index in range(5):
        case_id = f"tc-product-00{index + 1}"
        updated_at = f"2026-03-22T12:{59 - index:02d}:00+00:00"
        (project_dir / f"{case_id}.json").write_text(
            json.dumps(
                {
                    "asset_id": case_id,
                    "title": f"Case {index + 1}",
                    "page": "product",
                    "priority": "P1",
                    "updated_at": updated_at,
                }
            ),
            encoding="utf-8",
        )

    client = TestClient(app)
    response = client.get(
        "/api/workbench/cases",
        params={"project": "default", "page": 1, "page_size": 2, "focus_case_id": cid("tc-product-003")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["pagination"]["page"] == 2
    assert payload["pagination"]["total_pages"] == 3
    assert [item["case_id"] for item in payload["items"]] == [cid("tc-product-003"), cid("tc-product-004")]


def test_defect_endpoints_use_database_backend_when_enabled(monkeypatch: Any, tmp_path: Path) -> None:
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import sessionmaker

    from app.core.database import Base
    from app.models.workbench_state import WorkbenchDefectLink

    state_root = tmp_path / "state"
    default_dir = state_root / "default"
    runs_dir = state_root / "runs"
    reporting_dir = state_root / "reporting"

    defect_file = reporting_dir / "defect-links.json"
    history_file = default_dir / "history.json"
    runtime_file = default_dir / "runtime-runs.json"
    review_file = reporting_dir / "review-decisions.json"
    gate_file = reporting_dir / "execution-gate-decisions.json"
    calibration_file = reporting_dir / "failure-source-calibrations.json"

    db_file = tmp_path / "workbench-state.db"
    engine = create_engine(f"sqlite:///{db_file}", future=True)
    Base.metadata.create_all(bind=engine)
    test_session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    monkeypatch.setenv("WORKBENCH_STATE_BACKEND", "database")
    monkeypatch.setattr(workbench._workbench_state_store, "SessionLocal", test_session_local)

    monkeypatch.setattr(workbench, "WEB_UI_STATE_ROOT", state_root)
    monkeypatch.setattr(workbench, "WEB_UI_DEFAULT_STATE_DIR", default_dir)
    monkeypatch.setattr(workbench, "WEB_UI_RUNS_DIR", runs_dir)
    monkeypatch.setattr(workbench, "WEB_UI_REPORTING_DIR", reporting_dir)
    monkeypatch.setattr(workbench, "TEST_POINTS_ROOT", state_root / "test-points")
    monkeypatch.setattr(workbench, "ASSETS_CASES_ROOT", tmp_path / "assets" / "test-cases")
    monkeypatch.setattr(workbench, "AI_CASES_ROOT", tmp_path / "assets" / "test-cases" / "ai-generated")
    monkeypatch.setattr(workbench, "ALLURE_SNAPSHOTS_ROOT", tmp_path / "allure-snapshots")

    monkeypatch.setattr(workbench, "HISTORY_FILE", history_file)
    monkeypatch.setattr(workbench, "RUNTIME_RUNS_FILE", runtime_file)
    monkeypatch.setattr(workbench, "DEFECT_LINKS_FILE", defect_file)
    monkeypatch.setattr(workbench, "REVIEW_DECISIONS_FILE", review_file)
    monkeypatch.setattr(workbench, "EXECUTION_GATE_DECISIONS_FILE", gate_file)
    monkeypatch.setattr(workbench, "FAILURE_SOURCE_CALIBRATIONS_FILE", calibration_file)

    client = TestClient(app)
    payload = {
        "case_id": "TC-DEFECT-API-001",
        "defect_id": "BUG-API-001",
        "defect_url": "https://jira.example.com/browse/BUG-API-001",
        "system": "jira",
        "note": "integration-db-backend",
    }

    response_1 = client.post("/api/defects", json=payload)
    response_2 = client.post("/api/defects", json=payload)
    assert response_1.status_code == 201
    assert response_2.status_code == 201

    list_response = client.get("/api/defects", params={"case_id": cid("TC-DEFECT-API-001")})
    assert list_response.status_code == 200
    items = list_response.json()["items"]
    assert len(items) == 1
    assert items[0]["defect_id"] == "BUG-API-001"

    with test_session_local() as db:
        rows = db.execute(select(WorkbenchDefectLink)).scalars().all()
        assert len(rows) == 1
        assert rows[0].case_id == cid("TC-DEFECT-API-001")
        assert rows[0].defect_id == "BUG-API-001"

    snapshot = json.loads(defect_file.read_text(encoding="utf-8"))
    assert len(snapshot) == 1
    assert snapshot[0]["defect_id"] == "BUG-API-001"


def test_run_endpoint_starts_execution_from_case_path(monkeypatch: Any, tmp_path: Path) -> None:
    case_root = tmp_path / "assets" / "test-cases"
    case_path = case_root / "ai-generated" / "TC-RUN-001.yaml"
    case_path.parent.mkdir(parents=True, exist_ok=True)
    case_path.write_text("id: TC-RUN-001\n", encoding="utf-8")

    captured: dict[str, Any] = {}

    monkeypatch.setattr(workbench, "_ensure_dirs", lambda: None)
    monkeypatch.setattr(workbench, "ASSETS_CASES_ROOT", case_root)
    monkeypatch.setattr(workbench, "_safe_case_id", lambda value: value.upper())
    monkeypatch.setattr(workbench, "_is_within", lambda path, root: str(path).startswith(str(root)))
    monkeypatch.setattr(
        workbench,
        "_start_run",
        lambda **kwargs: captured.update(kwargs) or {"run_id": "RUN-RUN-1", "status": "queued"},
    )

    client = TestClient(app)
    response = client.post(
        "/api/workbench/run",
        json={
            "project": "default",
            "case_id": "tc-run-001",
            "case_path": str(case_path),
            "source": "manual",
        },
    )

    assert response.status_code == 200
    item = response.json()["item"]
    assert item["run_id"] == "RUN-RUN-1"
    assert captured["project"] == "default"
    assert captured["case_id"] == "TC-RUN-001"
    assert captured["case_path"] == case_path.resolve()
    assert captured["source"] == "manual"


def test_stream_run_events_replays_log_and_terminal_marker(monkeypatch: Any, tmp_path: Path) -> None:
    log_path = tmp_path / "RUN-STREAM-1.log"
    log_path.write_text("line-1\nline-2\n", encoding="utf-8")

    monkeypatch.setattr(workbench, "_ensure_dirs", lambda: None)
    monkeypatch.setattr(workbench, "_get_job", lambda _run_id: None)
    monkeypatch.setattr(
        workbench,
        "_read_json_list",
        lambda path: [
            {
                "run_id": "RUN-STREAM-1",
                "status": "passed",
                "log_path": str(log_path),
            }
        ]
        if path == workbench.RUNTIME_RUNS_FILE
        else [],
    )

    client = TestClient(app)
    response = client.get("/api/workbench/runs/RUN-STREAM-1/events")

    assert response.status_code == 200
    body = response.text
    assert '"line": "line-1"' in body
    assert '"line": "line-2"' in body
    assert '"event": "complete"' in body
    assert '"status": "passed"' in body


def test_download_log_returns_plain_text(monkeypatch: Any, tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    log_path = runs_dir / "RUN-DOWNLOAD-1.log"
    log_path.write_text("downloaded log\nsecond line\n", encoding="utf-8")

    monkeypatch.setattr(workbench, "_ensure_dirs", lambda: None)
    monkeypatch.setattr(workbench, "WEB_UI_RUNS_DIR", runs_dir)

    client = TestClient(app)
    response = client.get("/api/workbench/download-log/RUN-DOWNLOAD-1")

    assert response.status_code == 200
    assert response.headers["content-disposition"] == "attachment; filename=RUN-DOWNLOAD-1.log"
    assert response.text == "downloaded log\nsecond line\n"


def test_heal_and_rerun_returns_compound_summary(monkeypatch: Any) -> None:
    history_events: list[dict[str, Any]] = []

    monkeypatch.setattr(workbench, "_ensure_dirs", lambda: None)
    monkeypatch.setattr(
        workbench,
        "_find_run_item",
        lambda _run_id: {
            "run_id": "RUN-SOURCE-1",
            "project": "default",
            "case_id": "TC-RUN-001",
            "case_path": "/tmp/TC-RUN-001.yaml",
            "status": "failed",
        },
    )
    monkeypatch.setattr(
        workbench,
        "heal_run",
        lambda run_id: {"item": {"run_id": run_id, "status": "success", "healed": True}},
    )
    monkeypatch.setattr(
        workbench,
        "rerun_case",
        lambda run_id: {"item": {"run_id": "RUN-RERUN-1", "status": "running", "source_run_id": run_id}},
    )
    monkeypatch.setattr(
        workbench,
        "_wait_run_terminal",
        lambda run_id, timeout_seconds: ({"run_id": run_id, "status": "passed"}, False),
    )
    monkeypatch.setattr(workbench, "_append_history", lambda entry: history_events.append(entry))

    client = TestClient(app)
    response = client.post("/api/workbench/runs/RUN-SOURCE-1/heal-and-rerun", params={"wait_seconds": 5})

    assert response.status_code == 200
    item = response.json()["item"]
    assert item["source_run_id"] == "RUN-SOURCE-1"
    assert item["heal"]["ok"] is True
    assert item["heal"]["item"]["healed"] is True
    assert item["rerun"]["run_id"] == "RUN-RERUN-1"
    assert item["rerun"]["status"] == "passed"
    assert history_events[0]["action"] == "heal_and_rerun_case"
    assert history_events[0]["run_id"] == "RUN-RERUN-1"
    assert history_events[0]["heal_ok"] is True
    assert history_events[0]["rerun_status"] == "passed"
