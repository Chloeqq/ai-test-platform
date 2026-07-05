from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from app.api.workbench.facade import build_workbench_facade


router = APIRouter(tags=["workbench-scheduler"])
facade = build_workbench_facade()


@router.get("/api/workbench/scheduler/summary")
def get_scheduler_summary(limit: int = Query(default=100, ge=1, le=500)) -> dict[str, Any]:
    return facade.scheduler_summary(limit=limit)


@router.get("/api/workbench/scheduler/dispatch-plan")
def get_scheduler_dispatch_plan(limit: int = Query(default=200, ge=1, le=1000)) -> dict[str, Any]:
    return facade.scheduler_dispatch_plan(limit=limit)
