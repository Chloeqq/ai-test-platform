"""Quality Dashboard API — 质量仪表盘只读查询端点。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.quality_dashboard_service import (
    build_summary,
    build_ranking,
    build_issue_distribution,
    build_timeline,
)

router = APIRouter(tags=["quality-dashboard"], prefix="")


@router.get("/api/workbench/quality/summary")
def quality_summary(
    project: str = Query(default="mall"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return build_summary(project, db)


@router.get("/api/workbench/quality/ranking")
def quality_ranking(
    project: str = Query(default="mall"),
    limit: int = Query(default=10, ge=1, le=50),
) -> list[dict[str, Any]]:
    return build_ranking(project, limit)


@router.get("/api/workbench/quality/issues")
def quality_issues(
    project: str = Query(default="mall"),
) -> dict[str, Any]:
    return build_issue_distribution(project)


@router.get("/api/workbench/quality/timeline/{asset_id}")
def quality_timeline(
    asset_id: str,
    project: str = Query(default="mall"),
) -> list[dict[str, Any]]:
    return build_timeline(project, asset_id)
