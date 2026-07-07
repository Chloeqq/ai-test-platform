import sys
from pathlib import Path

import pytest


pytestmark = [pytest.mark.integration]


PROJECT_ROOT = Path(__file__).resolve().parents[4]
SRC_ROOT = PROJECT_ROOT / "apps" / "ai-orchestrator" / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from orchestrator_service import OrchestratorService


def _build_service() -> OrchestratorService:
    return OrchestratorService(repo_root=PROJECT_ROOT)


def test_parse_requirement_multisource_outputs_structured_contract():
    service = _build_service()
    requirement_spec = service.parse_requirement(
        requirement="退货申请页面支持按服务单号查询，普通用户只能查看自己的单据，结果尽快返回。",
        page="",
        source="manual",
        input_sources=[
            {"source_type": "prd", "content": "退货申请列表需支持服务单号、状态筛选"},
            {"source_type": "openapi", "content": "GET /api/return-apply/list\nPOST /api/return-apply/{id}/approve"},
            {"source_type": "git_diff", "content": "+++ b/apps/refund/service.py\n+def check_permission(user):\n+    pass"},
        ],
        prd_text="查询响应时间 P95 < 800ms，审批后状态应更新为已审核。",
        user_story="作为客服，我需要在退货申请页快速搜索并审核记录。",
        git_diff="diff --git a/apps/refund/service.py b/apps/refund/service.py\n+++ b/apps/refund/service.py\n+def check_permission(user):\n+    pass\n",
        defect_ticket="BUG-1023 unauthorized user can view others return apply, severity=critical",
        runtime_logs="ERROR timeout while querying return apply list",
        openapi_spec={
            "info": {"title": "Refund API"},
            "paths": {
                "/api/return-apply/list": {"get": {"summary": "查询退货申请列表"}},
                "/api/return-apply/{id}/approve": {"post": {"summary": "审核退货申请"}},
            },
        },
    )

    assert requirement_spec["version"] == "RequirementSpecV1"
    assert requirement_spec["page"] == "returnapply"
    assert len(requirement_spec["source_inputs"]) >= 6
    assert all(str(item.get("source_id", "")).strip() for item in requirement_spec["source_inputs"] if isinstance(item, dict))
    assert all(isinstance(item.get("reference_ids", []), list) for item in requirement_spec["source_inputs"] if isinstance(item, dict))

    intent_titles = [str(intent.get("title", "")) for intent in requirement_spec["test_intents"]]
    assert not any("+++" in title or "@@" in title for title in intent_titles)
    assert any(intent.get("intent_type") == "api" for intent in requirement_spec["test_intents"])
    assert any(intent.get("intent_type") == "regression" for intent in requirement_spec["test_intents"])
    assert all("source_ids" in intent for intent in requirement_spec["test_intents"])
    assert all(intent.get("source_ids") for intent in requirement_spec["test_intents"])

    assert requirement_spec["coverage_matrix"]
    assert all("traceability_status" in row for row in requirement_spec["coverage_matrix"])
    assert all("source_ids" in row for row in requirement_spec["coverage_matrix"])
    assert all("explanation" in row for row in requirement_spec["coverage_matrix"])

    change_impact = requirement_spec["change_impact"]
    assert "impact_score" in change_impact
    assert "changed_areas" in change_impact
    assert isinstance(change_impact["affected_intent_ids"], list)
    assert isinstance(change_impact["impacted_source_ids"], list)
    assert isinstance(change_impact["risk_signals"], list)
    assert isinstance(change_impact["factors"], list)
    assert isinstance(change_impact["top_factor"], dict)
    assert isinstance(change_impact["recommended_regression_scope"], list)
    assert change_impact["explanation"]

    assert requirement_spec["business_rules"]
    assert all(rule.get("rule_text") for rule in requirement_spec["business_rules"] if isinstance(rule, dict))
    assert any(rule.get("source_ids") for rule in requirement_spec["business_rules"] if isinstance(rule, dict))
    assert requirement_spec["ambiguities"]
    quality_gate = requirement_spec["quality_gate"]
    assert quality_gate["version"] == "RequirementQualityGateV1"
    assert quality_gate["stage"] == "parse"
    assert "decision" in quality_gate
    assert quality_gate["explanation"]
    assert "metrics" in quality_gate
    assert isinstance(quality_gate["blockers"], list)
    parser_runtime = requirement_spec.get("parser_runtime", {})
    assert parser_runtime.get("agent") == "requirement-parser-agent"
    assert str(parser_runtime.get("prompt_version", "")).startswith("requirement-parser.prompt.")
    assert str(parser_runtime.get("instructions_version", "")).startswith("requirement-parser.instructions.")
    assert parser_runtime.get("model")
    llm_trace = parser_runtime.get("llm_trace", {})
    assert isinstance(llm_trace, dict)
    assert "reason_code" in llm_trace
    assert "latency_ms" in llm_trace
    assert "overlay_key_count" in llm_trace
    assert isinstance(parser_runtime.get("source_summary"), dict)
    assert isinstance(parser_runtime.get("page_resolution"), dict)
    assert isinstance(parser_runtime["page_resolution"].get("candidate_details"), list)
    assert "conflict_detected" in parser_runtime["page_resolution"]
    if quality_gate["blockers"]:
        blocker = quality_gate["blockers"][0]
        assert blocker["code"]
        assert blocker["alert_code"].startswith("REQQG_")


def test_parse_requirement_accepts_empty_page_when_multi_source_present():
    service = _build_service()
    requirement_spec = service.parse_requirement(
        requirement="",
        page="",
        source="manual",
        openapi_spec={
            "info": {"title": "Order API"},
            "paths": {
                "/api/order/list": {"get": {"summary": "查询订单列表"}},
            },
        },
    )

    assert requirement_spec["version"] == "RequirementSpecV1"
    assert requirement_spec["page"]
    assert requirement_spec["test_intents"]
    assert requirement_spec["quality_gate"]["version"] == "RequirementQualityGateV1"
    assert isinstance(requirement_spec.get("parser_runtime"), dict)


def test_requirement_parse_telemetry_summary_contains_prompt_model_mode():
    service = _build_service()
    service.parse_requirement(
        requirement="验证商品列表页面可以查询并展示结果。",
        page="product",
        source="manual",
    )

    summary = service.get_requirement_parse_telemetry_summary(limit=200, stage="parse")

    assert summary["version"] == "RequirementParseTelemetrySummaryV1"
    assert summary["total_events"] >= 1
    assert "groups" in summary
    assert any(str(item.get("prompt_version", "")).startswith("requirement-parser.prompt.") for item in summary["groups"])
    assert any(str(item.get("mode", "")) for item in summary["groups"])
