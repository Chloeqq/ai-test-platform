from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.workbench.facade import build_workbench_facade
from app.core.database import get_db

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])
facade = build_workbench_facade()


@router.get("/overview")
def get_dashboard_overview(db: Session = Depends(get_db)) -> dict[str, Any]:
    return facade.dashboard_overview(db)


@router.get("/governance")
def get_dashboard_governance(db: Session = Depends(get_db)) -> dict[str, Any]:
    return facade.dashboard_governance(db)
