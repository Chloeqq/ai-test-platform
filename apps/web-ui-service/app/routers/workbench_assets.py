from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Query

from shared_backend import get_dictionary_items

from app.services import workbench_asset_service
from . import legacy_workbench


router = APIRouter(tags=["workbench-assets"])


@router.get("/api/workbench/case-dictionaries")
def get_case_dictionaries() -> dict[str, Any]:
    return {
        "items": {
            "project": get_dictionary_items("project"),
            "client": get_dictionary_items("client"),
            "page": get_dictionary_items("page"),
            "module": get_dictionary_items("module"),
            "case_type": get_dictionary_items("case_type"),
            "source": get_dictionary_items("source"),
            "case_status": get_dictionary_items("case_status"),
            "run_status": get_dictionary_items("run_status"),
            "ai_status": get_dictionary_items("ai_status"),
            "migration_status": get_dictionary_items("migration_status"),
        }
    }


@router.get("/api/workbench/cases")
def list_cases(
    project: str = Query(default="default"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    focus_case_id: str = Query(default=""),
) -> dict[str, Any]:
    legacy_workbench._sync_stage_a_workbench_state()
    legacy_workbench._ensure_dirs()
    return workbench_asset_service.build_cases_payload(
        project=project,
        page=page,
        page_size=page_size,
        focus_case_id=focus_case_id,
        collect_case_items=legacy_workbench._collect_case_items,
        paginate_case_items=legacy_workbench._paginate_case_items,
    )


@router.get("/api/workbench/cases/{case_id}")
def get_case(case_id: str, project: str = Query(default="default")) -> dict[str, Any]:
    legacy_workbench._sync_stage_a_workbench_state()
    legacy_workbench._ensure_dirs()
    return workbench_asset_service.build_case_detail(
        project=project,
        case_id=case_id,
        resolve_case_yaml_path=legacy_workbench._resolve_case_yaml_path,
        read_case_yaml=legacy_workbench._read_case_yaml,
    )


@router.put("/api/workbench/cases/{case_id}")
def save_case(case_id: str, payload: legacy_workbench.SaveCasePayload) -> dict[str, Any]:
    legacy_workbench._sync_stage_a_workbench_state()
    legacy_workbench._ensure_dirs()
    return workbench_asset_service.build_saved_case_payload(
        case_id=case_id,
        project=payload.project,
        yaml_content=payload.yaml_content,
        safe_case_id=legacy_workbench._safe_case_id,
        resolve_case_yaml_path=legacy_workbench._resolve_case_yaml_path,
        write_case_yaml=legacy_workbench._write_case_yaml,
        save_case_state=legacy_workbench._save_case_state,
        append_history=legacy_workbench._append_history,
        now_iso=legacy_workbench._now_iso,
    )


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
) -> dict[str, Any]:
    legacy_workbench._sync_stage_a_workbench_state()
    legacy_workbench._ensure_dirs()
    return workbench_asset_service.build_test_point_asset_items(
        project=project,
        page=page,
        keyword=keyword,
        source_type=source_type,
        coverage_status=coverage_status,
        review_status=review_status,
        gate_decision=gate_decision,
        selection_state=selection_state,
        state_project_dir=legacy_workbench._state_project_dir,
        normalize_page_slug=legacy_workbench._normalize_page_slug,
        load_test_point_asset=legacy_workbench._load_test_point_asset,
        latest_run_snapshot_for_case=legacy_workbench._latest_run_snapshot_for_case,
        build_traceability_summary=legacy_workbench._build_test_point_asset_traceability_summary,
        build_selection_summary=legacy_workbench._build_test_point_asset_selection_summary,
        build_coverage_summary=legacy_workbench._build_test_point_asset_coverage_summary,
        clamp_confidence=legacy_workbench._clamp_confidence,
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
) -> dict[str, Any]:
    payload = list_test_point_assets(
        project=project,
        page=page,
        keyword=keyword,
        source_type=source_type,
        coverage_status=coverage_status,
        review_status=review_status,
        gate_decision=gate_decision,
        selection_state=selection_state,
    )
    return {"item": payload.get("coverage_summary", {})}


@router.get("/api/workbench/test-point-assets/{asset_id}")
def get_test_point_asset(asset_id: str, project: str = Query(default="default")) -> dict[str, Any]:
    legacy_workbench._sync_stage_a_workbench_state()
    legacy_workbench._ensure_dirs()
    payload = workbench_asset_service.build_test_point_asset_detail(
        project=project,
        asset_id=asset_id,
        load_test_point_asset=legacy_workbench._load_test_point_asset,
        latest_run_snapshot_for_case=legacy_workbench._latest_run_snapshot_for_case,
        build_traceability_summary=legacy_workbench._build_test_point_asset_traceability_summary,
        build_selection_summary=legacy_workbench._build_test_point_asset_selection_summary,
        clamp_confidence=legacy_workbench._clamp_confidence,
    )
    if not payload:
        raise legacy_workbench.HTTPException(
            status_code=legacy_workbench.status.HTTP_404_NOT_FOUND,
            detail="test point asset not found",
        )
    return payload


@router.get("/api/workbench/test-point-assets/{asset_id}/coverage-matrix")
def get_test_point_asset_coverage_matrix(asset_id: str, project: str = Query(default="default")) -> dict[str, Any]:
    legacy_workbench._sync_stage_a_workbench_state()
    legacy_workbench._ensure_dirs()
    payload = workbench_asset_service.build_test_point_asset_detail(
        project=project,
        asset_id=asset_id,
        load_test_point_asset=legacy_workbench._load_test_point_asset,
        latest_run_snapshot_for_case=legacy_workbench._latest_run_snapshot_for_case,
        build_traceability_summary=legacy_workbench._build_test_point_asset_traceability_summary,
        build_selection_summary=legacy_workbench._build_test_point_asset_selection_summary,
        clamp_confidence=legacy_workbench._clamp_confidence,
    )
    if not payload:
        raise legacy_workbench.HTTPException(
            status_code=legacy_workbench.status.HTTP_404_NOT_FOUND,
            detail="test point asset not found",
        )
    item = payload.get("item", {}) if isinstance(payload.get("item"), dict) else {}
    return {"item": item.get("coverage_matrix", {}) if isinstance(item.get("coverage_matrix"), dict) else {}}
