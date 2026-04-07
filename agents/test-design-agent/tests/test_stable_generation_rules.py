from pathlib import Path
import sys


SRC_ROOT = Path(__file__).resolve().parents[1]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.agent import TestDesignAgent  # noqa: E402
from shared_backend.case_ids import match_case_id  # noqa: E402


def _build_agent_without_init() -> TestDesignAgent:
    return object.__new__(TestDesignAgent)


def test_login_step_must_remain_bare_after_normalization():
    agent = _build_agent_without_init()
    test_case = {
        "execution": {
            "page": "product",
            "steps": [
                {"action": "login", "target": "product_menu", "value": "should-drop"},
                {"action": "click", "target": "product_menu"},
            ],
        }
    }

    normalized = agent._normalize_steps_for_stable_style(test_case)

    assert normalized["execution"]["steps"][0] == {"action": "login"}


def test_product_page_generation_must_reuse_stable_smoke_prefix():
    agent = _build_agent_without_init()
    test_case = {
        "execution": {
            "page": "product",
            "steps": [
                {"action": "login"},
                {"action": "click", "target": "search_button"},
                {"action": "fill", "target": "search_input", "value": "手机"},
                {"action": "wait_for", "target": "product_list_title"},
                {"action": "assert_visible", "target": "product_list_title"},
            ],
        }
    }

    normalized = agent._enforce_stable_page_baseline(test_case, "product")

    assert normalized["execution"]["steps"][:2] == [
        {"action": "login"},
        {"action": "click", "target": "product_menu"},
    ]
    assert normalized["execution"]["steps"][2:] == [
        {"action": "fill", "target": "search_input", "value": "手机"},
        {"action": "wait_for", "target": "product_list_title"},
        {"action": "assert_visible", "target": "product_list_title"},
    ]


def test_login_page_generation_must_reuse_stable_smoke_shape():
    agent = _build_agent_without_init()
    test_case = {
        "execution": {
            "page": "login",
            "steps": [
                {"action": "login"},
                {"action": "assert_visible", "target": "navbar"},
            ],
        }
    }

    normalized = agent._enforce_stable_page_baseline(test_case, "login")

    assert normalized["execution"]["steps"] == [
        {"action": "login"},
        {"action": "assert_visible", "target": "home_menu"},
    ]


def test_build_test_points_from_case_keeps_step_order_and_semantics():
    agent = _build_agent_without_init()
    test_case = {
        "requirement": ["商品搜索"],
        "execution": {
            "page": "product",
            "steps": [
                {"action": "login"},
                {"action": "click", "target": "product_menu"},
                {"action": "fill", "target": "search_input", "value": "手机"},
                {"action": "assert_visible", "target": "product_list_title"},
            ],
        },
    }

    plan = agent._build_test_points_from_case(test_case)

    assert plan["page"] == "product"
    assert plan["requirement"] == ["商品搜索"]
    assert [point["action"] for point in plan["points"]] == [
        "login",
        "click",
        "fill",
        "assert_visible",
    ]
    assert [point["point_type"] for point in plan["points"]] == [
        "precondition",
        "navigation",
        "input",
        "assertion",
    ]
    assert plan["points"][1]["target"] == "product_menu"
    assert plan["points"][2]["value"] == "手机"


def test_render_case_from_test_points_preserves_stable_steps():
    agent = _build_agent_without_init()
    test_case = {
        "id": "tc-product-001",
        "requirement": ["商品搜索"],
        "execution": {
            "page": "product",
            "steps": [
                {"action": "login"},
                {"action": "click", "target": "product_menu"},
                {"action": "fill", "target": "search_input", "value": "手机"},
                {"action": "assert_visible", "target": "product_list_title"},
            ],
        },
    }

    plan = agent._build_test_points_from_case(test_case)
    rendered = agent._render_case_from_test_points(test_case, plan)

    assert rendered["execution"]["steps"] == test_case["execution"]["steps"]


def test_legacy_case_id_is_rewritten_to_platform_case_id(tmp_path, monkeypatch):
    monkeypatch.setattr(TestDesignAgent, "AI_CASES_ROOT", tmp_path)
    agent = _build_agent_without_init()
    parsed = {
        "id": "PROD-SEARCH-001",
        "title": "商品搜索-输入关键字-点击搜索-展示结果",
        "description": "验证商品搜索场景生成的本地 YAML 也遵循平台 ID 规则。",
        "tags": ["smoke", "search"],
        "execution": {
            "page": "product",
            "variables": {},
            "steps": [{"action": "login"}],
        },
    }

    normalized = agent._normalize_testcase(parsed, "product")

    assert normalized["id"] != "PROD-SEARCH-001"
    assert match_case_id(normalized["id"])
    assert normalized["id"].startswith("atp-web-")
    assert "-ai-" in normalized["id"]


def test_requirement_spec_case_and_plan_share_platform_case_id(tmp_path, monkeypatch):
    monkeypatch.setattr(TestDesignAgent, "AI_CASES_ROOT", tmp_path)
    agent = _build_agent_without_init()
    requirement_spec = {
        "case_id": "PROD-SEARCH-001",
        "title": "商品搜索-输入关键字-点击搜索-展示结果",
        "design_input": "验证商品搜索主流程",
        "tags": ["smoke", "search"],
        "test_intents": [
            {
                "intent_id": "intent-01",
                "title": "商品搜索结果展示",
                "intent_type": "functional",
                "priority": "P1",
                "steps_hint": ["输入关键字", "点击搜索", "展示商品列表"],
            }
        ],
    }

    requirement_rows = agent._normalize_requirement_rows(
        requirement="验证商品搜索主流程",
        requirement_spec=requirement_spec,
    )
    case = agent._build_case_from_requirement_spec(
        requirement_spec=requirement_spec,
        page="product",
        requirement_rows=requirement_rows,
    )
    plan = agent._build_points_from_requirement_spec(
        requirement_spec=requirement_spec,
        page="product",
        intents=requirement_spec["test_intents"],
    )

    assert match_case_id(case["id"])
    assert case["id"] == plan["case_id"]
    assert case["id"].startswith("atp-web-")
    assert "-ai-" in case["id"]
