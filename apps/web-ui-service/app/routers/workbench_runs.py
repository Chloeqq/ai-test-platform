from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.workbench.facade import build_workbench_facade
from app.api.workbench.schemas import RunCasePayload
from app.core.database import get_db

_logger = logging.getLogger(__name__)
router = APIRouter(tags=["workbench-runs"])
facade = build_workbench_facade()


@router.post("/api/workbench/run")
def run_case(payload: RunCasePayload, db: Session = Depends(get_db)) -> dict[str, Any]:
    return facade.run_case(payload=payload, db=db)


@router.get("/api/workbench/runs")
def list_runs(limit: int = Query(default=30, ge=1, le=200), db: Session = Depends(get_db)) -> dict[str, Any]:
    return facade.list_runs(limit=limit, db=db)


@router.get("/api/workbench/runs/{run_id}")
def get_run(run_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    return facade.get_run(run_id=run_id, db=db)


@router.post("/api/workbench/runs/{run_id}/rerun")
def rerun_case(run_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    return facade.rerun_case(run_id=run_id, db=db)


async def _sse_stream(run_id: str):
    """Minimal SSE stream: emit current status then close."""
    try:
        run_data = facade.get_run(run_id=run_id, db=None)  # type: ignore[arg-type]
        status = run_data.get("status", "unknown") if isinstance(run_data, dict) else "unknown"
    except Exception:
        status = "error"
    yield f"data: {json.dumps({'event': 'complete', 'status': status})}\n\n"
    await asyncio.sleep(0)


@router.get("/api/workbench/runs/{run_id}/events")
async def run_events(run_id: str):
    return StreamingResponse(_sse_stream(run_id), media_type="text/event-stream")


@router.get("/api/workbench/runs/{run_id}/analysis")
def run_analysis(run_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        run_data = facade.get_run(run_id=run_id, db=db)
    except Exception:
        run_data = {}
    failures = run_data.get("failures", []) if isinstance(run_data, dict) else []
    return {
        "run_id": run_id,
        "summary": f"共 {len(failures)} 项失败" if failures else "无失败记录",
        "failures": failures,
    }


@router.post("/api/workbench/runs/{run_id}/heal-and-rerun")
def heal_and_rerun(run_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    _logger.info("heal-and-rerun requested for run_id=%s (delegating to rerun)", run_id)
    return facade.rerun_case(run_id=run_id, db=db)
