from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.workbench.facade import build_workbench_facade


router = APIRouter(tags=["workbench-tasks"])
facade = build_workbench_facade()


@router.get("/api/workbench/projects")
def list_projects(db: Session = Depends(get_db)) -> dict[str, Any]:
    return facade.list_projects(db)


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
    return facade.list_execution_tasks(
        db=db,
        limit=limit,
        project_code=project_code,
        status=status,
        queue_status=queue_status,
        source=source,
        evidence_health_status=evidence_health_status,
        evidence_freshness_status=evidence_freshness_status,
        manifest_action=manifest_action,
        strict_mode_status=strict_mode_status,
        retry_enabled=retry_enabled,
        has_dependencies=has_dependencies,
    )


@router.get("/api/workbench/tasks/{task_id}")
def get_execution_task(task_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    return facade.get_execution_task(task_id, db)
