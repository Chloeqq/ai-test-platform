import json

import pytest

from app.api.workbench._helpers import (
    read_json_file as _read_json_file,
    write_json_file as _write_json_file,
)
from app.api.workbench.facade_helpers import (
    _candidate_from_asset_point,
    _point_review_status,
    _review_status_from_point,
)
from app.services import workbench_asset_service


def test_candidate_from_asset_point_prefers_current_step_values_over_stale_steps_hint() -> None:
    point = {
        "key": "intent-01",
        "intent_id": "intent-01",
        "point_type": "functional",
        "priority": "P0",
        "expected_result": "登录成功",
        "involved_elements": ["账号输入框", "密码输入框", "登录按钮"],
        "steps": [
            {
                "action": "candidate_step",
                "value": "在账号输入框输入正确账号 admin",
                "raw_text": "在账号输入框输入正确账号 admin",
            },
            {
                "action": "candidate_step",
                "value": "在密码输入框输入正确密码 macro",
                "raw_text": "在密码输入框输入正确密码 macro",
            },
            {"action": "candidate_step", "value": "点击登录按钮", "raw_text": "点击登录按钮"},
        ],
        "metadata": {
            "candidate_snapshot": {
                "intent_id": "intent-01",
                "title": "首次登录成功",
                "steps_hint": [
                    "input:账号输入框=test001",
                    "input:密码输入框=123456",
                    "click:登录按钮",
                ],
                "steps": [
                    "在账号输入框输入正确账号 test001",
                    "在密码输入框输入正确密码 123456",
                    "点击登录按钮",
                ],
                "expected": "页面跳转至平台工作台首页，顶部展示当前登录用户名 test001",
                "involved_elements": ["账号输入框", "密码输入框", "登录按钮"],
                "review_status": "approved",
            }
        },
    }

    candidate = _candidate_from_asset_point(point, fallback_title="登录页身份验证测试点集", fallback_priority="P1")

    assert candidate["steps_hint"] == [
        "input:账号输入框=admin",
        "input:密码输入框=macro",
        "click:登录按钮",
        "input:账号输入框=test001",
        "input:密码输入框=123456",
    ]
    assert candidate["steps"] == [
        "在账号输入框输入正确账号 admin",
        "在密码输入框输入正确密码 macro",
        "点击登录按钮",
    ]
    assert candidate["expected"] == "登录成功"


def test_load_test_point_asset_prefers_canonical_plan_file_over_embedded_stale_plan(tmp_path) -> None:
    state_root = tmp_path / "test-points"
    project_dir = state_root / "mall"
    plans_dir = project_dir / "plans"
    plans_dir.mkdir(parents=True)
    asset_id = "mall-web-login-auth-fn-ai-0021"
    stale_plan = {
        "version": "TestPointPlanV1",
        "project": "mall",
        "case_id": asset_id,
        "page": "login",
        "points": [
            {
                "key": "intent-01",
                "intent_id": "intent-01",
                "steps": [{"value": "在密码输入框输入正确密码 123456"}],
            }
        ],
    }
    canonical_plan = {
        "version": "TestPointPlanV1",
        "project": "mall",
        "case_id": asset_id,
        "page": "login",
        "priority": "P0",
        "source_type": "selection_save",
        "points": [
            {
                "key": "intent-01",
                "intent_id": "intent-01",
                "steps": [{"value": "在密码输入框输入正确密码 macro"}],
            }
        ],
    }
    (project_dir / f"{asset_id}.json").write_text(
        json.dumps({"asset_id": asset_id, "plan": stale_plan}, ensure_ascii=False),
        encoding="utf-8",
    )
    (plans_dir / f"{asset_id}.json").write_text(
        json.dumps(canonical_plan, ensure_ascii=False),
        encoding="utf-8",
    )

    asset = workbench_asset_service.load_test_point_asset_with_root("mall", asset_id, state_root=state_root)

    assert asset["plan"] == canonical_plan
    assert asset["priority"] == "P0"
    assert asset["source_type"] == "selection_save"
    assert asset["point_count"] == 1
    assert asset["plan"]["points"][0]["steps"][0]["value"] == "在密码输入框输入正确密码 macro"


def test_review_status_from_point_ignores_stale_candidate_snapshot() -> None:
    point = {
        "intent_id": "intent-01",
        "metadata": {
            "candidate_snapshot": {
                "review_status": "approved",
                "reviewed_at": "2026-05-19T10:00:00+08:00",
            }
        },
    }

    assert _review_status_from_point(point) == "pending"
    assert _point_review_status(point) == "pending"


def test_write_json_file_replaces_payload_without_leaving_temp_file(tmp_path) -> None:
    target = tmp_path / "asset.json"

    _write_json_file(target, {"version": 1})
    _write_json_file(target, {"version": 2, "points": [{"intent_id": "intent-01"}]})

    assert _read_json_file(target) == {"version": 2, "points": [{"intent_id": "intent-01"}]}
    assert not (tmp_path / ".asset.json.tmp").exists()
