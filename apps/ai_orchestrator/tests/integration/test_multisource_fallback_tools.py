from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest


pytestmark = [pytest.mark.integration]


PROJECT_ROOT = Path(__file__).resolve().parents[4]
SRC_ROOT = PROJECT_ROOT / "apps" / "ai-orchestrator" / "src"
APPS_ROOT = PROJECT_ROOT / "apps"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
if str(APPS_ROOT) not in sys.path:
    sys.path.insert(0, str(APPS_ROOT))

import orchestrator_service as orchestrator_module
from orchestrator_service import OrchestratorService


def _build_service() -> OrchestratorService:
    return OrchestratorService(repo_root=PROJECT_ROOT)


def _load_module(module_path: Path, module_name: str) -> Any:
    spec = importlib.util.spec_from_file_location(module_name, str(module_path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load module: {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_parse_requirement_fallback_uses_local_multisource_tools(monkeypatch: Any) -> None:
    service = _build_service()

    class FailedCompletedProcess:
        returncode = 1
        stderr = "requirement parser failed"
        stdout = ""

    monkeypatch.setattr(orchestrator_module.subprocess, "run", lambda *args, **kwargs: FailedCompletedProcess())

    requirement_spec = service.parse_requirement(
        requirement="",
        page="",
        source="manual",
        openapi_spec={
            "info": {"title": "Refund API"},
            "paths": {
                "/api/return-apply/list": {
                    "get": {
                        "summary": "查询退货申请列表",
                        "parameters": [
                            {"name": "status", "in": "query", "required": False, "schema": {"type": "string"}},
                        ],
                    }
                },
                "/api/return-apply/{id}/approve": {"post": {"summary": "审核退货申请"}},
            },
        },
        git_diff="diff --git a/apps/refund/service.py b/apps/refund/service.py\n+++ b/apps/refund/service.py\n+def check_permission(user):\n+    pass\n",
        defect_ticket="BUG-1023 unauthorized user can view others return apply, severity=critical",
    )

    assert requirement_spec["version"] == "RequirementSpecV1"
    assert requirement_spec["page"] == "returnapply"
    assert any(item.get("source_type") == "openapi" for item in requirement_spec["source_inputs"])
    assert any(item.get("source_type") == "git_diff" for item in requirement_spec["source_inputs"])
    assert any(item.get("source_type") == "defect_ticket" for item in requirement_spec["source_inputs"])
    assert all(item.get("source_id") for item in requirement_spec["source_inputs"] if isinstance(item, dict))
    assert any(intent.get("intent_type") == "api" for intent in requirement_spec["test_intents"])
    assert any(intent.get("intent_type") == "regression" for intent in requirement_spec["test_intents"])
    assert requirement_spec["parameter_constraints"]
    assert requirement_spec["business_rules"]
    assert requirement_spec["change_impact"]["changed_files"]
    assert requirement_spec["change_impact"]["changed_areas"]
    assert requirement_spec["change_impact"]["risk_signals"]
    assert requirement_spec["change_impact"]["impacted_source_ids"]
    assert requirement_spec["change_impact"]["impact_score"] >= 20
    assert requirement_spec["change_impact"]["factors"]
    assert requirement_spec["change_impact"]["top_factor"]["factor"]
    assert requirement_spec["change_impact"]["recommended_regression_scope"]
    assert requirement_spec["change_impact"]["why_manual_review"]
    assert requirement_spec["quality_gate"]["version"] == "RequirementQualityGateV1"
    assert requirement_spec["parser_runtime"]["page_resolution"]["page"] == "returnapply"


def test_parse_requirement_fallback_exposes_page_conflict_resolution(monkeypatch: Any) -> None:
    service = _build_service()

    class FailedCompletedProcess:
        returncode = 1
        stderr = "requirement parser failed"
        stdout = ""

    monkeypatch.setattr(orchestrator_module.subprocess, "run", lambda *args, **kwargs: FailedCompletedProcess())

    requirement_spec = service.parse_requirement(
        requirement="查询商品后进入订单确认页",
        page="",
        source="manual",
        openapi_spec={
            "info": {"title": "Order API"},
            "paths": {
                "/api/order/list": {"get": {"summary": "查询订单列表"}},
            },
        },
        git_diff="diff --git a/apps/product/page.ts b/apps/product/page.ts\n+++ b/apps/product/page.ts\n+const productTitle = '商品列表'\n",
        defect_ticket="BUG-77 component=product severity=high 商品页按钮文案错误",
    )

    page_resolution = requirement_spec["parser_runtime"]["page_resolution"]

    assert page_resolution["conflict_detected"] is True
    assert page_resolution["candidate_details"]
    assert page_resolution["chosen_candidate"]["page"] in {"order", "product"}
    assert page_resolution["resolution_strategy"] == "source_priority_then_score"
    assert page_resolution["source_priority_rules"]
    assert page_resolution["chosen_reason"]
    assert page_resolution["rejected_reasons"]
    assert page_resolution["conflict_candidate_details"]
    assert requirement_spec["page"] in {"order", "product"}


def test_local_test_point_schema_module_exposes_schema_and_normalizer() -> None:
    module = _load_module(
        SRC_ROOT / "schemas" / "test-point.schema.py",
        "ai_orchestrator_test_point_schema_test",
    )
    schema = module.get_test_point_plan_schema()
    normalized, warnings = module.normalize_test_point_plan(
        {
            "version": "TestPointPlanV1",
            "project": "default",
            "case_id": "TC-DEMO-001",
            "page": "product",
            "points": [
                {
                    "key": "product-01",
                    "point_type": "action",
                    "action": "click",
                    "description": "进入商品列表",
                    "priority": "P1",
                }
            ],
        },
        strict=False,
    )

    assert schema["properties"]["points"]["type"] == "array"
    assert normalized["version"] == "TestPointPlanV1"
    assert normalized["case_id"] == "TC-DEMO-001"
    assert isinstance(warnings, list)


def test_local_multisource_tools_extract_structured_signals() -> None:
    openapi_module = _load_module(
        SRC_ROOT / "tools" / "openapi-parser.tool.py",
        "ai_orchestrator_openapi_parser_tool_test",
    )
    git_diff_module = _load_module(
        SRC_ROOT / "tools" / "git-diff.tool.py",
        "ai_orchestrator_git_diff_tool_test",
    )
    jira_module = _load_module(
        SRC_ROOT / "tools" / "jira-reader.tool.py",
        "ai_orchestrator_jira_reader_tool_test",
    )

    openapi_payload = openapi_module.parse_openapi_spec(
        {
            "info": {"title": "Refund API"},
            "paths": {
                "/api/return-apply/{id}/approve": {
                    "post": {
                        "summary": "审核退货申请",
                        "requestBody": {
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "required": ["decision"],
                                        "properties": {
                                            "decision": {"type": "string", "enum": ["approve", "reject"]},
                                            "reason": {"type": "string", "maxLength": 200},
                                        },
                                    }
                                }
                            }
                        },
                    }
                }
            },
        }
    )
    diff_payload = git_diff_module.analyze_git_diff(
        "diff --git a/apps/refund/service.py b/apps/refund/service.py\n+++ b/apps/refund/service.py\n+def check_permission(user):\n+    assert user\n"
    )
    jira_payload = jira_module.parse_defect_ticket(
        "BUG-42 severity=critical component=refund labels=security regression\n- unauthorized user can approve return apply"
    )

    assert openapi_payload["parameter_constraints"]
    assert any(item.get("constraint_kind") == "request_body" for item in openapi_payload["parameter_constraints"])
    assert "approval_flow" in openapi_payload["changed_areas"]
    assert openapi_payload["risk_signals"]
    assert "permission" in diff_payload["changed_areas"]
    assert diff_payload["risk_signals"]
    assert jira_payload["business_rule_hints"]
    assert jira_payload["regression_priority_boost"] >= 1
