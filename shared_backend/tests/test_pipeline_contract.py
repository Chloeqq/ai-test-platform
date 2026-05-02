"""Contract tests: orchestrator output → normalizer → compiler full chain.

Validates that the data produced by the orchestrator (build_test_points_from_requirement_spec)
flows through normalize_test_point_plan_v1 and compile_execution_steps correctly.
"""
from __future__ import annotations

import pytest
from shared_backend.execution_compiler import compile_execution_steps
from shared_backend.schemas.contracts import normalize_test_point_plan_v1


_PAGE_OBJECT = {
    "elements": {
        "username_input": {"selector": "[placeholder='请输入用户名']", "type": "placeholder"},
        "password_input": {"selector": "[placeholder='请输入密码']", "type": "placeholder"},
        "login_button": {"selector": "button:text('登录')", "type": "role"},
        "search_input": {"selector": "#search", "type": "css"},
        "product_list_title": {"selector": ".list-title", "type": "css"},
    }
}


def _make_orchestrator_points() -> list[dict]:
    """Simulate the exact shape output by build_test_points_from_requirement_spec (post-P1.1 fix)."""
    return [
        {
            "key": "intent-01",
            "intent_id": "intent-01",
            "point_type": "action",
            "action": "fill",
            "target": "username_input",
            "value": "testuser",
            "description": "填写用户名",
            "priority": "P1",
            "expected_result": "用户名字段可输入且值回显正确。",
            "dependencies": [],
            "source_ids": [],
            "steps": [{"action": "fill", "target": "username_input", "value": "testuser", "raw_text": "填写用户名"}],
            "involved_elements": ["username_input"],
            "metadata": {
                "traceability": {
                    "intent_ids": ["intent-01"],
                    "source_ids": [],
                    "origin": "requirement_intent",
                }
            },
        },
        {
            "key": "intent-02",
            "intent_id": "intent-02",
            "point_type": "action",
            "action": "fill",
            "target": "password_input",
            "value": "password123",
            "description": "填写密码",
            "priority": "P1",
            "expected_result": "密码字段可输入且不明文显示。",
            "dependencies": ["intent-01"],
            "source_ids": [],
            "steps": [{"action": "fill", "target": "password_input", "value": "password123", "raw_text": "填写密码"}],
            "involved_elements": ["password_input"],
            "metadata": {
                "traceability": {
                    "intent_ids": ["intent-02"],
                    "source_ids": [],
                    "origin": "requirement_intent",
                }
            },
        },
        {
            "key": "intent-03",
            "intent_id": "intent-03",
            "point_type": "action",
            "action": "click",
            "target": "login_button",
            "description": "点击登录按钮",
            "priority": "P1",
            "expected_result": "点击后进入已登录状态页面。",
            "dependencies": ["intent-02"],
            "source_ids": [],
            "steps": [{"action": "click", "target": "login_button", "raw_text": "点击登录按钮"}],
            "involved_elements": ["login_button"],
            "metadata": {
                "traceability": {
                    "intent_ids": ["intent-03"],
                    "source_ids": [],
                    "origin": "requirement_intent",
                }
            },
        },
    ]


def _make_test_point_plan(points: list[dict]) -> dict:
    return {
        "version": "TestPointPlanV1",
        "project": "default",
        "case_id": "test-contract-001",
        "page": "login",
        "points": points,
    }


class TestNormalizerPreservesFields:
    """Ensure normalize_test_point_plan_v1 retains all critical fields."""

    def test_intent_id_preserved(self) -> None:
        plan = _make_test_point_plan(_make_orchestrator_points())
        result, warnings = normalize_test_point_plan_v1(plan)
        for point in result["points"]:
            assert "intent_id" in point, f"intent_id missing in normalized point: {point}"
            assert point["intent_id"].startswith("intent-")

    def test_involved_elements_preserved(self) -> None:
        plan = _make_test_point_plan(_make_orchestrator_points())
        result, warnings = normalize_test_point_plan_v1(plan)
        for point in result["points"]:
            assert "involved_elements" in point
            assert isinstance(point["involved_elements"], list)
            assert len(point["involved_elements"]) > 0

    def test_steps_preserved(self) -> None:
        plan = _make_test_point_plan(_make_orchestrator_points())
        result, warnings = normalize_test_point_plan_v1(plan)
        for point in result["points"]:
            assert point.get("steps") is not None, f"steps missing: {point}"
            assert isinstance(point["steps"], list)
            assert len(point["steps"]) == 1
            step = point["steps"][0]
            assert "action" in step
            assert "raw_text" in step

    def test_expected_result_preserved(self) -> None:
        plan = _make_test_point_plan(_make_orchestrator_points())
        result, _ = normalize_test_point_plan_v1(plan)
        for point in result["points"]:
            assert "expected_result" in point
            assert str(point["expected_result"]).strip()

    def test_expected_alias_normalized_to_expected_result(self) -> None:
        points = _make_orchestrator_points()
        points[0].pop("expected_result", None)
        points[0]["expected"] = "别名字段也应归一到 expected_result。"
        plan = _make_test_point_plan(points)
        result, _ = normalize_test_point_plan_v1(plan)
        assert result["points"][0]["expected_result"] == "别名字段也应归一到 expected_result。"

    def test_key_and_intent_id_consistent(self) -> None:
        points = _make_orchestrator_points()
        points[0]["key"] = "legacy-key-01"
        plan = _make_test_point_plan(points)
        result, _ = normalize_test_point_plan_v1(plan)
        assert result["points"][0]["key"] == "legacy-key-01"
        assert result["points"][0]["intent_id"] == "intent-01"

    def test_involved_elements_present_on_all_points(self) -> None:
        plan = _make_test_point_plan(_make_orchestrator_points())
        result, _ = normalize_test_point_plan_v1(plan)
        for point in result["points"]:
            inv = set(point.get("involved_elements", []))
            assert inv, f"involved_elements should not be empty: {point}"
            assert "dependent_elements" not in point, "dependent_elements must not appear in normalized output"


class TestPipelineBoundaryContractValidation:
    """Contract normalization at pipeline boundaries ensures fields are present."""

    def test_raw_orchestrator_points_get_normalized_before_compile(self) -> None:
        raw_points = [
            {
                "key": "raw-01",
                "intent_id": "raw-01",
                "action": "fill",
                "target": "search_input",
                "value": "test",
                "description": "raw point with intent_id",
                "involved_elements": ["search_input"],
                "steps": [{"action": "fill", "target": "search_input", "value": "test", "raw_text": "raw point with intent_id"}],
            }
        ]
        plan = _make_test_point_plan(raw_points)
        result, _ = normalize_test_point_plan_v1(plan)
        point = result["points"][0]
        assert point["intent_id"] == "raw-01"
        assert "search_input" in point["involved_elements"]
        steps = compile_execution_steps(result["points"], _PAGE_OBJECT)
        assert len(steps) >= 1
        for step in steps:
            assert step.get("intent_id"), f"step missing intent_id: {step}"

    def test_contract_normalization_is_idempotent(self) -> None:
        plan = _make_test_point_plan(_make_orchestrator_points())
        result1, _ = normalize_test_point_plan_v1(plan)
        plan2 = _make_test_point_plan(result1["points"])
        result2, _ = normalize_test_point_plan_v1(plan2)
        for p1, p2 in zip(result1["points"], result2["points"]):
            assert p1["intent_id"] == p2["intent_id"]
            assert p1["involved_elements"] == p2["involved_elements"]
            assert p1["key"] == p2["key"]

    def test_invalid_points_reject_after_normalization(self) -> None:
        raw_points = [
            {
                "key": f"strict-{i:02d}",
                "action": "nonexistent_action_xyz",
                "description": "bad action",
                "steps": [{"action": "nonexistent_action_xyz", "raw_text": "bad action"}],
            }
            for i in range(4)
        ]
        plan = _make_test_point_plan(raw_points)
        result, _ = normalize_test_point_plan_v1(plan)
        with pytest.raises(Exception):
            compile_execution_steps(result["points"], {"elements": {}})


class TestNormalizerToCompiler:
    """Normalized output feeds directly into compile_execution_steps."""

    def test_normalized_points_compile_without_error(self) -> None:
        plan = _make_test_point_plan(_make_orchestrator_points())
        result, _ = normalize_test_point_plan_v1(plan)
        steps = compile_execution_steps(result["points"], _PAGE_OBJECT)
        assert len(steps) >= 3

    def test_compiled_steps_have_intent_ids(self) -> None:
        plan = _make_test_point_plan(_make_orchestrator_points())
        result, _ = normalize_test_point_plan_v1(plan)
        steps = compile_execution_steps(result["points"], _PAGE_OBJECT)
        for step in steps:
            intent_id = step.get("intent_id", "")
            assert intent_id, f"step missing intent_id: {step}"
            assert "unknown" not in intent_id, f"intent_id should not be unknown: {intent_id}"

    def test_compiled_steps_have_selectors_for_known_targets(self) -> None:
        plan = _make_test_point_plan(_make_orchestrator_points())
        result, _ = normalize_test_point_plan_v1(plan)
        steps = compile_execution_steps(result["points"], _PAGE_OBJECT)
        resolved_count = 0
        for step in steps:
            trace = step.get("traceability", {})
            if trace.get("status") == "resolved":
                if step.get("action") == "login":
                    continue
                assert step.get("selector"), f"resolved step missing selector: {step}"
                resolved_count += 1
        assert resolved_count >= 2, f"expected at least 2 resolved steps, got {resolved_count}"

    def test_compiled_steps_are_resolved_only(self) -> None:
        plan = _make_test_point_plan(_make_orchestrator_points())
        result, _ = normalize_test_point_plan_v1(plan)
        steps = compile_execution_steps(result["points"], _PAGE_OBJECT)
        assert len(steps) > 0
        assert all(s.get("traceability", {}).get("status") == "resolved" for s in steps)


class TestNewChainOnlyPoints:
    """All points must provide intent_id and involved_elements explicitly."""

    def test_new_chain_normalizes_and_compiles(self) -> None:
        points = [
            {
                "key": "search-product",
                "intent_id": "search-product",
                "point_type": "action",
                "action": "fill",
                "target": "search_input",
                "value": "商品A",
                "description": "搜索商品",
                "priority": "P1",
                "dependencies": [],
                "source_ids": [],
                "steps": [{"action": "fill", "target": "search_input", "value": "商品A", "raw_text": "搜索商品"}],
                "involved_elements": ["search_input"],
            }
        ]
        plan = _make_test_point_plan(points)
        result, _ = normalize_test_point_plan_v1(plan)
        normalized_point = result["points"][0]
        assert normalized_point["intent_id"] == "search-product"
        assert "search_input" in normalized_point["involved_elements"]

        steps = compile_execution_steps(result["points"], _PAGE_OBJECT)
        assert len(steps) >= 1
        for step in steps:
            assert step.get("intent_id") == "search-product", f"intent_id must be propagated: {step}"


def _build_support():
    from pathlib import Path
    from services.requirement_testpoint_support import RequirementTestPointSupport
    return RequirementTestPointSupport(
        now=lambda: "2026-01-01T00:00:00Z",
        normalize_test_point_plan=lambda plan: (plan, []),
        build_test_point_traceability_summary=lambda *a, **kw: {},
        agent_root=Path(__file__).resolve().parents[2] / "agents",
        requirement_quality_gate_enabled=True,
        requirement_min_parse_confidence=0.3,
        requirement_min_test_intents=1,
        requirement_block_high_ambiguity=True,
        requirement_max_coverage_gap_ratio=1.0,
        blocker_catalog={},
    )


def test_build_test_points_from_requirement_spec_requires_page_object(monkeypatch) -> None:
    import services.requirement_testpoint_support as requirement_testpoint_support_module

    support = _build_support()
    monkeypatch.setattr(requirement_testpoint_support_module, "_fetch_page_element_codes", lambda *_args, **_kwargs: None)

    case = {"id": "case-001", "execution": {"page": "product"}, "requirement": "搜索商品"}
    requirement_spec = {
        "page": "product",
        "raw_requirement": "搜索商品",
        "design_input": "搜索商品",
        "test_intents": [
            {
                "intent_id": "intent-01",
                "title": "搜索商品",
                "intent_type": "functional",
                "priority": "P1",
                "expected_result": "搜索请求成功并返回商品结果。",
                "steps_hint": ["search"],
                "dependencies": [],
                "source_ids": [],
            }
        ],
    }

    with pytest.raises(ValueError, match="page object element_codes not found"):
        support.build_test_points_from_requirement_spec(case=case, requirement_spec=requirement_spec)


class TestQualityGateSourceTypeThresholds:
    """Verify that source_type-specific thresholds are correctly structured in the plan."""

    def test_openapi_spec_source_has_lower_intent_threshold(self) -> None:
        support = _build_support()
        thresholds = support._resolve_gate_thresholds("openapi_spec")
        assert thresholds["min_test_intents"] == 1
        assert thresholds["min_parse_confidence"] == 0.4

    def test_prd_text_source_has_higher_intent_threshold(self) -> None:
        support = _build_support()
        thresholds = support._resolve_gate_thresholds("prd_text")
        assert thresholds["min_test_intents"] == 3
        assert thresholds["min_parse_confidence"] == 0.6

    def test_unknown_source_falls_back_to_defaults(self) -> None:
        support = _build_support()
        thresholds = support._resolve_gate_thresholds("some_future_source")
        assert thresholds["min_test_intents"] == support._requirement_min_test_intents


class TestMapIntentToStepPOValidation:
    """map_intent_to_step validates targets against PO Store when page_elements provided."""

    def test_valid_target_preserved(self) -> None:
        from services.requirement_testpoint_support import RequirementTestPointSupport
        action, target, value = RequirementTestPointSupport.map_intent_to_step(
            page="product",
            intent_type="functional",
            title="搜索商品",
            steps_hint=["search"],
            page_elements=["search_input", "product_menu"],
        )
        assert action == "fill"
        assert target == "search_input"

    def test_invalid_target_raises(self) -> None:
        from services.requirement_testpoint_support import RequirementTestPointSupport
        with pytest.raises(ValueError, match="not found in PO Store"):
            RequirementTestPointSupport.map_intent_to_step(
                page="product",
                intent_type="functional",
                title="搜索商品",
                steps_hint=["search"],
                page_elements=["product_menu", "product_list_title"],
            )

    def test_no_page_elements_preserves_heuristic(self) -> None:
        from services.requirement_testpoint_support import RequirementTestPointSupport
        action, target, value = RequirementTestPointSupport.map_intent_to_step(
            page="product",
            intent_type="functional",
            title="搜索商品",
            steps_hint=["search"],
            page_elements=None,
        )
        assert action == "fill"
        assert target == "search_input"

    def test_empty_page_elements_preserves_heuristic(self) -> None:
        from services.requirement_testpoint_support import RequirementTestPointSupport
        action, target, value = RequirementTestPointSupport.map_intent_to_step(
            page="product",
            intent_type="functional",
            title="搜索商品",
            steps_hint=["search"],
            page_elements=[],
        )
        assert action == "fill"
        assert target == "search_input"
