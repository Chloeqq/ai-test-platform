from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

router = APIRouter(tags=["ui"])


@router.get("/cases", response_class=RedirectResponse)
@router.get("/assets/cases", include_in_schema=False, response_class=RedirectResponse)
def asset_cases_page(request: Request) -> RedirectResponse:
    query = str(request.url.query or "").strip()
    suffix = f"?{query}" if query else ""
    return RedirectResponse(url=f"/react/cases{suffix}", status_code=307)


@router.get("/cases/review", response_class=RedirectResponse)
@router.get("/assets/cases/review", include_in_schema=False, response_class=RedirectResponse)
def asset_cases_review_page(request: Request) -> RedirectResponse:
    query = str(request.url.query or "").strip()
    suffix = f"?{query}" if query else ""
    return RedirectResponse(url=f"/react/cases/review{suffix}", status_code=307)


@router.get("/cases/versions", response_class=RedirectResponse)
@router.get("/assets/cases/versions", include_in_schema=False, response_class=RedirectResponse)
def asset_cases_versions_page(request: Request) -> RedirectResponse:
    query = str(request.url.query or "").strip()
    suffix = f"?{query}" if query else ""
    return RedirectResponse(url=f"/react/cases/versions{suffix}", status_code=307)


@router.get("/assets/test-points", response_class=RedirectResponse)
def test_point_assets_page(request: Request) -> RedirectResponse:
    query = str(request.url.query or "").strip()
    suffix = f"?{query}" if query else ""
    return RedirectResponse(url=f"/react/assets/test-points{suffix}", status_code=307)


@router.get("/cases/tags", response_class=RedirectResponse)
@router.get("/assets/tags", include_in_schema=False, response_class=RedirectResponse)
def asset_tags_page(request: Request) -> RedirectResponse:
    query = str(request.url.query or "").strip()
    suffix = f"?{query}" if query else ""
    return RedirectResponse(url=f"/react/cases/tags{suffix}", status_code=307)


@router.get("/cases/generation-failures", response_class=RedirectResponse)
def case_generation_failures_page(request: Request) -> RedirectResponse:
    query = str(request.url.query or "").strip()
    suffix = f"?{query}" if query else ""
    return RedirectResponse(url=f"/react/cases/generation-failures{suffix}", status_code=307)


@router.get("/cases/{case_id}", response_class=RedirectResponse)
@router.get("/assets/cases/{case_id}", include_in_schema=False, response_class=RedirectResponse)
def asset_case_detail_page(request: Request, case_id: str) -> RedirectResponse:
    query = str(request.url.query or "").strip()
    suffix = f"?{query}" if query else ""
    return RedirectResponse(url=f"/react/cases/{case_id}{suffix}", status_code=307)


@router.get("/assets/test-points/{asset_id}", response_class=RedirectResponse)
def test_point_asset_detail_page(request: Request, asset_id: str) -> RedirectResponse:
    query = str(request.url.query or "").strip()
    suffix = f"?{query}" if query else ""
    return RedirectResponse(url=f"/react/assets/test-points/{asset_id}{suffix}", status_code=307)


@router.get("/assets/test-points/{asset_id}/edit", response_class=RedirectResponse)
def test_point_asset_edit_page(request: Request, asset_id: str) -> RedirectResponse:
    query = str(request.url.query or "").strip()
    suffix = f"?{query}" if query else ""
    return RedirectResponse(url=f"/react/assets/test-points/{asset_id}/edit{suffix}", status_code=307)


@router.get("/assets/test-points/{asset_id}/matrix", response_class=RedirectResponse)
def test_point_coverage_matrix_page(request: Request, asset_id: str) -> RedirectResponse:
    query = str(request.url.query or "").strip()
    suffix = f"?{query}" if query else ""
    return RedirectResponse(url=f"/react/assets/test-points/{asset_id}/matrix{suffix}", status_code=307)


@router.get("/assets/page-objects", response_class=RedirectResponse)
def asset_page_objects_page(request: Request) -> RedirectResponse:
    query = str(request.url.query or "").strip()
    suffix = f"?{query}" if query else ""
    return RedirectResponse(url=f"/react/assets/page-objects{suffix}", status_code=307)


@router.get("/assets/page-objects/{page_code}/elements", response_class=RedirectResponse)
def asset_page_object_elements_page(request: Request, page_code: str) -> RedirectResponse:
    query = str(request.url.query or "").strip()
    suffix = f"?{query}" if query else ""
    return RedirectResponse(url=f"/react/assets/page-objects/{page_code}/elements{suffix}", status_code=307)


@router.get("/assets/page-objects/recorder", response_class=RedirectResponse)
def asset_page_objects_recorder_page(request: Request) -> RedirectResponse:
    query = str(request.url.query or "").strip()
    suffix = f"?{query}" if query else ""
    return RedirectResponse(url=f"/react/assets/page-objects/recorder{suffix}", status_code=307)


@router.get("/assets/api-contracts", response_class=RedirectResponse)
def asset_api_contracts_page(request: Request) -> RedirectResponse:
    query = str(request.url.query or "").strip()
    suffix = f"?{query}" if query else ""
    return RedirectResponse(url=f"/react/assets/api-contracts{suffix}", status_code=307)


@router.get("/assets/data-templates", response_class=RedirectResponse)
def asset_data_templates_page(request: Request) -> RedirectResponse:
    query = str(request.url.query or "").strip()
    suffix = f"?{query}" if query else ""
    return RedirectResponse(url=f"/react/assets/data-templates{suffix}", status_code=307)
