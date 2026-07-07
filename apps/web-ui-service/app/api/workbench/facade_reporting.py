"""WorkbenchFacade 混入 —— 报表与仪表盘相关方法。

提取自 facade.py 以控制单文件大小在 2500 行以内。
"""
from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
from collections import defaultdict
from datetime import datetime, timedelta
from shared_backend.datetime_compat import UTC
from functools import partial
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Sequence
import yaml

from fastapi import HTTPException, Response, status
from shared_backend import get_dictionary_items
from shared_backend.case_ids import match_case_id, normalize_case_id
from shared_backend.element_binding import build_element_alias_map, resolve_element_code, resolve_involved_element_codes
from shared_backend.schemas.contracts import normalize_test_point_plan_v1
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.workbench import constants, store
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core import page_analysis_rules
from app.repositories.page_object_repository import PageObjectRepository
from app.repositories.test_case_repository import TestCaseRepository
from app.models.page_object import PageElement
from app.models.test_case import TestCase, TestCaseExecution
from app.services import (
    test_project_service,
    test_case_service,
    test_data_pool_service,
    workbench_analysis_service,
    workbench_asset_service,
    workbench_case_consistency_service,
    workbench_gate_service,
    workbench_governance_service,
    workbench_history_service,
    workbench_reporting_service,
    workbench_review_service,
    workbench_runtime_service,
    workbench_scheduler_service,
    workbench_task_service,
)
from app.services.workbench_generation_api.payloads import GenerateCasePayload as GenerationGenerateCasePayload
from app.services.workbench_generation_api.usecase_factory import build_generate_case_usecase

from ._http import get_json as _get_json
from ._helpers import (
    build_empty_trend as _build_empty_trend,
    default_overview as _default_overview,
    is_within as _is_within,
    normalize_generation_case_source as _normalize_generation_case_source,
    normalize_optional_project_code as _normalize_optional_project_code,
    normalize_test_point_review_status as _normalize_test_point_review_status,
    parse_iso_datetime as _parse_iso_datetime,
    python_literal as _python_literal,
    read_json_file as _read_json_file,
    safe_python_identifier as _safe_python_identifier,
    safe_rollback_or_invalidate as _safe_rollback_or_invalidate,
    text as _text,
    text_list as _text_list,
    to_utc as _to_utc,
    utc_now as _utc_now,
    validate_test_point_review_status as _validate_test_point_review_status,
    write_json_file as _write_json_file,
)
from .service import WorkbenchService
from .service import (
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
import logging
LOGGER = logging.getLogger(__name__)
_RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{8,128}$")

# 从 facade 导入模块级 helper 函数
from .facade_helpers import (  # noqa: E402
    _settings, _build_runtime_view_from_entry, _resolve_history_project_code,
    _attach_test_point_asset_summary, _point_review_status,
)


class WorkbenchFacadeReportingMixin:
    """报表、仪表盘、调度器的混入类。"""
    def report_failures(
        self,
        *,
        response: Response,
        case_id: str,
        keyword: str,
        defect_status: str,
        db: Session,
    ) -> dict[str, Any]:
        """WorkbenchFacade.report_failures 接口实现。"""
        store.ensure_dirs()
        workbench_reporting_service.apply_no_store_headers(response)
        case_center_case_ids = workbench_case_consistency_service.load_case_center_case_ids(db)

        def _collect_failure_entries_with_meta_filtered() -> tuple[list[dict[str, Any]], dict[str, Any]]:
            """WorkbenchFacade._collect_failure_entries_with_meta_filtered 接口实现。"""
            entries, meta = _collect_failure_entries_with_meta()
            filtered_entries, _filter_meta = workbench_case_consistency_service.filter_records_by_case_center(
                entries,
                case_center_case_ids=case_center_case_ids,
            )
            return filtered_entries, meta

        def _read_defect_items_filtered() -> list[dict[str, Any]]:
            """WorkbenchFacade._read_defect_items_filtered 接口实现。"""
            items = store.list_defect_items()
            filtered_items, _filter_meta = workbench_case_consistency_service.filter_records_by_case_center(
                items,
                case_center_case_ids=case_center_case_ids,
            )
            return filtered_items

        return workbench_reporting_service.build_report_failures(
            case_id=case_id,
            keyword=keyword,
            defect_status=defect_status,
            collect_failure_entries_with_meta=_collect_failure_entries_with_meta_filtered,
            normalize_failure_evidence_meta=workbench_reporting_service.normalize_failure_evidence_meta,
            read_defect_items=_read_defect_items_filtered,
        )

    def report_context(self, *, response: Response, db: Session) -> dict[str, Any]:
        """WorkbenchFacade.report_context 接口实现。"""
        store.ensure_dirs()
        workbench_reporting_service.apply_no_store_headers(response)
        case_center_case_ids = workbench_case_consistency_service.load_case_center_case_ids(db)
        commit_id = ""
        commit_message = ""
        branch_name = ""
        try:
            commit_id = (
                subprocess.run(["git", "rev-parse", "HEAD"],
                               cwd=str(constants.REPO_ROOT), capture_output=True, text=True, check=False, timeout=2)
                .stdout.strip()
            )
            commit_message = (
                subprocess.run(["git", "log", "-1", "--pretty=%s"],
                               cwd=str(constants.REPO_ROOT), capture_output=True, text=True, check=False, timeout=2)
                .stdout.strip()
            )
            branch_name = (
                subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"],
                               cwd=str(constants.REPO_ROOT), capture_output=True, text=True, check=False, timeout=2)
                .stdout.strip()
            )
        except Exception:
            logging.getLogger(__name__).warning(
                "report_context git metadata unavailable",
                exc_info=True,
            )

        def _collect_execution_records_with_meta_filtered(*, limit: int = 1000) -> tuple[list[dict[str, Any]], dict[str, Any]]:
            """WorkbenchFacade._collect_execution_records_with_meta_filtered 接口实现。"""
            rows, meta = _collect_execution_records_with_meta(limit=limit)
            filtered_rows, _filter_meta = workbench_case_consistency_service.filter_records_by_case_center(
                rows,
                case_center_case_ids=case_center_case_ids,
                case_id_resolver=lambda row: (
                    row.get("case_id")
                    or (
                        row.get("execution_record", {}).get("case_id")
                        if isinstance(row.get("execution_record"), dict)
                        else ""
                    )
                ),
            )
            return filtered_rows, meta

        return workbench_reporting_service.build_report_context(
            git_rev_parse_head=commit_id,
            git_log_subject=commit_message,
            git_branch=branch_name,
            collect_execution_records_with_meta=_collect_execution_records_with_meta_filtered,
            normalize_execution_meta=workbench_reporting_service.normalize_execution_meta,
            image_tag=os.getenv("IMAGE_TAG", ""),
            base_url=os.getenv("BASE_URL", "http://localhost:5174/#/login"),
            browser=os.getenv("PLAYWRIGHT_BROWSER", "chromium"),
            environment=os.getenv("APP_ENV", "local"),
        )

    def report_performance(self, *, response: Response, db: Session) -> dict[str, Any]:
        """WorkbenchFacade.report_performance 接口实现。"""
        store.ensure_dirs()
        workbench_reporting_service.apply_no_store_headers(response)
        case_center_case_ids = workbench_case_consistency_service.load_case_center_case_ids(db)

        def _collect_execution_records_with_meta_filtered(*, limit: int = 1000) -> tuple[list[dict[str, Any]], dict[str, Any]]:
            """WorkbenchFacade._collect_execution_records_with_meta_filtered 接口实现。"""
            rows, meta = _collect_execution_records_with_meta(limit=limit)
            filtered_rows, _filter_meta = workbench_case_consistency_service.filter_records_by_case_center(
                rows,
                case_center_case_ids=case_center_case_ids,
                case_id_resolver=lambda row: (
                    row.get("case_id")
                    or (
                        row.get("execution_record", {}).get("case_id")
                        if isinstance(row.get("execution_record"), dict)
                        else ""
                    )
                ),
            )
            return filtered_rows, meta

        return workbench_reporting_service.build_report_performance(
            collect_execution_records_with_meta=_collect_execution_records_with_meta_filtered,
            normalize_execution_meta=workbench_reporting_service.normalize_execution_meta,
        )

    def report_allure(self, response: Response) -> dict[str, Any]:
        """WorkbenchFacade.report_allure 接口实现。"""
        workbench_reporting_service.apply_no_store_headers(response)
        latest_results_dir = workbench_reporting_service.find_latest_run_allure_results(repo_root=constants.REPO_ROOT)
        return workbench_reporting_service.build_report_allure(
            available=(constants.ALLURE_REPORT_ROOT / "index.html").exists(),
            read_allure_summary=lambda: workbench_reporting_service.read_allure_summary(
                allure_report_root=constants.ALLURE_REPORT_ROOT
            ),
            read_allure_environment=lambda: workbench_reporting_service.read_allure_environment(
                allure_report_root=constants.ALLURE_REPORT_ROOT
            ),
            read_allure_executors=lambda: workbench_reporting_service.read_allure_executors(
                allure_report_root=constants.ALLURE_REPORT_ROOT
            ),
            ensure_allure_snapshot=lambda **kwargs: workbench_reporting_service.ensure_allure_snapshot(
                version=int(kwargs.get("version", 0) or 0),
                snapshot_slug=str(kwargs.get("snapshot_slug", "")),
                allure_report_root=constants.ALLURE_REPORT_ROOT,
                allure_snapshots_root=constants.ALLURE_SNAPSHOTS_ROOT,
            ),
            get_allure_index_version=lambda: workbench_reporting_service.get_allure_index_version(
                allure_report_root=constants.ALLURE_REPORT_ROOT
            ),
            current_results_dir=latest_results_dir,
        )

    def workbench_history(
        self,
        *,
        limit: int,
        page: int,
        page_size: int,
        project_code: str,
        keyword: str,
        sort: str,
        action: str,
        actor: str,
        status: str,
        risk_gate_decision: str,
        self_healing_status: str,
        db: Session,
    ) -> dict[str, Any]:
        """WorkbenchFacade.workbench_history 接口实现。"""
        store.ensure_dirs()
        project_code_value = _normalize_optional_project_code(project_code)
        history_items, _filter_meta = workbench_case_consistency_service.filter_records_by_case_center(
            store.read_history_items(),
            case_center_case_ids=workbench_case_consistency_service.load_case_center_case_ids(db),
        )
        if project_code_value:
            history_items = [item for item in history_items if _resolve_history_project_code(item) == project_code_value]

        project_status_cache: dict[str, str] = {}

        def resolve_project_status(project_code_value_raw: str) -> str:
            """WorkbenchFacade.resolve_project_status 接口实现。"""
            normalized_project_code = _normalize_optional_project_code(project_code_value_raw)
            if not normalized_project_code:
                return "active"
            if normalized_project_code not in project_status_cache:
                project_status_cache[normalized_project_code] = test_project_service.get_project_status(
                    db,
                    normalized_project_code,
                )
            return project_status_cache[normalized_project_code]

        def find_run_item_for_history(run_id: str) -> dict[str, Any]:
            run_item = self._service._find_run_item(run_id) if hasattr(self._service, "_find_run_item") else None
            if run_item:
                return run_item
            return workbench_runtime_service.find_run_item(
                run_id,
                get_job=store.get_run_job,
                read_runtime_runs=store.read_runtime_run_items,
                runtime_run_id_fn=workbench_runtime_service.runtime_run_id,
                runtime_view_with_execution_record_preferred_fn=_runtime_view_with_execution_record_preferred,
            ) or {}

        payload = workbench_history_service.list_history(
            history_items,
            resolve_governance_snapshot=lambda run_id: workbench_reporting_service.resolve_run_governance_snapshot(
                run_id,
                find_run_item=find_run_item_for_history,
                build_risk_report_summary=workbench_analysis_service.build_risk_report_summary,
                build_self_healing_summary=workbench_analysis_service.build_self_healing_summary,
                build_page_semantic_summary=workbench_analysis_service.build_page_semantic_summary,
            ),
            resolve_failure_snapshot=lambda run_id: workbench_reporting_service.resolve_run_failure_snapshot(
                run_id,
                find_run_item=find_run_item_for_history,
                normalize_failure_entry_view=_normalize_failure_entry_view,
                collect_failure_entries=lambda: _collect_failure_entries_with_meta()[0],
                is_within_fn=_is_within,
            ),
            normalize_page_slug=workbench_gate_service.normalize_page_slug,
            limit=limit,
            page=page,
            page_size=page_size,
            keyword=keyword,
            sort=sort,
            action=action,
            actor=actor,
            status=status,
            risk_gate_decision=risk_gate_decision,
            self_healing_status=self_healing_status,
        )
        for item in payload.get("items", []):
            if not isinstance(item, dict):
                continue
            resolved_project_code = _resolve_history_project_code(item)
            item["project_code"] = resolved_project_code
            item["project_status"] = resolve_project_status(resolved_project_code)
        return payload

    def workbench_quality_gate_summary(
        self,
        *,
        limit: int,
        alert_code: str,
        page: str,
        db: Session,
    ) -> dict[str, Any]:
        """WorkbenchFacade.workbench_quality_gate_summary 接口实现。"""
        store.ensure_dirs()
        history_items, _filter_meta = workbench_case_consistency_service.filter_records_by_case_center(
            store.read_history_items(),
            case_center_case_ids=workbench_case_consistency_service.load_case_center_case_ids(db),
        )
        return {
            "item": workbench_history_service.summarize_quality_gate_events(
                history_items,
                limit=limit,
                alert_code=alert_code,
                page=page,
                normalize_page_slug=workbench_gate_service.normalize_page_slug,
            )
        }

    def cleanup_case_consistency(self, *, purge_all: bool, confirm_text: str = "", db: Session) -> dict[str, Any]:
        """WorkbenchFacade.cleanup_case_consistency 接口实现。"""
        store.ensure_dirs()
        if purge_all and _text(confirm_text) != "清理全部执行状态":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "purge_all_confirmation_required",
                    "message": "请输入确认文本：清理全部执行状态",
                },
            )
        case_center_case_ids = workbench_case_consistency_service.load_case_center_case_ids(db)

        with store.FILE_LOCK:
            history_items = store.read_history_items()
            runtime_items = store.read_runtime_run_items()
            defect_items = store.read_defect_items()
            review_items = store.read_review_items()
            gate_decision_items = store.read_gate_decision_items()
            calibration_items = store.read_failure_source_calibration_items()
            if purge_all:
                store.clear_state_files()
                history_filter_meta = {
                    "enforced": True,
                    "total_records": len(history_items),
                    "removed_count": len(history_items),
                    "removed_case_ids": [],
                    "purged_all": True,
                }
                runtime_filter_meta = {
                    "enforced": True,
                    "total_records": len(runtime_items),
                    "removed_count": len(runtime_items),
                    "removed_case_ids": [],
                    "purged_all": True,
                }
                defect_filter_meta = {
                    "enforced": True,
                    "total_records": len(defect_items),
                    "removed_count": len(defect_items),
                    "removed_case_ids": [],
                    "purged_all": True,
                }
                review_filter_meta = {
                    "enforced": True,
                    "total_records": len(review_items),
                    "removed_count": len(review_items),
                    "removed_case_ids": [],
                    "purged_all": True,
                }
                gate_filter_meta = {
                    "enforced": True,
                    "total_records": len(gate_decision_items),
                    "removed_count": len(gate_decision_items),
                    "removed_case_ids": [],
                    "purged_all": True,
                }
                calibration_filter_meta = {
                    "enforced": True,
                    "total_records": len(calibration_items),
                    "removed_count": len(calibration_items),
                    "removed_case_ids": [],
                    "purged_all": True,
                }
            else:
                filtered_history_items, history_filter_meta = workbench_case_consistency_service.filter_records_by_case_center(
                    history_items,
                    case_center_case_ids=case_center_case_ids,
                )
                filtered_runtime_items, runtime_filter_meta = workbench_case_consistency_service.filter_records_by_case_center(
                    runtime_items,
                    case_center_case_ids=case_center_case_ids,
                )
                filtered_defect_items, defect_filter_meta = workbench_case_consistency_service.filter_records_by_case_center(
                    defect_items,
                    case_center_case_ids=case_center_case_ids,
                )
                filtered_review_items, review_filter_meta = workbench_case_consistency_service.filter_records_by_case_center(
                    review_items,
                    case_center_case_ids=case_center_case_ids,
                )
                filtered_gate_decision_items, gate_filter_meta = workbench_case_consistency_service.filter_records_by_case_center(
                    gate_decision_items,
                    case_center_case_ids=case_center_case_ids,
                )
                filtered_calibration_items, calibration_filter_meta = workbench_case_consistency_service.filter_records_by_case_center(
                    calibration_items,
                    case_center_case_ids=case_center_case_ids,
                )

                if history_filter_meta.get("removed_count", 0):
                    store.write_history_items(filtered_history_items)
                if runtime_filter_meta.get("removed_count", 0):
                    store.write_runtime_run_items(filtered_runtime_items)
                if defect_filter_meta.get("removed_count", 0):
                    store.write_defect_items(filtered_defect_items)
                if review_filter_meta.get("removed_count", 0):
                    store.write_review_items(filtered_review_items)
                if gate_filter_meta.get("removed_count", 0):
                    store.write_gate_decision_items(filtered_gate_decision_items)
                if calibration_filter_meta.get("removed_count", 0):
                    store.write_failure_source_calibration_items(filtered_calibration_items)

        reports_cleanup = workbench_case_consistency_service.cleanup_execution_report_files(
            execution_reports_root=constants.EXECUTION_REPORTS_ROOT,
            case_center_case_ids=case_center_case_ids,
        )
        task_artifacts_cleanup = workbench_case_consistency_service.cleanup_execution_task_artifacts(
            runner_artifacts_root=constants.RUNNER_ROOT / "artifacts",
            web_ui_runs_root=constants.WEB_UI_RUNS_DIR,
        )
        allure_cleanup = workbench_case_consistency_service.cleanup_allure_artifacts(
            allure_results_root=constants.ALLURE_RESULTS_ROOT,
            allure_report_root=constants.ALLURE_REPORT_ROOT,
            allure_snapshots_root=constants.ALLURE_SNAPSHOTS_ROOT,
            clear_report_root=False,
        )

        return {
            "history": history_filter_meta,
            "runtime_runs": runtime_filter_meta,
            "defect_links": defect_filter_meta,
            "review_decisions": review_filter_meta,
            "execution_gate_decisions": gate_filter_meta,
            "failure_source_calibrations": calibration_filter_meta,
            "execution_reports": reports_cleanup,
            "execution_task_artifacts": task_artifacts_cleanup,
            "allure_artifacts": allure_cleanup,
            "case_center_case_count": len(case_center_case_ids or []),
            "purge_all": purge_all,
        }

    def download_log(self, run_id: str, db: Session) -> Response:
        """WorkbenchFacade.download_log 接口实现。"""
        store.ensure_dirs()
        normalized_run_id = _text(run_id)
        if not _RUN_ID_PATTERN.fullmatch(normalized_run_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run not found")
        case_center_case_ids = workbench_case_consistency_service.load_case_center_case_ids(db)
        run_item = self._service._find_run_item(normalized_run_id) if hasattr(self._service, "_find_run_item") else None
        if not run_item:
            run_item = workbench_runtime_service.find_run_item(
                normalized_run_id,
                get_job=store.get_run_job,
                read_runtime_runs=store.read_runtime_run_items,
                runtime_run_id_fn=workbench_runtime_service.runtime_run_id,
                runtime_view_with_execution_record_preferred_fn=_runtime_view_with_execution_record_preferred,
            )
        if not run_item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run not found")
        if not workbench_case_consistency_service.is_case_tracked(
            run_item.get("case_id", ""),
            case_center_case_ids=case_center_case_ids,
        ):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run not found")
        log_path = (constants.WEB_UI_RUNS_DIR / f"{normalized_run_id}.log").resolve()
        if not _is_within(log_path, constants.WEB_UI_RUNS_DIR):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="log not found")
        if not log_path.exists():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="log not found")
        return Response(
            content=log_path.read_text(encoding="utf-8", errors="ignore"),
            media_type="text/plain; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename={normalized_run_id}.log"},
        )

    def dashboard_overview(self, db: Session) -> dict[str, Any]:
        """WorkbenchFacade.dashboard_overview 接口实现。"""
        return workbench_governance_service.build_dashboard_overview(db)

    def dashboard_governance(self, db: Session) -> dict[str, Any]:
        """WorkbenchFacade.dashboard_governance 接口实现。"""
        now = datetime.now(UTC)
        degraded_sources: list[str] = []
        quality_gate_summary: dict[str, Any] = {}
        task_snapshot: dict[str, Any] = {"items": [], "summary": {}}
        cluster_payload: dict[str, Any] = {
            "generated_at": now.isoformat(),
            "total_failed_reports": 0,
            "total_clusters": 0,
            "clusters": [],
        }
        flaky_payload: dict[str, Any] = {"top_flaky": []}
        governance_trend: dict[str, Any] = {"items": [], "summary_7d": {}}

        try:
            history_items = store.read_history_items()
            quality_gate_summary = workbench_history_service.summarize_quality_gate_events(
                history_items,
                limit=2000,
                normalize_page_slug=lambda value: str(value).strip().lower(),
            )
        except Exception:
            LOGGER.exception("dashboard governance degraded: quality gate summary unavailable")
            degraded_sources.append("quality_gate")

        try:
            store.ensure_dirs()
            execution_rows, execution_meta_raw = _collect_execution_records_with_meta(limit=200)
            execution_meta = workbench_reporting_service.normalize_execution_meta(execution_meta_raw)
            items: list[dict[str, Any]] = []
            for row in execution_rows:
                items.append(_build_execution_task_view(row))
                if len(items) >= 200:
                    break
            task_snapshot = {
                "items": items,
                "summary": _build_execution_task_summary(items=items, filter_snapshot={}, execution_meta=execution_meta),
            }
        except Exception:
            LOGGER.exception("dashboard governance degraded: task snapshot unavailable")
            degraded_sources.append("tasks")

        try:
            settings = _settings()
            cluster_payload = _get_json(
                f"{settings.orchestrator_url.rstrip('/')}/failures/clusters?limit=200&max_clusters=8",
                timeout_seconds=settings.orchestrator_timeout_seconds,
            )
        except Exception:
            LOGGER.exception("dashboard governance degraded: failure clusters unavailable")
            degraded_sources.append("failure_clusters")

        try:
            history_items = store.read_history_items()
            governance_trend = workbench_governance_service.build_governance_trend(
                history_items=history_items,
                resolve_governance_snapshot=lambda run_id: workbench_reporting_service.resolve_run_governance_snapshot(
                    run_id,
                    find_run_item=lambda _run_id: {},
                    build_risk_report_summary=workbench_analysis_service.build_risk_report_summary,
                    build_self_healing_summary=workbench_analysis_service.build_self_healing_summary,
                    build_page_semantic_summary=workbench_analysis_service.build_page_semantic_summary,
                ),
                quality_gate_summary=quality_gate_summary,
                now=now,
                days=14,
            )
        except Exception:
            LOGGER.exception("dashboard governance degraded: governance trend unavailable")
            degraded_sources.append("governance_trend")

        try:
            test_case_service.ensure_seed_data(db)
            repo = TestCaseRepository(db)
            cases = repo.list_all()
            executions = repo.list_all_executions_ordered()
            flaky_payload = {"top_flaky": workbench_governance_service.build_flaky_top5(cases, executions)}
        except Exception:
            LOGGER.exception("dashboard governance degraded: flaky snapshot unavailable")
            degraded_sources.append("flaky")

        return workbench_governance_service.build_governance_overview(
            quality_gate_summary=quality_gate_summary,
            task_snapshot=task_snapshot,
            cluster_payload=cluster_payload,
            flaky_payload=flaky_payload,
            governance_trend=governance_trend,
            degraded_sources=degraded_sources,
            now=now,
        )

    def scheduler_summary(self, *, limit: int) -> dict[str, Any]:
        """WorkbenchFacade.scheduler_summary 接口实现。"""
        store.ensure_dirs()
        execution_rows, execution_meta_raw = _collect_execution_records_with_meta(limit=max(limit * 3, 200))
        execution_meta = workbench_reporting_service.normalize_execution_meta(execution_meta_raw)
        items = [
            _build_execution_task_view(row)
            for row in execution_rows
        ][:limit]
        task_summary = _build_execution_task_summary(items=items, filter_snapshot={}, execution_meta=execution_meta)
        return {"item": workbench_scheduler_service.build_scheduler_summary(items=items, task_summary=task_summary)}

    def scheduler_dispatch_plan(self, *, limit: int) -> dict[str, Any]:
        """WorkbenchFacade.scheduler_dispatch_plan 接口实现。"""
        store.ensure_dirs()
        execution_rows, _execution_meta_raw = _collect_execution_records_with_meta(limit=max(limit * 3, 200))
        items = [
            _build_execution_task_view(row)
            for row in execution_rows
        ][:limit]
        return {"item": workbench_scheduler_service.build_scheduler_dispatch_plan(items=items)}


