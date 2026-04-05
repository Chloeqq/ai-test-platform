from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from app.routers import legacy_workbench
from app.services import workbench_reporting_service, workbench_scheduler_service


router = APIRouter(tags=["workbench-scheduler"])


def _load_task_items(*, limit: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    legacy_workbench._ensure_dirs()
    execution_rows, execution_meta_raw = legacy_workbench._collect_execution_records_with_meta(limit=max(limit * 3, 200))
    execution_meta = workbench_reporting_service.normalize_execution_meta(execution_meta_raw)
    items = [legacy_workbench._build_execution_task_view(row) for row in execution_rows]
    return items[:limit], execution_meta


@router.get("/api/workbench/scheduler/summary")
def get_scheduler_summary(limit: int = Query(default=100, ge=1, le=500)) -> dict[str, Any]:
    items, execution_meta = _load_task_items(limit=limit)
    task_summary = legacy_workbench._build_execution_task_summary(items=items, filter_snapshot={}, execution_meta=execution_meta)
    return {"item": workbench_scheduler_service.build_scheduler_summary(items=items, task_summary=task_summary)}


@router.get("/api/workbench/scheduler/dispatch-plan")
def get_scheduler_dispatch_plan(limit: int = Query(default=200, ge=1, le=1000)) -> dict[str, Any]:
    items, _execution_meta = _load_task_items(limit=limit)
    return {"item": workbench_scheduler_service.build_scheduler_dispatch_plan(items=items)}
