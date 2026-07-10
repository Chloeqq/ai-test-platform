from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.workbench.facade import build_workbench_facade
from app.api.workbench.schemas import WorkbenchReviewPayload
from app.core.database import get_db

router = APIRouter(tags=["workbench-reviews"])
facade = build_workbench_facade()


@router.post("/api/workbench/reviews")
def save_review(
    payload: WorkbenchReviewPayload,
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return facade.save_review(payload, request, db)
