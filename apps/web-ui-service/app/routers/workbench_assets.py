"""Workbench asset APIs — test-point-asset read/write and generation."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.workbench.facade import build_workbench_facade
from app.api.workbench.schemas import (
    BatchGenerateFromTestPointAssetsPayload,
    BatchTestPointAssetIdsPayload,
    UpsertTestPointAssetPayload,
)
from app.core.database import get_db


router = APIRouter(
    tags=["workbench-assets"],
    prefix="",
    responses={404: {"description": "Not found"}},
)
facade = build_workbench_facade()


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
