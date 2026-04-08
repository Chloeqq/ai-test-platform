from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.routers import legacy_workbench
from app.services import (
    workbench_case_consistency_service,
    workbench_project_service,
    workbench_reporting_service,
    workbench_task_service,
    test_project_service,
)


router = APIRouter(tags=["workbench-tasks"])


def _normalize_optional_project_code(value: str) -> str:
    raw = str(value or "").strip().lower()
    return raw


@router.get("/api/workbench/projects")
def list_projects(db: Session = Depends(get_db)) -> dict[str, Any]:
    legacy_workbench._ensure_dirs()
    items = workbench_project_service.list_project_items(db, state_root=legacy_workbench.TEST_POINTS_ROOT)
    return {
        "items": items,
        "codes": [str(item.get("project_code", "")).strip().lower() for item in items if item.get("project_code")],
    }


@router.get("/api/workbench/tasks")
def list_execution_tasks(
    limit: int = Query(default=50, ge=1, le=500),
    project_code: str = Query(default=""),
    status: str = Query(default=""),
    queue_status: str = Query(default=""),
    source: str = Query(default=""),
    evidence_health_status: str = Query(default=""),
    evidence_freshness_status: str = Query(default=""),
    manifest_action: str = Query(default=""),
    strict_mode_status: str = Query(default=""),
    retry_enabled: str = Query(default=""),
    has_dependencies: str = Query(default=""),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    legacy_workbench._ensure_dirs()
    case_center_case_ids = workbench_case_consistency_service.load_case_center_case_ids(db)
    execution_rows, execution_meta_raw = legacy_workbench._collect_execution_records_with_meta(limit=max(limit * 3, 200))
    execution_meta = workbench_reporting_service.normalize_execution_meta(execution_meta_raw)
    project_code_value = _normalize_optional_project_code(project_code)
    status_value = str(status or "").strip().lower()
    queue_status_value = str(queue_status or "").strip().lower()
    source_value = str(source or "").strip().lower()
    evidence_health_status_value = str(evidence_health_status or "").strip().lower()
    evidence_freshness_status_value = str(evidence_freshness_status or "").strip().lower()
    manifest_action_value = str(manifest_action or "").strip().lower()
    strict_mode_status_value = str(strict_mode_status or "").strip().lower()
    retry_enabled_value = workbench_task_service.parse_optional_bool_query(retry_enabled)
    has_dependencies_value = workbench_task_service.parse_optional_bool_query(has_dependencies)
    project_status_cache: dict[str, str] = {}

    def resolve_project_status(project_code_value_raw: str) -> str:
        normalized_project_code = _normalize_optional_project_code(project_code_value_raw)
        if not normalized_project_code:
            return "active"
        if normalized_project_code not in project_status_cache:
            project_status_cache[normalized_project_code] = test_project_service.get_project_status(db, normalized_project_code)
        return project_status_cache[normalized_project_code]

    items: list[dict[str, Any]] = []
    for row in execution_rows:
        task = legacy_workbench._build_execution_task_view(row)
        task_project_code = _normalize_optional_project_code(task.get("project_code") or task.get("project") or "")
        if project_code_value and task_project_code != project_code_value:
            continue
        if not workbench_case_consistency_service.is_case_tracked(
            task.get("case_id", ""),
            case_center_case_ids=case_center_case_ids,
        ):
            continue
        if status_value and str(task.get("status", "")).strip().lower() != status_value:
            continue
        if queue_status_value and str(task.get("queue_status", "")).strip().lower() != queue_status_value:
            continue
        if source_value and str(task.get("source", "")).strip().lower() != source_value:
            continue
        evidence_health = task.get("evidence_health", {}) if isinstance(task.get("evidence_health"), dict) else {}
        if evidence_health_status_value and str(evidence_health.get("status", "")).strip().lower() != evidence_health_status_value:
            continue
        evidence_freshness = task.get("evidence_freshness", {}) if isinstance(task.get("evidence_freshness"), dict) else {}
        if evidence_freshness_status_value and str(evidence_freshness.get("status", "")).strip().lower() != evidence_freshness_status_value:
            continue
        if manifest_action_value and str(task.get("manifest_action", "")).strip().lower() != manifest_action_value:
            continue
        strict_mode = task.get("strict_mode", {}) if isinstance(task.get("strict_mode"), dict) else {}
        if strict_mode_status_value and str(strict_mode.get("status", "")).strip().lower() != strict_mode_status_value:
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
        "project_code": project_code_value,
        "status": status_value,
        "queue_status": queue_status_value,
        "source": source_value,
        "evidence_health_status": evidence_health_status_value,
        "evidence_freshness_status": evidence_freshness_status_value,
        "manifest_action": manifest_action_value,
        "strict_mode_status": strict_mode_status_value,
        "retry_enabled": "" if retry_enabled_value is None else str(retry_enabled_value).lower(),
        "has_dependencies": "" if has_dependencies_value is None else str(has_dependencies_value).lower(),
    }
    return {
        "items": items,
        "summary": legacy_workbench._build_execution_task_summary(items=items, filter_snapshot=filter_snapshot, execution_meta=execution_meta),
    }


@router.get("/api/workbench/tasks/{task_id}")
def get_execution_task(task_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    legacy_workbench._ensure_dirs()
    case_center_case_ids = workbench_case_consistency_service.load_case_center_case_ids(db)
    normalized_task_id = str(task_id or "").strip()
    if not normalized_task_id:
        raise legacy_workbench.HTTPException(status_code=legacy_workbench.status.HTTP_404_NOT_FOUND, detail="task not found")
    execution_rows, execution_meta_raw = legacy_workbench._collect_execution_records_with_meta(limit=1000)
    execution_meta = workbench_reporting_service.normalize_execution_meta(execution_meta_raw)
    for row in execution_rows:
        task = legacy_workbench._build_execution_task_view(row)
        if str(task.get("task_id", "")).strip() == normalized_task_id:
            if not workbench_case_consistency_service.is_case_tracked(
                task.get("case_id", ""),
                case_center_case_ids=case_center_case_ids,
            ):
                raise legacy_workbench.HTTPException(status_code=legacy_workbench.status.HTTP_404_NOT_FOUND, detail="task not found")
            task_project_code = _normalize_optional_project_code(task.get("project_code") or task.get("project") or "")
            task["project_code"] = task_project_code or str(task.get("project", "")).strip().lower()
            task["project_status"] = test_project_service.get_project_status(db, task["project_code"])
            return {"item": task, "meta": execution_meta}
    raise legacy_workbench.HTTPException(status_code=legacy_workbench.status.HTTP_404_NOT_FOUND, detail="task not found")
