"""测试 Phase 4.1 Generate Gate + Phase 4.2 Review Gate。"""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.services.workbench_asset_views import (
    get_quality_gate_violations,
    check_generate_gate,
    check_approve_point_gate,
    check_execute_gate,
)


def _make_asset(*, plan_points: list[dict] | None = None) -> dict:
    return {"plan": {"points": plan_points or []}, "warnings": []}


def _make_point(intent_id: str, point_type: str = "functional", *, warnings: list[str] | None = None, steps: list[dict] | None = None) -> dict:
    return {
        "intent_id": intent_id,
        "point_type": point_type,
        "warnings": warnings or [],
        "steps": steps or [],
    }


def _step(action: str) -> dict:
    return {"action": action}


# ── zero_assertion → block ──

def test_zero_assertion_blocked() -> None:
    """有零断言 point（无 candidate_step）→ block violation。"""
    asset = _make_asset(plan_points=[
        _make_point("intent-01", steps=[_step("input"), _step("click")], warnings=[
            "assertion_missing: 无可执行断言",
        ]),
    ])
    violations = get_quality_gate_violations(asset)
    blocks = [v for v in violations if v["severity"] == "block"]
    assert len(blocks) == 1
    assert blocks[0]["code"] == "zero_assertion"
    assert "intent-01" in blocks[0]["intent_ids"]

    with pytest.raises(HTTPException) as exc:
        check_generate_gate(asset)
    assert exc.value.status_code == 422
    assert "quality_gate_blocked" in str(exc.value.detail)


# ── unprocessed → block ──

def test_unprocessed_blocked() -> None:
    """candidate_step + 零断言 → unprocessed block violation。"""
    asset = _make_asset(plan_points=[
        _make_point("intent-25", steps=[_step("candidate_step")], warnings=[
            "assertion_missing: 无可执行断言",
        ]),
    ])
    violations = get_quality_gate_violations(asset)
    blocks = [v for v in violations if v["severity"] == "block"]
    assert any(v["code"] == "unprocessed" for v in blocks)
    assert "intent-25" in [v for v in violations if v["code"] == "unprocessed"][0]["intent_ids"]

    with pytest.raises(HTTPException):
        check_generate_gate(asset)


# ── PASS → success ──

def test_pass_no_violations() -> None:
    """全断言 + 无 candidate_step → 无 block violation。"""
    asset = _make_asset(plan_points=[
        _make_point("intent-01", steps=[_step("input"), _step("assert_visible")]),
        _make_point("intent-02", steps=[_step("input"), _step("assert_text")]),
    ])
    violations = get_quality_gate_violations(asset)
    blocks = [v for v in violations if v["severity"] == "block"]
    assert len(blocks) == 0
    # 不应抛异常
    check_generate_gate(asset)


# ── data_warning → allowed (不影响 generate) ──

def test_data_warning_allowed() -> None:
    """仅有 data_warning 的 point → 不产生 block violation。"""
    asset = _make_asset(plan_points=[
        _make_point("intent-01", steps=[_step("input"), _step("assert_text")], warnings=[
            "用户名输入框 的空格输入需要后续由 DSL 数据引用执行",
            "用户名输入框 输入步骤缺少明确测试数据",
        ]),
    ])
    violations = get_quality_gate_violations(asset)
    blocks = [v for v in violations if v["severity"] == "block"]
    assert len(blocks) == 0
    # quality_warning 可能有，但只是 review 级 → generate 不阻断
    check_generate_gate(asset)


# ── multi-point: violation intent_ids 正确 ──

def test_violation_intent_ids() -> None:
    """多个 point 的 violation 应正确列出涉及的 intent_ids。"""
    asset = _make_asset(plan_points=[
        _make_point("intent-01", steps=[_step("input"), _step("click")], warnings=["assertion_missing"]),
        _make_point("intent-02", steps=[_step("input"), _step("assert_visible")]),
        _make_point("intent-03", steps=[_step("input"), _step("click")], warnings=["assertion_missing"]),
    ])
    violations = get_quality_gate_violations(asset)
    zero_v = next(v for v in violations if v["code"] == "zero_assertion")
    assert sorted(zero_v["intent_ids"]) == ["intent-01", "intent-03"]


# ── candidate_step + 有断言 → review 级（不阻断 generate）──

def test_candidate_step_with_assertion_review_only() -> None:
    """candidate_step 但有断言 → review 级，不阻断 generate。"""
    asset = _make_asset(plan_points=[
        _make_point("intent-02", steps=[_step("candidate_step"), _step("assert_visible")], warnings=[
            "步骤仍需人工结构化",
        ]),
    ])
    violations = get_quality_gate_violations(asset)
    blocks = [v for v in violations if v["severity"] == "block"]
    assert len(blocks) == 0
    assert any(v["code"] == "candidate_step" and v["severity"] == "review" for v in violations)
    check_generate_gate(asset)


# ── 空 asset ──

def test_empty_asset_no_crash() -> None:
    """空 asset 不应崩溃。"""
    asset = _make_asset(plan_points=[])
    violations = get_quality_gate_violations(asset)
    assert len(violations) == 0
    check_generate_gate(asset)


# ════════════════════════════════════════════════════════════════
# Phase 4.2: check_approve_point_gate
# ════════════════════════════════════════════════════════════════


def test_approve_assertion_missing_blocked() -> None:
    """assertion_missing warning → approve blocked。"""
    point = _make_point("intent-01", steps=[_step("input"), _step("click")], warnings=[
        "assertion_missing: 无可执行断言",
    ])
    with pytest.raises(HTTPException) as exc:
        check_approve_point_gate(point)
    assert exc.value.status_code == 422
    assert "gate_reject_blocked" in str(exc.value.detail)


def test_approve_zero_assertion_blocked() -> None:
    """无 assertion + 无 warning → approve blocked（零断言检测）。"""
    point = _make_point("intent-01", steps=[_step("input"), _step("click")])
    with pytest.raises(HTTPException) as exc:
        check_approve_point_gate(point)
    assert exc.value.status_code == 422


def test_approve_candidate_step_no_assertion_blocked() -> None:
    """candidate_step + 无断言 → approve blocked。"""
    point = _make_point("intent-01", steps=[_step("candidate_step")])
    with pytest.raises(HTTPException) as exc:
        check_approve_point_gate(point)
    assert exc.value.status_code == 422


def test_approve_pass_success() -> None:
    """有断言的正常 point → approve 成功。"""
    point = _make_point("intent-01", steps=[_step("input"), _step("assert_visible")])
    check_approve_point_gate(point)


def test_approve_candidate_step_with_assertion_allowed() -> None:
    """candidate_step + 有断言 → approve 允许。"""
    point = _make_point("intent-01", steps=[_step("candidate_step"), _step("assert_visible")], warnings=[
        "步骤仍需人工结构化",
    ])
    check_approve_point_gate(point)


def test_approve_data_warning_allowed() -> None:
    """仅有 data_warning → approve 允许。"""
    point = _make_point("intent-01", steps=[_step("input"), _step("assert_text")], warnings=[
        "用户名输入框 的空格输入需要后续由 DSL 数据引用执行",
        "用户名输入框 输入步骤缺少明确测试数据",
    ])
    check_approve_point_gate(point)


# ════════════════════════════════════════════════════════════════
# Phase 4.3: check_execute_gate
# ════════════════════════════════════════════════════════════════


def test_execute_reject_blocked() -> None:
    """source_asset + REJECT → execute blocked。"""
    asset = _make_asset(plan_points=[
        _make_point("intent-01", steps=[_step("input"), _step("click")], warnings=[
            "assertion_missing: 无可执行断言",
        ]),
    ])
    with pytest.raises(HTTPException) as exc:
        check_execute_gate(asset)
    assert exc.value.status_code == 422
    assert "quality_gate_blocked" in str(exc.value.detail)


def test_execute_pass_success() -> None:
    """source_asset + PASS → execute allowed。"""
    asset = _make_asset(plan_points=[
        _make_point("intent-01", steps=[_step("input"), _step("assert_visible")]),
    ])
    check_execute_gate(asset)


def test_execute_unprocessed_blocked() -> None:
    """unprocessed (candidate_step + 无断言) → execute blocked。"""
    asset = _make_asset(plan_points=[
        _make_point("intent-25", steps=[_step("candidate_step")]),
    ])
    with pytest.raises(HTTPException):
        check_execute_gate(asset)


def test_execute_data_warning_allowed() -> None:
    """data_warning → execute 不阻断。"""
    asset = _make_asset(plan_points=[
        _make_point("intent-01", steps=[_step("input"), _step("assert_text")], warnings=[
            "用户名输入框 的空格输入需要后续由 DSL 数据引用执行",
        ]),
    ])
    check_execute_gate(asset)
