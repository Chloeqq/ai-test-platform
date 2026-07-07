from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

router = APIRouter(tags=["ui"])


@router.get("/quality/flaky", response_class=RedirectResponse)
def quality_flaky_page(request: Request) -> RedirectResponse:
    query = str(request.url.query or "").strip()
    suffix = f"?{query}" if query else ""
    return RedirectResponse(url=f"/react/quality/flaky{suffix}", status_code=307)


@router.get("/quality/failure-clusters", response_class=RedirectResponse)
@router.get("/quality/clusters", include_in_schema=False, response_class=RedirectResponse)
def quality_clusters_page(request: Request) -> RedirectResponse:
    query = str(request.url.query or "").strip()
    suffix = f"?{query}" if query else ""
    return RedirectResponse(url=f"/react/quality/failure-clusters{suffix}", status_code=307)


@router.get("/quality/trends", response_class=RedirectResponse)
def quality_trends_page(request: Request) -> RedirectResponse:
    query = str(request.url.query or "").strip()
    suffix = f"?{query}" if query else ""
    return RedirectResponse(url=f"/react/quality/trends{suffix}", status_code=307)


@router.get("/quality/gates", response_class=RedirectResponse)
@router.get("/gate", include_in_schema=False, response_class=RedirectResponse)
def gate_config_page(request: Request) -> RedirectResponse:
    query = str(request.url.query or "").strip()
    suffix = f"?{query}" if query else ""
    return RedirectResponse(url=f"/react/quality/gates{suffix}", status_code=307)


@router.get("/defects", response_class=RedirectResponse)
def defects_page(request: Request) -> RedirectResponse:
    query = str(request.url.query or "").strip()
    suffix = f"?{query}" if query else ""
    return RedirectResponse(url=f"/react/defects{suffix}", status_code=307)


@router.get("/settings/scheduler", response_class=RedirectResponse)
def scheduler_page(request: Request) -> RedirectResponse:
    query = str(request.url.query or "").strip()
    suffix = f"?{query}" if query else ""
    return RedirectResponse(url=f"/react/settings/scheduler{suffix}", status_code=307)


@router.get("/system/projects", response_class=RedirectResponse)
@router.get("/settings/projects", include_in_schema=False, response_class=RedirectResponse)
def settings_projects_page(request: Request) -> RedirectResponse:
    query = str(request.url.query or "").strip()
    suffix = f"?{query}" if query else ""
    return RedirectResponse(url=f"/react/system/projects{suffix}", status_code=307)


@router.get("/system/source-config", response_class=RedirectResponse)
@router.get("/settings/source-config", include_in_schema=False, response_class=RedirectResponse)
def settings_source_config_page(request: Request) -> RedirectResponse:
    query = str(request.url.query or "").strip()
    suffix = f"?{query}" if query else ""
    return RedirectResponse(url=f"/react/system/source-config{suffix}", status_code=307)


@router.get("/system/environments", response_class=RedirectResponse)
@router.get("/settings/environments", include_in_schema=False, response_class=RedirectResponse)
def settings_environments_page(request: Request) -> RedirectResponse:
    query = str(request.url.query or "").strip()
    suffix = f"?{query}" if query else ""
    return RedirectResponse(url=f"/react/system/environments{suffix}", status_code=307)


@router.get("/system/nodes", response_class=RedirectResponse)
@router.get("/settings/nodes", include_in_schema=False, response_class=RedirectResponse)
def settings_nodes_page(request: Request) -> RedirectResponse:
    query = str(request.url.query or "").strip()
    suffix = f"?{query}" if query else ""
    return RedirectResponse(url=f"/react/system/nodes{suffix}", status_code=307)


@router.get("/system/integrations", response_class=RedirectResponse)
@router.get("/settings/integrations", include_in_schema=False, response_class=RedirectResponse)
def settings_integrations_page(request: Request) -> RedirectResponse:
    query = str(request.url.query or "").strip()
    suffix = f"?{query}" if query else ""
    return RedirectResponse(url=f"/react/system/integrations{suffix}", status_code=307)


@router.get("/system/roles", response_class=RedirectResponse)
@router.get("/settings/roles", include_in_schema=False, response_class=RedirectResponse)
def settings_roles_page(request: Request) -> RedirectResponse:
    query = str(request.url.query or "").strip()
    suffix = f"?{query}" if query else ""
    return RedirectResponse(url=f"/react/system/roles{suffix}", status_code=307)
