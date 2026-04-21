from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.workbench.facade import build_workbench_facade
from app.api.workbench.schemas import ExecutionGateDecisionActionPayload, ExecutionGateDecisionPayload
from app.core.database import get_db


router = APIRouter(tags=["workbench-gate"])
facade = build_workbench_facade()


@router.get("/api/workbench/execution-gate/config")
def get_execution_gate_config() -> dict[str, Any]:
    return facade.get_execution_gate_config()


@router.post("/api/workbench/execution-gate/decisions")
def save_execution_gate_decision(
    payload: ExecutionGateDecisionPayload,
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return facade.save_execution_gate_decision(payload, request, db)


@router.post("/api/workbench/execution-gate/decisions/approve")
def approve_execution_gate_decision(
    payload: ExecutionGateDecisionActionPayload,
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return facade.approve_execution_gate_decision(payload, request, db)


@router.post("/api/workbench/execution-gate/decisions/revoke")
def revoke_execution_gate_decision(
    payload: ExecutionGateDecisionActionPayload,
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return facade.revoke_execution_gate_decision(payload, request, db)
