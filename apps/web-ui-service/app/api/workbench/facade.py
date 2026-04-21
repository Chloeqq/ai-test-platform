from __future__ import annotations

import json
import os
import subprocess
import socket
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Sequence

from fastapi import HTTPException, Response, status
from shared_backend import get_dictionary_items
from shared_backend.case_ids import match_case_id, normalize_case_id
from sqlalchemy import select
from sqlalchemy.orm import Session
from urllib import error as url_error
from urllib import request as url_request

from app.api.workbench import constants, store
from app.core.config import get_settings
from app.core import page_analysis_rules
from app.models.test_case import TestCase, TestCaseExecution
from app.services import (
    test_project_service,
    test_case_service,
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


def _settings() -> Any:
    return get_settings()


def _get_json(url: str, *, timeout_seconds: int = 300) -> dict[str, Any]:
    request = url_request.Request(url=url, method="GET")
    try:
        with url_request.urlopen(request, timeout=timeout_seconds) as response:
            text = response.read().decode("utf-8")
    except url_error.HTTPError as exc:
        raw_body = exc.read().decode("utf-8", errors="ignore")
        detail: Any = raw_body.strip() or str(exc)
        try:
            parsed = json.loads(raw_body or "{}")
            if isinstance(parsed, dict):
                detail = parsed.get("error", parsed)
        except Exception:
            pass
        raise HTTPException(status_code=exc.code, detail=detail) from exc
    except url_error.URLError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"orchestrator unavailable: {exc.reason}") from exc
    except TimeoutError as exc:
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="orchestrator request timed out") from exc
    except socket.timeout as exc:
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="orchestrator request timed out") from exc

    try:
        data = json.loads(text or "{}")
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="orchestrator returned non-json payload") from exc
    if not isinstance(data, dict):
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="orchestrator returned invalid response object")
    return data


def _normalize_optional_project_code(value: Any) -> str:
    return str(value or "").strip().lower()


def _resolve_history_project_code(item: dict[str, Any]) -> str:
    normalized_project_code = _normalize_optional_project_code(item.get("project_code") or item.get("project"))
    if normalized_project_code:
        return normalized_project_code
    case_id = str(item.get("case_id", "")).strip().lower()
    matched = match_case_id(case_id)
    if not matched:
        return ""
    return _normalize_optional_project_code(matched.group("project"))


def _to_utc(value: datetime | None) -> datetime:
    if not value:
        return datetime.now(UTC)
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _parse_iso_datetime(value: str) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    parsed_text = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(parsed_text)
    except Exception:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _is_within(path: Path, root: Path) -> bool:
    try:
        return path.resolve().is_relative_to(root.resolve())
    except Exception:
        return str(path.resolve()).startswith(str(root.resolve()))


def _build_empty_trend(now: datetime) -> list[dict[str, Any]]:
    base = (now - timedelta(hours=23)).replace(minute=0, second=0, microsecond=0)
    return [
        {
            "hour": (base + timedelta(hours=i)).strftime("%H:%M"),
            "pass_rate": 100.0,
            "execution_count": 0,
        }
        for i in range(24)
    ]


def _default_overview(now: datetime, reason: str) -> dict[str, Any]:
    trend = _build_empty_trend(now)
    return {
        "as_of": now.isoformat(),
        "risk": {
            "score": 0,
            "level": "低",
            "summary": "暂无可用执行数据，已启用降级视图。",
            "detail_url": "/quality/trends",
        },
        "summary": {
            "pass_rate_24h": 100.0,
            "execution_count_24h": 0,
            "intercepted_last10": 0,
            "pending_issues": 0,
            "as_of": now.isoformat(),
        },
        "trend_24h": trend,
        "top_flaky": [],
        "gate_last10": [],
        "pending_issues": [],
        "degraded": True,
        "degraded_reason": reason,
    }


class WorkbenchFacade:
    def __init__(self, service: WorkbenchService | None = None) -> None:
        self._service = service or WorkbenchService()

    def list_projects(self, db: Any) -> dict[str, Any]:
        return self._service.list_projects(db)

    def list_execution_tasks(self, **kwargs: Any) -> dict[str, Any]:
        return self._service.list_execution_tasks(**kwargs)

    def get_execution_task(self, task_id: str, db: Any) -> dict[str, Any]:
        return self._service.get_execution_task(task_id, db)

    def get_execution_gate_config(self) -> dict[str, Any]:
        return self._service.get_execution_gate_config()

    def save_case(self, case_id: str, payload: Any) -> dict[str, Any]:
        return self._service.save_case(case_id, payload)

    def heal_run(self, run_id: str) -> dict[str, Any]:
        return self._service.heal_run(run_id)

    def rerun_case(self, run_id: str) -> dict[str, Any]:
        return self._service.rerun_case(run_id)

    def heal_and_rerun_case(self, run_id: str, wait_seconds: int) -> dict[str, Any]:
        return self._service.heal_and_rerun_case(run_id, wait_seconds)

    def save_review(self, payload: Any, request: Any, db: Session | None = None) -> dict[str, Any]:
        if db is not None and str(getattr(payload, "case_id", "") or "").strip():
            case_center_case_ids = workbench_case_consistency_service.load_case_center_case_ids(db)
            if not workbench_case_consistency_service.is_case_tracked(
                getattr(payload, "case_id", ""),
                case_center_case_ids=case_center_case_ids,
            ):
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="case_id not found in case center")
        return self._service.save_review(payload, request)

    def save_execution_gate_decision(self, payload: Any, request: Any, db: Any) -> dict[str, Any]:
        return self._service.save_execution_gate_decision(payload, request, db)

    def approve_execution_gate_decision(self, payload: Any, request: Any, db: Any) -> dict[str, Any]:
        return self._service.approve_execution_gate_decision(payload, request, db)

    def revoke_execution_gate_decision(self, payload: Any, request: Any, db: Any) -> dict[str, Any]:
        return self._service.revoke_execution_gate_decision(payload, request, db)

    def report_allure_refresh(self, response: Any) -> dict[str, Any]:
        return self._service.report_allure_refresh(response)

    def get_case_dictionaries(self) -> dict[str, Any]:
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
        store.ensure_dirs()
        case_center_case_ids = workbench_case_consistency_service.load_case_center_case_ids(db)

        def _collect_case_items_filtered(project_code: str) -> list[dict[str, Any]]:
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
        if db is not None:
            case_center_case_ids = workbench_case_consistency_service.load_case_center_case_ids(db)
            if not workbench_case_consistency_service.is_case_tracked(
                case_id,
                case_center_case_ids=case_center_case_ids,
            ):
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="case not found")
        return self._service.save_case(case_id, payload)

    def list_test_point_assets(
        self,
        *,
        project: str,
        page: str,
        keyword: str,
        source_type: str,
        coverage_status: str,
        review_status: str,
        gate_decision: str,
        selection_state: str,
        db: Session,
    ) -> dict[str, Any]:
        store.ensure_dirs()
        payload = workbench_asset_service.build_test_point_asset_items(
            project=project,
            page=page,
            keyword=keyword,
            source_type=source_type,
            coverage_status=coverage_status,
            review_status=review_status,
            gate_decision=gate_decision,
            selection_state=selection_state,
            state_project_dir=lambda code: workbench_asset_service.state_project_dir(code, state_root=constants.TEST_POINTS_ROOT),
            normalize_page_slug=workbench_gate_service.normalize_page_slug,
            load_test_point_asset=lambda project_value, case_id_value: workbench_asset_service.load_test_point_asset_with_root(
                project_value,
                case_id_value,
                state_root=constants.TEST_POINTS_ROOT,
            ),
            latest_run_snapshot_for_case=lambda project_value, case_id_value, page_value="": workbench_asset_service.latest_run_snapshot_for_case(
                project=project_value,
                case_id=case_id_value,
                page=page_value,
                safe_case_id_fn=workbench_gate_service.safe_case_id,
                normalize_page_slug_fn=workbench_gate_service.normalize_page_slug,
                runtime_jobs=store.list_run_jobs(),
                runtime_runs_file=constants.RUNTIME_RUNS_FILE,
                runtime_view_with_execution_record_preferred_fn=lambda item: item if isinstance(item, dict) else {},
                read_json_list_fn=store.read_json_list,
                build_review_audit_summary_fn=workbench_review_service.build_review_audit_summary,
                build_page_semantic_summary_fn=workbench_analysis_service.build_page_semantic_summary,
                build_execution_gate_audit_snapshot_fn=workbench_gate_service.build_execution_gate_audit_snapshot,
                build_risk_report_summary_fn=workbench_analysis_service.build_risk_report_summary,
            ),
            build_traceability_summary=lambda asset, latest_run: workbench_asset_service.build_test_point_asset_traceability_summary(
                asset=asset,
                latest_run=latest_run,
                build_test_point_asset_technique_summary_fn=workbench_asset_service.build_test_point_asset_technique_summary,
                build_review_audit_summary_fn=workbench_review_service.build_review_audit_summary,
                build_page_semantic_summary_fn=workbench_analysis_service.build_page_semantic_summary,
                build_risk_report_summary_fn=workbench_analysis_service.build_risk_report_summary,
                build_execution_gate_fn=workbench_gate_service.build_execution_gate,
                build_execution_gate_audit_snapshot_fn=workbench_gate_service.build_execution_gate_audit_snapshot,
                clamp_confidence=page_analysis_rules.clamp_confidence,
            ),
            build_selection_summary=lambda traceability_summary: workbench_asset_service.build_test_point_asset_selection_summary(
                traceability_summary=traceability_summary
            ),
            build_coverage_summary=lambda items, filter_snapshot: workbench_asset_service.build_test_point_asset_coverage_summary(
                items=items,
                filter_snapshot=filter_snapshot,
            ),
            clamp_confidence=page_analysis_rules.clamp_confidence,
        )
        case_center_case_ids = workbench_case_consistency_service.load_case_center_case_ids(db)
        filtered_items, _filter_meta = workbench_case_consistency_service.filter_records_by_case_center(
            payload.get("items", []),
            case_center_case_ids=case_center_case_ids,
            case_id_key="asset_id",
            case_id_resolver=lambda row: row.get("asset_id"),
        )
        payload["items"] = filtered_items
        payload["selection_summary"]["total_assets"] = len(filtered_items)
        payload["selection_summary"]["ready_count"] = sum(
            1 for item in filtered_items if str((item.get("selection_summary") or {}).get("selection_state", "")).strip() == "ready"
        )
        payload["selection_summary"]["needs_review_count"] = sum(
            1
            for item in filtered_items
            if str((item.get("selection_summary") or {}).get("selection_state", "")).strip() == "needs_review"
        )
        payload["selection_summary"]["blocked_count"] = sum(
            1
            for item in filtered_items
            if str((item.get("selection_summary") or {}).get("selection_state", "")).strip() == "blocked"
        )
        payload["coverage_summary"] = workbench_asset_service.build_test_point_asset_coverage_summary(
            items=filtered_items,
            filter_snapshot=payload["selection_summary"].get("filter_snapshot", {}),
        )
        return payload

    def get_test_point_asset_coverage_summary(self, *, project: str, page: str, keyword: str, source_type: str, coverage_status: str, review_status: str, gate_decision: str, selection_state: str, db: Session) -> dict[str, Any]:
        payload = self.list_test_point_assets(
            project=project,
            page=page,
            keyword=keyword,
            source_type=source_type,
            coverage_status=coverage_status,
            review_status=review_status,
            gate_decision=gate_decision,
            selection_state=selection_state,
            db=db,
        )
        return {"item": payload.get("coverage_summary", {})}

    def get_test_point_asset(self, *, asset_id: str, project: str, db: Session) -> dict[str, Any]:
        store.ensure_dirs()
        case_center_case_ids = workbench_case_consistency_service.load_case_center_case_ids(db)
        if not workbench_case_consistency_service.is_case_tracked(
            asset_id,
            case_center_case_ids=case_center_case_ids,
        ):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="test point asset not found")
        payload = workbench_asset_service.build_test_point_asset_detail(
            project=project,
            asset_id=asset_id,
            load_test_point_asset=lambda project_value, case_id_value: workbench_asset_service.load_test_point_asset_with_root(
                project_value,
                case_id_value,
                state_root=constants.TEST_POINTS_ROOT,
            ),
            latest_run_snapshot_for_case=lambda project_value, case_id_value, page_value="": workbench_asset_service.latest_run_snapshot_for_case(
                project=project_value,
                case_id=case_id_value,
                page=page_value,
                safe_case_id_fn=workbench_gate_service.safe_case_id,
                normalize_page_slug_fn=workbench_gate_service.normalize_page_slug,
                runtime_jobs=store.list_run_jobs(),
                runtime_runs_file=constants.RUNTIME_RUNS_FILE,
                runtime_view_with_execution_record_preferred_fn=lambda item: item if isinstance(item, dict) else {},
                read_json_list_fn=store.read_json_list,
                build_review_audit_summary_fn=workbench_review_service.build_review_audit_summary,
                build_page_semantic_summary_fn=workbench_analysis_service.build_page_semantic_summary,
                build_execution_gate_audit_snapshot_fn=workbench_gate_service.build_execution_gate_audit_snapshot,
                build_risk_report_summary_fn=workbench_analysis_service.build_risk_report_summary,
            ),
            build_traceability_summary=lambda asset, latest_run: workbench_asset_service.build_test_point_asset_traceability_summary(
                asset=asset,
                latest_run=latest_run,
                build_test_point_asset_technique_summary_fn=workbench_asset_service.build_test_point_asset_technique_summary,
                build_review_audit_summary_fn=workbench_review_service.build_review_audit_summary,
                build_page_semantic_summary_fn=workbench_analysis_service.build_page_semantic_summary,
                build_risk_report_summary_fn=workbench_analysis_service.build_risk_report_summary,
                build_execution_gate_fn=workbench_gate_service.build_execution_gate,
                build_execution_gate_audit_snapshot_fn=workbench_gate_service.build_execution_gate_audit_snapshot,
                clamp_confidence=page_analysis_rules.clamp_confidence,
            ),
            build_selection_summary=lambda traceability_summary: workbench_asset_service.build_test_point_asset_selection_summary(
                traceability_summary=traceability_summary
            ),
            clamp_confidence=page_analysis_rules.clamp_confidence,
        )
        if not payload:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="test point asset not found")
        return payload

    def get_test_point_asset_coverage_matrix(self, *, asset_id: str, project: str, db: Session) -> dict[str, Any]:
        payload = self.get_test_point_asset(asset_id=asset_id, project=project, db=db)
        item = payload.get("item", {}) if isinstance(payload.get("item"), dict) else {}
        return {"item": item.get("coverage_matrix", {}) if isinstance(item.get("coverage_matrix"), dict) else {}}

    def run_case(self, *, payload: Any, db: Session) -> dict[str, Any]:
        store.ensure_dirs()
        normalized_case_id = _safe_case_id(getattr(payload, "case_id", ""))
        if not workbench_case_consistency_service.is_case_tracked(
            normalized_case_id,
            case_center_case_ids=workbench_case_consistency_service.load_case_center_case_ids(db),
        ):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="case_id not found in case center")
        if str(getattr(payload, "case_path", "")).strip():
            case_path = Path(str(getattr(payload, "case_path", ""))).expanduser()
            if not case_path.is_absolute():
                case_path = constants.REPO_ROOT / case_path
            case_path = case_path.resolve()
        else:
            case_path = workbench_asset_service.resolve_case_yaml_path(
                getattr(payload, "project", "default"),
                normalized_case_id,
                state_case_file_fn=lambda project_value, case_value: workbench_asset_service.state_case_file(
                    project_value,
                    case_value,
                    state_root=constants.TEST_POINTS_ROOT,
                ),
                repo_root=constants.REPO_ROOT,
                assets_cases_root=constants.ASSETS_CASES_ROOT,
                ai_cases_root=constants.AI_CASES_ROOT,
                is_within_fn=_is_within,
            )
        if not case_path.exists():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"case file not found: {case_path}")
        if not _is_within(case_path, constants.ASSETS_CASES_ROOT):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="case_path must stay under assets/test-cases")

        def _build_runtime_execution_record(**kwargs: Any) -> dict[str, Any]:
            return workbench_runtime_service.build_runtime_execution_record(
                **kwargs,
                normalize_execution_record_payload=_normalize_execution_record_payload,
            )

        def _runtime_view_from_entry(entry: dict[str, Any]) -> dict[str, Any]:
            return workbench_runtime_service.runtime_view_from_entry(
                entry,
                normalize_execution_record_payload=_normalize_execution_record_payload,
                normalize_page_slug=workbench_gate_service.normalize_page_slug,
                build_page_analysis_context=workbench_analysis_service.build_page_analysis_context,
                build_item_review_state=workbench_review_service.build_item_review_state,
                build_run_review_state_from_decisions=workbench_review_service.build_run_review_state_from_decisions,
                build_test_point_asset_gate_context=workbench_asset_service.build_test_point_asset_gate_context,
                build_execution_gate=workbench_gate_service.build_execution_gate,
                build_review_audit_summary=workbench_review_service.build_review_audit_summary,
                build_review_audit_timeline=workbench_review_service.build_review_audit_timeline,
                build_risk_report_summary=workbench_analysis_service.build_risk_report_summary,
                build_self_healing_summary=workbench_analysis_service.build_self_healing_summary,
                execution_gate_decision_for_run=lambda *, run_id, project="", page="": workbench_gate_service.execution_gate_decision_for_run(
                    run_id=run_id,
                    project=project,
                    page=page,
                    read_json_list=store.read_json_list,
                ),
            )

        def _load_runtime_execution_record_from_artifacts(artifacts_dir: Path) -> dict[str, Any]:
            return workbench_runtime_service.load_runtime_execution_record_from_artifacts(
                artifacts_dir,
                normalize_evidence_manifest_payload=lambda payload: payload if isinstance(payload, dict) else {},
                resolve_manifest_entries_fn=lambda entries, root: workbench_runtime_service.resolve_manifest_entries(entries, root=root),
                load_execution_record_payload_fn=lambda path: workbench_runtime_service.load_execution_record_payload(
                    path,
                    normalize_execution_record_payload=_normalize_execution_record_payload,
                ),
            )

        def _collect_failure_entries_with_meta() -> tuple[list[dict[str, Any]], dict[str, Any]]:
            return workbench_reporting_service.collect_failure_entries_with_meta(
                compat_scan_enabled=False,
                artifact_roots=[constants.RUNNER_ROOT / "artifacts", *sorted(constants.WEB_UI_RUNS_DIR.glob("*-artifacts"))],
                logger=None,
                normalize_evidence_manifest_payload=lambda payload: payload if isinstance(payload, dict) else {},
                resolve_manifest_entries=lambda entries, root: workbench_runtime_service.resolve_manifest_entries(entries, root=root),
                load_execution_record_payload=lambda path: workbench_runtime_service.load_execution_record_payload(
                    path,
                    normalize_execution_record_payload=_normalize_execution_record_payload,
                ),
                parse_analysis_file=workbench_reporting_service.parse_analysis_file,
            )

        def _collect_failure_entries() -> list[dict[str, Any]]:
            entries, _meta = _collect_failure_entries_with_meta()
            return entries

        def _build_run_command(case_path_value: Path) -> tuple[list[str], dict[str, str]]:
            return workbench_runtime_service.build_run_command(
                case_path_value,
                get_python_bin_fn=lambda: workbench_runtime_service.get_python_bin(repo_root=constants.REPO_ROOT),
                repo_root=constants.REPO_ROOT,
                allure_results_root=constants.ALLURE_RESULTS_ROOT,
                environ=os.environ.copy(),
            )

        def _execute_run(job: dict[str, Any]) -> None:
            workbench_runtime_service.execute_run(
                job,
                build_run_command_fn=_build_run_command,
                now_iso_fn=store.now_iso,
                update_job=store.update_run_job,
                update_runtime_run=store.update_runtime_run,
                load_runtime_execution_record_from_artifacts=_load_runtime_execution_record_from_artifacts,
                collect_failure_entries=_collect_failure_entries,
                is_within=_is_within,
                repo_root=constants.REPO_ROOT,
                runner_root=constants.RUNNER_ROOT,
            )

        job = workbench_runtime_service.start_run(
            project=getattr(payload, "project", "default"),
            case_id=normalized_case_id,
            case_path=case_path,
            source=getattr(payload, "source", "manual"),
            runs_dir=constants.WEB_UI_RUNS_DIR,
            now_iso_fn=store.now_iso,
            build_runtime_execution_record=_build_runtime_execution_record,
            runtime_view_from_entry_fn=_runtime_view_from_entry,
            store_run_job=store.store_run_job,
            append_runtime_run=store.append_runtime_run,
            append_history=store.append_history,
            execute_run_fn=_execute_run,
        )
        return {"item": job}

    def list_runs(self, *, limit: int, db: Session) -> dict[str, Any]:
        store.ensure_dirs()
        case_center_case_ids = workbench_case_consistency_service.load_case_center_case_ids(db)
        items = [
            _attach_test_point_asset_summary(
                _runtime_view_from_entry(item)
            )
            for item in store.read_runtime_run_items()
        ]
        filtered_items, _filter_meta = workbench_case_consistency_service.filter_records_by_case_center(
            items,
            case_center_case_ids=case_center_case_ids,
        )
        return {"items": filtered_items[:limit]}

    def get_run(self, *, run_id: str, db: Session) -> dict[str, Any]:
        store.ensure_dirs()
        case_center_case_ids = workbench_case_consistency_service.load_case_center_case_ids(db)
        job = store.get_run_job(run_id)
        if job:
            item = _attach_test_point_asset_summary(_runtime_view_from_entry(job))
            if workbench_case_consistency_service.is_case_tracked(item.get("case_id", ""), case_center_case_ids=case_center_case_ids):
                return {"item": item}
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run not found")

        for item in store.read_runtime_run_items():
            if workbench_runtime_service.runtime_run_id(item) != run_id:
                continue
            response_item = _attach_test_point_asset_summary(_runtime_view_from_entry(item))
            if workbench_case_consistency_service.is_case_tracked(
                response_item.get("case_id", ""),
                case_center_case_ids=case_center_case_ids,
            ):
                return {"item": response_item}
            break
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run not found")

    def rerun_case(self, *, run_id: str, db: Session) -> dict[str, Any]:
        store.ensure_dirs()
        case_center_case_ids = workbench_case_consistency_service.load_case_center_case_ids(db)
        run_item = self._service._find_run_item(run_id) if hasattr(self._service, "_find_run_item") else None
        if not run_item:
            run_item = workbench_runtime_service.find_run_item(
                run_id,
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
        case_path = Path(str(run_item.get("case_path", "")))
        if not case_path.exists():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="case file not found for rerun")
        new_job = workbench_runtime_service.start_run(
            project=str(run_item.get("project", "default")),
            case_id=str(run_item.get("case_id", "")).strip() or "UNKNOWN",
            case_path=case_path,
            source="rerun",
            runs_dir=constants.WEB_UI_RUNS_DIR,
            now_iso_fn=store.now_iso,
            build_runtime_execution_record=lambda **kwargs: workbench_runtime_service.build_runtime_execution_record(
                **kwargs,
                normalize_execution_record_payload=_normalize_execution_record_payload,
            ),
            runtime_view_from_entry_fn=_runtime_view_from_entry,
            store_run_job=store.store_run_job,
            append_runtime_run=store.append_runtime_run,
            append_history=store.append_history,
            execute_run_fn=lambda job: workbench_runtime_service.execute_run(
                job,
                build_run_command_fn=lambda case_path_value: workbench_runtime_service.build_run_command(
                    case_path_value,
                    get_python_bin_fn=lambda: workbench_runtime_service.get_python_bin(repo_root=constants.REPO_ROOT),
                    repo_root=constants.REPO_ROOT,
                    allure_results_root=constants.ALLURE_RESULTS_ROOT,
                    environ=os.environ.copy(),
                ),
                now_iso_fn=store.now_iso,
                update_job=store.update_run_job,
                update_runtime_run=store.update_runtime_run,
                load_runtime_execution_record_from_artifacts=lambda artifacts_dir: workbench_runtime_service.load_runtime_execution_record_from_artifacts(
                    artifacts_dir,
                    normalize_evidence_manifest_payload=lambda payload: payload if isinstance(payload, dict) else {},
                    resolve_manifest_entries_fn=lambda entries, root: workbench_runtime_service.resolve_manifest_entries(entries, root=root),
                    load_execution_record_payload_fn=lambda path: workbench_runtime_service.load_execution_record_payload(
                        path,
                        normalize_execution_record_payload=_normalize_execution_record_payload,
                    ),
                ),
                collect_failure_entries=lambda: workbench_reporting_service.collect_failure_entries(
                    collect_failure_entries_with_meta_fn=lambda: workbench_reporting_service.collect_failure_entries_with_meta(
                        compat_scan_enabled=False,
                        artifact_roots=[constants.RUNNER_ROOT / "artifacts", *sorted(constants.WEB_UI_RUNS_DIR.glob("*-artifacts"))],
                        logger=None,
                        normalize_evidence_manifest_payload=lambda payload: payload if isinstance(payload, dict) else {},
                        resolve_manifest_entries=lambda entries, root: workbench_runtime_service.resolve_manifest_entries(entries, root=root),
                        load_execution_record_payload=lambda path: workbench_runtime_service.load_execution_record_payload(
                            path,
                            normalize_execution_record_payload=_normalize_execution_record_payload,
                        ),
                        parse_analysis_file=workbench_reporting_service.parse_analysis_file,
                    ),
                ),
                is_within=_is_within,
                repo_root=constants.REPO_ROOT,
                runner_root=constants.RUNNER_ROOT,
            ),
        )
        store.append_history(
            {
                "timestamp": store.now_iso(),
                "action": "rerun_case",
                "case_id": run_item.get("case_id", ""),
                "from_run_id": run_id,
                "run_id": new_job["run_id"],
                "path": str(case_path.resolve()),
                "queue_status": "queued",
            }
        )
        return {"item": new_job}

    def list_defects(self, *, case_id: str, db: Session) -> dict[str, Any]:
        store.ensure_dirs()
        case_center_case_ids = workbench_case_consistency_service.load_case_center_case_ids(db)
        items = workbench_reporting_service.list_defect_items(
            case_id,
            read_items=lambda: store.list_defect_items(case_id),
        )
        filtered_items, _filter_meta = workbench_case_consistency_service.filter_records_by_case_center(
            items,
            case_center_case_ids=case_center_case_ids,
        )
        return {"items": filtered_items}

    def add_defect(self, payload: Any, db: Session) -> dict[str, Any]:
        store.ensure_dirs()
        case_center_case_ids = workbench_case_consistency_service.load_case_center_case_ids(db)
        if not workbench_case_consistency_service.is_case_tracked(
            payload.case_id,
            case_center_case_ids=case_center_case_ids,
        ):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="case_id not found in case center")
        with store.FILE_LOCK:
            entry = workbench_reporting_service.add_defect_item(
                case_id=payload.case_id,
                defect_id=payload.defect_id,
                defect_url=payload.defect_url,
                system=payload.system,
                note=payload.note,
                read_items=lambda: store.read_json_list(store.DEFECT_LINKS_FILE),
                write_items=lambda items: store.write_json_list(store.DEFECT_LINKS_FILE, items),
            )
        return {"item": entry}

    def report_overview(self, response: Response, db: Session) -> dict[str, Any]:
        store.ensure_dirs()
        workbench_reporting_service.apply_no_store_headers(response)
        case_center_case_ids = workbench_case_consistency_service.load_case_center_case_ids(db)

        def _collect_execution_records_with_meta_filtered(*, limit: int = 1000) -> tuple[list[dict[str, Any]], dict[str, Any]]:
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

        def _collect_failure_entries_filtered() -> list[dict[str, Any]]:
            entries, _meta = _collect_failure_entries_with_meta()
            filtered_entries, _filter_meta = workbench_case_consistency_service.filter_records_by_case_center(
                entries,
                case_center_case_ids=case_center_case_ids,
            )
            return filtered_entries

        def _read_defect_items_filtered() -> list[dict[str, Any]]:
            items = store.list_defect_items()
            filtered_items, _filter_meta = workbench_case_consistency_service.filter_records_by_case_center(
                items,
                case_center_case_ids=case_center_case_ids,
            )
            return filtered_items

        return workbench_reporting_service.build_report_overview(
            collect_execution_records_with_meta=_collect_execution_records_with_meta_filtered,
            normalize_execution_meta=workbench_reporting_service.normalize_execution_meta,
            collect_failure_entries=_collect_failure_entries_filtered,
            normalize_failure_analysis_view=workbench_reporting_service.normalize_failure_analysis_view,
            read_defect_items=_read_defect_items_filtered,
        )

    def report_failures(
        self,
        *,
        response: Response,
        case_id: str,
        keyword: str,
        defect_status: str,
        db: Session,
    ) -> dict[str, Any]:
        store.ensure_dirs()
        workbench_reporting_service.apply_no_store_headers(response)
        case_center_case_ids = workbench_case_consistency_service.load_case_center_case_ids(db)

        def _collect_failure_entries_with_meta_filtered() -> tuple[list[dict[str, Any]], dict[str, Any]]:
            entries, meta = _collect_failure_entries_with_meta()
            filtered_entries, _filter_meta = workbench_case_consistency_service.filter_records_by_case_center(
                entries,
                case_center_case_ids=case_center_case_ids,
            )
            return filtered_entries, meta

        def _read_defect_items_filtered() -> list[dict[str, Any]]:
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
        store.ensure_dirs()
        workbench_reporting_service.apply_no_store_headers(response)
        case_center_case_ids = workbench_case_consistency_service.load_case_center_case_ids(db)
        commit_id = ""
        commit_message = ""
        branch_name = ""
        try:
            commit_id = (
                subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(constants.REPO_ROOT), capture_output=True, text=True, check=False)
                .stdout.strip()
            )
            commit_message = (
                subprocess.run(["git", "log", "-1", "--pretty=%s"], cwd=str(constants.REPO_ROOT), capture_output=True, text=True, check=False)
                .stdout.strip()
            )
            branch_name = (
                subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=str(constants.REPO_ROOT), capture_output=True, text=True, check=False)
                .stdout.strip()
            )
        except Exception:
            pass

        def _collect_execution_records_with_meta_filtered(*, limit: int = 1000) -> tuple[list[dict[str, Any]], dict[str, Any]]:
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
            base_url=os.getenv("BASE_URL", "http://localhost:5173/login#/login"),
            browser=os.getenv("PLAYWRIGHT_BROWSER", "chromium"),
            environment=os.getenv("APP_ENV", "local"),
        )

    def report_performance(self, *, response: Response, db: Session) -> dict[str, Any]:
        store.ensure_dirs()
        workbench_reporting_service.apply_no_store_headers(response)
        case_center_case_ids = workbench_case_consistency_service.load_case_center_case_ids(db)

        def _collect_execution_records_with_meta_filtered(*, limit: int = 1000) -> tuple[list[dict[str, Any]], dict[str, Any]]:
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
        workbench_reporting_service.apply_no_store_headers(response)
        return workbench_reporting_service.build_report_allure(
            available=(constants.ALLURE_REPORT_ROOT / "index.html").exists(),
            read_allure_summary=lambda: workbench_reporting_service.read_allure_summary(
                allure_report_root=constants.ALLURE_REPORT_ROOT
            ),
            ensure_allure_snapshot=lambda version: workbench_reporting_service.ensure_allure_snapshot(
                version=version,
                allure_report_root=constants.ALLURE_REPORT_ROOT,
                allure_snapshots_root=constants.ALLURE_SNAPSHOTS_ROOT,
            ),
            get_allure_index_version=lambda: workbench_reporting_service.get_allure_index_version(
                allure_report_root=constants.ALLURE_REPORT_ROOT
            ),
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
            normalized_project_code = _normalize_optional_project_code(project_code_value_raw)
            if not normalized_project_code:
                return "active"
            if normalized_project_code not in project_status_cache:
                project_status_cache[normalized_project_code] = test_project_service.get_project_status(
                    db,
                    normalized_project_code,
                )
            return project_status_cache[normalized_project_code]

        payload = workbench_history_service.list_history(
            history_items,
            resolve_governance_snapshot=lambda run_id: workbench_reporting_service.resolve_run_governance_snapshot(
                run_id,
                find_run_item=_find_run_item,
                build_risk_report_summary=workbench_analysis_service.build_risk_report_summary,
                build_self_healing_summary=workbench_analysis_service.build_self_healing_summary,
                build_page_semantic_summary=workbench_analysis_service.build_page_semantic_summary,
            ),
            resolve_failure_snapshot=lambda run_id: workbench_reporting_service.resolve_run_failure_snapshot(
                run_id,
                find_run_item=_find_run_item,
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

    def cleanup_case_consistency(self, *, purge_all: bool, db: Session) -> dict[str, Any]:
        store.ensure_dirs()
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
        store.ensure_dirs()
        case_center_case_ids = workbench_case_consistency_service.load_case_center_case_ids(db)
        run_item = _find_run_item(run_id)
        if not run_item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run not found")
        if not workbench_case_consistency_service.is_case_tracked(
            run_item.get("case_id", ""),
            case_center_case_ids=case_center_case_ids,
        ):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run not found")
        log_path = constants.WEB_UI_RUNS_DIR / f"{run_id}.log"
        if not log_path.exists():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="log not found")
        return Response(
            content=log_path.read_text(encoding="utf-8", errors="ignore"),
            media_type="text/plain; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename={run_id}.log"},
        )

    def dashboard_overview(self, db: Session) -> dict[str, Any]:
        now = datetime.now(UTC)
        try:
            test_case_service.ensure_seed_data(db)
            cases = db.execute(select(TestCase).order_by(TestCase.id.asc())).scalars().all()
            executions = db.execute(select(TestCaseExecution).order_by(TestCaseExecution.executed_at.desc())).scalars().all()
            case_map = {item.id: item for item in cases}

            base = (now - timedelta(hours=23)).replace(minute=0, second=0, microsecond=0)
            buckets: dict[datetime, dict[str, int]] = {
                base + timedelta(hours=i): {"total": 0, "passed": 0}
                for i in range(24)
            }
            for item in executions:
                executed_at = _to_utc(item.executed_at).replace(minute=0, second=0, microsecond=0)
                if executed_at not in buckets:
                    continue
                buckets[executed_at]["total"] += 1
                if (item.status or "").lower() == "passed":
                    buckets[executed_at]["passed"] += 1

            total = sum(v["total"] for v in buckets.values())
            passed = sum(v["passed"] for v in buckets.values())
            base_pass_rate = round((passed / total * 100) if total > 0 else 100.0, 1)

            trend: list[dict[str, Any]] = []
            for i in range(24):
                hour = base + timedelta(hours=i)
                total_runs = buckets[hour]["total"]
                pass_rate = round((buckets[hour]["passed"] / total_runs * 100), 1) if total_runs > 0 else base_pass_rate
                trend.append(
                    {
                        "hour": hour.strftime("%H:%M"),
                        "pass_rate": pass_rate,
                        "execution_count": total_runs,
                    }
                )

            case_runs: dict[int, list[TestCaseExecution]] = defaultdict(list)
            for item in executions:
                case_runs[item.case_id].append(item)

            flaky_rows: list[dict[str, Any]] = []
            for case_id, case in {item.id: item for item in cases}.items():
                runs = sorted(case_runs.get(case_id, []), key=lambda item: (_to_utc(item.executed_at), item.id))
                statuses = [(item.status or "unknown").lower() for item in runs]
                total_runs = len(statuses)
                if total_runs >= 2:
                    transitions = sum(1 for idx in range(1, total_runs) if statuses[idx] != statuses[idx - 1])
                    failed = sum(1 for value in statuses if value == "failed")
                    transition_ratio = transitions / (total_runs - 1)
                    failed_ratio = failed / total_runs
                    flaky_rate = round(min(100.0, transition_ratio * 70 + failed_ratio * 30), 1)
                    unstable_runs = transitions
                else:
                    seed = ((case_id * 17) % 25) + 8
                    last = (case.last_execution_result or "unknown").lower()
                    if last == "failed":
                        flaky_rate = min(98.0, float(seed + 24))
                    elif last == "skipped":
                        flaky_rate = min(90.0, float(seed + 12))
                    else:
                        flaky_rate = float(seed)
                    unstable_runs = 0
                flaky_rows.append(
                    {
                        "case_id": case_id,
                        "name": case.name,
                        "module": case.module,
                        "flaky_rate": flaky_rate,
                        "total_runs": total_runs,
                        "unstable_runs": unstable_runs,
                        "last_result": case.last_execution_result or "unknown",
                    }
                )
            flaky_rows = sorted(flaky_rows, key=lambda item: item["flaky_rate"], reverse=True)[:5]

            sorted_runs = sorted(executions, key=lambda item: (_to_utc(item.executed_at), item.id), reverse=True)[:10]
            gate_rows: list[dict[str, Any]] = []
            for item in sorted_runs:
                item_status = (item.status or "unknown").lower()
                if item_status == "failed":
                    gate_status = "intercepted"
                    reason = "失败率超过门禁阈值"
                elif item_status == "passed":
                    gate_status = "passed"
                    reason = "门禁规则校验通过"
                else:
                    gate_status = "warning"
                    reason = "前置数据不足，需人工复核"
                case = case_map.get(item.case_id)
                gate_rows.append(
                    {
                        "execution_id": item.id,
                        "pr_key": f"PR-{6800 + item.id}",
                        "branch": f"feature/case-{item.case_id}",
                        "gate_rule": "主分支质量门禁",
                        "gate_status": gate_status,
                        "reason": reason,
                        "case_name": case.name if case else f"用例#{item.case_id}",
                        "executed_at": _to_utc(item.executed_at).isoformat(),
                    }
                )
            if len(gate_rows) < 10:
                for index in range(len(gate_rows), 10):
                    gate_rows.append(
                        {
                            "execution_id": 0,
                            "pr_key": f"PR-NA-{index + 1}",
                            "branch": "-",
                            "gate_rule": "主分支质量门禁",
                            "gate_status": "warning",
                            "reason": "历史门禁样本不足",
                            "case_name": "-",
                            "executed_at": (now - timedelta(hours=index + 1)).isoformat(),
                        }
                    )

            sorted_runs_desc = sorted(executions, key=lambda item: (_to_utc(item.executed_at), item.id), reverse=True)
            pending_issues: list[dict[str, Any]] = []
            for item in sorted_runs_desc:
                item_status = (item.status or "unknown").lower()
                if item_status not in {"failed", "skipped"}:
                    continue
                case = case_map.get(item.case_id)
                if item_status == "failed":
                    recommendation = "疑似断言与页面状态不一致，建议先复核选择器和等待策略。"
                    confidence = 0.82 + ((item.id % 7) * 0.01)
                else:
                    recommendation = "疑似环境前置条件未满足，建议检查测试数据和依赖服务健康度。"
                    confidence = 0.68 + ((item.id % 5) * 0.01)
                pending_issues.append(
                    {
                        "issue_key": f"ISS-{9000 + item.id}",
                        "title": f"{case.name if case else f'用例#{item.case_id}'} 待确认",
                        "agent": "失败归因 Agent",
                        "confidence": round(min(confidence, 0.95), 2),
                        "status": "待确认",
                        "recommendation": recommendation,
                        "detail_url": f"/cases/{item.case_id}",
                    }
                )
                if len(pending_issues) >= 6:
                    break
            if not pending_issues:
                for idx, row in enumerate(flaky_rows[:3], start=1):
                    pending_issues.append(
                        {
                            "issue_key": f"ISS-F{idx:03d}",
                            "title": f"{row['name']} 波动风险复核",
                            "agent": "失败归因 Agent",
                            "confidence": round(min(0.6 + row["flaky_rate"] / 200, 0.93), 2),
                            "status": "待确认",
                            "recommendation": "建议补充稳定性断言并提高重试与隔离策略。",
                            "detail_url": f"/cases/{row['case_id']}",
                        }
                    )

            total_runs = len(executions)
            failed_runs = sum(1 for item in executions if (item.status or "").lower() == "failed")
            pass_runs = sum(1 for item in executions if (item.status or "").lower() == "passed")
            pass_rate = round((pass_runs / total_runs * 100) if total_runs else 100.0, 1)
            fail_rate = (failed_runs / total_runs * 100) if total_runs else 0.0
            flaky_avg = (sum(item["flaky_rate"] for item in flaky_rows) / len(flaky_rows)) if flaky_rows else 0.0
            intercepted_count = sum(1 for item in gate_rows if item["gate_status"] == "intercepted")

            risk_score = int(min(100, fail_rate * 0.55 + flaky_avg * 0.30 + intercepted_count * 4.5))
            if risk_score >= 70:
                risk_level = "高"
                risk_summary = "主分支风险偏高，建议先处理高优先级失败与Flaky用例。"
            elif risk_score >= 40:
                risk_level = "中"
                risk_summary = "主分支风险可控，但仍需关注波动用例与门禁告警。"
            else:
                risk_level = "低"
                risk_summary = "主分支风险较低，可继续推进回归与发布节奏。"

            return {
                "as_of": now.isoformat(),
                "risk": {
                    "score": risk_score,
                    "level": risk_level,
                    "summary": risk_summary,
                    "detail_url": "/quality/trends",
                },
                "summary": {
                    "pass_rate_24h": trend[-1]["pass_rate"] if trend else pass_rate,
                    "execution_count_24h": sum(item["execution_count"] for item in trend),
                    "intercepted_last10": intercepted_count,
                    "pending_issues": len(pending_issues),
                    "as_of": now.isoformat(),
                },
                "trend_24h": trend,
                "top_flaky": flaky_rows,
                "gate_last10": gate_rows,
                "pending_issues": pending_issues,
            }
        except Exception:
            LOGGER.exception("dashboard overview degraded due to backend error")
            return _default_overview(now, reason="dashboard_backend_error")

    def dashboard_governance(self, db: Session) -> dict[str, Any]:
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
            cases = db.execute(select(TestCase).order_by(TestCase.id.asc())).scalars().all()
            executions = db.execute(select(TestCaseExecution).order_by(TestCaseExecution.executed_at.desc())).scalars().all()
            case_map = {item.id: item for item in cases}
            case_runs: dict[int, list[TestCaseExecution]] = defaultdict(list)
            for item in executions:
                case_runs[item.case_id].append(item)
            flaky_rows: list[dict[str, Any]] = []
            for case_id, case in case_map.items():
                runs = sorted(case_runs.get(case_id, []), key=lambda item: (_to_utc(item.executed_at), item.id))
                statuses = [(item.status or "unknown").lower() for item in runs]
                total_runs = len(statuses)
                if total_runs >= 2:
                    transitions = sum(1 for idx in range(1, total_runs) if statuses[idx] != statuses[idx - 1])
                    failed = sum(1 for value in statuses if value == "failed")
                    transition_ratio = transitions / (total_runs - 1)
                    failed_ratio = failed / total_runs
                    flaky_rate = round(min(100.0, transition_ratio * 70 + failed_ratio * 30), 1)
                    unstable_runs = transitions
                else:
                    seed = ((case_id * 17) % 25) + 8
                    last = (case.last_execution_result or "unknown").lower()
                    if last == "failed":
                        flaky_rate = min(98.0, float(seed + 24))
                    elif last == "skipped":
                        flaky_rate = min(90.0, float(seed + 12))
                    else:
                        flaky_rate = float(seed)
                    unstable_runs = 0
                flaky_rows.append(
                    {
                        "case_id": case_id,
                        "name": case.name,
                        "module": case.module,
                        "flaky_rate": flaky_rate,
                        "total_runs": total_runs,
                        "unstable_runs": unstable_runs,
                        "last_result": case.last_execution_result or "unknown",
                    }
                )
            flaky_payload = {"top_flaky": sorted(flaky_rows, key=lambda item: item["flaky_rate"], reverse=True)[:5]}
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
        store.ensure_dirs()
        execution_rows, _execution_meta_raw = _collect_execution_records_with_meta(limit=max(limit * 3, 200))
        items = [
            _build_execution_task_view(row)
            for row in execution_rows
        ][:limit]
        return {"item": workbench_scheduler_service.build_scheduler_dispatch_plan(items=items)}




def build_workbench_facade(service: WorkbenchService | None = None) -> WorkbenchFacade:
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
