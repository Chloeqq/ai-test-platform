from __future__ import annotations

from pathlib import Path

from app.services import workbench_asset_service
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
    assert "now_iso_fn" in captured["test_point_plan"]
    assert "normalize_test_point_plan_payload" in captured["test_point_plan"]
    assert "upsert_test_point_asset_snapshot" in captured["test_point_plan"]
