"""Workbench API 门面层。

该模块负责将路由层请求编排到各个 service，并补齐跨模块流程中的
聚合逻辑、降级逻辑和部分运行态数据拼装。
"""
from __future__ import annotations

import logging
from typing import Any

from app.api.workbench import constants, store
from app.services import (
    workbench_asset_service,
    workbench_case_consistency_service,
)
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from shared_backend import get_dictionary_items

from ._helpers import (
    is_within as _is_within,
)
from .service import (
    WorkbenchService,
    _append_history,
    _append_runtime_run,
    _build_execution_task_summary,
    _build_execution_task_view,
    _collect_execution_records_with_meta,
    _collect_failure_entries,
    _collect_failure_entries_with_meta,
    _ensure_dirs,
    _execution_record_time_value,
    _load_runtime_execution_record_from_artifacts,
    _normalize_execution_record_payload,
    _normalize_failure_entry_view,
    _read_json_list,
    _runtime_run_id,
    _runtime_view_from_entry,
    _runtime_view_with_execution_record_preferred,
    _safe_case_id,
    _sync_stage_a_workbench_state,
    _sync_stage_b_workbench_gate,
    _update_runtime_run,
    _write_json_list,
)

LOGGER = logging.getLogger(__name__)

# ---- 以下 helper 函数已移至 facade_helpers.py ----
from .facade_helpers import (  # noqa: E402
    _settings,
)
from .facade_reporting import WorkbenchFacadeReportingMixin  # noqa: E402

# 以下方法体已移至 facade_test_point_assets.py 和 facade_reporting.py 的混入类
from .facade_test_point_assets import WorkbenchFacadeTestPointAssetsMixin  # noqa: E402


class WorkbenchFacade(WorkbenchFacadeTestPointAssetsMixin, WorkbenchFacadeReportingMixin):
    """Workbench 门面层：对外提供聚合后的业务接口。"""

    def __init__(self, service: WorkbenchService | None = None) -> None:
        """允许注入 service，便于测试替身和分层调用。"""
        self._service = service or WorkbenchService()

    def list_projects(self, db: Any) -> dict[str, Any]:
        """列出项目字典与可用项目视图。"""
        return self._service.list_projects(db)

    def list_execution_tasks(self, **kwargs: Any) -> dict[str, Any]:
        """查询执行任务列表（支持筛选参数透传）。"""
        return self._service.list_execution_tasks(**kwargs)

    def get_execution_task(self, task_id: str, db: Any) -> dict[str, Any]:
        """查询单个执行任务详情。"""
        return self._service.get_execution_task(task_id, db)

    def get_execution_gate_config(self) -> dict[str, Any]:
        """WorkbenchFacade.get_execution_gate_config 接口实现。"""
        return self._service.get_execution_gate_config()

    def heal_run(self, run_id: str) -> dict[str, Any]:
        """WorkbenchFacade.heal_run 接口实现。"""
        return self._service.heal_run(run_id)

    def heal_and_rerun_case(self, run_id: str, wait_seconds: int) -> dict[str, Any]:
        """WorkbenchFacade.heal_and_rerun_case 接口实现。"""
        return self._service.heal_and_rerun_case(run_id, wait_seconds)

    def save_review(self, payload: Any, request: Any, db: Session | None = None) -> dict[str, Any]:
        """保存评审记录；若传入 db 则附带 case center 一致性校验。"""
        if db is not None and str(getattr(payload, "case_id", "") or "").strip():
            case_center_case_ids = workbench_case_consistency_service.load_case_center_case_ids(db)
            if not workbench_case_consistency_service.is_case_tracked(
                getattr(payload, "case_id", ""),
                case_center_case_ids=case_center_case_ids,
            ):
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="case_id not found in case center")
        return self._service.save_review(payload, request)

    def save_execution_gate_decision(self, payload: Any, request: Any, db: Any) -> dict[str, Any]:
        """WorkbenchFacade.save_execution_gate_decision 接口实现。"""
        return self._service.save_execution_gate_decision(payload, request, db)

    def approve_execution_gate_decision(self, payload: Any, request: Any, db: Any) -> dict[str, Any]:
        """WorkbenchFacade.approve_execution_gate_decision 接口实现。"""
        return self._service.approve_execution_gate_decision(payload, request, db)

    def revoke_execution_gate_decision(self, payload: Any, request: Any, db: Any) -> dict[str, Any]:
        """WorkbenchFacade.revoke_execution_gate_decision 接口实现。"""
        return self._service.revoke_execution_gate_decision(payload, request, db)

    def report_allure_refresh(self, response: Any) -> dict[str, Any]:
        """WorkbenchFacade.report_allure_refresh 接口实现。"""
        return self._service.report_allure_refresh(response)

    def get_case_dictionaries(self) -> dict[str, Any]:
        """WorkbenchFacade.get_case_dictionaries 接口实现。"""
        return {
            "items": {
                "project": get_dictionary_items("project"),
                "client": get_dictionary_items("client"),
                "page": get_dictionary_items("page"),
                "module": get_dictionary_items("module"),
                "case_type": get_dictionary_items("case_type"),
                "source": get_dictionary_items("source"),
                "case_status": get_dictionary_items("case_status"),
                "run_status": get_dictionary_items("run_status"),
                "ai_status": get_dictionary_items("ai_status"),
                "migration_status": get_dictionary_items("migration_status"),
            }
        }

    def list_cases(
        self,
        *,
        project: str,
        page: int,
        page_size: int,
        focus_case_id: str,
        db: Session,
    ) -> dict[str, Any]:
        """分页查询用例列表，并按 case center 做一致性过滤。"""
        store.ensure_dirs()
        case_center_case_ids = workbench_case_consistency_service.load_case_center_case_ids(db)

        def _collect_case_items_filtered(project_code: str) -> list[dict[str, Any]]:
            """WorkbenchFacade._collect_case_items_filtered 接口实现。"""
            items = workbench_asset_service.collect_case_items(
                project_code,
                state_project_dir_fn=lambda code: workbench_asset_service.state_project_dir(
                    code,
                    state_root=constants.TEST_POINTS_ROOT,
                ),
                resolve_case_yaml_path_fn=lambda project_value, case_id_value: workbench_asset_service.resolve_case_yaml_path(
                    project_value,
                    case_id_value,
                    state_case_file_fn=lambda project_value_inner, case_value_inner: workbench_asset_service.state_case_file(
                        project_value_inner,
                        case_value_inner,
                        state_root=constants.TEST_POINTS_ROOT,
                    ),
                    repo_root=constants.REPO_ROOT,
                    assets_cases_root=constants.ASSETS_CASES_ROOT,
                    ai_cases_root=constants.AI_CASES_ROOT,
                    is_within_fn=_is_within,
                ),
                ai_cases_root=constants.AI_CASES_ROOT,
            )
            filtered_items, _filter_meta = workbench_case_consistency_service.filter_records_by_case_center(
                items,
                case_center_case_ids=case_center_case_ids,
            )
            return filtered_items

        return workbench_asset_service.build_cases_payload(
            project=project,
            page=page,
            page_size=page_size,
            focus_case_id=focus_case_id,
            collect_case_items=_collect_case_items_filtered,
            paginate_case_items=workbench_asset_service.paginate_case_items,
        )

    def get_case(self, *, case_id: str, project: str, db: Session) -> dict[str, Any]:
        """获取单个用例详情（含 case center 存在性校验）。"""
        store.ensure_dirs()
        case_center_case_ids = workbench_case_consistency_service.load_case_center_case_ids(db)
        if not workbench_case_consistency_service.is_case_tracked(
            case_id,
            case_center_case_ids=case_center_case_ids,
        ):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="case not found")
        return workbench_asset_service.build_case_detail(
            project=project,
            case_id=case_id,
            resolve_case_yaml_path=lambda project_value, case_id_value: workbench_asset_service.resolve_case_yaml_path(
                project_value,
                case_id_value,
                state_case_file_fn=lambda project_value_inner, case_value_inner: workbench_asset_service.state_case_file(
                    project_value_inner,
                    case_value_inner,
                    state_root=constants.TEST_POINTS_ROOT,
                ),
                repo_root=constants.REPO_ROOT,
                assets_cases_root=constants.ASSETS_CASES_ROOT,
                ai_cases_root=constants.AI_CASES_ROOT,
                is_within_fn=_is_within,
            ),
            read_case_yaml=workbench_asset_service.read_case_yaml,
        )

    def save_case(self, case_id: str, payload: Any, db: Session | None = None) -> dict[str, Any]:
        """保存用例内容；可选执行 case center 归属校验。"""
        if db is not None:
            case_center_case_ids = workbench_case_consistency_service.load_case_center_case_ids(db)
            if not workbench_case_consistency_service.is_case_tracked(
                case_id,
                case_center_case_ids=case_center_case_ids,
            ):
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="case not found")
        return self._service.save_case(case_id, payload)

# ═══════════════════════════════════════════════════════════════
# 构建函数
# ═══════════════════════════════════════════════════════════════
def build_workbench_facade(service: WorkbenchService | None = None) -> WorkbenchFacade:
    """build_workbench_facade 功能入口。"""
    return WorkbenchFacade(service=service)


__all__ = [
    "WorkbenchFacade",
    "build_workbench_facade",
    "_settings",
    "_sync_stage_a_workbench_state",
    "_sync_stage_b_workbench_gate",
    "_ensure_dirs",
    "_read_json_list",
    "_write_json_list",
    "_append_history",
    "_append_runtime_run",
    "_update_runtime_run",
    "_safe_case_id",
    "_runtime_run_id",
    "_runtime_view_from_entry",
    "_normalize_execution_record_payload",
    "_execution_record_time_value",
    "_collect_execution_records_with_meta",
    "_build_execution_task_view",
    "_build_execution_task_summary",
    "_load_runtime_execution_record_from_artifacts",
    "_runtime_view_with_execution_record_preferred",
    "_collect_failure_entries_with_meta",
    "_collect_failure_entries",
    "_normalize_failure_entry_view",
]
