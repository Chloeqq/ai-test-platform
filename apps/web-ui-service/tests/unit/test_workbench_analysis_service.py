# ruff: noqa: E402
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


WEB_UI_ROOT = Path(__file__).resolve().parents[2]
if str(WEB_UI_ROOT) not in sys.path:
    sys.path.insert(0, str(WEB_UI_ROOT))
APPS_ROOT = Path(__file__).resolve().parents[3]
if str(APPS_ROOT) not in sys.path:
    sys.path.insert(0, str(APPS_ROOT))

from app.services import workbench_analysis_service as analysis_service


def test_build_page_analysis_context_normalizes_bundle_contract(monkeypatch) -> None:
    def fake_consume_page_analysis_bundle(**kwargs):
        assert kwargs["page"] == "product"
        return {
            "analysis_bundle": {"version": "PageAnalysisBundleV1"},
            "page_surface": {"page": "product"},
            "page_surface_summary": {"confidence": 0.9},
            "page_semantic": {"page_type": "list"},
            "page_semantic_summary": {"page_type": "list", "confidence": 0.85},
            "page_object": {"page": "product"},
            "page_object_summary": {"confidence": 0.8},
            "test_points": {"page": "product"},
            "test_point_summary": {"confidence": 0.75},
            "model_versions": {"page_surface": "PageSurfaceV1"},
            "consumed_models": {"page_surface": True},
            "confidence": 0.92,
            "warnings": ["low confidence element"],
            "requires_review": True,
        }

    monkeypatch.setattr(analysis_service, "consume_page_analysis_bundle", fake_consume_page_analysis_bundle)

    context = analysis_service.build_page_analysis_context(
        page="product",
        project="default",
        case_id="TC-001",
        page_url="http://localhost/product",
        page_surface={"page": "product"},
        page_object={"page": "product"},
        test_points={"page": "product"},
    )

    assert context["analysis_bundle"]["version"] == "PageAnalysisBundleV1"
    assert context["page_surface_summary"]["confidence"] == 0.9
    assert context["page_semantic_summary"]["page_type"] == "list"
    assert context["confidence"] == 0.92
    assert context["requires_review"] is True


def test_normalize_entry_wrappers_delegate_to_pipeline(monkeypatch) -> None:
    calls: dict[str, Any] = {}

    def fake_surface(payload, page="", requested_url=""):
        calls["surface"] = {"payload": payload, "page": page, "requested_url": requested_url}
        return {"page": page, "requested_url": requested_url}

    def fake_object(payload, page="", path=""):
        calls["object"] = {"payload": payload, "page": page, "path": path}
        return {"page": page, "path": path}

    def fake_bundle(**kwargs):
        calls["bundle"] = kwargs
        return {"analysis_bundle": {"version": "x"}}

    monkeypatch.setattr(
        analysis_service,
        "normalize_page_surface_model",
        fake_surface,
    )
    monkeypatch.setattr(
        analysis_service,
        "normalize_page_object_model",
        fake_object,
    )
    monkeypatch.setattr(
        analysis_service,
        "consume_page_analysis_bundle",
        fake_bundle,
    )

    surface = analysis_service.normalize_page_surface({"raw": True}, page="product", requested_url="http://x")
    page_object = analysis_service.normalize_page_object_draft({"raw": True}, page="product", path="/tmp/po.yaml")
    bundle = analysis_service.consume_model_bundle(page="product", project="default")

    assert calls["surface"]["page"] == "product"
    assert calls["object"]["path"] == "/tmp/po.yaml"
    assert calls["bundle"]["page"] == "product"
    assert surface["page"] == "product"
    assert page_object["path"] == "/tmp/po.yaml"
    assert bundle["analysis_bundle"]["version"] == "x"


def test_surface_wrappers_delegate_to_rules(monkeypatch) -> None:
    calls: dict[str, Any] = {}

    def fake_candidate(**kwargs):
        calls["candidate"] = kwargs
        return {"key": kwargs["key"], "confidence": kwargs["confidence"]}

    def fake_candidates(page, surface):
        calls["candidates"] = {"page": page, "surface": surface}
        return [{"key": "login_button"}]

    def fake_summary(surface):
        calls["summary"] = {"surface": surface}
        return {"confidence": 0.9}

    def fake_inferred(page, surface):
        calls["inferred"] = {"page": page, "surface": surface}
        return {"login_button": {"locator_type": "role"}}

    def fake_snapshot(**kwargs):
        calls["snapshot"] = kwargs
        return {"surface": "ok"}

    monkeypatch.setattr(analysis_service.page_analysis_rules, "build_surface_element_candidate", fake_candidate)
    monkeypatch.setattr(analysis_service.page_analysis_rules, "build_surface_element_candidates", fake_candidates)
    monkeypatch.setattr(analysis_service.page_analysis_rules, "surface_confidence_summary", fake_summary)
    monkeypatch.setattr(analysis_service.page_analysis_rules, "surface_inferred_elements", fake_inferred)
    monkeypatch.setattr(analysis_service.page_analysis_rules, "build_surface_result_from_snapshot", fake_snapshot)

    candidate = analysis_service.build_surface_element_candidate(
        key="login_button",
        label="登录",
        locator_type="role",
        locator_value="登录",
        confidence=0.8,
        source="rules",
    )
    candidates = analysis_service.build_surface_element_candidates("product", {"page": "product"})
    summary = analysis_service.surface_confidence_summary({"page": "product"})
    inferred = analysis_service.surface_inferred_elements("product", {"page": "product"})
    snapshot = analysis_service.build_surface_result_from_snapshot(
        page_url="http://x",
        payload={"page": "product"},
        frame_surface={},
        login_url="http://login",
        login_attempted=True,
        login_succeeded=True,
        redirected_to_login=False,
        login_network_idle_reached=True,
        target_network_idle_reached=True,
        marker_selector="#app",
        selector_wait_status="stable",
        requested_route="/pms/product",
        final_route="/pms/product",
        route_mismatch=False,
        stability={"status": "stable"},
    )

    assert calls["candidate"]["key"] == "login_button"
    assert calls["candidates"]["page"] == "product"
    assert calls["summary"]["surface"]["page"] == "product"
    assert calls["inferred"]["page"] == "product"
    assert calls["snapshot"]["page_url"] == "http://x"
    assert candidate["confidence"] == 0.8
    assert candidates[0]["key"] == "login_button"
    assert summary["confidence"] == 0.9
    assert inferred["login_button"]["locator_type"] == "role"
    assert snapshot["surface"] == "ok"


def test_test_point_chain_helpers_delegate_and_annotate(monkeypatch) -> None:
    calls: dict[str, Any] = {}

    def fake_normalize(payload, strict=False):
        calls["normalize"] = {"payload": payload, "strict": strict}
        return payload

    monkeypatch.setattr(analysis_service, "normalize_test_point_plan_model", fake_normalize)

    plan = analysis_service.steps_to_points(
        "product",
        "商品详情",
        [
            {"action": "login"},
            {"action": "click", "target": "search_button"},
            {"action": "assert_visible", "target": "product_table"},
        ],
    )
    surface_index = analysis_service.surface_candidate_confidence_index(
        {"element_candidates": [{"key": "search_button", "confidence": 0.82, "label": "查询"}]}
    )
    inherited = analysis_service.inherit_test_point_confidence_from_surface(
        plan={
            "points": [
                {"key": "tp-1", "dependent_elements": ["search_button"], "confidence": 0.9, "warnings": []}
            ]
        },
        surface={"element_candidates": [{"key": "search_button", "confidence": 0.62, "label": "查询"}]},
    )
    annotated = analysis_service.annotate_test_point_plan_review(
        {
            "points": [
                {
                    "key": "tp-1",
                    "action": "click",
                    "confidence": 0.8,
                    "warnings": ["needs review"],
                    "requires_review": True,
                    "dependent_elements": ["search_button"],
                }
            ]
        }
    )
    review_items = analysis_service.build_test_point_review_items(
        {
            "points": [
                {"key": "tp-1", "description": "点击查询", "confidence": 0.55, "requires_review": True, "warnings": ["w"]},
                {"key": "tp-2", "description": "无需复核", "confidence": 0.9, "requires_review": False},
            ]
        }
    )

    assert calls["normalize"]["strict"] is False
    assert plan["points"][1]["suggestion"] == "review"
    assert plan["points"][1]["confidence"] < 0.75
    assert surface_index["search_button"]["confidence"] == 0.82
    assert inherited["points"][0]["confidence"] == 0.62
    assert annotated["review_summary"]["pending_review_count"] == 1
    assert review_items[0]["key"] == "tp-1"
    assert review_items[0]["suggestion"] == "skip"


def test_build_page_object_quality_uses_default_resolver_and_rule_helpers(monkeypatch, tmp_path) -> None:
    calls: dict[str, Any] = {}

    def fake_required_page_elements(page, requirement, surface):
        calls["required"] = {"page": page, "requirement": requirement, "surface": surface}
        return ["login_button", "search_button"]

    def fake_surface_inferred_elements(page, surface):
        calls["inferred"] = {"page": page, "surface": surface}
        return {"login_button": {"locator_type": "role", "locator_value": "登录", "role": "button"}}

    def fake_summary(surface):
        calls["summary"] = surface
        return {"confidence": 0.8, "warnings": ["surface warning"]}

    def fake_normalize(payload, page="", path=""):
        calls["normalize"] = {"payload": payload, "page": page, "path": path}
        return payload

    monkeypatch.setattr(analysis_service.page_analysis_rules, "required_page_elements", fake_required_page_elements)
    monkeypatch.setattr(analysis_service.page_analysis_rules, "surface_inferred_elements", fake_surface_inferred_elements)
    monkeypatch.setattr(analysis_service.page_analysis_rules, "surface_confidence_summary", fake_summary)
    monkeypatch.setattr(analysis_service, "normalize_page_object_model", fake_normalize)

    page_object_path = tmp_path / "product.page-object.yaml"
    page_object_path.write_text(
        "page: product\nelements:\n  login_button:\n    locator_type: role\n    locator_value: 登录\n    role: button\n",
        encoding="utf-8",
    )

    result = analysis_service.build_page_object_quality(
        "product",
        "搜索商品",
        {"search_placeholder": "商品", "element_candidates": []},
        page_object_path,
        default_page_elements_fn=lambda _page: {
            "login_button": {"locator_type": "role", "locator_value": "登录", "role": "button"},
            "search_button": {"locator_type": "role", "locator_value": "查询", "role": "button"},
        },
    )

    assert calls["required"]["page"] == "product"
    assert calls["inferred"]["page"] == "product"
    assert calls["normalize"]["page"] == "product"
    assert result["summary"]["missing_required_count"] == 1
    assert result["coverage"]["status"] == "partial"
    assert result["low_confidence_items"]
    assert any(item["key"] in {"login_button", "search_button"} for item in result["low_confidence_items"])


def test_default_page_elements_and_safe_key_delegate_to_rules() -> None:
    defaults = analysis_service.default_page_elements("product")
    fallback_defaults = analysis_service.default_page_elements("custom")
    safe_key = analysis_service.safe_element_key("查询按钮", "search_button")

    assert "product_table" in defaults
    assert fallback_defaults["login_button"]["locator_value"] == "登录"
    assert safe_key == "search_button"


def test_normalize_test_point_plan_delegates_to_pipeline(monkeypatch) -> None:
    calls: dict[str, Any] = {}

    def fake_normalize(payload, strict=False):
        calls["normalize"] = {"payload": payload, "strict": strict}
        return {"normalized": True, "strict": strict}

    monkeypatch.setattr(analysis_service, "normalize_test_point_plan_model", fake_normalize)

    result = analysis_service.normalize_test_point_plan({"points": []}, strict=True)

    assert calls["normalize"]["strict"] is True
    assert result["normalized"] is True


def test_build_failure_analysis_for_risk_flags_confidence_gap() -> None:
    result = analysis_service.build_failure_analysis_for_risk(
        final_status="passed",
        page_object_summary={"missing_required_count": 2},
        test_points={"review_summary": {"skip_suggestion_count": 1}},
    )

    assert result["failure_category"] == "confidence_gap"
    assert result["risk_level"] == "medium"
    assert result["requires_manual_review"] is True
    assert result["recommended_action"] == "manual_review"


def test_build_review_section_preserves_actor_display_for_existing_entry() -> None:
    section = analysis_service.build_review_section(
        review_type="risk",
        items=[{"key": "risk_decision", "label": "风险决策确认"}],
        existing_entry={
            "status": "confirmed",
            "items": [{"key": "risk_decision", "label": "风险决策确认"}],
            "updated_at": "2026-03-22T17:20:54+00:00",
            "note": "checked",
            "confirmed_by": "betty",
            "confirmed_by_role": "admin",
        },
    )

    assert section["status"] == "confirmed"
    assert section["candidate_count"] == 1
    assert section["actor_display"] == "betty (admin)"
    assert section["items"][0]["key"] == "risk_decision"


def test_build_risk_review_items_emits_single_review_card() -> None:
    items = analysis_service.build_risk_review_items(
        {
            "confidence": 0.88,
            "recommendation": "当前风险可控，可继续执行后续回归或放行。",
            "gate_decision": "allow",
            "risk_level": "low",
            "risk_score": 24,
            "evidence": ["execution_status=24 (执行状态=passed)"],
        }
    )

    assert len(items) == 1
    assert items[0]["key"] == "risk_decision"
    assert items[0]["confidence"] == 0.88
    assert items[0]["warnings"] == ["execution_status=24 (执行状态=passed)"]


def test_risk_helpers_normalize_and_summarize() -> None:
    factors = analysis_service.normalize_risk_factors(
        [
            {"factor": "execution_status", "score": "24", "reason": "执行状态=passed", "category": "execution"},
            {"factor": "low_confidence_elements", "score": 8, "reason": "低置信度元素 2 个", "category": "page_surface"},
        ],
        source="unit-test",
    )

    assert factors[0]["source"] == "unit-test"
    assert factors[0]["score"] == 24
    summary = analysis_service.build_risk_factor_summary(factors=factors)
    evidence = analysis_service.build_risk_evidence(factors=factors)
    semantic_evidence = analysis_service.build_semantic_risk_evidence(
        page_semantic_summary={
            "page_type": "list",
            "business_domain": "product",
            "primary_goal": "inspect_page",
            "confidence": 0.9,
            "requires_review": False,
        }
    )

    assert summary["factor_count"] == 2
    assert summary["top_factor"]["factor"] == "execution_status"
    assert evidence[0] == "execution_status=24 (执行状态=passed)"
    assert semantic_evidence[0].startswith("page_semantic=type:list,domain:product")


def test_reviewer_display_name_handles_unknown_role() -> None:
    assert analysis_service.reviewer_display_name({"confirmed_by": "betty", "confirmed_by_role": "admin"}) == "betty (admin)"
    assert analysis_service.reviewer_display_name({"confirmed_by": "betty", "confirmed_by_role": "unknown"}) == "betty"
    assert analysis_service.reviewer_display_name({}) == "anonymous"
