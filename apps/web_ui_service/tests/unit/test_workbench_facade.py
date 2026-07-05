"""WorkbenchFacade 特征测试——锁定现有行为，保护重构。

测试策略：
- 薄代理方法：验证正确委托给 WorkbenchService
- 有 inline 逻辑的方法：mock 底层依赖，验证返回结构的 shape
- 不关心返回值具体数值，只关心结构、类型和关键 key 存在性
"""
from __future__ import annotations

from datetime import datetime, timezone
from shared_backend.datetime_compat import UTC
from typing import Any
from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session

from app.api.workbench.facade import (
    WorkbenchFacade,
    build_workbench_facade,
    _normalize_optional_project_code,
    _to_utc,
    _utc_now,
    _text,
    _safe_rollback_or_invalidate,
    _normalize_test_point_review_status,
    _validate_test_point_review_status,
    _is_virtual_test_point_element,
    _candidate_snapshot_from_point,
    _review_status_from_point,
    _review_status_from_candidate,
    _review_summary_from_points,
)
from app.api.workbench.service import WorkbenchService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_service() -> MagicMock:
    return MagicMock(spec=WorkbenchService)


@pytest.fixture
def facade(mock_service: MagicMock) -> WorkbenchFacade:
    return WorkbenchFacade(service=mock_service)


@pytest.fixture
def mock_db() -> MagicMock:
    return MagicMock(spec=Session)


def _empty_scalars() -> MagicMock:
    """Simulate db.execute(select(...)).scalars().all() returning empty list."""
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    return result


# ---------------------------------------------------------------------------
# 薄代理方法——验证委托
# ---------------------------------------------------------------------------

class TestThinDelegators:
    """验证薄代理方法正确委托给 WorkbenchService。"""

    def test_list_projects(self, facade: WorkbenchFacade, mock_service: MagicMock, mock_db: MagicMock) -> None:
        mock_service.list_projects.return_value = {"projects": {}}
        result = facade.list_projects(mock_db)
        mock_service.list_projects.assert_called_once_with(mock_db)
        assert isinstance(result, dict)

    def test_list_execution_tasks(self, facade: WorkbenchFacade, mock_service: MagicMock) -> None:
        mock_service.list_execution_tasks.return_value = {"tasks": []}
        result = facade.list_execution_tasks(project="atp")
        mock_service.list_execution_tasks.assert_called_once_with(project="atp")
        assert isinstance(result, dict)

    def test_get_execution_task(self, facade: WorkbenchFacade, mock_service: MagicMock, mock_db: MagicMock) -> None:
        mock_service.get_execution_task.return_value = {"task_id": "t1"}
        result = facade.get_execution_task("t1", mock_db)
        mock_service.get_execution_task.assert_called_once_with("t1", mock_db)
        assert result == {"task_id": "t1"}

    def test_get_execution_gate_config(self, facade: WorkbenchFacade, mock_service: MagicMock) -> None:
        mock_service.get_execution_gate_config.return_value = {"rules": []}
        result = facade.get_execution_gate_config()
        assert isinstance(result, dict)

    def test_heal_run(self, facade: WorkbenchFacade, mock_service: MagicMock) -> None:
        mock_service.heal_run.return_value = {"status": "healed"}
        result = facade.heal_run("run-1")
        mock_service.heal_run.assert_called_once_with("run-1")

    def test_heal_and_rerun_case(self, facade: WorkbenchFacade, mock_service: MagicMock) -> None:
        mock_service.heal_and_rerun_case.return_value = {"status": "rerun"}
        result = facade.heal_and_rerun_case("run-1", 30)
        mock_service.heal_and_rerun_case.assert_called_once_with("run-1", 30)

    def test_save_execution_gate_decision(self, facade: WorkbenchFacade, mock_service: MagicMock, mock_db: MagicMock) -> None:
        mock_service.save_execution_gate_decision.return_value = {"ok": True}
        result = facade.save_execution_gate_decision(MagicMock(), MagicMock(), mock_db)
        assert result == {"ok": True}

    def test_approve_execution_gate_decision(self, facade: WorkbenchFacade, mock_service: MagicMock, mock_db: MagicMock) -> None:
        mock_service.approve_execution_gate_decision.return_value = {"ok": True}
        result = facade.approve_execution_gate_decision(MagicMock(), MagicMock(), mock_db)
        assert result == {"ok": True}

    def test_revoke_execution_gate_decision(self, facade: WorkbenchFacade, mock_service: MagicMock, mock_db: MagicMock) -> None:
        mock_service.revoke_execution_gate_decision.return_value = {"ok": True}
        result = facade.revoke_execution_gate_decision(MagicMock(), MagicMock(), mock_db)
        assert result == {"ok": True}

    def test_report_allure_refresh(self, facade: WorkbenchFacade, mock_service: MagicMock) -> None:
        mock_service.report_allure_refresh.return_value = {"refreshed": True}
        result = facade.report_allure_refresh(MagicMock())
        assert result == {"refreshed": True}

    def test_save_review_no_db(self, facade: WorkbenchFacade, mock_service: MagicMock) -> None:
        mock_service.save_review.return_value = {"review_id": "r1"}
        payload = MagicMock()
        payload.case_id = ""
        result = facade.save_review(payload, MagicMock(), db=None)
        mock_service.save_review.assert_called_once()


# ---------------------------------------------------------------------------
# get_case_dictionaries——静态字典
# ---------------------------------------------------------------------------

class TestCaseDictionaries:
    def test_returns_expected_keys(self, facade: WorkbenchFacade) -> None:
        result = facade.get_case_dictionaries()
        items = result["items"]
        expected = {
            "project", "client", "page", "module", "case_type",
            "source", "case_status", "run_status", "ai_status", "migration_status",
        }
        assert set(items.keys()) == expected


# ---------------------------------------------------------------------------
# dashboard_overview——最复杂方法（~200行）
# ---------------------------------------------------------------------------

class TestDashboardOverview:
    """dashboard_overview 在空数据库场景下走正常路径（不会进 except 降级）。"""

    def _setup_mocks(self, monkeypatch: pytest.MonkeyPatch, mock_db: MagicMock) -> None:
        monkeypatch.setattr(
            "app.api.workbench.facade.test_case_service.ensure_seed_data",
            lambda db: None,
        )
        mock_db.execute.side_effect = lambda stmt: _empty_scalars()

    def test_returns_as_of_and_risk(
        self, facade: WorkbenchFacade, mock_db: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._setup_mocks(monkeypatch, mock_db)
        result = facade.dashboard_overview(mock_db)
        assert isinstance(result, dict)
        assert "as_of" in result
        assert "risk" in result
        assert isinstance(result["risk"], dict)

    def test_returns_summary_with_pass_rate(
        self, facade: WorkbenchFacade, mock_db: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._setup_mocks(monkeypatch, mock_db)
        result = facade.dashboard_overview(mock_db)
        assert "summary" in result
        assert "pass_rate_24h" in result["summary"]

    def test_trend_24h_is_list_of_24(
        self, facade: WorkbenchFacade, mock_db: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._setup_mocks(monkeypatch, mock_db)
        result = facade.dashboard_overview(mock_db)
        assert "trend_24h" in result
        trend = result["trend_24h"]
        assert isinstance(trend, list)
        assert len(trend) == 24

    def test_top_flaky_is_list(
        self, facade: WorkbenchFacade, mock_db: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._setup_mocks(monkeypatch, mock_db)
        result = facade.dashboard_overview(mock_db)
        assert "top_flaky" in result
        assert isinstance(result["top_flaky"], list)

    def test_gate_last10_is_list_of_10(
        self, facade: WorkbenchFacade, mock_db: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._setup_mocks(monkeypatch, mock_db)
        result = facade.dashboard_overview(mock_db)
        assert "gate_last10" in result
        gate = result["gate_last10"]
        assert isinstance(gate, list)
        assert len(gate) == 10

    def test_pending_issues_is_list(
        self, facade: WorkbenchFacade, mock_db: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._setup_mocks(monkeypatch, mock_db)
        result = facade.dashboard_overview(mock_db)
        assert "pending_issues" in result
        assert isinstance(result["pending_issues"], list)

    def test_risk_has_score_and_level(
        self, facade: WorkbenchFacade, mock_db: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._setup_mocks(monkeypatch, mock_db)
        result = facade.dashboard_overview(mock_db)
        risk = result["risk"]
        assert "score" in risk
        assert "level" in risk
        assert isinstance(risk["score"], int)
        assert isinstance(risk["level"], str)


# ---------------------------------------------------------------------------
# dashboard_governance——128行
# ---------------------------------------------------------------------------

class TestDashboardGovernance:
    def test_returns_governance_key(
        self, facade: WorkbenchFacade, mock_db: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "app.api.workbench.facade.store.read_history_items",
            lambda: [],
        )
        monkeypatch.setattr(
            "app.api.workbench.facade.test_case_service.ensure_seed_data",
            lambda db: None,
        )
        monkeypatch.setattr(
            "app.api.workbench.facade.workbench_governance_service.build_governance_overview",
            lambda **kwargs: {"governance": {"risk_level": "低", "degraded_sources": [], "trend": []}},
        )

        def _mock_execute(stmt: Any) -> MagicMock:
            m = MagicMock()
            m.scalars.return_value.all.return_value = []
            return m

        mock_db.execute.side_effect = _mock_execute

        result = facade.dashboard_governance(mock_db)
        assert isinstance(result, dict)
        assert "governance" in result


# ---------------------------------------------------------------------------
# list_test_point_assets
# ---------------------------------------------------------------------------

class TestListTestPointAssets:
    def test_returns_items_and_total(
        self, facade: WorkbenchFacade, mock_db: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "app.api.workbench.facade_helpers.store.ensure_dirs",
            lambda: None,
        )
        monkeypatch.setattr(
            "app.api.workbench.facade.workbench_asset_service.build_test_point_asset_items",
            lambda **kwargs: {
                "items": [], "total": 0, "selection_summary": {"filter_snapshot": {}},
                "source_filter": {}, "review_filter": {}, "gate_filter": {},
            },
        )
        monkeypatch.setattr(
            "app.api.workbench.facade.workbench_asset_service.build_test_point_asset_coverage_summary",
            lambda **kwargs: {},
        )

        result = facade.list_test_point_assets(
            project="atp", page="login", keyword="", source_type="",
            coverage_status="", review_status="", gate_decision="",
            selection_state="", db=mock_db,
        )
        assert isinstance(result, dict)
        assert "items" in result
        assert "total" in result


# ---------------------------------------------------------------------------
# upsert_test_point_asset
# ---------------------------------------------------------------------------

class TestUpsertTestPointAsset:
    def test_returns_asset_id(
        self, facade: WorkbenchFacade, mock_db: MagicMock, monkeypatch: pytest.MonkeyPatch, tmp_path: Any
    ) -> None:
        monkeypatch.setattr(
            "app.api.workbench.facade_helpers.store.ensure_dirs",
            lambda: None,
        )
        monkeypatch.setattr(
            "app.api.workbench.facade_test_point_assets.test_project_service.ensure_project_active_for_write",
            lambda db, project: MagicMock(project_code=project),
        )
        monkeypatch.setattr(
            "app.api.workbench.facade_helpers._test_point_asset_state_paths",
            lambda project, asset_id: (tmp_path / "asset.json", tmp_path / "plan.json"),
        )
        monkeypatch.setattr(
            "app.api.workbench._helpers.read_json_file",
            lambda path: {},
        )
        monkeypatch.setattr(
            "app.api.workbench.facade_helpers._page_object_generation_context",
            lambda db, project, page: {"page": page, "elements": {}, "page_url": ""},
        )
        monkeypatch.setattr(
            "app.api.workbench.facade_helpers._normalize_points_involved_elements",
            lambda points, page_context: points,
        )
        monkeypatch.setattr(
            "app.api.workbench._helpers.write_json_file",
            lambda path, payload: None,
        )
        monkeypatch.setattr(
            "app.api.workbench.facade_helpers.workbench_asset_service.upsert_test_point_asset_snapshot",
            lambda **kwargs: {"asset_id": "asset-001"},
        )
        monkeypatch.setattr(
            "app.api.workbench.facade_helpers.workbench_asset_service.build_test_point_asset_detail",
            lambda **kwargs: {"item": {"asset_id": "asset-001", "title": "测试"}},
        )
        monkeypatch.setattr(
            "app.api.workbench.facade_helpers._build_generation_diagnostics_for_asset",
            lambda project, asset: {},
        )
        monkeypatch.setattr(
            "app.api.workbench.facade_helpers.store.read_history_items",
            lambda: [],
        )
        monkeypatch.setattr(
            "app.api.workbench.facade_helpers.store.append_history",
            lambda item, db=None: None,
        )
        monkeypatch.setattr(
            "app.api.workbench.facade_helpers.store.now_iso",
            lambda: "2026-01-01T00:00:00Z",
        )
        monkeypatch.setattr(
            "app.api.workbench.facade_helpers.workbench_gate_service.normalize_page_slug",
            lambda value: str(value or "").strip().lower(),
        )

        payload = MagicMock()
        payload.project = "atp"
        payload.page = "login"
        payload.source_type = "manual"
        payload.asset_id = "asset-001"
        payload.title = "テスト"
        payload.priority = ""
        payload.requirement = ""
        payload.selected_candidates = []
        payload.points = []

        result = facade.upsert_test_point_asset(payload=payload, db=mock_db)
        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# get_test_point_asset
# ---------------------------------------------------------------------------

class TestGetTestPointAsset:
    def test_returns_asset_dict(
        self, facade: WorkbenchFacade, mock_db: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "app.api.workbench.facade_helpers.store.ensure_dirs",
            lambda: None,
        )
        monkeypatch.setattr(
            "app.api.workbench.facade_helpers.store.read_history_items",
            lambda: [],
        )
        monkeypatch.setattr(
            "app.api.workbench.facade_helpers.workbench_asset_service.build_test_point_asset_detail",
            lambda **kwargs: {
                "item": {
                    "asset_id": "asset-001", "title": "test",
                    "project": "atp", "page": "login",
                    "source_type": "manual", "plan": {"points": []},
                }
            },
        )
        monkeypatch.setattr(
            "app.api.workbench.facade_helpers._build_generation_diagnostics_for_asset",
            lambda project, asset: {},
        )

        result = facade.get_test_point_asset(asset_id="asset-001", project="atp", db=mock_db)
        assert isinstance(result, dict)
        assert "item" in result


# ---------------------------------------------------------------------------
# delete_test_point_asset
# ---------------------------------------------------------------------------

class TestDeleteTestPointAsset:
    def test_returns_result(
        self, facade: WorkbenchFacade, mock_db: MagicMock, monkeypatch: pytest.MonkeyPatch, tmp_path: Any
    ) -> None:
        monkeypatch.setattr(
            "app.api.workbench.facade_helpers.store.ensure_dirs",
            lambda: None,
        )
        monkeypatch.setattr(
            "app.api.workbench.facade_test_point_assets.test_project_service.ensure_project_active_for_write",
            lambda db, project: MagicMock(project_code=project),
        )
        project_dir = tmp_path / "atp"
        project_dir.mkdir()
        (project_dir / "asset-001.json").write_text("{}")
        monkeypatch.setattr(
            "app.api.workbench.facade_helpers.workbench_asset_service.state_project_dir",
            lambda project, state_root: project_dir,
        )
        monkeypatch.setattr(
            "app.api.workbench.facade_helpers.store.append_history",
            lambda item, db=None: None,
        )
        monkeypatch.setattr(
            "app.api.workbench.facade_helpers.store.now_iso",
            lambda: "2026-01-01T00:00:00Z",
        )

        result = facade.delete_test_point_asset(asset_id="asset-001", project="atp", db=mock_db)
        assert isinstance(result, dict)
        assert "item" in result


# ---------------------------------------------------------------------------
# preview_test_point_script
# ---------------------------------------------------------------------------

class TestPreviewTestPointScript:
    def test_returns_script_preview(
        self, facade: WorkbenchFacade, mock_db: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def _mock_load(project: str, asset_id: str, **kwargs: Any) -> dict[str, Any]:
            return {
                "asset_id": asset_id, "title": "test",
                "page": "login", "source_type": "manual",
                "review_status": "approved",
                "plan": {"points": [{"intent_id": "I001", "title": "登录成功",
                                       "steps": ["输入账号"], "expected_result": "成功",
                                       "review_status": "approved"}]},
            }

        monkeypatch.setattr(
            "app.api.workbench.facade_helpers.workbench_asset_service.load_test_point_asset_with_root",
            _mock_load,
        )
        monkeypatch.setattr(
            "app.api.workbench.facade_test_point_assets._page_object_generation_context",
            lambda db, project, page: {
                "page_object_found": True, "page_url": "",
                "page_object": {"page": "login", "page_url": "", "elements": {
                    "btn": {"selector": "#btn", "type": "css",
                        "status": "active", "review_status": "approved", "stability_level": "high"},
                }},
                "base_blockers": [],
            },
        )

        result = facade.preview_test_point_script(
            asset_id="asset-001", project="atp", intent_id="I001", db=mock_db
        )
        assert isinstance(result, dict)
        assert "item" in result


# ---------------------------------------------------------------------------
# build_workbench_facade
# ---------------------------------------------------------------------------

class TestBuildWorkbenchFacade:
    def test_returns_workbench_facade(self) -> None:
        assert isinstance(build_workbench_facade(), WorkbenchFacade)

    def test_accepts_optional_service(self) -> None:
        svc = MagicMock(spec=WorkbenchService)
        assert isinstance(build_workbench_facade(service=svc), WorkbenchFacade)


# ---------------------------------------------------------------------------
# 纯工具函数——无副作用，可精确断言
# ---------------------------------------------------------------------------

class TestUtilityFunctions:
    def test_normalize_optional_project_code(self) -> None:
        assert _normalize_optional_project_code(None) == ""
        assert _normalize_optional_project_code("ATP") == "atp"
        assert _normalize_optional_project_code(123) == "123"

    def test_to_utc_adds_utc_tzinfo(self) -> None:
        result = _to_utc(datetime(2026, 1, 1, 12, 0, 0))
        assert result.tzinfo == UTC

    def test_to_utc_returns_current_utc_for_falsy(self) -> None:
        result = _to_utc(None)
        assert result.tzinfo == UTC

    def test_to_utc_preserves_aware_datetime(self) -> None:
        aware = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        assert _to_utc(aware).tzinfo == UTC

    def test_utc_now_returns_utc(self) -> None:
        assert _utc_now().tzinfo == UTC

    def test_text_converts_all_to_string(self) -> None:
        assert _text("hello") == "hello"
        assert _text(123) == "123"
        assert _text(None) == ""
        assert _text("") == ""

    def test_safe_rollback_does_not_raise(self, mock_db: MagicMock) -> None:
        _safe_rollback_or_invalidate(mock_db)

    def test_safe_rollback_handles_error(self, mock_db: MagicMock) -> None:
        mock_db.rollback.side_effect = RuntimeError("db error")
        _safe_rollback_or_invalidate(mock_db)

    def test_normalize_test_point_review_status(self) -> None:
        assert isinstance(_normalize_test_point_review_status("pending"), str)

    def test_validate_test_point_review_status(self) -> None:
        assert isinstance(_validate_test_point_review_status("approved"), str)

    def test_is_virtual_test_point_element(self) -> None:
        assert _is_virtual_test_point_element(None) is False

    def test_candidate_snapshot_from_point(self) -> None:
        point = {"intent_id": "I001", "title": "登录", "priority": "P0",
                  "steps": ["输入账号"], "expected_result": "登录成功"}
        assert isinstance(_candidate_snapshot_from_point(point), dict)

    def test_review_status_from_point(self) -> None:
        assert isinstance(_review_status_from_point({}), str)

    def test_review_status_from_candidate(self) -> None:
        assert isinstance(_review_status_from_candidate({}), str)

    def test_review_summary_from_points(self) -> None:
        points = [{"review_status": "approved"}, {"review_status": "pending"}]
        assert isinstance(_review_summary_from_points(points), dict)
