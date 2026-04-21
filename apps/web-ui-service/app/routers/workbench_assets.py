"""Workbench asset APIs — read/write YAML-based test assets and dictionaries.

These endpoints operate on file-system assets under ``assets/test-cases/`` and
``assets/page-objects/``.  For the database-backed test-case CRUD tree, see
``test_cases.py`` (``/api/test-cases``).
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.workbench.facade import build_workbench_facade
from app.api.workbench.schemas import SaveCasePayload
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
def save_case(
    case_id: str,
    payload: SaveCasePayload,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return facade.save_case(case_id, payload, db)


@router.get("/api/workbench/test-point-assets")
def list_test_point_assets(
    project: str = Query(default="default"),
    page: str = Query(default=""),
    keyword: str = Query(default=""),
    source_type: str = Query(default=""),
    coverage_status: str = Query(default=""),
    review_status: str = Query(default=""),
    gate_decision: str = Query(default=""),
    selection_state: str = Query(default=""),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return facade.list_test_point_assets(
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


@router.get("/api/workbench/test-point-assets/coverage-summary")
def get_test_point_asset_coverage_summary(
    project: str = Query(default="default"),
    page: str = Query(default=""),
    keyword: str = Query(default=""),
    source_type: str = Query(default=""),
    coverage_status: str = Query(default=""),
    review_status: str = Query(default=""),
    gate_decision: str = Query(default=""),
    selection_state: str = Query(default=""),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return facade.get_test_point_asset_coverage_summary(
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


@router.get("/api/workbench/test-point-assets/{asset_id}")
def get_test_point_asset(
    asset_id: str,
    project: str = Query(default="default"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return facade.get_test_point_asset(asset_id=asset_id, project=project, db=db)


@router.get("/api/workbench/test-point-assets/{asset_id}/coverage-matrix")
def get_test_point_asset_coverage_matrix(
    asset_id: str,
    project: str = Query(default="default"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return facade.get_test_point_asset_coverage_matrix(asset_id=asset_id, project=project, db=db)
