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
from app.api.workbench.schemas import (
    BatchGenerateFromTestPointAssetsPayload,
    BatchTestPointAssetIdsPayload,
    BatchTestPointReviewPayload,
    BatchWorkbenchTestCaseDeletePayload,
    SaveCasePayload,
    UpsertTestPointAssetPayload,
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
        project=project,
        page=page,
        keyword=keyword,
        status_filter=status,
        intent_type=intent_type,
        priority=priority,
        can_generate=can_generate,
        page_index=page_index,
        page_size=page_size,
        db=db,
    )


@router.post("/api/workbench/test-point-reviews/batch")
def batch_review_test_points(
    payload: BatchTestPointReviewPayload,
    db: Session = Depends(get_db),
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
        project=project,
        page=page,
        source_asset=source_asset,
        intent_type=intent_type,
        priority=priority,
        execution_status=execution_status,
        active_status=active_status,
        keyword=keyword,
        page_index=page_index,
        page_size=page_size,
        db=db,
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
        project=project,
        asset_id=asset_id,
        keyword=keyword,
        page_index=page_index,
        page_size=page_size,
    )


@router.get("/api/workbench/test-cases/{case_id}")
def get_workbench_test_case(
    case_id: str,
    project: str = Query(default="default"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return facade.get_workbench_test_case(case_id=case_id, project=project, db=db)


@router.delete("/api/workbench/test-cases/{case_id}")
def delete_workbench_test_case(
    case_id: str,
    project: str = Query(default="default"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return facade.delete_workbench_test_cases(
        project=project,
        case_ids=[case_id],
        delete_all=False,
        db=db,
    )


@router.post("/api/workbench/test-cases/batch/delete")
def batch_delete_workbench_test_cases(
    payload: BatchWorkbenchTestCaseDeletePayload,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return facade.delete_workbench_test_cases(
        project=payload.project,
        case_ids=payload.case_ids,
        delete_all=payload.delete_all,
        confirm_text=payload.confirm_text,
        db=db,
    )


@router.post("/api/workbench/test-point-assets")
def upsert_test_point_asset(
    payload: UpsertTestPointAssetPayload,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return facade.upsert_test_point_asset(payload=payload, db=db)


@router.put("/api/workbench/test-point-assets/{asset_id}")
def update_test_point_asset(
    asset_id: str,
    payload: UpsertTestPointAssetPayload,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    payload.asset_id = asset_id
    return facade.upsert_test_point_asset(payload=payload, db=db)


@router.delete("/api/workbench/test-point-assets/{asset_id}")
def delete_test_point_asset(
    asset_id: str,
    project: str = Query(default="default"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return facade.delete_test_point_asset(asset_id=asset_id, project=project, db=db)


@router.post("/api/workbench/test-point-assets/batch/delete")
def batch_delete_test_point_assets(
    payload: BatchTestPointAssetIdsPayload,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return facade.batch_delete_test_point_assets(project=payload.project, asset_ids=payload.asset_ids, db=db)


@router.post("/api/workbench/test-point-assets/batch/generate-cases")
def batch_generate_cases_from_test_point_assets(
    payload: BatchGenerateFromTestPointAssetsPayload,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return facade.generate_cases_from_test_point_assets(
        project=payload.project,
        asset_ids=payload.asset_ids,
        intent_ids=payload.intent_ids,
        source=payload.source,
        db=db,
    )


@router.get("/api/workbench/preview-script")
def preview_test_point_script(
    project: str = Query(default="default"),
    asset_id: str = Query(min_length=1),
    intent_id: str = Query(min_length=1),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return facade.preview_test_point_script(
        project=project,
        asset_id=asset_id,
        intent_id=intent_id,
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
