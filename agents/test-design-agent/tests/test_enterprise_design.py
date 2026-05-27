from pathlib import Path
import sys


SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from src.agent import TestDesignAgent  # noqa: E402
from src.test_points import build_test_point_plan  # noqa: E402


def _build_agent_without_init() -> TestDesignAgent:
    return object.__new__(TestDesignAgent)


def test_build_test_point_plan_includes_confidence_and_review_summary():
    plan = build_test_point_plan(
        page="product",
        requirement=["商品列表搜索"],
        steps=[
            {"action": "login"},
            {"action": "click"},
            {"action": "fill", "target": "search_input", "value": "手机"},
            {"action": "assert_visible", "target": "product_list_title"},
        ],
    )

    assert plan.confidence is not None
    assert plan.review_summary["total_points"] == 4
    assert plan.review_summary["pending_review_count"] >= 1
    assert plan.points[1].requires_review is True
    assert "缺少 target" in plan.points[1].warnings[0]


def test_design_bundle_from_requirement_spec_produces_traceability_and_case():
    agent = _build_agent_without_init()
    bundle = agent.design_bundle(
        requirement="商品列表页支持按名称搜索",
        page="product",
        requirement_spec={
            "page": "product",
            "priority": "P1",
            "design_input": "商品列表页支持按名称搜索",
            "test_intents": [
                {
                    "intent_id": "intent-01",
                    "title": "登录后进入商品页",
                    "intent_type": "functional",
                    "priority": "P0",
                    "steps_hint": ["login", "open:product"],
                },
                {
                    "intent_id": "intent-02",
                    "title": "搜索商品并查看结果",
                    "intent_type": "functional",
                    "priority": "P1",
                    "steps_hint": ["search"],
                },
            ],
        },
    )

    assert bundle["version"] == "TestDesignBundleV1"
    assert bundle["case"]["execution"]["page"] == "product"
    assert bundle["case"]["execution"]["steps"][:2] == [
        {"action": "login"},
        {"action": "click", "target": "product_menu"},
    ]
    assert bundle["test_points"]["review_summary"]["total_points"] == 2
    assert bundle["traceability"]["point_links"]
    assert bundle["traceability"]["coverage_ratio"] > 0
    assert bundle["review_summary"]["total_points"] == bundle["test_points"]["review_summary"]["total_points"]
    assert bundle["requires_review"] in {True, False}


def test_design_bundle_adds_boundary_and_equivalence_points_from_field_definitions():
    agent = _build_agent_without_init()
    bundle = agent.design_bundle(
        page="catalog",
        requirement_spec={
            "page": "catalog",
            "priority": "P1",
            "design_input": "搜索关键字需要做结构化约束测试",
            "test_intents": [
                {
                    "intent_id": "intent-search",
                    "title": "输入关键字进行搜索",
                    "intent_type": "functional",
                    "priority": "P1",
                    "steps_hint": ["search"],
                }
            ],
            "field_definitions": [
                {
                    "field_key": "keyword",
                    "title": "搜索关键字",
                    "target": "search_input",
                    "field_type": "string",
                    "required": True,
                    "constraints": {"min_length": 1, "max_length": 20},
                    "source_ids": ["prd.keyword"],
                }
            ],
        },
    )

    technique_points = [
        point
        for point in bundle["test_points"]["points"]
        if point.get("execution_scope") == "design_only"
    ]

    assert bundle["case"]["execution"]["steps"] == [
        {"action": "login"},
        {"action": "fill", "target": "search_input", "value": "3"},
    ]
    assert technique_points
    assert any(point["technique_type"] == "boundary" for point in technique_points)
    assert any(point["technique_type"] == "equivalence" for point in technique_points)
    assert all(point["field_key"] == "keyword" for point in technique_points)
    assert bundle["test_points"]["metadata"]["field_definition_count"] == 1
    assert bundle["test_points"]["review_summary"]["technique_distribution"]["boundary"] >= 1
    assert bundle["test_points"]["review_summary"]["technique_distribution"]["equivalence"] >= 1
    assert bundle["traceability"]["design_only_point_count"] == len(technique_points)


def test_design_bundle_supports_date_amount_and_api_parameter_constraints():
    agent = _build_agent_without_init()
    bundle = agent.design_bundle(
        page="billing",
        requirement_spec={
            "page": "billing",
            "priority": "P0",
            "design_input": "账单查询接口和页面表单需要约束覆盖",
            "test_intents": [
                {
                    "intent_id": "intent-billing-search",
                    "title": "进入账单查询页",
                    "intent_type": "functional",
                    "priority": "P0",
                    "steps_hint": ["open:billing"],
                }
            ],
            "field_definitions": [
                {
                    "field_key": "settlement_date",
                    "title": "结算日期",
                    "target": "settlement_date_input",
                    "type": "string",
                    "format": "date",
                    "constraints": {"min_date": "2026-01-01", "max_date": "2026-12-31"},
                },
                {
                    "field_key": "amount",
                    "title": "账单金额",
                    "target": "amount_input",
                    "field_type": "amount",
                    "constraints": {"min": 0, "max": 9999.99},
                },
            ],
            "parameter_constraints": [
                {
                    "name": "pageNo",
                    "title": "分页页码",
                    "in": "query",
                    "method": "GET",
                    "path": "/api/billing/list",
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 200,
                    "source_ids": ["swagger.billing.pageNo"],
                }
            ],
        },
    )

    technique_points = [
        point
        for point in bundle["test_points"]["points"]
        if point.get("execution_scope") == "design_only"
    ]
    date_points = [point for point in technique_points if point.get("field_key") == "settlement_date"]
    amount_points = [point for point in technique_points if point.get("field_key") == "amount"]
    api_points = [point for point in technique_points if point.get("field_key") == "pageNo"]

    assert any(point["technique_source"] == "min_date" for point in date_points)
    assert any(point["technique_source"] == "invalid_date_format" for point in date_points)
    assert any(point["technique_source"] == "negative_value" for point in amount_points)
    assert any(point["technique_source"] == "min_value" for point in api_points)
    assert all(point["action"] == "api_request" for point in api_points)
    assert all(point["point_type"] == "api" for point in api_points)
    assert all(point["parameter_location"] == "query" for point in api_points)
    assert all(point["api_method"] == "GET" for point in api_points)
    assert all(point["api_path"] == "/api/billing/list" for point in api_points)
    assert bundle["test_points"]["metadata"]["field_definition_count"] == 3
    assert bundle["test_points"]["review_summary"]["technique_distribution"]["boundary"] >= 4
