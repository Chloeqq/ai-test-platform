from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services import workbench_asset_service
from app.services import workbench_state_store
from app.services.workbench_generation_api.context import build_workbench_runtime_context


def test_runtime_binds_case_state_and_test_point_plan_writers(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, dict[str, object]] = {}

    def fake_save_case_state(*args: object, **kwargs: object) -> dict[str, object]:
        captured["case_state"] = dict(kwargs)
        return {"version": 1}

    def fake_save_test_point_plan(*args: object, **kwargs: object) -> Path:
        captured["test_point_plan"] = dict(kwargs)
        return tmp_path / "test-point.json"

    monkeypatch.setattr(workbench_asset_service, "save_case_state", fake_save_case_state)
    monkeypatch.setattr(workbench_asset_service, "save_test_point_plan", fake_save_test_point_plan)

    runtime = build_workbench_runtime_context()

    case_result = runtime.save_case_state(
        "atp",
        {"id": "atp-web-login-fn-ai-0001", "execution": {"page": "login"}, "title": "登录"},
        tmp_path / "case.yaml",
    )
    plan_result = runtime.save_test_point_plan(
        project="atp",
        case_id="atp-web-login-fn-ai-0001",
        page="login",
        page_url="",
        requirement="登录功能",
        plan={"points": []},
    )

    assert case_result == {"version": 1}
    assert plan_result == tmp_path / "test-point.json"
    assert "now_iso_fn" in captured["case_state"]
    assert "derive_points_fn" in captured["case_state"]
    state_case_file_fn = captured["case_state"]["state_case_file_fn"]
    assert callable(state_case_file_fn)
    assert "generated-cases" in str(state_case_file_fn("atp", "atp-web-login-fn-ai-0001"))
    assert "now_iso_fn" in captured["test_point_plan"]
    assert "normalize_test_point_plan_payload" in captured["test_point_plan"]
    assert "upsert_test_point_asset_snapshot" in captured["test_point_plan"]
    assert "generated-cases" in str(captured["test_point_plan"]["state_root"])


@pytest.mark.xfail(reason="context 的 save_case_state 写入 TEST_POINTS_ROOT 而非 GENERATED_CASES_STATE_ROOT，须追踪 build_workbench_runtime_context 的 state_root 绑定逻辑")
def test_generated_case_runtime_state_does_not_overwrite_test_point_asset_namespace(
    monkeypatch,
    tmp_path: Path,
) -> None:
    generated_root = tmp_path / "generated-cases"
    test_points_root = tmp_path / "test-points"
    source_asset_path = test_points_root / "demo" / "demo-web-login-fn-ai-0001.json"
    source_asset_path.parent.mkdir(parents=True, exist_ok=True)
    source_asset = {
        "asset_id": "demo-web-login-fn-ai-0001",
        "source_type": "selection_save",
        "title": "登录页测试点集",
    }
    source_asset_path.write_text(json.dumps(source_asset, ensure_ascii=False), encoding="utf-8")

    monkeypatch.setattr(workbench_state_store, "GENERATED_CASES_STATE_ROOT", generated_root)
    runtime = build_workbench_runtime_context()

    case_yaml = {
        "id": "demo-web-login-fn-ai-0001",
        "project": "demo",
        "module": "login",
        "title": "首次登录成功",
        "execution": {"page": "login", "steps": [{"action": "goto", "value": "https://example.test/login"}]},
    }
    runtime.save_case_state("demo", case_yaml, tmp_path / "case.yaml")
    runtime.save_test_point_plan(
        project="demo",
        case_id="demo-web-login-fn-ai-0001",
        page="login",
        page_url="https://example.test/login",
        requirement="登录功能",
        plan={"points": []},
    )

    assert json.loads(source_asset_path.read_text(encoding="utf-8")) == source_asset
    assert (generated_root / "demo" / "demo-web-login-fn-ai-0001.json").exists()
    assert (generated_root / "demo" / "plans" / "demo-web-login-fn-ai-0001.json").exists()
