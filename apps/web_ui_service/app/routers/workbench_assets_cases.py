"""Workbench case & review APIs."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.workbench.facade import build_workbench_facade
from app.api.workbench.schemas import (
    BatchTestPointReviewPayload,
    BatchWorkbenchTestCaseDeletePayload,
    SaveCasePayload,
)
from app.core.database import get_db

router = APIRouter(
    tags=["workbench-assets"],
    prefix="",
    responses={404: {"description": "Not found"}},
)
facade = build_workbench_facade()


@router.get("/api/workbench/case-dictionaries")
def get_case_dictionaries() -> dict[str, Any]:
    return facade.get_case_dictionaries()


@router.get("/api/workbench/cases")
def list_cases(
    project: str = Query(default="default"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    focus_case_id: str = Query(default=""),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return facade.list_cases(project=project, page=page, page_size=page_size, focus_case_id=focus_case_id, db=db)


@router.get("/api/workbench/cases/{case_id}")
def get_case(case_id: str, project: str = Query(default="default"), db: Session = Depends(get_db)) -> dict[str, Any]:
    return facade.get_case(case_id=case_id, project=project, db=db)


@router.put("/api/workbench/cases/{case_id}")
def save_case(case_id: str, payload: SaveCasePayload, db: Session = Depends(get_db)) -> dict[str, Any]:
    return facade.save_case(case_id, payload, db)


@router.get("/api/workbench/test-point-reviews")
def list_test_point_reviews(
    project: str = Query(default="default"),
    page: str = Query(default=""),
    keyword: str = Query(default=""),
    status: str = Query(default=""),
    intent_type: str = Query(default=""),
    priority: str = Query(default=""),
    can_generate: str = Query(default=""),
    page_index: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return facade.list_test_point_reviews(
        project=project, page=page, keyword=keyword, status_filter=status,
        intent_type=intent_type, priority=priority, can_generate=can_generate,
        page_index=page_index, page_size=page_size, db=db,
    )


@router.post("/api/workbench/test-point-reviews/batch")
def batch_review_test_points(
    payload: BatchTestPointReviewPayload, db: Session = Depends(get_db),
) -> dict[str, Any]:
    return facade.batch_review_test_points(payload=payload, db=db)


@router.get("/api/workbench/test-cases")
def list_workbench_test_cases(
    project: str = Query(default="default"),
    page: str = Query(default=""),
    source_asset: str = Query(default=""),
    intent_type: str = Query(default=""),
    priority: str = Query(default=""),
    execution_status: str = Query(default=""),
    active_status: str = Query(default="active"),
    keyword: str = Query(default=""),
    page_index: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return facade.list_workbench_test_cases(
        project=project, page=page, source_asset=source_asset,
        intent_type=intent_type, priority=priority, execution_status=execution_status,
        active_status=active_status, keyword=keyword,
        page_index=page_index, page_size=page_size, db=db,
    )


@router.get("/api/workbench/test-case-generation-failures")
def list_test_case_generation_failures(
    project: str = Query(default="default"),
    asset_id: str = Query(default=""),
    keyword: str = Query(default=""),
    page_index: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
) -> dict[str, Any]:
    return facade.list_test_case_generation_failures(
        project=project, asset_id=asset_id, keyword=keyword,
        page_index=page_index, page_size=page_size,
    )


@router.get("/api/workbench/test-cases/{case_id}")
def get_workbench_test_case(
    case_id: str, project: str = Query(default="default"), db: Session = Depends(get_db),
) -> dict[str, Any]:
    return facade.get_workbench_test_case(case_id=case_id, project=project, db=db)


@router.delete("/api/workbench/test-cases/{case_id}")
def delete_workbench_test_case(
    case_id: str, project: str = Query(default="default"), db: Session = Depends(get_db),
) -> dict[str, Any]:
    return facade.delete_workbench_test_cases(
        project=project, case_ids=[case_id], delete_all=False, db=db,
    )


@router.post("/api/workbench/test-cases/batch/delete")
def batch_delete_workbench_test_cases(
    payload: BatchWorkbenchTestCaseDeletePayload, db: Session = Depends(get_db),
) -> dict[str, Any]:
    return facade.delete_workbench_test_cases(
        project=payload.project, case_ids=payload.case_ids,
        delete_all=payload.delete_all, confirm_text=payload.confirm_text, db=db,
    )
