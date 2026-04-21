from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.core.security import get_current_user
from app.services import ui_shell_service

router = APIRouter(tags=["ui"])


@router.get("/react", response_class=HTMLResponse)
@router.get("/react/{subpath:path}", include_in_schema=False, response_class=HTMLResponse)
def react_console_page(request: Request, subpath: str = "") -> HTMLResponse:
    normalized_subpath = str(subpath or "").strip().lstrip("/")
    if normalized_subpath.startswith("dashboard"):
        current_key = "dashboard"
    elif normalized_subpath.startswith("login"):
        current_key = "dashboard"
    elif normalized_subpath.startswith("cases/review"):
        current_key = "case_reviews"
    elif normalized_subpath.startswith("cases/versions"):
        current_key = "case_versions"
    elif normalized_subpath.startswith("cases/tags"):
        current_key = "tag_management"
    elif normalized_subpath.startswith("cases/"):
        current_key = "cases"
    elif normalized_subpath.startswith("cases"):
        current_key = "cases"
    elif normalized_subpath.startswith("assets/test-points"):
        current_key = "test_point_assets"
    elif normalized_subpath.startswith("assets/page-objects/recorder"):
        current_key = "page_objects_recorder"
    elif normalized_subpath.startswith("assets/page-objects"):
        current_key = "page_objects"
    elif normalized_subpath.startswith("assets/api-contracts"):
        current_key = "api_contracts"
    elif normalized_subpath.startswith("assets/data-templates"):
        current_key = "data_templates"
    elif normalized_subpath.startswith("system/environments"):
        current_key = "env_management"
    elif normalized_subpath.startswith("system/nodes"):
        current_key = "node_management"
    elif normalized_subpath.startswith("system/integrations"):
        current_key = "integration_config"
    elif normalized_subpath.startswith("system/roles"):
        current_key = "role_permissions"
    elif normalized_subpath.startswith("ai-generation/history"):
        current_key = "workbench_history"
    elif normalized_subpath.startswith("ai-generation/prompts"):
        current_key = "prompt_management"
    elif normalized_subpath.startswith("ai-generation"):
        current_key = "workbench_generate"
    elif normalized_subpath.startswith("quality/flaky"):
        current_key = "flaky"
    elif normalized_subpath.startswith("quality/failure-clusters") or normalized_subpath.startswith("quality/clusters"):
        current_key = "failure_clusters"
    elif normalized_subpath.startswith("quality/trends"):
        current_key = "trend_analysis"
    elif normalized_subpath.startswith("quality/gates"):
        current_key = "gate_config"
    elif normalized_subpath.startswith("defects"):
        current_key = "defects"
    elif normalized_subpath.startswith("settings/scheduler"):
        current_key = "scheduler"
    elif normalized_subpath.startswith("execution/plans"):
        current_key = "execution_plans"
    elif normalized_subpath.startswith("execution/workbench"):
        current_key = "workbench"
    elif normalized_subpath.startswith("execution/results"):
        current_key = "report_overview"
    elif normalized_subpath.startswith("execution/runs"):
        current_key = "execution_records"
    elif normalized_subpath == "":
        current_key = "dashboard"
    else:
        current_key = "execution_records"
    return ui_shell_service.render_template(
        request,
        "react_app.html",
        current_key=current_key,
        context={
            "page_title": "React Console",
            "page_description": "TypeScript + React 主链入口（迁移中）。",
            "breadcrumbs": ["首页", "React Console"],
            "react_subpath": subpath,
        },
    )


@router.get("/execution/workbench", response_class=RedirectResponse)
def workbench_page(request: Request) -> RedirectResponse:
    query = str(request.url.query or "").strip()
    suffix = f"?{query}" if query else ""
    return RedirectResponse(url=f"/react/execution/workbench{suffix}", status_code=307)


@router.get("/execution/workbench/{case_id}", include_in_schema=False, response_class=RedirectResponse)
def execution_workbench_case_page(case_id: str) -> RedirectResponse:
    return RedirectResponse(url=f"/execution/workbench?case_id={case_id}", status_code=307)


@router.get("/ai-generation", response_class=RedirectResponse)
def workbench_generate_page(request: Request) -> RedirectResponse:
    query = str(request.url.query or "").strip()
    suffix = f"?{query}" if query else ""
    return RedirectResponse(url=f"/react/ai-generation{suffix}", status_code=307)


@router.get("/ai-generation/preview", response_class=RedirectResponse)
def workbench_preview_page() -> RedirectResponse:
    return RedirectResponse(url="/react/ai-generation?step=3", status_code=307)


@router.get("/ai-generation/history", response_class=RedirectResponse)
def workbench_history_page(request: Request) -> RedirectResponse:
    query = str(request.url.query or "").strip()
    suffix = f"?{query}" if query else ""
    return RedirectResponse(url=f"/react/ai-generation/history{suffix}", status_code=307)


@router.get("/ai-generation/prompts", response_class=RedirectResponse)
def prompt_management_page(request: Request) -> RedirectResponse:
    query = str(request.url.query or "").strip()
    suffix = f"?{query}" if query else ""
    return RedirectResponse(url=f"/react/ai-generation/prompts{suffix}", status_code=307)


@router.get("/execution/plans", response_class=RedirectResponse)
def execution_plans_page(request: Request) -> RedirectResponse:
    query = str(request.url.query or "").strip()
    suffix = f"?{query}" if query else ""
    return RedirectResponse(url=f"/react/execution/plans{suffix}", status_code=307)


@router.get("/execution/runs", response_class=RedirectResponse)
def execution_records_page(request: Request) -> RedirectResponse:
    query = str(request.url.query or "").strip()
    suffix = f"?{query}" if query else ""
    return RedirectResponse(url=f"/react/execution/runs{suffix}", status_code=307)


@router.get("/execution/results", response_class=RedirectResponse)
def report_overview_page(request: Request) -> RedirectResponse:
    query = str(request.url.query or "").strip()
    suffix = f"?{query}" if query else ""
    return RedirectResponse(url=f"/react/execution/results{suffix}", status_code=307)


@router.get("/execution/results/failures", response_class=RedirectResponse)
def report_failures_page(request: Request) -> RedirectResponse:
    query = str(request.url.query or "").strip()
    suffix = f"?{query}" if query else ""
    return RedirectResponse(url=f"/react/execution/results/failures{suffix}", status_code=307)


@router.get("/execution/results/context", response_class=RedirectResponse)
def report_context_page(request: Request) -> RedirectResponse:
    query = str(request.url.query or "").strip()
    suffix = f"?{query}" if query else ""
    return RedirectResponse(url=f"/react/execution/results/context{suffix}", status_code=307)


@router.get("/execution/results/performance", response_class=RedirectResponse)
def report_performance_page(request: Request) -> RedirectResponse:
    query = str(request.url.query or "").strip()
    suffix = f"?{query}" if query else ""
    return RedirectResponse(url=f"/react/execution/results/performance{suffix}", status_code=307)


@router.get("/execution/results/allure", response_class=RedirectResponse)
def report_allure_page(request: Request) -> RedirectResponse:
    query = str(request.url.query or "").strip()
    suffix = f"?{query}" if query else ""
    return RedirectResponse(url=f"/react/execution/results/allure{suffix}", status_code=307)


@router.get("/execution/results/{execution_id}", response_class=RedirectResponse, dependencies=[Depends(get_current_user)])
def execution_report_page(
    execution_id: int,
) -> RedirectResponse:
    return RedirectResponse(url=f"/react/execution/results/{execution_id}", status_code=307)
