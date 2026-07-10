from __future__ import annotations

import os
import subprocess
from datetime import datetime
from functools import partial
from pathlib import Path
from typing import Any

from app.api.workbench import constants, store
from app.core import page_analysis_rules
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.services import (
    test_data_pool_service,
    test_project_service,
    workbench_analysis_service,
    workbench_asset_service,
    workbench_case_consistency_service,
    workbench_gate_service,
    workbench_project_service,
    workbench_reporting_service,
    workbench_review_service,
    workbench_runtime_service,
    workbench_task_service,
)
from fastapi import HTTPException, status

from datetime_compat import UTC
from shared_backend.case_ids import normalize_case_id


def _safe_case_id(raw: str) -> str:
    text = str(raw).strip()
    return normalize_case_id(text) if text else "atp-web-common-core-fn-ai-0001"


def _normalize_execution_record_payload(payload: dict[str, Any], *, strict: bool = False) -> dict[str, Any]:
    return payload if isinstance(payload, dict) else {}


def _shim_callable(name: str, default_impl: Any, *, current: Any | None = None) -> Any:
    _ = name
    _ = current
    return default_impl


def _utc_now() -> datetime:
    return datetime.now(UTC)


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


def _normalize_page_slug(value: str) -> str:
    return workbench_gate_service.normalize_page_slug(value)


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except Exception:
        return False


def _resolve_case_yaml_path(project: str, case_id: str) -> Path:
    return workbench_asset_service.resolve_case_yaml_path(
        project,
        case_id,
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


def _get_python_bin() -> str:
    return workbench_runtime_service.get_python_bin(repo_root=constants.REPO_ROOT)


def _build_runtime_execution_record(
    *,
    run_id: str,
    case_id: str,
    project: str,
    source: str,
    mode: str,
    status: str,
    started_at: str,
    finished_at: str,
    return_code: int | None,
    created_at: str = "",
) -> dict[str, Any]:
    return workbench_runtime_service.build_runtime_execution_record(
        run_id=run_id,
        case_id=case_id,
        project=project,
        source=source,
        mode=mode,
        status=status,
        started_at=started_at,
        finished_at=finished_at,
        return_code=return_code,
        created_at=created_at,
        normalize_execution_record_payload=_normalize_execution_record_payload,
    )


def _runtime_view_from_entry(entry: dict[str, Any]) -> dict[str, Any]:
    return _shim_callable(
        "_runtime_view_from_entry",
        lambda value: dict(value) if isinstance(value, dict) else {},
        current=_runtime_view_from_entry,
    )(entry)


def _load_runtime_execution_record_from_artifacts(artifacts_dir: Path) -> dict[str, Any]:
    return _shim_callable(
        "_load_runtime_execution_record_from_artifacts",
        lambda value: workbench_runtime_service.load_runtime_execution_record_from_artifacts(
            value,
            normalize_evidence_manifest_payload=lambda payload: payload if isinstance(payload, dict) else {},
            resolve_manifest_entries_fn=lambda entries, root: workbench_runtime_service.resolve_manifest_entries(entries, root=root),
            load_execution_record_payload_fn=lambda path: workbench_runtime_service.load_execution_record_payload(
                path,
                normalize_execution_record_payload=_normalize_execution_record_payload,
            ),
        ),
        current=_load_runtime_execution_record_from_artifacts,
    )(
        artifacts_dir,
    )


def _runtime_view_with_execution_record_preferred(entry: dict[str, Any]) -> dict[str, Any]:
    return _shim_callable(
        "_runtime_view_with_execution_record_preferred",
        lambda value: workbench_runtime_service.runtime_view_with_execution_record_preferred(
            value,
            runtime_view_from_entry_fn=_runtime_view_from_entry,
            load_runtime_execution_record_from_artifacts=_load_runtime_execution_record_from_artifacts,
            normalize_execution_record_payload=_normalize_execution_record_payload,
        ),
        current=_runtime_view_with_execution_record_preferred,
    )(
        entry,
    )


def _collect_failure_entries_with_meta() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    settings = get_settings()
    compat_scan_enabled = bool(getattr(settings, "evidence_manifest_compat_scan_enabled", True))
    return _shim_callable(
        "_collect_failure_entries_with_meta",
        lambda: workbench_reporting_service.collect_failure_entries_with_meta(
            compat_scan_enabled=compat_scan_enabled,
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
        current=_collect_failure_entries_with_meta,
    )()


def _collect_failure_entries() -> list[dict[str, Any]]:
    return _shim_callable(
        "_collect_failure_entries",
        lambda: _collect_failure_entries_with_meta()[0],
        current=_collect_failure_entries,
    )()


def _normalize_failure_entry_view(entry: dict[str, Any] | None) -> dict[str, Any]:
    return _shim_callable(
        "_normalize_failure_entry_view",
        lambda value: value if isinstance(value, dict) else {},
        current=_normalize_failure_entry_view,
    )(entry)


def _append_history(entry: dict[str, Any]) -> None:
    _shim_callable("_append_history", store.append_history, current=_append_history)(entry)


def _append_runtime_run(entry: dict[str, Any]) -> None:
    _shim_callable("_append_runtime_run", store.append_runtime_run, current=_append_runtime_run)(entry)


def _update_runtime_run(run_id: str, updates: dict[str, Any]) -> None:
    _shim_callable("_update_runtime_run", store.update_runtime_run, current=_update_runtime_run)(run_id, updates)


def _read_json_list(path: Path) -> list[dict[str, Any]]:
    return _shim_callable("_read_json_list", store.read_json_list, current=_read_json_list)(path)


def _write_json_list(path: Path, items: list[dict[str, Any]]) -> None:
    _shim_callable("_write_json_list", store.write_json_list, current=_write_json_list)(path, items)


def _ensure_dirs() -> None:
    _shim_callable("_ensure_dirs", store.ensure_dirs, current=_ensure_dirs)()


def _runtime_run_id(item: dict[str, Any]) -> str:
    return _shim_callable(
        "_runtime_run_id",
        workbench_runtime_service.runtime_run_id,
        current=_runtime_run_id,
    )(item)


def _execution_record_time_value(record: dict[str, Any]) -> str:
    return _shim_callable(
        "_execution_record_time_value",
        workbench_task_service.execution_record_time_value,
        current=_execution_record_time_value,
    )(record)


def _build_execution_task_view(entry: dict[str, Any]) -> dict[str, Any]:
    return _shim_callable(
        "_build_execution_task_view",
        lambda value: workbench_task_service.build_execution_task_view(
            value,
            normalize_execution_record_payload=_normalize_execution_record_payload,
            build_task_evidence_freshness_fn=workbench_task_service.build_task_evidence_freshness,
            utc_now=_utc_now,
            parse_iso_datetime=_parse_iso_datetime,
        ),
        current=_build_execution_task_view,
    )(entry)


def _build_execution_task_summary(
    *,
    items: list[dict[str, Any]],
    filter_snapshot: dict[str, Any],
    execution_meta: dict[str, Any],
) -> dict[str, Any]:
    return workbench_task_service.build_execution_task_summary(
        items=items,
        filter_snapshot=filter_snapshot,
        execution_meta=execution_meta,
        build_task_governance_risk_fn=workbench_task_service.build_task_governance_risk,
    )


def _collect_execution_records_with_meta(*, limit: int = 1000) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    return workbench_task_service.collect_execution_records_with_meta(
        limit=limit,
        compat_scan_enabled=bool(get_settings().evidence_manifest_compat_scan_enabled),
        artifact_roots=[constants.RUNNER_ROOT / "artifacts", *sorted(constants.WEB_UI_RUNS_DIR.glob("*-artifacts"))],
        logger=None,
        normalize_evidence_manifest_payload=lambda payload: payload if isinstance(payload, dict) else {},
        resolve_manifest_entries=lambda entries, root: workbench_runtime_service.resolve_manifest_entries(entries, root=root),
        load_execution_record_payload=lambda path: workbench_runtime_service.load_execution_record_payload(
            path,
            normalize_execution_record_payload=_normalize_execution_record_payload,
        ),
        execution_record_time_value=workbench_task_service.execution_record_time_value,
        runtime_jobs=store.list_run_jobs(),
        runtime_runs_file=store.RUNTIME_RUNS_FILE,
        runtime_view_from_entry=_runtime_view_from_entry,
        read_json_list=store.read_json_list,
        normalize_execution_record_payload=_normalize_execution_record_payload,
    )


def _sync_stage_a_workbench_state(*args: Any, **kwargs: Any) -> None:
    return None


def _sync_stage_b_workbench_gate(*args: Any, **kwargs: Any) -> None:
    return None


def _build_run_command(case_path: Path) -> tuple[list[str], dict[str, str]]:
    # 合法例外：后台执行线程无 db Session，需短暂创建独立 Session 获取数据池快照
    runner_environ = os.environ.copy()
    with SessionLocal() as db:
        runner_environ["DSL_DATA_POOL_JSON"] = test_data_pool_service.serialize_runner_data_pool_snapshot(db)
    return workbench_runtime_service.build_run_command(
        case_path,
        get_python_bin_fn=_get_python_bin,
        repo_root=constants.REPO_ROOT,
        allure_results_root=constants.ALLURE_RESULTS_ROOT,
        environ=runner_environ,
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


def _start_run(*, project: str, case_id: str, case_path: Path, source: str) -> dict[str, Any]:
    return workbench_runtime_service.start_run(
        project=project,
        case_id=case_id,
        case_path=case_path,
        source=source,
        runs_dir=constants.WEB_UI_RUNS_DIR,
        now_iso_fn=store.now_iso,
        build_runtime_execution_record=_build_runtime_execution_record,
        runtime_view_from_entry_fn=_runtime_view_from_entry,
        store_run_job=store.store_run_job,
        append_runtime_run=store.append_runtime_run,
        append_history=store.append_history,
        execute_run_fn=_execute_run,
    )


class WorkbenchService:
    def list_projects(self, db: Any) -> dict[str, Any]:
        store.ensure_dirs()
        items = workbench_project_service.list_project_items(db, state_root=constants.TEST_POINTS_ROOT)
        return {
            "items": items,
            "codes": [str(item.get("project_code", "")).strip().lower() for item in items if item.get("project_code")],
        }

    def list_execution_tasks(self, **kwargs: Any) -> dict[str, Any]:
        db = kwargs.pop("db", None)
        limit = int(kwargs.pop("limit", 50))
        project_code = str(kwargs.pop("project_code", "") or "").strip().lower()
        status = str(kwargs.pop("status", "") or "").strip().lower()
        queue_status = str(kwargs.pop("queue_status", "") or "").strip().lower()
        source = str(kwargs.pop("source", "") or "").strip().lower()
        evidence_health_status = str(kwargs.pop("evidence_health_status", "") or "").strip().lower()
        evidence_freshness_status = str(kwargs.pop("evidence_freshness_status", "") or "").strip().lower()
        manifest_action = str(kwargs.pop("manifest_action", "") or "").strip().lower()
        strict_mode_status = str(kwargs.pop("strict_mode_status", "") or "").strip().lower()
        retry_enabled = kwargs.pop("retry_enabled", "")
        has_dependencies = kwargs.pop("has_dependencies", "")
        store.ensure_dirs()
        case_center_case_ids = workbench_case_consistency_service.load_case_center_case_ids(db)
        execution_rows, execution_meta_raw = _collect_execution_records_with_meta(limit=max(limit * 3, 200))
        execution_meta = workbench_reporting_service.normalize_execution_meta(execution_meta_raw)
        retry_enabled_value = workbench_task_service.parse_optional_bool_query(retry_enabled)
        has_dependencies_value = workbench_task_service.parse_optional_bool_query(has_dependencies)
        project_status_cache: dict[str, str] = {}

        def resolve_project_status(project_code_value_raw: str) -> str:
            normalized_project_code = str(project_code_value_raw or "").strip().lower()
            if not normalized_project_code:
                return "active"
            if normalized_project_code not in project_status_cache:
                project_status_cache[normalized_project_code] = test_project_service.get_project_status(
                    db,
                    normalized_project_code,
                )
            return project_status_cache[normalized_project_code]

        items: list[dict[str, Any]] = []
        for row in execution_rows:
            task = _build_execution_task_view(row)
            task_project_code = str(task.get("project_code") or task.get("project") or "").strip().lower()
            if project_code and task_project_code != project_code:
                continue
            if not workbench_case_consistency_service.is_case_tracked(
                task.get("case_id", ""),
                case_center_case_ids=case_center_case_ids,
            ):
                continue
            if status and str(task.get("status", "")).strip().lower() != status:
                continue
            if queue_status and str(task.get("queue_status", "")).strip().lower() != queue_status:
                continue
            if source and str(task.get("source", "")).strip().lower() != source:
                continue
            evidence_health = task.get("evidence_health", {}) if isinstance(task.get("evidence_health"), dict) else {}
            if evidence_health_status and str(evidence_health.get("status", "")).strip().lower() != evidence_health_status:
                continue
            evidence_freshness = task.get("evidence_freshness", {}) if isinstance(task.get("evidence_freshness"), dict) else {}
            if evidence_freshness_status and str(evidence_freshness.get("status", "")).strip().lower() != evidence_freshness_status:
                continue
            if manifest_action and str(task.get("manifest_action", "")).strip().lower() != manifest_action:
                continue
            strict_mode = task.get("strict_mode", {}) if isinstance(task.get("strict_mode"), dict) else {}
            if strict_mode_status and str(strict_mode.get("status", "")).strip().lower() != strict_mode_status:
                continue
            retry = task.get("retry", {}) if isinstance(task.get("retry"), dict) else {}
            if retry_enabled_value is not None and bool(retry.get("enabled", False)) != retry_enabled_value:
                continue
            dependency = task.get("dependency", {}) if isinstance(task.get("dependency"), dict) else {}
            if has_dependencies_value is not None and bool(dependency.get("has_dependencies", False)) != has_dependencies_value:
                continue
            task["project_code"] = task_project_code or str(task.get("project", "")).strip().lower()
            task["project_status"] = resolve_project_status(task["project_code"])
            items.append(task)
            if len(items) >= limit:
                break
        filter_snapshot = {
            "project_code": project_code,
            "status": status,
            "queue_status": queue_status,
            "source": source,
            "evidence_health_status": evidence_health_status,
            "evidence_freshness_status": evidence_freshness_status,
            "manifest_action": manifest_action,
            "strict_mode_status": strict_mode_status,
            "retry_enabled": "" if retry_enabled_value is None else str(retry_enabled_value).lower(),
            "has_dependencies": "" if has_dependencies_value is None else str(has_dependencies_value).lower(),
        }
        return {
            "items": items,
            "summary": _build_execution_task_summary(items=items, filter_snapshot=filter_snapshot, execution_meta=execution_meta),
        }

    def get_execution_task(self, task_id: str, db: Any) -> dict[str, Any]:
        store.ensure_dirs()
        case_center_case_ids = workbench_case_consistency_service.load_case_center_case_ids(db)
        normalized_task_id = str(task_id or "").strip()
        if not normalized_task_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="task not found")
        execution_rows, execution_meta_raw = _collect_execution_records_with_meta(limit=1000)
        execution_meta = workbench_reporting_service.normalize_execution_meta(execution_meta_raw)
        for row in execution_rows:
            task = _build_execution_task_view(row)
            if str(task.get("task_id", "")).strip() == normalized_task_id:
                if not workbench_case_consistency_service.is_case_tracked(
                    task.get("case_id", ""),
                    case_center_case_ids=case_center_case_ids,
                ):
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="task not found")
                task_project_code = str(task.get("project_code") or task.get("project") or "").strip().lower()
                task["project_code"] = task_project_code or str(task.get("project", "")).strip().lower()
                task["project_status"] = test_project_service.get_project_status(db, task["project_code"])
                return {"item": task, "meta": execution_meta}
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="task not found")

    def get_execution_gate_config(self) -> dict[str, Any]:
        settings = get_settings()
        policy_baseline = workbench_gate_service.execution_gate_policy_baseline()
        return {
            "item": {
                "version": "ExecutionGateConfigV1",
                "block_missing_required_threshold": max(
                    1,
                    int(getattr(settings, "execution_gate_block_missing_required_threshold", 2) or 2),
                ),
                "block_on_failed_status": bool(getattr(settings, "execution_gate_block_on_failed_status", True)),
                "block_on_risk_block": bool(getattr(settings, "execution_gate_block_on_risk_block", True)),
                "warn_on_pending_reviews": bool(getattr(settings, "execution_gate_warn_on_pending_reviews", True)),
                "warn_on_low_confidence_elements": bool(
                    getattr(settings, "execution_gate_warn_on_low_confidence_elements", True)
                ),
                "warn_on_pending_test_points": bool(
                    getattr(settings, "execution_gate_warn_on_pending_test_points", True)
                ),
                "block_missing_dependency_points_threshold": max(
                    1,
                    int(getattr(settings, "execution_gate_block_missing_dependency_points_threshold", 1) or 1),
                ),
                "warn_on_low_confidence_dependency_points": bool(
                    getattr(settings, "execution_gate_warn_on_low_confidence_dependency_points", True)
                ),
                "decision_privileged_roles": [
                    str(item).strip().lower()
                    for item in getattr(settings, "execution_gate_decision_privileged_roles", [])
                    if str(item).strip()
                ],
                "dual_approval_enabled": bool(getattr(settings, "execution_gate_dual_approval_enabled", False)),
                "dual_approval_bypass_roles": [
                    str(item).strip().lower()
                    for item in getattr(settings, "execution_gate_dual_approval_bypass_roles", [])
                    if str(item).strip()
                ],
                "policy_baseline": policy_baseline,
                "updated_at": store.now_iso(),
            }
        }

    def _find_run_item(self, run_id: str) -> dict[str, Any] | None:
        normalized_run_id = str(run_id or "").strip()
        if not normalized_run_id:
            return None
        job = store.get_run_job(normalized_run_id)
        if job:
            return job
        for item in store.read_runtime_run_items():
            if str(item.get("run_id", "")).strip() != normalized_run_id:
                continue
            return _runtime_view_with_execution_record_preferred(dict(item))
        return None

    def _append_execution_gate_history(self, entry: dict[str, Any]) -> None:
        store.append_history(entry)

    def save_execution_gate_decision(self, payload: Any, request: Any, db: Any) -> dict[str, Any]:
        store.ensure_dirs()
        case_center_case_ids = workbench_case_consistency_service.load_case_center_case_ids(db)
        if str(getattr(payload, "case_id", "") or "").strip() and not workbench_case_consistency_service.is_case_tracked(
            getattr(payload, "case_id", ""),
            case_center_case_ids=case_center_case_ids,
        ):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="case_id not found in case center")

        actor = workbench_review_service.extract_review_actor(request)
        try:
            actor = workbench_review_service.require_authenticated_review_actor(actor)
        except HTTPException as exc:
            self._append_execution_gate_history(
                {
                    "timestamp": store.now_iso(),
                    "action": "execution_gate_decision_rejected_auth",
                    "case_id": workbench_gate_service.safe_case_id(payload.case_id) if str(payload.case_id).strip() else "",
                    "page": workbench_gate_service.normalize_page_slug(payload.page) if str(payload.page).strip() else "",
                    "run_id": str(payload.run_id).strip(),
                    "status": "rejected",
                    "detail_summary": "执行门禁决策被拒绝：未登录或身份不可追溯",
                    "confirmed_by": str(actor.get("confirmed_by", "")).strip() or "anonymous",
                    "confirmed_by_role": str(actor.get("confirmed_by_role", "")).strip() or "unknown",
                    "actor_display": workbench_analysis_service.reviewer_display_name(actor),
                    "source": "execution-gate-decision",
                    "note": "review_auth_required",
                }
            )
            raise exc

        try:
            workbench_gate_service.require_execution_gate_decision_permission(actor, payload.decision)
        except HTTPException as exc:
            self._append_execution_gate_history(
                {
                    "timestamp": store.now_iso(),
                    "action": "execution_gate_decision_rejected_permission",
                    "case_id": workbench_gate_service.safe_case_id(payload.case_id) if str(payload.case_id).strip() else "",
                    "page": workbench_gate_service.normalize_page_slug(payload.page) if str(payload.page).strip() else "",
                    "run_id": str(payload.run_id).strip(),
                    "status": "rejected",
                    "detail_summary": "执行门禁决策被拒绝：当前角色无权限",
                    "confirmed_by": str(actor.get("confirmed_by", "")).strip() or "anonymous",
                    "confirmed_by_role": str(actor.get("confirmed_by_role", "")).strip() or "unknown",
                    "actor_display": workbench_analysis_service.reviewer_display_name(actor),
                    "source": "execution-gate-decision",
                    "note": "review_permission_required",
                }
            )
            raise exc

        record = workbench_gate_service.upsert_execution_gate_decision(payload, actor=actor)
        gate_snapshot = workbench_gate_service.resolve_execution_gate_audit_snapshot(
            project=record.get("project", "mall"),
            run_id=record.get("run_id", ""),
            page=record.get("page", ""),
            find_run_item=self._find_run_item,
            normalize_page_slug_fn=workbench_gate_service.normalize_page_slug,
            build_execution_gate_audit_snapshot_fn=workbench_gate_service.build_execution_gate_audit_snapshot,
        )
        gate_reason_summary = str(gate_snapshot.get("gate_reason_summary", "")).strip()
        self._append_execution_gate_history(
            {
                "timestamp": record["updated_at"],
                "action": "execution_gate_decided",
                "case_id": record.get("case_id", ""),
                "page": record.get("page", ""),
                "run_id": record.get("run_id", ""),
                "status": "confirmed",
                "review_type": "execution_gate",
                "detail_summary": f"执行门禁人工决策：{record.get('decision', 'manual_review')}"
                + (f"（{gate_reason_summary}）" if gate_reason_summary else ""),
                "decision": record.get("decision", "manual_review"),
                "approval_status": record.get("approval_status", "approved"),
                "record_status": record.get("record_status", "active"),
                "gate_reason_summary": gate_reason_summary,
                "matched_rules": gate_snapshot.get("matched_rules", []),
                "evidence": gate_snapshot.get("evidence", []),
                "metrics": gate_snapshot.get("metrics", {}),
                "config_snapshot": gate_snapshot.get("config_snapshot", {}),
                "note": record.get("note", ""),
                "confirmed_by": str(record.get("decided_by", "")).strip() or "anonymous",
                "confirmed_by_role": str(record.get("decided_by_role", "")).strip() or "unknown",
                "actor_display": workbench_analysis_service.reviewer_display_name(
                    {
                        "confirmed_by": record.get("decided_by", ""),
                        "confirmed_by_role": record.get("decided_by_role", ""),
                    }
                ),
                "source": "execution-gate-decision",
            }
        )
        return {
            "item": record,
            "summary": {
                "project": record["project"],
                "run_id": record["run_id"],
                "page": record["page"],
                "decision": record["decision"],
                "approval_status": record.get("approval_status", "approved"),
                "record_status": record.get("record_status", "active"),
                "note": record.get("note", ""),
                "decided_by": record.get("decided_by", "anonymous"),
                "decided_by_role": record.get("decided_by_role", "unknown"),
                "updated_at": record["updated_at"],
            },
        }

    def approve_execution_gate_decision(self, payload: Any, request: Any, db: Any) -> dict[str, Any]:
        store.ensure_dirs()
        case_center_case_ids = workbench_case_consistency_service.load_case_center_case_ids(db)
        existing_decision = workbench_gate_service.execution_gate_decision_for_run(
            run_id=payload.run_id,
            project=payload.project,
            page=payload.page,
            read_json_list=store.read_json_list,
        )
        existing_case_id = str(existing_decision.get("case_id", "")).strip()
        if existing_case_id and not workbench_case_consistency_service.is_case_tracked(
            existing_case_id,
            case_center_case_ids=case_center_case_ids,
        ):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="case_id not found in case center")

        actor = workbench_review_service.extract_review_actor(request)
        try:
            actor = workbench_review_service.require_authenticated_review_actor(actor)
        except HTTPException as exc:
            self._append_execution_gate_history(
                {
                    "timestamp": store.now_iso(),
                    "action": "execution_gate_approve_rejected_auth",
                    "case_id": "",
                    "page": workbench_gate_service.normalize_page_slug(payload.page) if str(payload.page).strip() else "",
                    "run_id": str(payload.run_id).strip(),
                    "status": "rejected",
                    "detail_summary": "执行门禁二次审批被拒绝：未登录或身份不可追溯",
                    "confirmed_by": str(actor.get("confirmed_by", "")).strip() or "anonymous",
                    "confirmed_by_role": str(actor.get("confirmed_by_role", "")).strip() or "unknown",
                    "actor_display": workbench_analysis_service.reviewer_display_name(actor),
                    "source": "execution-gate-decision",
                    "note": "review_auth_required",
                }
            )
            raise exc

        record = workbench_gate_service.approve_execution_gate_decision(
            project=payload.project,
            run_id=payload.run_id,
            page=payload.page,
            actor=actor,
            note=payload.note,
        )
        gate_snapshot = workbench_gate_service.resolve_execution_gate_audit_snapshot(
            project=record.get("project", "mall"),
            run_id=record.get("run_id", ""),
            page=record.get("page", ""),
            find_run_item=self._find_run_item,
            normalize_page_slug_fn=workbench_gate_service.normalize_page_slug,
            build_execution_gate_audit_snapshot_fn=workbench_gate_service.build_execution_gate_audit_snapshot,
        )
        gate_reason_summary = str(gate_snapshot.get("gate_reason_summary", "")).strip()
        self._append_execution_gate_history(
            {
                "timestamp": record["updated_at"],
                "action": "execution_gate_approved",
                "case_id": record.get("case_id", ""),
                "page": record.get("page", ""),
                "run_id": record.get("run_id", ""),
                "status": "confirmed",
                "review_type": "execution_gate",
                "detail_summary": f"执行门禁二次审批通过：{record.get('decision', 'manual_review')}"
                + (f"（{gate_reason_summary}）" if gate_reason_summary else ""),
                "decision": record.get("decision", "manual_review"),
                "approval_status": record.get("approval_status", "approved"),
                "record_status": record.get("record_status", "active"),
                "gate_reason_summary": gate_reason_summary,
                "matched_rules": gate_snapshot.get("matched_rules", []),
                "evidence": gate_snapshot.get("evidence", []),
                "metrics": gate_snapshot.get("metrics", {}),
                "config_snapshot": gate_snapshot.get("config_snapshot", {}),
                "note": record.get("note", ""),
                "confirmed_by": str(record.get("second_approver", "")).strip() or "anonymous",
                "confirmed_by_role": str(record.get("second_approver_role", "")).strip() or "unknown",
                "actor_display": workbench_analysis_service.reviewer_display_name(
                    {
                        "confirmed_by": record.get("second_approver", ""),
                        "confirmed_by_role": record.get("second_approver_role", ""),
                    }
                ),
                "source": "execution-gate-decision",
            }
        )
        return {
            "item": record,
            "summary": {
                "project": record["project"],
                "run_id": record["run_id"],
                "page": record["page"],
                "decision": record["decision"],
                "approval_status": record.get("approval_status", "approved"),
                "record_status": record.get("record_status", "active"),
                "second_approver": record.get("second_approver", ""),
                "second_approver_role": record.get("second_approver_role", ""),
                "updated_at": record["updated_at"],
            },
        }

    def revoke_execution_gate_decision(self, payload: Any, request: Any, db: Any) -> dict[str, Any]:
        store.ensure_dirs()
        case_center_case_ids = workbench_case_consistency_service.load_case_center_case_ids(db)
        existing_decision = workbench_gate_service.execution_gate_decision_for_run(
            run_id=payload.run_id,
            project=payload.project,
            page=payload.page,
            read_json_list=store.read_json_list,
        )
        existing_case_id = str(existing_decision.get("case_id", "")).strip()
        if existing_case_id and not workbench_case_consistency_service.is_case_tracked(
            existing_case_id,
            case_center_case_ids=case_center_case_ids,
        ):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="case_id not found in case center")

        actor = workbench_review_service.extract_review_actor(request)
        try:
            actor = workbench_review_service.require_authenticated_review_actor(actor)
        except HTTPException as exc:
            self._append_execution_gate_history(
                {
                    "timestamp": store.now_iso(),
                    "action": "execution_gate_revoke_rejected_auth",
                    "case_id": "",
                    "page": workbench_gate_service.normalize_page_slug(payload.page) if str(payload.page).strip() else "",
                    "run_id": str(payload.run_id).strip(),
                    "status": "rejected",
                    "detail_summary": "执行门禁撤销被拒绝：未登录或身份不可追溯",
                    "confirmed_by": str(actor.get("confirmed_by", "")).strip() or "anonymous",
                    "confirmed_by_role": str(actor.get("confirmed_by_role", "")).strip() or "unknown",
                    "actor_display": workbench_analysis_service.reviewer_display_name(actor),
                    "source": "execution-gate-decision",
                    "note": "review_auth_required",
                }
            )
            raise exc

        record = workbench_gate_service.revoke_execution_gate_decision(
            project=payload.project,
            run_id=payload.run_id,
            page=payload.page,
            actor=actor,
            note=payload.note,
        )
        gate_snapshot = workbench_gate_service.resolve_execution_gate_audit_snapshot(
            project=record.get("project", "mall"),
            run_id=record.get("run_id", ""),
            page=record.get("page", ""),
            find_run_item=self._find_run_item,
            normalize_page_slug_fn=workbench_gate_service.normalize_page_slug,
            build_execution_gate_audit_snapshot_fn=workbench_gate_service.build_execution_gate_audit_snapshot,
        )
        gate_reason_summary = str(gate_snapshot.get("gate_reason_summary", "")).strip()
        self._append_execution_gate_history(
            {
                "timestamp": record["updated_at"],
                "action": "execution_gate_revoked",
                "case_id": record.get("case_id", ""),
                "page": record.get("page", ""),
                "run_id": record.get("run_id", ""),
                "status": "confirmed",
                "review_type": "execution_gate",
                "detail_summary": f"执行门禁决策已撤销：{record.get('decision', 'manual_review')}"
                + (f"（{gate_reason_summary}）" if gate_reason_summary else ""),
                "decision": record.get("decision", "manual_review"),
                "approval_status": record.get("approval_status", "approved"),
                "record_status": record.get("record_status", "revoked"),
                "gate_reason_summary": gate_reason_summary,
                "matched_rules": gate_snapshot.get("matched_rules", []),
                "evidence": gate_snapshot.get("evidence", []),
                "metrics": gate_snapshot.get("metrics", {}),
                "config_snapshot": gate_snapshot.get("config_snapshot", {}),
                "note": record.get("note", ""),
                "confirmed_by": str(record.get("revoked_by", "")).strip() or "anonymous",
                "confirmed_by_role": str(record.get("revoked_by_role", "")).strip() or "unknown",
                "actor_display": workbench_analysis_service.reviewer_display_name(
                    {
                        "confirmed_by": record.get("revoked_by", ""),
                        "confirmed_by_role": record.get("revoked_by_role", ""),
                    }
                ),
                "source": "execution-gate-decision",
            }
        )
        return {
            "item": record,
            "summary": {
                "project": record["project"],
                "run_id": record["run_id"],
                "page": record["page"],
                "decision": record["decision"],
                "approval_status": record.get("approval_status", "approved"),
                "record_status": record.get("record_status", "revoked"),
                "revoked_by": record.get("revoked_by", ""),
                "revoked_by_role": record.get("revoked_by_role", ""),
                "updated_at": record["updated_at"],
            },
        }

    def save_case(self, case_id: str, payload: Any) -> dict[str, Any]:
        store.ensure_dirs()
        return workbench_asset_service.build_saved_case_payload(
            case_id=case_id,
            project=payload.project,
            yaml_content=payload.yaml_content,
            safe_case_id=_safe_case_id,
            resolve_case_yaml_path=_resolve_case_yaml_path,
            write_case_yaml=workbench_asset_service.write_case_yaml,
            save_case_state=lambda project_code, case_yaml, source_path: workbench_asset_service.save_case_state(
                project_code,
                case_yaml,
                source_path,
                safe_case_id_fn=_safe_case_id,
                now_iso_fn=store.now_iso,
                derive_points_fn=workbench_asset_service.derive_points,
                state_case_file_fn=lambda project_value, case_value: workbench_asset_service.state_case_file(
                    project_value,
                    case_value,
                    state_root=constants.TEST_POINTS_ROOT,
                ),
                state_case_versions_dir_fn=lambda project_value, case_value: workbench_asset_service.state_case_versions_dir(
                    project_value,
                    case_value,
                    state_root=constants.TEST_POINTS_ROOT,
                ),
            ),
            append_history=store.append_history,
            now_iso=store.now_iso,
            ensure_project_writable=lambda project_code: project_code,
        )

    def heal_run(self, run_id: str) -> dict[str, Any]:
        store.ensure_dirs()
        run_item = self._find_run_item(run_id)
        if not run_item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run not found")
        case_path = Path(str(run_item.get("case_path", "")))
        if not case_path.exists():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="case file not found for this run")

        artifacts_dir = Path(str(run_item.get("artifacts_dir", "")))
        if not artifacts_dir.exists():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="artifact directory not found")

        candidate_dirs = [path.parent for path in artifacts_dir.rglob("suggestion.json")]
        if not candidate_dirs:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="suggestion.json not found; cannot heal")
        artifact_case_dir = max(candidate_dirs, key=lambda p: p.stat().st_mtime)

        command = [
            _get_python_bin(),
            str(constants.REPO_ROOT / "agents" / "self-healing-advisor-agent" / "apply_fix.py"),
            "auto-heal",
            "--case",
            str(case_path.resolve()),
            "--artifacts",
            str(artifact_case_dir.resolve()),
            "--previous-attempts",
            "0",
        ]
        result = subprocess.run(
            command,
            cwd=str(constants.REPO_ROOT),
            text=True,
            capture_output=True,
            check=False,
        )
        output = (result.stdout or "") + ("\n" + result.stderr if result.stderr else "")
        payload = workbench_runtime_service.extract_json_from_text(output)
        if result.returncode != 0:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "message": "self-healing failed",
                    "return_code": result.returncode,
                    "output": output[-3000:],
                },
            )

        store.append_history(
            {
                "timestamp": store.now_iso(),
                "action": "self_heal",
                "case_id": run_item.get("case_id", ""),
                "run_id": run_id,
                "artifact_dir": str(artifact_case_dir.resolve()),
                "status": payload.get("status", "success"),
            }
        )
        return {"item": payload, "raw_output": output}

    def rerun_case(self, run_id: str) -> dict[str, Any]:
        store.ensure_dirs()
        run_item = self._find_run_item(run_id)
        if not run_item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run not found")
        case_path = Path(str(run_item.get("case_path", "")))
        if not case_path.exists():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="case file not found for rerun")
        new_job = _start_run(
            project=str(run_item.get("project", "mall")),
            case_id=str(run_item.get("case_id", "")).strip() or "UNKNOWN",
            case_path=case_path,
            source="rerun",
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

    def heal_and_rerun_case(self, run_id: str, wait_seconds: int) -> dict[str, Any]:
        store.ensure_dirs()
        source_item = self._find_run_item(run_id)
        if not source_item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run not found")

        heal_ok = True
        heal_item: dict[str, Any] = {}
        heal_error: Any = None
        try:
            heal_resp = self.heal_run(run_id)
            heal_item = heal_resp.get("item", {}) if isinstance(heal_resp, dict) else {}
        except HTTPException as exc:
            heal_ok = False
            heal_error = exc.detail
        except Exception as exc:  # pragma: no cover
            heal_ok = False
            heal_error = str(exc)

        rerun_resp = self.rerun_case(run_id)
        rerun_job = rerun_resp.get("item", {})
        rerun_id = str(rerun_job.get("run_id", "")).strip()
        final_item, timed_out = workbench_runtime_service.wait_run_terminal(
            rerun_id,
            timeout_seconds=wait_seconds,
            find_run_item=self._find_run_item,
        )
        status_value = str((final_item or rerun_job).get("status", "running")).strip().lower() or "running"

        summary = {
            "source_run_id": run_id,
            "source_status": source_item.get("status", ""),
            "heal": {
                "ok": heal_ok,
                "item": heal_item,
                "error": heal_error,
            },
            "rerun": {
                "run_id": rerun_id,
                "status": status_value,
                "timed_out": timed_out,
                "item": final_item or rerun_job,
            },
        }
        store.append_history(
            {
                "timestamp": store.now_iso(),
                "action": "heal_and_rerun_case",
                "case_id": source_item.get("case_id", ""),
                "from_run_id": run_id,
                "run_id": rerun_id,
                "heal_ok": heal_ok,
                "rerun_status": status_value,
            }
        )
        return {"item": summary}

    def save_review(self, payload: Any, request: Any) -> dict[str, Any]:
        store.ensure_dirs()
        actor = workbench_review_service.extract_review_actor(request)
        try:
            actor = workbench_review_service.require_authenticated_review_actor(actor)
        except HTTPException as exc:
            store.append_history(
                {
                    "timestamp": store.now_iso(),
                    "action": "review_rejected_auth",
                    "case_id": _safe_case_id(payload.case_id) if str(payload.case_id).strip() else "",
                    "page": _normalize_page_slug(payload.page) if str(payload.page).strip() else "",
                    "run_id": str(payload.run_id).strip(),
                    "status": "rejected",
                    "review_type": workbench_review_service.normalize_review_type(payload.review_type),
                    "review_item_count": len(payload.items),
                    "review_items": [
                        str(item.get("label") or item.get("key") or "").strip()
                        for item in payload.items[:10]
                        if isinstance(item, dict) and str(item.get("label") or item.get("key") or "").strip()
                    ],
                    "detail_summary": "确认点提交被拒绝：未登录或身份不可追溯",
                    "confirmed_by": str(actor.get("confirmed_by", "")).strip() or "anonymous",
                    "confirmed_by_role": str(actor.get("confirmed_by_role", "")).strip() or "unknown",
                    "actor_display": workbench_analysis_service.reviewer_display_name(actor),
                    "source": "workbench-review",
                    "note": "review_auth_required",
                }
            )
            raise exc

        record = workbench_review_service.upsert_review_decision(payload, actor=actor)
        review_type = str(record.get("review_type", "")).strip() or "unknown"
        status_value = str(record.get("status", "")).strip() or "confirmed"
        reviewed_items = record.get("items") if isinstance(record.get("items"), list) else []
        item_labels = [
            str(item.get("label") or item.get("key") or "").strip()
            for item in reviewed_items
            if isinstance(item, dict) and str(item.get("label") or item.get("key") or "").strip()
        ]
        store.append_history(
            {
                "timestamp": record["updated_at"],
                "action": f"review_{status_value}",
                "case_id": record.get("case_id", ""),
                "page": record.get("page", ""),
                "run_id": record.get("run_id", ""),
                "status": status_value,
                "review_type": review_type,
                "review_item_count": len(reviewed_items),
                "review_items": item_labels[:10],
                "detail_summary": f"{review_type} 确认 {len(reviewed_items)} 项",
                "confirmed_by": str(record.get("confirmed_by", "")).strip() or "anonymous",
                "confirmed_by_role": str(record.get("confirmed_by_role", "")).strip() or "unknown",
                "actor_display": workbench_analysis_service.reviewer_display_name(record),
                "source": "workbench-review",
                "note": record.get("note", ""),
            }
        )
        calibration_sample = workbench_reporting_service.record_failure_source_calibration_sample(
            review_record=record,
            feedback=payload.failure_source_feedback if isinstance(payload.failure_source_feedback, dict) else None,
            resolve_run_failure_snapshot_fn=lambda run_id_value: workbench_reporting_service.resolve_run_failure_snapshot(
                run_id_value,
                find_run_item=self._find_run_item,
                normalize_failure_entry_view=_normalize_failure_entry_view,
                collect_failure_entries=_collect_failure_entries,
                is_within_fn=_is_within,
            ),
            clamp_confidence=page_analysis_rules.clamp_confidence,
            reviewer_display_name_fn=workbench_analysis_service.reviewer_display_name,
            now_iso_fn=store.now_iso,
            read_json_list_fn=store.read_json_list,
            write_json_list_fn=store.write_json_list,
            calibration_file=constants.FAILURE_SOURCE_CALIBRATIONS_FILE,
        )
        if calibration_sample:
            store.append_history(
                {
                    "timestamp": calibration_sample.get("created_at", store.now_iso()),
                    "action": "failure_source_calibration_recorded",
                    "case_id": calibration_sample.get("case_id", ""),
                    "page": calibration_sample.get("page", ""),
                    "run_id": calibration_sample.get("run_id", ""),
                    "status": "recorded",
                    "review_type": calibration_sample.get("review_type", ""),
                    "detail_summary": f"failure_source 校准样本已记录：{calibration_sample.get('predicted_failure_source', '-') or '-'} -> {calibration_sample.get('confirmed_failure_source', '-') or '-'}",
                    "confirmed_by": calibration_sample.get("confirmed_by", "anonymous"),
                    "confirmed_by_role": calibration_sample.get("confirmed_by_role", "unknown"),
                    "actor_display": calibration_sample.get("actor_display", workbench_analysis_service.reviewer_display_name(record)),
                    "source": "failure-source-calibration",
                    "decision": calibration_sample.get("human_decision", ""),
                    "note": calibration_sample.get("feedback_reason", ""),
                }
            )
        return {
            "item": record,
            "summary": {
                "project": record["project"],
                "run_id": record["run_id"],
                "page": record["page"],
                "review_type": record["review_type"],
                "status": record["status"],
                "candidate_count": len(record["items"]),
                "confirmed_by": record.get("confirmed_by", "anonymous"),
                "confirmed_by_role": record.get("confirmed_by_role", "unknown"),
                "updated_at": record["updated_at"],
            },
            "calibration_sample": calibration_sample,
        }

    def report_allure_refresh(self, response: Any) -> dict[str, Any]:
        store.ensure_dirs()
        workbench_reporting_service.apply_no_store_headers(response)
        payload = workbench_reporting_service.refresh_allure_report(
            python_bin=_get_python_bin(),
            runner_root=constants.RUNNER_ROOT,
            repo_root=constants.REPO_ROOT,
            allure_report_root=constants.ALLURE_REPORT_ROOT,
            run_command=subprocess.run,
            read_allure_summary=partial(
                workbench_reporting_service.read_allure_summary,
                allure_report_root=constants.ALLURE_REPORT_ROOT,
            ),
            read_allure_environment=partial(
                workbench_reporting_service.read_allure_environment,
                allure_report_root=constants.ALLURE_REPORT_ROOT,
            ),
            read_allure_executors=partial(
                workbench_reporting_service.read_allure_executors,
                allure_report_root=constants.ALLURE_REPORT_ROOT,
            ),
            ensure_allure_snapshot=partial(
                workbench_reporting_service.ensure_allure_snapshot,
                allure_report_root=constants.ALLURE_REPORT_ROOT,
                allure_snapshots_root=constants.ALLURE_SNAPSHOTS_ROOT,
            ),
            get_allure_index_version=partial(
                workbench_reporting_service.get_allure_index_version,
                allure_report_root=constants.ALLURE_REPORT_ROOT,
            ),
        )
        if "error" in payload:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=payload["error"])
        return payload


def build_workbench_service() -> WorkbenchService:
    return WorkbenchService()
