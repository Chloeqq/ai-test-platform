from __future__ import annotations

import logging
import urllib.request
from typing import Any

from fastapi import APIRouter, Depends, Query, Request, Response, status
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.workbench.facade import build_workbench_facade
from app.api.workbench.schemas import DefectPayload
from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.test_case import TestCase, TestCaseExecution
from shared_backend.observability import get_request_id, summarize_http_context

_logger = logging.getLogger(__name__)
router = APIRouter(tags=["workbench-reporting"])
facade = build_workbench_facade()


@router.get("/api/defects")
def list_defects(case_id: str = Query(default=""), db: Session = Depends(get_db)) -> dict[str, Any]:
    return facade.list_defects(case_id=case_id, db=db)


@router.post("/api/defects", status_code=status.HTTP_201_CREATED)
def add_defect(payload: DefectPayload, db: Session = Depends(get_db)) -> dict[str, Any]:
    return facade.add_defect(payload, db)


@router.get("/api/report/overview")
def report_overview(response: Response, db: Session = Depends(get_db)) -> dict[str, Any]:
    return facade.report_overview(response, db)


@router.get("/api/report/failures")
def report_failures(
    response: Response,
    case_id: str = Query(default=""),
    keyword: str = Query(default=""),
    defect_status: str = Query(default="all"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return facade.report_failures(
        response=response,
        case_id=case_id,
        keyword=keyword,
        defect_status=defect_status,
        db=db,
    )


@router.get("/api/report/context")
def report_context(response: Response, db: Session = Depends(get_db)) -> dict[str, Any]:
    return facade.report_context(response=response, db=db)


@router.get("/api/report/performance")
def report_performance(response: Response, db: Session = Depends(get_db)) -> dict[str, Any]:
    return facade.report_performance(response=response, db=db)


@router.get("/api/report/allure")
def report_allure(response: Response) -> dict[str, Any]:
    return facade.report_allure(response)


@router.post("/api/report/allure/refresh")
def report_allure_refresh(response: Response) -> dict[str, Any]:
    return facade.report_allure_refresh(response)


@router.get("/api/report/executions/{execution_id}")
def report_execution_detail(
    execution_id: int,
    db: Session = Depends(get_db),
    _user: Any = Depends(get_current_user),
) -> dict[str, Any]:
    execution = db.execute(
        select(TestCaseExecution).where(TestCaseExecution.id == execution_id)
    ).scalar_one_or_none()
    if not execution:
        raise HTTPException(status_code=404, detail="execution report not found")

    case = db.execute(
        select(TestCase).where(TestCase.id == execution.case_id)
    ).scalar_one_or_none()
    return {
        "item": {
            "execution_id": execution.id,
            "case_id": execution.case_id,
            "case_name": case.name if case else f"用例 ID {execution.case_id}",
            "status": execution.status,
            "duration_ms": execution.duration_ms,
            "report_url": execution.report_url,
            "executed_at": execution.executed_at,
        }
    }


@router.get("/api/workbench/history")
def workbench_history(
    limit: int = Query(default=500, ge=1, le=1000),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    project_code: str = Query(default=""),
    keyword: str = Query(default=""),
    sort: str = Query(default="timestamp_desc"),
    action: str = Query(default=""),
    actor: str = Query(default=""),
    status: str = Query(default=""),
    risk_gate_decision: str = Query(default=""),
    self_healing_status: str = Query(default=""),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return facade.workbench_history(
        limit=limit,
        page=page,
        page_size=page_size,
        project_code=project_code,
        keyword=keyword,
        sort=sort,
        action=action,
        actor=actor,
        status=status,
        risk_gate_decision=risk_gate_decision,
        self_healing_status=self_healing_status,
        db=db,
    )


@router.get("/api/workbench/quality-gates/summary")
def workbench_quality_gate_summary(
    limit: int = Query(default=500, ge=50, le=5000),
    alert_code: str = Query(default=""),
    page: str = Query(default=""),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return facade.workbench_quality_gate_summary(limit=limit, alert_code=alert_code, page=page, db=db)


@router.post("/api/workbench/case-consistency/cleanup")
def cleanup_case_consistency(
    purge_all: bool = Query(default=False),
    confirm_text: str = Query(default=""),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return facade.cleanup_case_consistency(purge_all=purge_all, confirm_text=confirm_text, db=db)


@router.get("/api/workbench/download-log/{run_id}")
def download_log(run_id: str, db: Session = Depends(get_db)) -> Response:
    return facade.download_log(run_id, db)


def _proxy_orchestrator(path: str) -> dict[str, Any]:
    settings = get_settings()
    url = f"{settings.orchestrator_url.rstrip('/')}{path}"
    request_id = get_request_id()
    request = urllib.request.Request(url=url, method="GET")
    if request_id:
        request.add_header("X-Request-Id", request_id)
    try:
        with urllib.request.urlopen(request, timeout=10) as resp:
            import json
            payload = json.loads(resp.read())
            _logger.info(
                "orchestrator_proxy_end %s",
                summarize_http_context(
                    method="GET",
                    path=url,
                    request_id=request_id,
                    status_code=getattr(resp, "status", 200),
                ),
            )
            return payload
    except Exception:
        _logger.exception(
            "orchestrator_proxy_failed %s",
            summarize_http_context(method="GET", path=url, request_id=request_id),
        )
        return {"clusters": [], "error": "orchestrator unavailable"}


@router.get("/failures/clusters")
def failure_clusters(request: Request) -> dict[str, Any]:
    qs = str(request.url.query)
    path = f"/failures/clusters?{qs}" if qs else "/failures/clusters"
    return _proxy_orchestrator(path)


@router.get("/failures/clusters/{cluster_id}")
def failure_cluster_detail(cluster_id: str, limit: int = Query(default=50)) -> dict[str, Any]:
    return _proxy_orchestrator(f"/failures/clusters/{cluster_id}?limit={limit}")
