from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.workbench_generation_api.payloads import (
    AutoRunPayload,
    FullChainRunPayload,
    GenerateCasePayload,
    PrecheckSelectedIntentsPayload,
)
from app.services.workbench_generation_api.preview_test_points_usecase import build_preview_usecase
from app.services.workbench_generation_api import preview_store
from app.services.workbench_generation_api.usecase_factory import (
    build_auto_run_usecase,
    build_full_chain_usecase,
    build_generate_case_usecase,
    build_precheck_selected_intents_usecase,
    build_save_test_point_assets_usecase,
)
from shared_backend import ExecutionCompilerError


router = APIRouter(tags=["workbench-generation"])
# ARCHITECTURE GUARANTEE:
# Router must not import pipeline / flags / normalizer / repository internals.


@router.post("/api/workbench/generate", status_code=status.HTTP_201_CREATED)
def generate_case(payload: GenerateCasePayload, db: Session = Depends(get_db)) -> dict[str, Any]:
    return build_generate_case_usecase(db).execute(payload)


@router.post("/api/workbench/full-chain/run", status_code=status.HTTP_201_CREATED)
def run_full_chain(payload: FullChainRunPayload, db: Session = Depends(get_db)) -> dict[str, Any]:
    return build_full_chain_usecase(db).execute(payload)


@router.post("/api/workbench/preview-test-points")
def preview_test_points(
    payload: GenerateCasePayload,
    usecase: Any = Depends(build_preview_usecase),
) -> dict[str, Any]:
    try:
        return usecase.execute(payload)
    except ExecutionCompilerError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.to_detail()) from exc


@router.get("/api/workbench/preview-test-points/{preview_id}/diagnostics")
def get_preview_test_points_diagnostics(preview_id: str) -> dict[str, Any]:
    return preview_store.build_preview_diagnostics(preview_id)


@router.get("/api/workbench/preview-test-points/{preview_id}/test-intents/{intent_id}")
def get_preview_test_intent(preview_id: str, intent_id: str) -> dict[str, Any]:
    return preview_store.build_preview_intent_detail(preview_id, intent_id)


@router.post("/api/workbench/auto-run")
def auto_run(payload: AutoRunPayload, db: Session = Depends(get_db)) -> dict[str, Any]:
    return build_auto_run_usecase(db).execute(payload)


@router.post("/api/workbench/precheck-selected-intents")
def precheck_selected_intents(
    payload: PrecheckSelectedIntentsPayload,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        return build_precheck_selected_intents_usecase(db).execute(payload)
    except ExecutionCompilerError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.to_detail()) from exc


@router.post("/api/workbench/test-point-assets/save", status_code=status.HTTP_201_CREATED)
def save_test_point_assets(
    payload: GenerateCasePayload,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return build_save_test_point_assets_usecase(db).execute(payload)
