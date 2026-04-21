"""Baseline guard tests for the new-chain-only convergence."""
from __future__ import annotations

import pytest
from shared_backend.execution_compiler import (
    ExecutionCompilerError,
    compile_execution_steps,
    normalize_test_points,
)
from shared_backend.schemas.contracts import normalize_test_point_plan_v1


_PAGE_OBJECT = {
    "elements": {
        "username_input": {"selector": "[placeholder='请输入用户名']", "type": "placeholder"},
        "password_input": {"selector": "[placeholder='请输入密码']", "type": "placeholder"},
        "login_button": {"selector": "button:text('登录')", "type": "role"},
    }
}

_NEW_CHAIN_POINTS = [
    {
        "intent_id": "intent-login-01",
        "action": "fill",
        "target": "username_input",
        "value": "admin",
        "description": "填写用户名",
        "involved_elements": ["username_input"],
        "steps": [{"action": "fill", "target": "username_input", "value": "admin", "raw_text": "填写用户名"}],
    },
    {
        "intent_id": "intent-login-02",
        "action": "fill",
        "target": "password_input",
        "value": "secret",
        "description": "填写密码",
        "involved_elements": ["password_input"],
        "steps": [{"action": "fill", "target": "password_input", "value": "secret", "raw_text": "填写密码"}],
    },
    {
        "intent_id": "intent-login-03",
        "action": "click",
        "target": "login_button",
        "description": "点击登录",
        "involved_elements": ["login_button"],
        "steps": [{"action": "click", "target": "login_button", "raw_text": "点击登录"}],
    },
]


class TestNewChainInvolvedElementsOnly:
    """involved_elements is the sole canonical field in new-chain output."""

    def test_normalize_outputs_involved_elements(self) -> None:
        normalized = normalize_test_points(_NEW_CHAIN_POINTS)
        for point in normalized:
            assert "involved_elements" in point
            assert isinstance(point["involved_elements"], list)
            assert len(point["involved_elements"]) > 0

    def test_involved_preferred_when_both_present(self) -> None:
        points = [
            {
                "intent_id": "intent-01",
                "action": "click",
                "target": "login_button",
                "involved_elements": ["login_button"],
                "steps": [{"action": "click", "target": "login_button", "raw_text": "点击登录"}],
                "dependent_elements": ["username_input"],
            }
        ]
        normalized = normalize_test_points(points)
        assert normalized[0]["involved_elements"] == ["login_button"]

    def test_legacy_dependent_elements_no_longer_used(self) -> None:
        """dependent_elements is ignored; only involved_elements is read."""
        points = [
            {
                "intent_id": "intent-compat",
                "action": "click",
                "steps": [{"action": "click", "target": "login_button", "raw_text": "点击登录"}],
                "dependent_elements": ["login_button"],
            }
        ]
        normalized = normalize_test_points(points)
        assert normalized[0]["involved_elements"] == []


class TestNewChainIntentIdPrimary:
    """intent_id is the sole primary key in new-chain output."""

    def test_intent_id_is_primary(self) -> None:
        normalized = normalize_test_points(_NEW_CHAIN_POINTS)
        for point in normalized:
            assert point["intent_id"].startswith("intent-login-")

    def test_missing_intent_id_not_filled_from_key(self) -> None:
        """key no longer fills intent_id; missing intent_id must fail."""
        points = [{"key": "legacy-key-01", "action": "click", "target": "login_button"}]
        with pytest.raises(ExecutionCompilerError):
            normalize_test_points(points)


class TestPreconditionPointContract:
    """Precondition points must include intent_id, steps, and involved_elements."""

    def test_precondition_point_has_required_fields(self) -> None:
        precondition = {
            "key": "product-00",
            "intent_id": "product-00",
            "point_type": "precondition",
            "action": "login",
            "description": "Use shared login precondition.",
            "priority": "P0",
            "dependencies": [],
            "source_ids": [],
            "steps": [{"action": "login", "raw_text": "Use shared login precondition."}],
            "involved_elements": [],
        }
        assert precondition["intent_id"] == precondition["key"]
        assert isinstance(precondition["steps"], list)
        assert len(precondition["steps"]) > 0
        assert "involved_elements" in precondition

    def test_precondition_normalizes_through_plan(self) -> None:
        precondition = {
            "key": "login-00",
            "intent_id": "login-00",
            "point_type": "precondition",
            "action": "login",
            "description": "Use shared login precondition.",
            "steps": [{"action": "login", "raw_text": "Use shared login precondition."}],
            "involved_elements": [],
        }
        plan = {
            "version": "TestPointPlanV1",
            "project": "default",
            "case_id": "precondition-001",
            "page": "login",
            "points": [precondition],
        }
        result, _ = normalize_test_point_plan_v1(plan)
        point = result["points"][0]
        assert point["intent_id"] == "login-00"
        assert isinstance(point["steps"], list)
        assert len(point["steps"]) > 0
        assert "involved_elements" in point

    def test_precondition_compiles_without_error(self) -> None:
        precondition = {
            "intent_id": "login-00",
            "action": "login",
            "description": "Use shared login precondition.",
            "steps": [{"action": "login", "raw_text": "Use shared login precondition."}],
            "involved_elements": [],
        }
        steps = compile_execution_steps([precondition], _PAGE_OBJECT)
        assert len(steps) >= 1
        for step in steps:
            assert step.get("intent_id"), f"step must have intent_id: {step}"


class TestNormalizerContractOutput:
    """normalize_test_point_plan_v1 must produce involved_elements for new-chain points."""

    def test_new_chain_plan_has_involved_elements(self) -> None:
        plan = {
            "version": "TestPointPlanV1",
            "project": "default",
            "case_id": "baseline-001",
            "page": "login",
            "points": _NEW_CHAIN_POINTS,
        }
        result, warnings = normalize_test_point_plan_v1(plan)
        for point in result["points"]:
            assert "involved_elements" in point
            assert len(point["involved_elements"]) > 0
            assert point.get("intent_id"), "intent_id must be present"


class TestCompilerBaselineSnapshot:
    """Compiler output shape is stable for known inputs."""

    def test_compiled_steps_count(self) -> None:
        steps = compile_execution_steps(_NEW_CHAIN_POINTS, _PAGE_OBJECT)
        assert len(steps) >= 3

    def test_compiled_steps_have_selectors(self) -> None:
        steps = compile_execution_steps(_NEW_CHAIN_POINTS, _PAGE_OBJECT)
        resolved = [s for s in steps if s.get("traceability", {}).get("status") == "resolved"]
        assert len(resolved) >= 2
        for step in resolved:
            assert step.get("selector"), f"resolved step must have selector: {step}"

    def test_compiled_steps_have_intent_ids(self) -> None:
        steps = compile_execution_steps(_NEW_CHAIN_POINTS, _PAGE_OBJECT)
        for step in steps:
            assert step.get("intent_id"), f"step must have intent_id: {step}"
            assert "unknown" not in step["intent_id"]

    def test_all_known_elements_resolve(self) -> None:
        steps = compile_execution_steps(_NEW_CHAIN_POINTS, _PAGE_OBJECT)
        total = len(steps)
        assert total > 0
        assert all(s.get("traceability", {}).get("status") == "resolved" for s in steps)
