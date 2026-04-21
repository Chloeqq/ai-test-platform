from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.workbench_generation_api.payloads import AutoRunPayload, FullChainRunPayload, GenerateCasePayload
from app.services.workbench_generation_api.preview_test_points_usecase import build_preview_usecase
from app.services.workbench_generation_api.usecase_factory import (
    build_auto_run_usecase,
    build_full_chain_usecase,
    build_generate_case_usecase,
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


@router.post("/api/workbench/auto-run")
def auto_run(payload: AutoRunPayload, db: Session = Depends(get_db)) -> dict[str, Any]:
    return build_auto_run_usecase(db).execute(payload)
