from __future__ import annotations

import os
import subprocess
from typing import Any

from fastapi import APIRouter, Query, Response, status

from app.services import workbench_history_service, workbench_reporting_service
from . import legacy_workbench


router = APIRouter(tags=["workbench-reporting"])


def _list_defect_items(case_id: str = "") -> list[dict[str, Any]]:
    legacy_workbench._sync_stage_a_workbench_state()
    legacy_workbench._ensure_dirs()
    with legacy_workbench._FILE_LOCK:
        items = legacy_workbench._read_json_list(legacy_workbench.DEFECT_LINKS_FILE)
    if case_id.strip():
        items = [item for item in items if str(item.get("case_id", "")).strip() == case_id.strip()]
    items.sort(key=lambda item: str(item.get("linked_at", "")), reverse=True)
    return items


@router.get("/api/defects")
def list_defects(case_id: str = Query(default="")) -> dict[str, Any]:
    legacy_workbench._sync_stage_a_workbench_state()
    legacy_workbench._ensure_dirs()
    return {
        "items": workbench_reporting_service.list_defect_items(
            case_id,
            read_items=lambda: _list_defect_items(),
        )
    }


@router.post("/api/defects", status_code=status.HTTP_201_CREATED)
def add_defect(payload: legacy_workbench.DefectPayload) -> dict[str, Any]:
    legacy_workbench._sync_stage_a_workbench_state()
    legacy_workbench._ensure_dirs()
    with legacy_workbench._FILE_LOCK:
        entry = workbench_reporting_service.add_defect_item(
            case_id=payload.case_id,
            defect_id=payload.defect_id,
            defect_url=payload.defect_url,
            system=payload.system,
            note=payload.note,
            read_items=lambda: legacy_workbench._read_json_list(legacy_workbench.DEFECT_LINKS_FILE),
            write_items=lambda items: legacy_workbench._write_json_list(legacy_workbench.DEFECT_LINKS_FILE, items),
        )
    return {"item": entry}


@router.get("/api/report/overview")
def report_overview(response: Response) -> dict[str, Any]:
    legacy_workbench._sync_stage_a_workbench_state()
    legacy_workbench._ensure_dirs()
    workbench_reporting_service.apply_no_store_headers(response)
    return workbench_reporting_service.build_report_overview(
        collect_execution_records_with_meta=legacy_workbench._collect_execution_records_with_meta,
        normalize_execution_meta=legacy_workbench._normalize_execution_meta,
        collect_failure_entries=legacy_workbench._collect_failure_entries,
        normalize_failure_analysis_view=legacy_workbench._normalize_failure_analysis_view,
        read_defect_items=lambda: _list_defect_items(),
    )


@router.get("/api/report/failures")
def report_failures(
    response: Response,
    case_id: str = Query(default=""),
    keyword: str = Query(default=""),
    defect_status: str = Query(default="all"),
) -> dict[str, Any]:
    legacy_workbench._sync_stage_a_workbench_state()
    legacy_workbench._ensure_dirs()
    workbench_reporting_service.apply_no_store_headers(response)
    return workbench_reporting_service.build_report_failures(
        case_id=case_id,
        keyword=keyword,
        defect_status=defect_status,
        collect_failure_entries_with_meta=legacy_workbench._collect_failure_entries_with_meta,
        normalize_failure_evidence_meta=legacy_workbench._normalize_failure_evidence_meta,
        read_defect_items=lambda: _list_defect_items(),
    )


@router.get("/api/report/context")
def report_context(response: Response) -> dict[str, Any]:
    legacy_workbench._sync_stage_a_workbench_state()
    legacy_workbench._ensure_dirs()
    workbench_reporting_service.apply_no_store_headers(response)
    commit_id = ""
    commit_message = ""
    branch_name = ""
    try:
        commit_id = (
            subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(legacy_workbench.REPO_ROOT), capture_output=True, text=True, check=False)
            .stdout.strip()
        )
        commit_message = (
            subprocess.run(["git", "log", "-1", "--pretty=%s"], cwd=str(legacy_workbench.REPO_ROOT), capture_output=True, text=True, check=False)
            .stdout.strip()
        )
        branch_name = (
            subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=str(legacy_workbench.REPO_ROOT), capture_output=True, text=True, check=False)
            .stdout.strip()
        )
    except Exception:
        pass
    return workbench_reporting_service.build_report_context(
        git_rev_parse_head=commit_id,
        git_log_subject=commit_message,
        git_branch=branch_name,
        collect_execution_records_with_meta=legacy_workbench._collect_execution_records_with_meta,
        normalize_execution_meta=legacy_workbench._normalize_execution_meta,
        image_tag=os.getenv("IMAGE_TAG", ""),
        base_url=os.getenv("BASE_URL", "http://localhost:5173/login#/login"),
        browser=os.getenv("PLAYWRIGHT_BROWSER", "chromium"),
        environment=os.getenv("APP_ENV", "local"),
    )


@router.get("/api/report/performance")
def report_performance(response: Response) -> dict[str, Any]:
    legacy_workbench._sync_stage_a_workbench_state()
    legacy_workbench._ensure_dirs()
    workbench_reporting_service.apply_no_store_headers(response)
    return workbench_reporting_service.build_report_performance(
        collect_execution_records_with_meta=legacy_workbench._collect_execution_records_with_meta,
        normalize_execution_meta=legacy_workbench._normalize_execution_meta,
    )


@router.get("/api/report/allure")
def report_allure(response: Response) -> dict[str, Any]:
    workbench_reporting_service.apply_no_store_headers(response)
    return workbench_reporting_service.build_report_allure(
        available=(legacy_workbench.ALLURE_REPORT_ROOT / "index.html").exists(),
        read_allure_summary=legacy_workbench._read_allure_summary,
        ensure_allure_snapshot=legacy_workbench._ensure_allure_snapshot,
        get_allure_index_version=legacy_workbench._get_allure_index_version,
    )


@router.post("/api/report/allure/refresh")
def report_allure_refresh(response: Response) -> dict[str, Any]:
    legacy_workbench._sync_stage_a_workbench_state()
    legacy_workbench._ensure_dirs()
    workbench_reporting_service.apply_no_store_headers(response)
    payload = workbench_reporting_service.refresh_allure_report(
        python_bin=legacy_workbench._get_python_bin(),
        runner_root=legacy_workbench.RUNNER_ROOT,
        repo_root=legacy_workbench.REPO_ROOT,
        allure_report_root=legacy_workbench.ALLURE_REPORT_ROOT,
        run_command=subprocess.run,
        read_allure_summary=legacy_workbench._read_allure_summary,
        ensure_allure_snapshot=legacy_workbench._ensure_allure_snapshot,
        get_allure_index_version=legacy_workbench._get_allure_index_version,
    )
    if "error" in payload:
        error = payload["error"]
        raise legacy_workbench.HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error,
        )
    return payload


@router.get("/api/workbench/history")
def workbench_history(
    limit: int = Query(default=500, ge=1, le=1000),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    keyword: str = Query(default=""),
    sort: str = Query(default="timestamp_desc"),
    action: str = Query(default=""),
    actor: str = Query(default=""),
    status: str = Query(default=""),
    risk_gate_decision: str = Query(default=""),
    self_healing_status: str = Query(default=""),
) -> dict[str, Any]:
    legacy_workbench._sync_stage_a_workbench_state()
    legacy_workbench._ensure_dirs()
    history_items = legacy_workbench._read_json_list(legacy_workbench.HISTORY_FILE)
    return workbench_history_service.list_history(
        history_items,
        resolve_governance_snapshot=legacy_workbench._resolve_run_governance_snapshot,
        resolve_failure_snapshot=legacy_workbench._resolve_run_failure_snapshot,
        normalize_page_slug=legacy_workbench._normalize_page_slug,
        limit=limit,
        page=page,
        page_size=page_size,
        keyword=keyword,
        sort=sort,
        action=action,
        actor=actor,
        status=status,
        risk_gate_decision=risk_gate_decision,
        self_healing_status=self_healing_status,
    )


@router.get("/api/workbench/quality-gates/summary")
def workbench_quality_gate_summary(
    limit: int = Query(default=500, ge=50, le=5000),
    alert_code: str = Query(default=""),
    page: str = Query(default=""),
) -> dict[str, Any]:
    legacy_workbench._sync_stage_a_workbench_state()
    legacy_workbench._ensure_dirs()
    history_items = legacy_workbench._read_json_list(legacy_workbench.HISTORY_FILE)
    return {"item": workbench_history_service.summarize_quality_gate_events(
        history_items,
        limit=limit,
        alert_code=alert_code,
        page=page,
        normalize_page_slug=legacy_workbench._normalize_page_slug,
    )}


@router.get("/api/workbench/download-log/{run_id}")
def download_log(run_id: str) -> Response:
    legacy_workbench._sync_stage_a_workbench_state()
    legacy_workbench._ensure_dirs()
    log_path = legacy_workbench.WEB_UI_RUNS_DIR / f"{run_id}.log"
    if not log_path.exists():
        raise legacy_workbench.HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="log not found")
    return Response(
        content=log_path.read_text(encoding="utf-8", errors="ignore"),
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={run_id}.log"},
    )
