# ruff: noqa: E402
import logging
import os
import subprocess  # noqa: F401 - re-exported for sibling routers
import sys
import threading
from datetime_compat import UTC
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core import page_analysis_rules

router = APIRouter(tags=["legacy-workbench"])

REPO_ROOT = Path(__file__).resolve().parents[4]
APPS_ROOT = REPO_ROOT / "apps"
if str(APPS_ROOT) not in sys.path:
    sys.path.insert(0, str(APPS_ROOT))

from app.services import workbench_analysis_service as _workbench_analysis_service
from app.services import workbench_gate_service as _workbench_gate_service
from app.services import workbench_asset_service as _workbench_asset_service
from app.services import workbench_generation_service as _workbench_generation_service
from app.services import workbench_history_service as _workbench_history_service
from app.services import workbench_orchestrator_service as _workbench_orchestrator_service
from app.services import workbench_reporting_service as _workbench_reporting_service
from app.services import workbench_review_service as _workbench_review_service
from app.services import workbench_runtime_service as _workbench_runtime_service
from app.services import workbench_task_service as _workbench_task_service
from app.services import workbench_state_store as _workbench_state_store

WEB_UI_STATE_ROOT = REPO_ROOT / "web-ui" / "state"
WEB_UI_DEFAULT_STATE_DIR = WEB_UI_STATE_ROOT / "default"
WEB_UI_RUNS_DIR = WEB_UI_STATE_ROOT / "runs"
WEB_UI_REPORTING_DIR = WEB_UI_STATE_ROOT / "reporting"
TEST_POINTS_ROOT = WEB_UI_STATE_ROOT / "test-points"
ASSETS_CASES_ROOT = REPO_ROOT / "assets" / "test-cases"
AI_CASES_ROOT = ASSETS_CASES_ROOT / "ai-generated"
PAGE_OBJECTS_ROOT = REPO_ROOT / "assets" / "page-objects" / "web"
RUNNER_ROOT = REPO_ROOT / "runners" / "web-playwright-python"
ALLURE_RESULTS_ROOT = RUNNER_ROOT / "allure-results"
ALLURE_REPORT_ROOT = RUNNER_ROOT / "allure-report"
ALLURE_SNAPSHOTS_ROOT = RUNNER_ROOT / "allure-report-snapshots"
EXECUTION_REPORTS_ROOT = REPO_ROOT / "reports" / "executions"
HISTORY_FILE = WEB_UI_DEFAULT_STATE_DIR / "history.json"
RUNTIME_RUNS_FILE = WEB_UI_DEFAULT_STATE_DIR / "runtime-runs.json"
DEFECT_LINKS_FILE = WEB_UI_REPORTING_DIR / "defect-links.json"
REVIEW_DECISIONS_FILE = WEB_UI_REPORTING_DIR / "review-decisions.json"
EXECUTION_GATE_DECISIONS_FILE = WEB_UI_REPORTING_DIR / "execution-gate-decisions.json"
FAILURE_SOURCE_CALIBRATIONS_FILE = WEB_UI_REPORTING_DIR / "failure-source-calibrations.json"

_FILE_LOCK = threading.Lock()
_RUN_LOCK = threading.Lock()
_RUN_JOBS: dict[str, dict[str, Any]] = {}
SETTINGS = get_settings()
LOGGER = logging.getLogger(__name__)

try:
    from shared_backend.schemas import (
        normalize_evidence_manifest_v1,
        normalize_execution_record_v1,
    )
except Exception:  # pragma: no cover - keep runtime resilient when shared package unavailable
    normalize_evidence_manifest_v1 = None  # type: ignore[assignment]
    normalize_execution_record_v1 = None  # type: ignore[assignment]

PAGE_ALIAS_MAP = {
    "addprouct": "addproduct",
    "add-product": "addproduct",
}

PAGE_CANONICAL_HASH_ROUTE = {
    "product": "/pms/product",
    "addproduct": "/pms/addProduct",
    "order": "/oms/order",
}

PAGE_FRIENDLY_NAME = {
    "product": "商品列表",
    "addproduct": "添加商品",
    "order": "订单列表",
    "returnapply": "退货申请",
}

PAGE_OBJECT_DEFAULTS: dict[str, dict[str, dict[str, str]]] = {
    "product": {
        "login_button": {"locator_type": "role", "role": "button", "locator_value": "登录"},
        "product_menu": {"locator_type": "role", "role": "menuitem", "locator_value": "商品列表"},
        "product_list_title": {"locator_type": "text", "locator_value": "商品列表"},
        "search_input": {"locator_type": "css", "locator_value": "input[placeholder*='商品']"},
        "search_button": {"locator_type": "role", "role": "button", "locator_value": "查询"},
        "product_table": {"locator_type": "css", "locator_value": ".el-table"},
    },
    "addproduct": {
        "login_button": {"locator_type": "role", "role": "button", "locator_value": "登录"},
        "addproduct_menu": {"locator_type": "role", "role": "menuitem", "locator_value": "添加商品"},
        "addproduct_list_title": {"locator_type": "text", "locator_value": "添加商品"},
        "addproduct_form": {"locator_type": "css", "locator_value": ".el-form"},
        "save_button": {"locator_type": "role", "role": "button", "locator_value": "保存"},
    },
    "order": {
        "login_button": {"locator_type": "role", "role": "button", "locator_value": "登录"},
        "order_menu": {"locator_type": "role", "role": "menuitem", "locator_value": "订单列表"},
        "order_list_title": {"locator_type": "text", "locator_value": "订单列表"},
        "order_table": {"locator_type": "css", "locator_value": ".el-table"},
    },
}


class GenerateCasePayload(BaseModel):
    project: str = Field(default="default")
    page: str = Field(default="")
    requirement: str = Field(default="")
    title: str = Field(default="")
    case_id: str = Field(default="")
    priority: str = Field(default="P1")
    tags: list[str] = Field(default_factory=lambda: ["ai-generated"])
    source: str = Field(default="manual")
    input_sources: list[dict[str, Any]] = Field(default_factory=list)
    openapi_spec: dict[str, Any] | None = None
    prd_text: str = Field(default="")
    prd_url: str = Field(default="")
    user_story: str = Field(default="")
    git_diff: str = Field(default="")
    git_diff_path: str = Field(default="")
    openapi_url: str = Field(default="")
    defect_ticket: str = Field(default="")
    runtime_logs: str = Field(default="")


class SaveCasePayload(BaseModel):
    project: str = Field(default="default")
    yaml_content: str = Field(min_length=1)


class RunCasePayload(BaseModel):
    project: str = Field(default="default")
    case_id: str = Field(min_length=1)
    case_path: str = Field(default="")
    source: str = Field(default="manual")


class AutoRunPayload(BaseModel):
    project: str = Field(default="default")
    requirement: str = Field(default="")
    page_urls: list[str] = Field(min_length=1, max_length=20)
    source: str = Field(default="manual")
    input_sources: list[dict[str, Any]] = Field(default_factory=list)
    openapi_spec: dict[str, Any] | None = None
    prd_text: str = Field(default="")
    prd_url: str = Field(default="")
    user_story: str = Field(default="")
    git_diff: str = Field(default="")
    git_diff_path: str = Field(default="")
    openapi_url: str = Field(default="")
    defect_ticket: str = Field(default="")
    runtime_logs: str = Field(default="")
    wait_seconds: int = Field(default=240, ge=30, le=1800)


class DefectPayload(BaseModel):
    case_id: str = Field(min_length=1)
    defect_id: str = Field(min_length=1)
    defect_url: str = Field(default="")
    system: str = Field(default="manual")
    note: str = Field(default="")


class WorkbenchReviewPayload(BaseModel):
    project: str = Field(default="default")
    run_id: str = Field(min_length=1)
    case_id: str = Field(default="")
    page: str = Field(min_length=1)
    review_type: str = Field(min_length=1)
    status: str = Field(default="confirmed")
    items: list[dict[str, Any]] = Field(default_factory=list)
    note: str = Field(default="")
    failure_source_feedback: dict[str, Any] | None = None


class ExecutionGateDecisionPayload(BaseModel):
    project: str = Field(default="default")
    run_id: str = Field(min_length=1)
    case_id: str = Field(default="")
    page: str = Field(min_length=1)
    decision: str = Field(min_length=1)
    note: str = Field(default="")


class ExecutionGateDecisionActionPayload(BaseModel):
    project: str = Field(default="default")
    run_id: str = Field(min_length=1)
    page: str = Field(min_length=1)
    note: str = Field(default="")


def _now_iso() -> str:
    return _workbench_state_store.now_iso()


def _normalize_failure_source_value(value: Any) -> str:
    return _workbench_reporting_service.normalize_failure_source_value(value)


def _sanitize_review_items(items: list[dict[str, Any]], *, review_type: str) -> list[dict[str, Any]]:
    return _workbench_review_service.sanitize_review_items(items, review_type=review_type)


def _sanitize_failure_source_feedback(
    feedback: dict[str, Any] | None,
    *,
    predicted_source: str,
) -> dict[str, Any]:
    return _workbench_reporting_service.sanitize_failure_source_feedback(
        feedback,
        predicted_source=predicted_source,
    )


def _record_failure_source_calibration_sample(
    *,
    review_record: dict[str, Any],
    feedback: dict[str, Any] | None = None,
) -> dict[str, Any]:
    with _FILE_LOCK:
        return _workbench_reporting_service.record_failure_source_calibration_sample(
            review_record=review_record,
            feedback=feedback,
            resolve_run_failure_snapshot_fn=_resolve_run_failure_snapshot,
            clamp_confidence=_clamp_confidence,
            reviewer_display_name_fn=_reviewer_display_name,
            now_iso_fn=_now_iso,
            read_json_list_fn=_read_json_list,
            write_json_list_fn=_write_json_list,
            calibration_file=FAILURE_SOURCE_CALIBRATIONS_FILE,
        )


def _review_decisions_for_run(run_id: str, *, project: str = "", page: str = "") -> dict[tuple[str, str], dict[str, Any]]:
    return _workbench_review_service.review_decisions_for_run(
        run_id,
        project=project,
        page=page,
        read_json_list_fn=_read_json_list,
        review_decisions_file=REVIEW_DECISIONS_FILE,
        normalize_page_slug_fn=_normalize_page_slug,
        normalize_review_type_fn=_normalize_review_type,
        normalize_review_status_fn=_normalize_review_status,
        sanitize_review_items_fn=_sanitize_review_items,
    )


def _reviewer_display_name(entry: dict[str, Any] | None) -> str:
    return _workbench_analysis_service.reviewer_display_name(entry)


def _normalize_history_text_list(value: Any, *, limit: int = 10) -> list[str]:
    return _workbench_gate_service.normalize_history_text_list(value, limit=limit)


def _resolve_execution_gate_audit_snapshot(
    *,
    project: str,
    run_id: str,
    page: str,
) -> dict[str, Any]:
    _sync_stage_b_workbench_gate()
    return _workbench_gate_service.resolve_execution_gate_audit_snapshot(
        project=project,
        run_id=run_id,
        page=page,
        find_run_item=_find_run_item,
        normalize_page_slug_fn=_normalize_page_slug,
        build_execution_gate_audit_snapshot_fn=_build_execution_gate_audit_snapshot,
    )


def _summarize_quality_gate_events(limit: int = 500, *, alert_code: str = "", page: str = "") -> dict[str, Any]:
    _ensure_dirs()
    _sync_stage_a_workbench_state()
    history_items = _read_json_list(HISTORY_FILE)
    return _workbench_history_service.summarize_quality_gate_events(
        history_items,
        limit=limit,
        alert_code=alert_code,
        page=page,
        normalize_page_slug=_normalize_page_slug,
    )


def _normalize_execution_record_payload(payload: dict[str, Any], *, strict: bool = False) -> dict[str, Any]:
    if normalize_execution_record_v1 is None:
        return payload if isinstance(payload, dict) else {}
    try:
        normalized, warnings = normalize_execution_record_v1(payload, strict=strict)
        for warning in warnings:
            LOGGER.warning("execution_record normalization warning: %s", warning)
        return normalized
    except Exception as exc:
        LOGGER.warning("execution_record normalization failed, keep raw payload: %s", exc)
        return payload if isinstance(payload, dict) else {}


def _normalize_evidence_manifest_payload(payload: dict[str, Any], *, strict: bool = False) -> dict[str, Any]:
    if normalize_evidence_manifest_v1 is None:
        return payload if isinstance(payload, dict) else {}
    try:
        normalized, warnings = normalize_evidence_manifest_v1(payload, strict=strict)
        for warning in warnings:
            LOGGER.warning("evidence_manifest normalization warning: %s", warning)
        return normalized
    except Exception as exc:
        LOGGER.warning("evidence_manifest normalization failed, keep raw payload: %s", exc)
        return payload if isinstance(payload, dict) else {}


def _normalize_test_point_plan_payload(payload: dict[str, Any], *, strict: bool = False) -> dict[str, Any]:
    return _workbench_analysis_service.normalize_test_point_plan(payload, strict=strict)


def _normalize_test_point_plan_payload_for_asset(payload: dict[str, Any], strict: bool = False) -> dict[str, Any]:
    return _normalize_test_point_plan_payload(payload, strict=strict)


def _runtime_run_id(item: dict[str, Any]) -> str:
    return _workbench_runtime_service.runtime_run_id(item)


def _build_runtime_execution_record(
    *,
    run_id: str,
    case_id: str,
    project: str,
    source: str,
    mode: str,
    status: str,
    started_at: str,
    finished_at: str,
    return_code: int | None,
    created_at: str = "",
) -> dict[str, Any]:
    return _workbench_runtime_service.build_runtime_execution_record(
        run_id=run_id,
        case_id=case_id,
        project=project,
        source=source,
        mode=mode,
        status=status,
        started_at=started_at,
        finished_at=finished_at,
        return_code=return_code,
        created_at=created_at,
        normalize_execution_record_payload=_normalize_execution_record_payload,
    )


def _runtime_view_from_entry(entry: dict[str, Any]) -> dict[str, Any]:
    return _workbench_runtime_service.runtime_view_from_entry(
        entry,
        normalize_execution_record_payload=_normalize_execution_record_payload,
        normalize_page_slug=_normalize_page_slug,
        build_page_analysis_context=_build_page_analysis_context,
        build_item_review_state=_build_item_review_state,
        build_run_review_state_from_decisions=_build_run_review_state_from_decisions,
        build_test_point_asset_gate_context=_build_test_point_asset_gate_context,
        build_execution_gate=_build_execution_gate,
        build_review_audit_summary=_build_review_audit_summary,
        build_review_audit_timeline=_build_review_audit_timeline,
        build_risk_report_summary=_build_risk_report_summary,
        build_self_healing_summary=_build_self_healing_summary,
        execution_gate_decision_for_run=_execution_gate_decision_for_run,
    )


def _runtime_view_with_execution_record_preferred(entry: dict[str, Any]) -> dict[str, Any]:
    return _workbench_runtime_service.runtime_view_with_execution_record_preferred(
        entry,
        runtime_view_from_entry_fn=_runtime_view_from_entry,
        load_runtime_execution_record_from_artifacts=_load_runtime_execution_record_from_artifacts,
        normalize_execution_record_payload=_normalize_execution_record_payload,
    )


def _safe_case_id(raw: str) -> str:
    return _workbench_gate_service.safe_case_id(raw)


def _normalize_page_slug(value: str) -> str:
    return _workbench_gate_service.normalize_page_slug(value)


def _extract_page_from_url(raw_url: str) -> tuple[str, str]:
    return _workbench_analysis_service.extract_page_from_url(
        raw_url,
        normalize_page_slug_fn=_normalize_page_slug,
        http_exception_cls=HTTPException,
        bad_request_status=status.HTTP_400_BAD_REQUEST,
    )


def _build_system_requirement(*, page: str, page_url: str = "", has_multisource_inputs: bool = False) -> str:
    return _workbench_generation_service.build_system_requirement(
        page=page,
        page_url=page_url,
        has_multisource_inputs=has_multisource_inputs,
        normalize_page_slug_fn=_normalize_page_slug,
        page_friendly_name=PAGE_FRIENDLY_NAME,
    )


def _resolve_page_url(raw_url: str, page: str) -> str:
    return _workbench_analysis_service.resolve_page_url(
        raw_url,
        page,
        canonical_hash_routes=PAGE_CANONICAL_HASH_ROUTE,
    )


def _route_signature(raw_url: str) -> str:
    return _workbench_analysis_service.route_signature(raw_url)


def _is_allowed_host_pattern(hostname: str) -> bool:
    return _workbench_analysis_service.is_allowed_host_pattern(
        hostname,
        patterns=[str(item).strip().lower() for item in getattr(SETTINGS, "page_surface_allowed_hosts", []) if str(item).strip()],
    )


def _is_private_or_local_hostname(hostname: str, port: int | None) -> bool:
    return _workbench_analysis_service.is_private_or_local_hostname(hostname, port)


def _validate_page_surface_url(raw_url: str) -> str:
    return _workbench_analysis_service.validate_page_surface_url(
        raw_url,
        allow_private_hosts=bool(getattr(SETTINGS, "page_surface_allow_private_hosts", False)),
        allowed_host_patterns=[str(item).strip().lower() for item in getattr(SETTINGS, "page_surface_allowed_hosts", []) if str(item).strip()],
        http_exception_cls=HTTPException,
        bad_request_status=status.HTTP_400_BAD_REQUEST,
        unprocessable_entity_status=422,
    )


def _default_page_elements(page: str) -> dict[str, dict[str, str]]:
    return _workbench_analysis_service.default_page_elements(page)


def _ensure_page_object(page: str) -> Path:
    return _workbench_analysis_service.ensure_page_object(
        page,
        page_objects_root=PAGE_OBJECTS_ROOT,
        default_page_elements_fn=_workbench_analysis_service.default_page_elements,
    )


def _post_json(url: str, payload: dict[str, Any], timeout_seconds: int = 300) -> dict[str, Any]:
    return _workbench_orchestrator_service.post_json(
        url,
        payload,
        timeout_seconds=timeout_seconds,
        http_exception_cls=HTTPException,
        bad_gateway_status=status.HTTP_502_BAD_GATEWAY,
        gateway_timeout_status=status.HTTP_504_GATEWAY_TIMEOUT,
    )


def _extract_quality_gate(payload: Any) -> dict[str, Any] | None:
    return _workbench_generation_service.extract_quality_gate(payload)


def _is_quality_gate_blocked(payload: Any) -> tuple[bool, dict[str, Any] | None]:
    return _workbench_generation_service.is_quality_gate_blocked(payload)


def _render_requirement_spec_markdown(requirement_spec: dict[str, Any]) -> str:
    return _workbench_generation_service.render_requirement_spec_markdown(requirement_spec)


def _run_orchestrator_generate(
    *,
    requirement: str,
    page: str,
    source: str,
    input_sources: list[dict[str, Any]] | None = None,
    openapi_spec: dict[str, Any] | None = None,
    prd_text: str = "",
    prd_url: str = "",
    user_story: str = "",
    git_diff: str = "",
    git_diff_path: str = "",
    openapi_url: str = "",
    defect_ticket: str = "",
    runtime_logs: str = "",
) -> dict[str, Any]:
    endpoint = f"{SETTINGS.orchestrator_url.rstrip('/')}/orchestrate"
    payload: dict[str, Any] = {
        "requirement": requirement,
        "page": page,
        "source": source,
        "mode": "generate_only",
        "execute": False,
    }
    if input_sources:
        payload["input_sources"] = input_sources
    if isinstance(openapi_spec, dict) and openapi_spec:
        payload["openapi_spec"] = openapi_spec
    if prd_text.strip():
        payload["prd_text"] = prd_text
    if prd_url.strip():
        payload["prd_url"] = prd_url
    if user_story.strip():
        payload["user_story"] = user_story
    if git_diff.strip():
        payload["git_diff"] = git_diff
    if git_diff_path.strip():
        payload["git_diff_path"] = git_diff_path
    if openapi_url.strip():
        payload["openapi_url"] = openapi_url
    if defect_ticket.strip():
        payload["defect_ticket"] = defect_ticket
    if runtime_logs.strip():
        payload["runtime_logs"] = runtime_logs
    return _post_json(
        endpoint,
        payload,
        timeout_seconds=SETTINGS.orchestrator_timeout_seconds,
    )


def _run_orchestrator_parse(
    *,
    requirement: str,
    page: str,
    source: str,
    input_sources: list[dict[str, Any]] | None = None,
    openapi_spec: dict[str, Any] | None = None,
    prd_text: str = "",
    prd_url: str = "",
    user_story: str = "",
    git_diff: str = "",
    git_diff_path: str = "",
    openapi_url: str = "",
    defect_ticket: str = "",
    runtime_logs: str = "",
) -> dict[str, Any]:
    endpoint = f"{SETTINGS.orchestrator_url.rstrip('/')}/requirements/parse"
    payload: dict[str, Any] = {
        "requirement": requirement,
        "page": page,
        "source": source,
    }
    if input_sources:
        payload["input_sources"] = input_sources
    if isinstance(openapi_spec, dict) and openapi_spec:
        payload["openapi_spec"] = openapi_spec
    if prd_text.strip():
        payload["prd_text"] = prd_text
    if prd_url.strip():
        payload["prd_url"] = prd_url
    if user_story.strip():
        payload["user_story"] = user_story
    if git_diff.strip():
        payload["git_diff"] = git_diff
    if git_diff_path.strip():
        payload["git_diff_path"] = git_diff_path
    if openapi_url.strip():
        payload["openapi_url"] = openapi_url
    if defect_ticket.strip():
        payload["defect_ticket"] = defect_ticket
    if runtime_logs.strip():
        payload["runtime_logs"] = runtime_logs
    return _post_json(endpoint, payload, timeout_seconds=SETTINGS.orchestrator_timeout_seconds)


def _run_orchestrator_risk(
    *,
    requirement_spec: dict[str, Any],
    execution_plan: dict[str, Any],
    execution_record: dict[str, Any],
    failure_analysis: dict[str, Any],
    failure_triage: dict[str, Any] | None = None,
) -> dict[str, Any]:
    endpoint = f"{SETTINGS.orchestrator_url.rstrip('/')}/risk/evaluate"
    payload = {
        "requirement_spec": requirement_spec if isinstance(requirement_spec, dict) else {},
        "execution_plan": execution_plan if isinstance(execution_plan, dict) else {},
        "execution_record": execution_record if isinstance(execution_record, dict) else {},
        "failure_analysis": failure_analysis if isinstance(failure_analysis, dict) else {},
        "failure_triage": failure_triage if isinstance(failure_triage, dict) else {},
    }
    return _post_json(endpoint, payload, timeout_seconds=SETTINGS.orchestrator_timeout_seconds)


def _build_requirement_spec_for_risk(*, page: str, requirement: str, quality_gate: dict[str, Any] | None = None) -> dict[str, Any]:
    return _workbench_generation_service.build_requirement_spec_for_risk(
        page=page,
        requirement=requirement,
        quality_gate=quality_gate,
    )


def _build_execution_gate(
    *,
    page: str,
    final_status: str,
    coverage: dict[str, Any],
    page_surface_summary: dict[str, Any],
    page_semantic_summary: dict[str, Any],
    page_object_summary: dict[str, Any],
    test_points: dict[str, Any],
    review_state: dict[str, Any],
    risk_report: dict[str, Any] | None = None,
    test_point_asset_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return _workbench_gate_service.build_execution_gate(
        page=page,
        final_status=final_status,
        coverage=coverage,
        page_surface_summary=page_surface_summary,
        page_semantic_summary=page_semantic_summary,
        page_object_summary=page_object_summary,
        test_points=test_points,
        review_state=review_state,
        risk_report=risk_report,
        test_point_asset_context=test_point_asset_context,
        dedup_keep_order_fn=_dedup_keep_order,
    )


def _execution_gate_policy_baseline() -> dict[str, Any]:
    return _workbench_gate_service.execution_gate_policy_baseline()


def _build_execution_plan_for_risk(
    *,
    page: str,
    steps: list[dict[str, Any]],
    test_points: dict[str, Any],
    coverage: dict[str, Any],
    page_surface_summary: dict[str, Any],
    page_semantic_summary: dict[str, Any],
    page_object_summary: dict[str, Any],
    review_state: dict[str, Any],
    final_status: str,
) -> dict[str, Any]:
    return _workbench_generation_service.build_execution_plan_for_risk(
        page=page,
        steps=steps,
        test_points=test_points,
        coverage=coverage,
        page_surface_summary=page_surface_summary,
        page_semantic_summary=page_semantic_summary,
        page_object_summary=page_object_summary,
        review_state=review_state,
        final_status=final_status,
        build_execution_gate_fn=_build_execution_gate,
    )


def _build_failure_analysis_for_risk(*, final_status: str, page_object_summary: dict[str, Any], test_points: dict[str, Any]) -> dict[str, Any]:
    return _workbench_analysis_service.build_failure_analysis_for_risk(
        final_status=final_status,
        page_object_summary=page_object_summary,
        test_points=test_points,
    )


def _evaluate_risk_report(
    *,
    page: str,
    requirement: str,
    quality_gate: dict[str, Any] | None,
    steps: list[dict[str, Any]],
    final_status: str,
    run_id: str,
    project: str,
    page_surface_summary: dict[str, Any],
    page_object_summary: dict[str, Any],
    test_points: dict[str, Any],
    review_state: dict[str, Any],
    page_surface: dict[str, Any] | None = None,
    page_object: dict[str, Any] | None = None,
    requirement_spec: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return _workbench_analysis_service.evaluate_risk_report(
        page=page,
        requirement=requirement,
        quality_gate=quality_gate,
        steps=steps,
        final_status=final_status,
        run_id=run_id,
        project=project,
        page_surface_summary=page_surface_summary,
        page_object_summary=page_object_summary,
        test_points=test_points,
        review_state=review_state,
        page_surface=page_surface,
        page_object=page_object,
        requirement_spec=requirement_spec,
        build_page_analysis_context_fn=_build_page_analysis_context,
        build_requirement_spec_for_risk_fn=_build_requirement_spec_for_risk,
        build_execution_plan_for_risk_fn=_build_execution_plan_for_risk,
        find_run_item_fn=_find_run_item,
        build_runtime_execution_record_fn=_build_runtime_execution_record,
        run_orchestrator_risk_fn=_run_orchestrator_risk,
        build_risk_report_fn=_build_risk_report,
        http_exception_cls=HTTPException,
    )


def _save_test_point_plan(
    *,
    project: str,
    case_id: str,
    page: str,
    page_url: str,
    requirement: str,
    plan: dict[str, Any],
    case_path: Path | None = None,
    page_object_path: Path | None = None,
) -> Path:
    return _workbench_asset_service.save_test_point_plan(
        project=project,
        case_id=case_id,
        page=page,
        page_url=page_url,
        requirement=requirement,
        plan=plan,
        now_iso_fn=_now_iso,
        normalize_test_point_plan_payload=_normalize_test_point_plan_payload_for_asset,
        upsert_test_point_asset_snapshot=lambda **kwargs: _workbench_asset_service.upsert_test_point_asset_snapshot(
            **kwargs,
            now_iso_fn=_now_iso,
            count_test_point_types_fn=lambda items: _count_test_point_types(items),
            build_test_point_asset_semantic_summary_fn=lambda page_name, plan_payload: _build_test_point_asset_semantic_summary(
                page=page_name,
                normalized_plan=plan_payload,
            ),
            build_test_point_asset_technique_summary_fn=lambda plan_payload: _build_test_point_asset_technique_summary(
                normalized_plan=plan_payload,
            ),
            merge_reference_items_fn=lambda existing, new: _merge_reference_items(existing, new),
        ),
        state_root=TEST_POINTS_ROOT,
        case_path=case_path,
        page_object_path=page_object_path,
    )


def _count_test_point_types(points: list[dict[str, Any]]) -> dict[str, int]:
    return _workbench_asset_service.count_test_point_types(points)


def _build_test_point_asset_semantic_summary(
    *,
    page: str,
    normalized_plan: dict[str, Any],
) -> dict[str, Any]:
    return _workbench_asset_service.build_test_point_asset_semantic_summary(
        page=page,
        normalized_plan=normalized_plan,
        normalize_page_slug_fn=_normalize_page_slug,
        clamp_confidence=_clamp_confidence,
    )


def _build_test_point_asset_technique_summary(
    *,
    normalized_plan: dict[str, Any],
) -> dict[str, Any]:
    return _workbench_asset_service.build_test_point_asset_technique_summary(
        normalized_plan=normalized_plan,
    )


def _merge_reference_items(*reference_lists: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return _workbench_asset_service.merge_reference_items(*reference_lists)


def _upsert_test_point_asset_snapshot(
    *,
    project: str,
    case_id: str,
    page: str,
    requirement: str,
    normalized_plan: dict[str, Any],
    plan_path: Path,
    case_path: Path | None = None,
    page_object_path: Path | None = None,
) -> dict[str, Any]:
    return _workbench_asset_service.upsert_test_point_asset_snapshot(
        project=project,
        case_id=case_id,
        page=page,
        requirement=requirement,
        normalized_plan=normalized_plan,
        plan_path=plan_path,
        case_path=case_path,
        page_object_path=page_object_path,
        now_iso_fn=_now_iso,
        count_test_point_types_fn=lambda items: _count_test_point_types(items),
        build_test_point_asset_semantic_summary_fn=lambda page_name, plan_payload: _build_test_point_asset_semantic_summary(
            page=page_name,
            normalized_plan=plan_payload,
        ),
        build_test_point_asset_technique_summary_fn=lambda plan_payload: _build_test_point_asset_technique_summary(
            normalized_plan=plan_payload,
        ),
        merge_reference_items_fn=lambda existing, new: _merge_reference_items(existing, new),
        state_root=TEST_POINTS_ROOT,
    )


def _load_test_point_asset(project: str, case_id: str) -> dict[str, Any]:
    return _workbench_asset_service.load_test_point_asset_with_root(project, case_id, state_root=TEST_POINTS_ROOT)


def _latest_run_snapshot_for_case(*, project: str, case_id: str, page: str = "") -> dict[str, Any]:
    runtime_jobs: list[dict[str, Any]] = []
    with _RUN_LOCK:
        runtime_jobs.extend([dict(item) for item in _RUN_JOBS.values()])
    return _workbench_asset_service.latest_run_snapshot_for_case(
        project=project,
        case_id=case_id,
        page=page,
        safe_case_id_fn=_safe_case_id,
        normalize_page_slug_fn=_normalize_page_slug,
        runtime_jobs=runtime_jobs,
        runtime_runs_file=RUNTIME_RUNS_FILE,
        runtime_view_with_execution_record_preferred_fn=_runtime_view_with_execution_record_preferred,
        read_json_list_fn=_read_json_list,
        build_review_audit_summary_fn=_build_review_audit_summary,
        build_page_semantic_summary_fn=_build_page_semantic_summary,
        build_execution_gate_audit_snapshot_fn=_build_execution_gate_audit_snapshot,
        build_risk_report_summary_fn=_build_risk_report_summary,
    )


def _build_test_point_asset_traceability_summary(
    *,
    asset: dict[str, Any],
    latest_run: dict[str, Any] | None,
) -> dict[str, Any]:
    return _workbench_asset_service.build_test_point_asset_traceability_summary(
        asset=asset,
        latest_run=latest_run,
        build_test_point_asset_technique_summary_fn=lambda normalized_plan: _build_test_point_asset_technique_summary(
            normalized_plan=normalized_plan
        ),
        build_review_audit_summary_fn=_build_review_audit_summary,
        build_page_semantic_summary_fn=_build_page_semantic_summary,
        build_risk_report_summary_fn=_build_risk_report_summary,
        build_execution_gate_fn=_build_execution_gate,
        build_execution_gate_audit_snapshot_fn=_build_execution_gate_audit_snapshot,
        clamp_confidence=_clamp_confidence,
    )


def _build_test_point_asset_selection_summary(
    *,
    traceability_summary: dict[str, Any],
) -> dict[str, Any]:
    return _workbench_asset_service.build_test_point_asset_selection_summary(
        traceability_summary=traceability_summary
    )


def _build_test_point_asset_gate_context(
    *,
    project: str,
    case_id: str,
    page: str,
    coverage: dict[str, Any],
    review_state: dict[str, Any],
    risk_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return _workbench_asset_service.build_test_point_asset_gate_context(
        project=project,
        case_id=case_id,
        page=page,
        coverage=coverage,
        review_state=review_state,
        risk_report=risk_report,
        safe_case_id_fn=_safe_case_id,
        load_test_point_asset=_load_test_point_asset,
        build_review_audit_summary_fn=_build_review_audit_summary,
        build_traceability_summary=_build_test_point_asset_traceability_summary,
        build_selection_summary=_build_test_point_asset_selection_summary,
    )


def _build_test_point_asset_summary(project: str, case_id: str) -> dict[str, Any]:
    return _workbench_asset_service.build_test_point_asset_summary(
        project=project,
        case_id=case_id,
        load_test_point_asset=_load_test_point_asset,
        latest_run_snapshot_for_case=_latest_run_snapshot_for_case,
        build_traceability_summary=_build_test_point_asset_traceability_summary,
        build_selection_summary=_build_test_point_asset_selection_summary,
        clamp_confidence=_clamp_confidence,
    )


def _build_test_point_asset_coverage_summary(
    *,
    items: list[dict[str, Any]],
    filter_snapshot: dict[str, Any],
) -> dict[str, Any]:
    return _workbench_asset_service.build_test_point_asset_coverage_summary(
        items=items,
        filter_snapshot=filter_snapshot,
    )


def _attach_test_point_asset_summary(item: dict[str, Any] | None) -> dict[str, Any]:
    source = dict(item) if isinstance(item, dict) else {}
    project = str(source.get("project", "default")).strip() or "default"
    case_id = _safe_case_id(str(source.get("case_id", "")).strip()) if str(source.get("case_id", "")).strip() else ""
    if not case_id:
        return source
    source["test_point_asset"] = _build_test_point_asset_summary(project, case_id)
    return source


def _build_fallback_case(
    *,
    page: str,
    requirement: str,
    resolved_page_url: str,
    steps: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    case_id = _safe_case_id(f"SMOKE-{page.upper()}-{datetime.now(UTC).strftime('%H%M%S')}")
    fallback_steps = steps or [
        {"action": "login"},
        {"action": "goto", "value": resolved_page_url},
        {"action": "assert_url", "value": resolved_page_url},
    ]
    return {
        "version": "v4",
        "id": case_id,
        "title": f"SMOKE-{page.upper()}-FALLBACK",
        "module": page,
        "priority": "P1",
        "tags": ["ai-generated", "smoke", page, "fallback"],
        "owner": "qa-team",
        "status": "automated",
        "description": f"Fallback URL-driven smoke for {page}.",
        "requirement": [requirement, f"url: {resolved_page_url}"],
        "data": {},
        "execution": {
            "runner": "playwright",
            "page": page,
            "variables": {},
            "steps": fallback_steps,
        },
    }


def _extract_requirement_search_value(requirement: str) -> str:
    return _workbench_analysis_service.extract_requirement_search_value(requirement)


def _requires_search_flow(requirement: str) -> bool:
    return _workbench_analysis_service.requires_search_flow(requirement)


def _requires_dialog_flow(requirement: str) -> bool:
    return page_analysis_rules.requires_dialog_flow(requirement)


def _safe_element_key(value: str, fallback: str) -> str:
    return _workbench_analysis_service.safe_element_key(value, fallback)


def _clamp_confidence(value: float) -> float:
    return page_analysis_rules.clamp_confidence(value)


def _normalize_page_surface(payload: dict[str, Any] | None, *, page: str = "", requested_url: str = "") -> dict[str, Any]:
    return _workbench_analysis_service.normalize_page_surface(payload, page=page, requested_url=requested_url)


def _normalize_page_object_draft(payload: dict[str, Any] | None, *, page: str = "", path: str = "") -> dict[str, Any]:
    return _workbench_analysis_service.normalize_page_object_draft(payload, page=page, path=path)


def _consume_model_bundle(
    *,
    page: str,
    project: str = "default",
    case_id: str = "",
    page_url: str = "",
    page_surface: dict[str, Any] | None = None,
    page_object: dict[str, Any] | None = None,
    test_points: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return _workbench_analysis_service.consume_model_bundle(
        page=_normalize_page_slug(page),
        project=project,
        case_id=case_id,
        page_url=page_url,
        page_surface=page_surface,
        page_object=page_object,
        test_points=test_points,
    )


def _build_page_analysis_context(
    *,
    page: str,
    project: str = "default",
    case_id: str = "",
    page_url: str = "",
    page_surface: dict[str, Any] | None = None,
    page_object: dict[str, Any] | None = None,
    test_points: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return _workbench_analysis_service.build_page_analysis_context(
        page=_normalize_page_slug(page),
        project=project,
        case_id=case_id,
        page_url=page_url,
        page_surface=page_surface,
        page_object=page_object,
        test_points=test_points,
    )


def _build_surface_element_candidate(
    *,
    key: str,
    label: str,
    locator_type: str,
    locator_value: str,
    confidence: float,
    source: str,
    role: str = "",
    warnings: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return _workbench_analysis_service.build_surface_element_candidate(
        key=key,
        label=label,
        locator_type=locator_type,
        locator_value=locator_value,
        confidence=confidence,
        source=source,
        role=role,
        warnings=warnings,
        metadata=metadata,
    )


def _build_surface_element_candidates(page: str, surface: dict[str, Any]) -> list[dict[str, Any]]:
    return _workbench_analysis_service.build_surface_element_candidates(page, surface)


def _surface_confidence_summary(surface: dict[str, Any]) -> dict[str, Any]:
    return _workbench_analysis_service.surface_confidence_summary(surface)


def _surface_inferred_elements(page: str, surface: dict[str, Any]) -> dict[str, dict[str, str]]:
    return _workbench_analysis_service.surface_inferred_elements(page, surface)


def _build_surface_result_from_snapshot(
    *,
    page_url: str,
    payload: dict[str, Any],
    frame_surface: dict[str, Any],
    login_url: str,
    login_attempted: bool,
    login_succeeded: bool,
    redirected_to_login: bool,
    login_network_idle_reached: bool,
    target_network_idle_reached: bool,
    marker_selector: str,
    selector_wait_status: str,
    requested_route: str,
    final_route: str,
    route_mismatch: bool,
    stability: dict[str, Any],
) -> dict[str, Any]:
    return _workbench_analysis_service.build_surface_result_from_snapshot(
        page_url=page_url,
        payload=payload,
        frame_surface=frame_surface,
        login_url=login_url,
        login_attempted=login_attempted,
        login_succeeded=login_succeeded,
        redirected_to_login=redirected_to_login,
        login_network_idle_reached=login_network_idle_reached,
        target_network_idle_reached=target_network_idle_reached,
        marker_selector=marker_selector,
        selector_wait_status=selector_wait_status,
        requested_route=requested_route,
        final_route=final_route,
        route_mismatch=route_mismatch,
        stability=stability,
    )


def _dedup_keep_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for item in items:
        key = str(item).strip()
        if not key or key in seen:
            continue
        seen.add(key)
        output.append(key)
    return output


def _required_page_elements(page: str, requirement: str, surface: dict[str, Any]) -> list[str]:
    return _workbench_analysis_service.required_page_elements(page, requirement, surface)


def _element_signature(element: Any) -> tuple[str, str, str]:
    return _workbench_analysis_service.element_signature(element)


def _build_page_object_quality(
    page: str,
    requirement: str,
    surface: dict[str, Any],
    page_object_path: Path,
) -> dict[str, Any]:
    return _workbench_analysis_service.build_page_object_quality(
        page,
        requirement,
        surface,
        page_object_path,
        default_page_elements_fn=_default_page_elements,
    )


def _steps_to_points(page: str, requirement: str, steps: list[dict[str, Any]]) -> dict[str, Any]:
    return _workbench_analysis_service.steps_to_points(page, requirement, steps)


def _annotate_test_point_plan_review(plan: dict[str, Any]) -> dict[str, Any]:
    return _workbench_analysis_service.annotate_test_point_plan_review(plan)


def _surface_candidate_confidence_index(surface: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return _workbench_analysis_service.surface_candidate_confidence_index(surface)


def _inherit_test_point_confidence_from_surface(*, plan: dict[str, Any], surface: dict[str, Any]) -> dict[str, Any]:
    return _workbench_analysis_service.inherit_test_point_confidence_from_surface(plan=plan, surface=surface)


def _build_test_point_review_items(plan: dict[str, Any]) -> list[dict[str, Any]]:
    return _workbench_analysis_service.build_test_point_review_items(plan)


def _build_risk_report(
    *,
    page: str,
    final_status: str,
    page_surface_summary: dict[str, Any],
    page_semantic_summary: dict[str, Any] | None,
    page_object_summary: dict[str, Any],
    test_points: dict[str, Any],
    review_state: dict[str, Any],
) -> dict[str, Any]:
    return _workbench_analysis_service.build_risk_report(
        page=page,
        final_status=final_status,
        page_surface_summary=page_surface_summary,
        page_semantic_summary=page_semantic_summary,
        page_object_summary=page_object_summary,
        test_points=test_points,
        review_state=review_state,
    )


def _normalize_risk_factors(
    factors: list[Any] | None,
    *,
    source: str,
) -> list[dict[str, Any]]:
    return _workbench_analysis_service.normalize_risk_factors(factors, source=source)


def _build_risk_evidence(*, factors: list[dict[str, Any]]) -> list[str]:
    return _workbench_analysis_service.build_risk_evidence(factors=factors)


def _build_semantic_risk_evidence(
    *,
    page_semantic_summary: dict[str, Any] | None,
) -> list[str]:
    return _workbench_analysis_service.build_semantic_risk_evidence(page_semantic_summary=page_semantic_summary)


def _build_risk_factor_summary(*, factors: list[dict[str, Any]]) -> dict[str, Any]:
    return _workbench_analysis_service.build_risk_factor_summary(factors=factors)


def _build_risk_report_summary(risk_report: dict[str, Any] | None) -> dict[str, Any]:
    return _workbench_analysis_service.build_risk_report_summary(risk_report)


def _build_page_semantic_summary(
    page_semantic: dict[str, Any] | None,
    *,
    fallback_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return _workbench_analysis_service.build_page_semantic_summary(page_semantic, fallback_summary=fallback_summary)


def _load_latest_self_healing_result(artifacts_dir: Path) -> dict[str, Any]:
    return _workbench_analysis_service.load_latest_self_healing_result(artifacts_dir)


def _build_self_healing_summary(
    *,
    execution_record: dict[str, Any] | None,
    artifacts_dir: str = "",
) -> dict[str, Any]:
    return _workbench_analysis_service.build_self_healing_summary(
        execution_record=execution_record,
        artifacts_dir=artifacts_dir,
        load_latest_self_healing_result_fn=_load_latest_self_healing_result,
    )


def _build_risk_review_items(risk_report: dict[str, Any]) -> list[dict[str, Any]]:
    return _workbench_analysis_service.build_risk_review_items(risk_report)


def _build_review_section(
    *,
    review_type: str,
    items: list[dict[str, Any]],
    existing_entry: dict[str, Any] | None,
) -> dict[str, Any]:
    return _workbench_analysis_service.build_review_section(
        review_type=review_type,
        items=items,
        existing_entry=existing_entry,
    )


def _build_item_review_state(
    *,
    project: str,
    run_id: str,
    page: str,
    page_surface_summary: dict[str, Any],
    test_points: dict[str, Any],
    page_surface: dict[str, Any] | None = None,
    page_object: dict[str, Any] | None = None,
    risk_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return _workbench_review_service.build_item_review_state(
        project=project,
        run_id=run_id,
        page=page,
        page_surface_summary=page_surface_summary,
        test_points=test_points,
        page_surface=page_surface,
        page_object=page_object,
        risk_report=risk_report,
        normalize_page_slug_fn=_normalize_page_slug,
        build_page_analysis_context_fn=_build_page_analysis_context,
        review_decisions_for_run_fn=_review_decisions_for_run,
        build_test_point_review_items_fn=_build_test_point_review_items,
        build_review_section_fn=_build_review_section,
        build_risk_review_items_fn=_build_risk_review_items,
    )


def _build_run_review_state_from_decisions(*, project: str, run_id: str, page: str = "") -> dict[str, Any]:
    return _workbench_review_service.build_run_review_state_from_decisions(
        project=project,
        run_id=run_id,
        page=page,
        review_decisions_for_run_fn=_review_decisions_for_run,
        normalize_page_slug_fn=_normalize_page_slug,
        build_review_section_fn=_build_review_section,
    )


def _sync_stage_b_workbench_gate() -> None:
    _sync_stage_a_workbench_state()
    _workbench_gate_service.SETTINGS = SETTINGS


def _normalize_execution_gate_decision(value: str) -> str:
    _sync_stage_b_workbench_gate()
    return _workbench_gate_service.normalize_execution_gate_decision(value)


def _execution_gate_decision_identity(item: dict[str, Any]) -> tuple[str, str, str]:
    return _workbench_gate_service.execution_gate_decision_identity(item)


def _normalized_role(value: str) -> str:
    return _workbench_gate_service.normalized_role(value)


def _is_execution_gate_privileged_role(role: str) -> bool:
    _sync_stage_b_workbench_gate()
    return _workbench_gate_service.is_execution_gate_privileged_role(role)


def _can_bypass_dual_approval(role: str) -> bool:
    _sync_stage_b_workbench_gate()
    return _workbench_gate_service.can_bypass_dual_approval(role)


def _require_execution_gate_decision_permission(actor: dict[str, str], decision: str) -> None:
    _sync_stage_b_workbench_gate()
    _workbench_gate_service.require_execution_gate_decision_permission(actor, decision)


def _execution_gate_decision_for_run(*, run_id: str, project: str = "", page: str = "") -> dict[str, Any]:
    _sync_stage_b_workbench_gate()
    return _workbench_gate_service.execution_gate_decision_for_run(
        run_id=run_id,
        project=project,
        page=page,
        read_json_list=_read_json_list,
    )


def _upsert_execution_gate_decision(
    payload: ExecutionGateDecisionPayload,
    *,
    actor: dict[str, str] | None = None,
) -> dict[str, Any]:
    _sync_stage_b_workbench_gate()
    return _workbench_gate_service.upsert_execution_gate_decision(payload, actor=actor)


def _approve_execution_gate_decision(
    *,
    project: str,
    run_id: str,
    page: str,
    actor: dict[str, str],
    note: str = "",
) -> dict[str, Any]:
    _sync_stage_b_workbench_gate()
    return _workbench_gate_service.approve_execution_gate_decision(
        project=project,
        run_id=run_id,
        page=page,
        actor=actor,
        note=note,
    )


def _revoke_execution_gate_decision(
    *,
    project: str,
    run_id: str,
    page: str,
    actor: dict[str, str],
    note: str = "",
) -> dict[str, Any]:
    _sync_stage_b_workbench_gate()
    return _workbench_gate_service.revoke_execution_gate_decision(
        project=project,
        run_id=run_id,
        page=page,
        actor=actor,
        note=note,
    )


def _build_execution_gate_audit_snapshot(execution_gate: dict[str, Any] | None) -> dict[str, Any]:
    return _workbench_gate_service.build_execution_gate_audit_snapshot(execution_gate)


def _build_workbench_history(
    *,
    limit: int = 50,
    action: str = "",
    actor: str = "",
    status: str = "",
    risk_gate_decision: str = "",
    self_healing_status: str = "",
) -> dict[str, Any]:
    _ensure_dirs()
    _sync_stage_a_workbench_state()
    history_items = _read_json_list(HISTORY_FILE)
    return _workbench_history_service.build_workbench_history_payload(
        history_items=history_items,
        resolve_governance_snapshot=_resolve_run_governance_snapshot,
        resolve_failure_snapshot=_resolve_run_failure_snapshot,
        normalize_page_slug=_normalize_page_slug,
        limit=limit,
        action=action,
        actor=actor,
        status=status,
        risk_gate_decision=risk_gate_decision,
        self_healing_status=self_healing_status,
    )


def _compute_surface_stability(samples: list[dict[str, int]]) -> dict[str, Any]:
    return _workbench_analysis_service.compute_surface_stability(samples)


def _wait_for_surface_stable(page: Any, *, attempts: int = 4, interval_ms: int = 400) -> dict[str, Any]:
    return _workbench_analysis_service.wait_for_surface_stable(page, attempts=attempts, interval_ms=interval_ms)


def _collect_frame_surface(page: Any) -> dict[str, Any]:
    return _workbench_analysis_service.collect_frame_surface(page)


def _extract_page_surface(page_url: str) -> dict[str, Any]:
    return _workbench_analysis_service.extract_page_surface(
        page_url,
        settings=SETTINGS,
        validate_page_surface_url_fn=_validate_page_surface_url,
        wait_for_surface_stable_fn=_wait_for_surface_stable,
        collect_frame_surface_fn=_collect_frame_surface,
        route_signature_fn=_route_signature,
        build_surface_result_from_snapshot_fn=_build_surface_result_from_snapshot,
        build_surface_element_candidates_fn=_build_surface_element_candidates,
        surface_confidence_summary_fn=_surface_confidence_summary,
        normalize_page_surface_fn=_normalize_page_surface,
        extract_page_from_url_fn=_extract_page_from_url,
        dedup_keep_order_fn=_dedup_keep_order,
    )


def _enhance_page_object_from_surface(page: str, surface: dict[str, Any]) -> Path:
    return _workbench_analysis_service.enhance_page_object_from_surface(
        page,
        surface,
        ensure_page_object_fn=_ensure_page_object,
        surface_inferred_elements_fn=_surface_inferred_elements,
    )


def _build_requirement_steps(requirement: str, page: str, resolved_page_url: str, surface: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    return _workbench_analysis_service.build_requirement_steps(
        requirement,
        page,
        resolved_page_url,
        surface,
        requires_search_flow_fn=_requires_search_flow,
        extract_requirement_search_value_fn=_extract_requirement_search_value,
    )


def _state_project_dir(project: str) -> Path:
    return _workbench_asset_service.state_project_dir(project, state_root=TEST_POINTS_ROOT)


def _state_case_file(project: str, case_id: str) -> Path:
    return _workbench_asset_service.state_case_file(project, case_id, state_root=TEST_POINTS_ROOT)


def _state_case_versions_dir(project: str, case_id: str) -> Path:
    return _workbench_asset_service.state_case_versions_dir(project, case_id, state_root=TEST_POINTS_ROOT)


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except Exception:
        return False


def _resolve_case_yaml_path(project: str, case_id: str) -> Path:
    return _workbench_asset_service.resolve_case_yaml_path(
        project,
        case_id,
        state_case_file_fn=_state_case_file,
        repo_root=REPO_ROOT,
        assets_cases_root=ASSETS_CASES_ROOT,
        ai_cases_root=AI_CASES_ROOT,
        is_within_fn=_is_within,
    )


def _read_case_yaml(path: Path) -> tuple[dict[str, Any], str]:
    return _workbench_asset_service.read_case_yaml(path)


def _write_case_yaml(path: Path, payload: dict[str, Any]) -> str:
    return _workbench_asset_service.write_case_yaml(path, payload)


def _collect_case_items(project: str) -> list[dict[str, Any]]:
    return _workbench_asset_service.collect_case_items(
        project,
        state_project_dir_fn=_state_project_dir,
        resolve_case_yaml_path_fn=_resolve_case_yaml_path,
        ai_cases_root=AI_CASES_ROOT,
    )


def _paginate_case_items(
    items: list[dict[str, Any]],
    *,
    page: int,
    page_size: int,
    focus_case_id: str = "",
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    return _workbench_asset_service.paginate_case_items(
        items,
        page=page,
        page_size=page_size,
        focus_case_id=focus_case_id,
    )


def _infer_targets(page_name: str) -> tuple[str, str]:
    return _workbench_asset_service.infer_targets(page_name, page_objects_root=PAGE_OBJECTS_ROOT)


def _derive_points(case_yaml: dict[str, Any]) -> dict[str, Any]:
    return _workbench_asset_service.derive_points(case_yaml)


def _save_case_state(project: str, case_yaml: dict[str, Any], source_path: Path) -> dict[str, Any]:
    return _workbench_asset_service.save_case_state(
        project,
        case_yaml,
        source_path,
        safe_case_id_fn=_safe_case_id,
        now_iso_fn=_now_iso,
        derive_points_fn=_derive_points,
        state_case_file_fn=_state_case_file,
        state_case_versions_dir_fn=_state_case_versions_dir,
    )


def _parse_analysis_file(path: Path) -> dict[str, Any]:
    return _workbench_reporting_service.parse_analysis_file(path)


def _normalize_failure_analysis_view(analysis: dict[str, Any] | None) -> dict[str, Any]:
    return _workbench_reporting_service.normalize_failure_analysis_view(analysis)


def _normalize_failure_entry_view(entry: dict[str, Any] | None) -> dict[str, Any]:
    return _workbench_reporting_service.normalize_failure_entry_view(entry)


def _build_run_failure_source_summary(failures: list[dict[str, Any]]) -> dict[str, Any]:
    return _workbench_reporting_service.build_run_failure_source_summary(
        failures,
        clamp_confidence=_clamp_confidence,
    )


def _resolve_run_failure_snapshot(run_id: str) -> dict[str, Any]:
    return _workbench_reporting_service.resolve_run_failure_snapshot(
        run_id,
        find_run_item=_find_run_item,
        normalize_failure_entry_view=_normalize_failure_entry_view,
        collect_failure_entries=_collect_failure_entries,
        is_within_fn=_is_within,
    )


def _resolve_run_governance_snapshot(run_id: str) -> dict[str, Any]:
    return _workbench_reporting_service.resolve_run_governance_snapshot(
        run_id,
        find_run_item=_find_run_item,
        build_risk_report_summary=_build_risk_report_summary,
        build_self_healing_summary=_build_self_healing_summary,
        build_page_semantic_summary=_build_page_semantic_summary,
    )


def _resolve_manifest_entries(entries: Any, root: Path) -> list[Path]:
    return _workbench_runtime_service.resolve_manifest_entries(entries, root=root)


def _load_execution_record_payload(path: Path) -> dict[str, Any]:
    return _workbench_runtime_service.load_execution_record_payload(
        path,
        normalize_execution_record_payload=_normalize_execution_record_payload,
    )


def _collect_failure_entries_with_meta() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    compat_scan_enabled = bool(getattr(SETTINGS, "evidence_manifest_compat_scan_enabled", True))
    return _workbench_reporting_service.collect_failure_entries_with_meta(
        compat_scan_enabled=compat_scan_enabled,
        artifact_roots=[RUNNER_ROOT / "artifacts"] + sorted(WEB_UI_RUNS_DIR.glob("*-artifacts")),
        logger=LOGGER,
        normalize_evidence_manifest_payload=_normalize_evidence_manifest_payload,
        resolve_manifest_entries=lambda entries, root: _resolve_manifest_entries(entries, root=root),
        load_execution_record_payload=_load_execution_record_payload,
        parse_analysis_file=_parse_analysis_file,
    )


def _collect_failure_entries() -> list[dict[str, Any]]:
    return _workbench_reporting_service.collect_failure_entries(
        collect_failure_entries_with_meta_fn=_collect_failure_entries_with_meta,
    )


def _normalize_failure_evidence_meta(meta: dict[str, Any] | None) -> dict[str, Any]:
    return _workbench_reporting_service.normalize_failure_evidence_meta(meta)


def _normalize_execution_meta(meta: dict[str, Any] | None) -> dict[str, Any]:
    return _workbench_reporting_service.normalize_execution_meta(meta)


def _execution_record_time_value(record: dict[str, Any]) -> str:
    return _workbench_task_service.execution_record_time_value(record)


def _collect_execution_records_with_meta(*, limit: int = 1000) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    compat_scan_enabled = bool(getattr(SETTINGS, "evidence_manifest_compat_scan_enabled", True))
    artifact_roots = [RUNNER_ROOT / "artifacts"] + sorted(WEB_UI_RUNS_DIR.glob("*-artifacts"))
    runtime_jobs: list[dict[str, Any]] = []
    with _RUN_LOCK:
        runtime_jobs.extend([dict(item) for item in _RUN_JOBS.values()])
    return _workbench_task_service.collect_execution_records_with_meta(
        limit=limit,
        compat_scan_enabled=compat_scan_enabled,
        artifact_roots=artifact_roots,
        logger=LOGGER,
        normalize_evidence_manifest_payload=_normalize_evidence_manifest_payload,
        resolve_manifest_entries=_resolve_manifest_entries,
        load_execution_record_payload=_load_execution_record_payload,
        execution_record_time_value=_execution_record_time_value,
        runtime_jobs=runtime_jobs,
        runtime_runs_file=RUNTIME_RUNS_FILE,
        runtime_view_from_entry=_runtime_view_from_entry,
        read_json_list=_read_json_list,
        normalize_execution_record_payload=_normalize_execution_record_payload,
    )


def _build_execution_task_view(entry: dict[str, Any]) -> dict[str, Any]:
    return _workbench_task_service.build_execution_task_view(
        entry,
        normalize_execution_record_payload=_normalize_execution_record_payload,
        build_task_evidence_freshness_fn=_workbench_task_service.build_task_evidence_freshness,
        utc_now=_utc_now,
        parse_iso_datetime=_parse_iso_datetime,
    )


def _parse_optional_bool_query(value: Any) -> bool | None:
    return _workbench_task_service.parse_optional_bool_query(value)


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _parse_iso_datetime(value: str) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    parsed_text = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(parsed_text)
    except Exception:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _build_task_evidence_freshness(
    *,
    task_source: str,
    queue_status: str,
    started_at: str,
    finished_at: str,
    created_at: str,
    has_manifest: bool,
) -> dict[str, Any]:
    source_value = str(task_source or "").strip().lower()
    queue_value = str(queue_status or "").strip().lower()
    if source_value == "runtime_realtime" and queue_value in {"queued", "running"}:
        reference_time = finished_at or started_at or created_at
        reference_dt = _parse_iso_datetime(reference_time)
        age_seconds = max(0, int((_utc_now() - reference_dt).total_seconds())) if reference_dt else None
        return {
            "status": "live",
            "reason": "任务仍处于 runtime 实时态，证据可能仍在持续写入。",
            "age_seconds": age_seconds,
            "reference_time": reference_time,
            "stale": False,
            "source_window_hours": 0,
        }
    if source_value == "runtime_fallback":
        reference_time = finished_at or started_at or created_at
        reference_dt = _parse_iso_datetime(reference_time)
        age_seconds = max(0, int((_utc_now() - reference_dt).total_seconds())) if reference_dt else None
        return {
            "status": "stale",
            "reason": "任务当前仅依赖 runtime_fallback，缺少稳定落盘证据事实源。",
            "age_seconds": age_seconds,
            "reference_time": reference_time,
            "stale": True,
            "source_window_hours": 0,
        }

    reference_time = finished_at or started_at or created_at
    reference_dt = _parse_iso_datetime(reference_time)
    if reference_dt is None:
        return {
            "status": "unknown",
            "reason": "任务缺少可用于判断证据时效的时间戳。",
            "age_seconds": None,
            "reference_time": reference_time,
            "stale": False,
            "source_window_hours": 0,
        }

    age_seconds = max(0, int((_utc_now() - reference_dt).total_seconds()))
    freshness_window_hours = 24 if has_manifest else (12 if source_value == "compat_scan" else 6)
    freshness_window_seconds = freshness_window_hours * 3600
    if age_seconds <= freshness_window_seconds:
        freshness_status = "fresh"
        freshness_reason = "任务证据仍处于新鲜窗口内。"
    elif age_seconds <= freshness_window_seconds * 3:
        freshness_status = "aging"
        freshness_reason = "任务证据已超出新鲜窗口，建议尽快完成治理或复核。"
    else:
        freshness_status = "stale"
        freshness_reason = "任务证据已进入陈旧区间，建议优先回填或重新执行。"
    return {
        "status": freshness_status,
        "reason": freshness_reason,
        "age_seconds": age_seconds,
        "reference_time": reference_time,
        "stale": freshness_status == "stale",
        "source_window_hours": freshness_window_hours,
    }


def _build_task_governance_risk(item: dict[str, Any]) -> dict[str, Any]:
    return _workbench_task_service.build_task_governance_risk(item)


def _build_execution_task_summary(
    *,
    items: list[dict[str, Any]],
    filter_snapshot: dict[str, Any],
    execution_meta: dict[str, Any],
) -> dict[str, Any]:
    return _workbench_task_service.build_execution_task_summary(
        items=items,
        filter_snapshot=filter_snapshot,
        execution_meta=execution_meta,
        build_task_governance_risk_fn=_build_task_governance_risk,
    )


def _load_defects() -> list[dict[str, Any]]:
    with _FILE_LOCK:
        return _workbench_reporting_service.load_defect_items(
            read_items=lambda: _read_json_list(DEFECT_LINKS_FILE),
        )


def _get_python_bin() -> str:
    return _workbench_runtime_service.get_python_bin(repo_root=REPO_ROOT)


def _apply_no_store_headers(response: Response) -> None:
    _workbench_reporting_service.apply_no_store_headers(response)


def _get_allure_index_version() -> int:
    return _workbench_reporting_service.get_allure_index_version(
        allure_report_root=ALLURE_REPORT_ROOT,
    )


def _read_allure_summary() -> dict[str, Any]:
    return _workbench_reporting_service.read_allure_summary(
        allure_report_root=ALLURE_REPORT_ROOT,
    )


def _ensure_allure_snapshot(version: int) -> str:
    return _workbench_reporting_service.ensure_allure_snapshot(
        version=version,
        allure_report_root=ALLURE_REPORT_ROOT,
        allure_snapshots_root=ALLURE_SNAPSHOTS_ROOT,
    )


def _build_run_command(case_path: Path) -> tuple[list[str], dict[str, str]]:
    return _workbench_runtime_service.build_run_command(
        case_path,
        get_python_bin_fn=_get_python_bin,
        repo_root=REPO_ROOT,
        allure_results_root=ALLURE_RESULTS_ROOT,
        environ=os.environ.copy(),
    )


def _update_job(run_id: str, updates: dict[str, Any]) -> None:
    with _RUN_LOCK:
        job = _RUN_JOBS.get(run_id)
        if not job:
            return
        merged = dict(job)
        merged.update(updates if isinstance(updates, dict) else {})
        _RUN_JOBS[run_id] = _runtime_view_from_entry(merged)


def _get_job(run_id: str) -> dict[str, Any] | None:
    with _RUN_LOCK:
        job = _RUN_JOBS.get(run_id)
        if not job:
            return None
        return _runtime_view_with_execution_record_preferred(dict(job))


def _find_run_item(run_id: str) -> dict[str, Any] | None:
    return _workbench_runtime_service.find_run_item(
        run_id,
        get_job=_get_job,
        read_runtime_runs=lambda: _read_json_list(RUNTIME_RUNS_FILE),
        runtime_run_id_fn=_runtime_run_id,
        runtime_view_with_execution_record_preferred_fn=_runtime_view_with_execution_record_preferred,
    )


def _wait_run_terminal(run_id: str, timeout_seconds: int) -> tuple[dict[str, Any] | None, bool]:
    return _workbench_runtime_service.wait_run_terminal(
        run_id,
        timeout_seconds,
        find_run_item=_find_run_item,
    )


def _load_runtime_execution_record_from_artifacts(artifacts_dir: Path) -> dict[str, Any]:
    return _workbench_runtime_service.load_runtime_execution_record_from_artifacts(
        artifacts_dir,
        normalize_evidence_manifest_payload=_normalize_evidence_manifest_payload,
        resolve_manifest_entries_fn=lambda entries, root: _resolve_manifest_entries(entries, root=root),
        load_execution_record_payload_fn=_load_execution_record_payload,
    )


def _execute_run(job: dict[str, Any]) -> None:
    _workbench_runtime_service.execute_run(
        job,
        build_run_command_fn=_build_run_command,
        now_iso_fn=_now_iso,
        update_job=_update_job,
        update_runtime_run=_update_runtime_run,
        load_runtime_execution_record_from_artifacts=_load_runtime_execution_record_from_artifacts,
        collect_failure_entries=_collect_failure_entries,
        is_within=_is_within,
        repo_root=REPO_ROOT,
        runner_root=RUNNER_ROOT,
    )


def _start_run(*, project: str, case_id: str, case_path: Path, source: str) -> dict[str, Any]:
    def _store_run_job(run_id: str, job: dict[str, Any]) -> None:
        with _RUN_LOCK:
            _RUN_JOBS[run_id] = dict(job)

    return _workbench_runtime_service.start_run(
        project=project,
        case_id=case_id,
        case_path=case_path,
        source=source,
        runs_dir=WEB_UI_RUNS_DIR,
        now_iso_fn=_now_iso,
        build_runtime_execution_record=_build_runtime_execution_record,
        runtime_view_from_entry_fn=_runtime_view_from_entry,
        store_run_job=_store_run_job,
        append_runtime_run=_append_runtime_run,
        append_history=_append_history,
        execute_run_fn=_execute_run,
    )


def _extract_json_from_text(text: str) -> dict[str, Any]:
    return _workbench_runtime_service.extract_json_from_text(text)


def list_projects() -> dict[str, Any]:
    _ensure_dirs()
    projects = []
    if TEST_POINTS_ROOT.exists():
        for item in sorted(TEST_POINTS_ROOT.iterdir()):
            if item.is_dir():
                projects.append(item.name)
    if "default" not in projects:
        projects.insert(0, "default")
    return {"items": projects}


def list_execution_tasks(
    limit: int = Query(default=50, ge=1, le=500),
    status: str = Query(default=""),
    queue_status: str = Query(default=""),
    source: str = Query(default=""),
    evidence_health_status: str = Query(default=""),
    evidence_freshness_status: str = Query(default=""),
    manifest_action: str = Query(default=""),
    retry_enabled: str = Query(default=""),
    has_dependencies: str = Query(default=""),
) -> dict[str, Any]:
    _ensure_dirs()
    execution_rows, execution_meta_raw = _collect_execution_records_with_meta(limit=max(limit * 3, 200))
    execution_meta = _normalize_execution_meta(execution_meta_raw)
    status_value = str(status or "").strip().lower()
    queue_status_value = str(queue_status or "").strip().lower()
    source_value = str(source or "").strip().lower()
    evidence_health_status_value = str(evidence_health_status or "").strip().lower()
    evidence_freshness_status_value = str(evidence_freshness_status or "").strip().lower()
    manifest_action_value = str(manifest_action or "").strip().lower()
    retry_enabled_value = _parse_optional_bool_query(retry_enabled)
    has_dependencies_value = _parse_optional_bool_query(has_dependencies)
    items: list[dict[str, Any]] = []
    for row in execution_rows:
        task = _build_execution_task_view(row)
        if status_value and str(task.get("status", "")).strip().lower() != status_value:
            continue
        if queue_status_value and str(task.get("queue_status", "")).strip().lower() != queue_status_value:
            continue
        if source_value and str(task.get("source", "")).strip().lower() != source_value:
            continue
        evidence_health = task.get("evidence_health", {}) if isinstance(task.get("evidence_health"), dict) else {}
        if evidence_health_status_value and str(evidence_health.get("status", "")).strip().lower() != evidence_health_status_value:
            continue
        evidence_freshness = task.get("evidence_freshness", {}) if isinstance(task.get("evidence_freshness"), dict) else {}
        if evidence_freshness_status_value and str(evidence_freshness.get("status", "")).strip().lower() != evidence_freshness_status_value:
            continue
        if manifest_action_value and str(task.get("manifest_action", "")).strip().lower() != manifest_action_value:
            continue
        retry = task.get("retry", {}) if isinstance(task.get("retry"), dict) else {}
        if retry_enabled_value is not None and bool(retry.get("enabled", False)) != retry_enabled_value:
            continue
        dependency = task.get("dependency", {}) if isinstance(task.get("dependency"), dict) else {}
        if has_dependencies_value is not None and bool(dependency.get("has_dependencies", False)) != has_dependencies_value:
            continue
        items.append(task)
        if len(items) >= limit:
            break
    filter_snapshot = {
        "status": status_value,
        "queue_status": queue_status_value,
        "source": source_value,
        "evidence_health_status": evidence_health_status_value,
        "evidence_freshness_status": evidence_freshness_status_value,
        "manifest_action": manifest_action_value,
        "retry_enabled": "" if retry_enabled_value is None else str(retry_enabled_value).lower(),
        "has_dependencies": "" if has_dependencies_value is None else str(has_dependencies_value).lower(),
    }
    return {
        "items": items,
        "summary": _build_execution_task_summary(items=items, filter_snapshot=filter_snapshot, execution_meta=execution_meta),
    }


def get_execution_task(task_id: str) -> dict[str, Any]:
    _ensure_dirs()
    normalized_task_id = str(task_id or "").strip()
    if not normalized_task_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="task not found")
    execution_rows, execution_meta_raw = _collect_execution_records_with_meta(limit=1000)
    execution_meta = _normalize_execution_meta(execution_meta_raw)
    for row in execution_rows:
        task = _build_execution_task_view(row)
        if str(task.get("task_id", "")).strip() == normalized_task_id:
            return {"item": task, "meta": execution_meta}
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="task not found")


def get_execution_gate_config() -> dict[str, Any]:
    policy_baseline = _execution_gate_policy_baseline()
    return {
        "item": {
            "version": "ExecutionGateConfigV1",
            "block_missing_required_threshold": max(
                1,
                int(getattr(SETTINGS, "execution_gate_block_missing_required_threshold", 2) or 2),
            ),
            "block_on_failed_status": bool(getattr(SETTINGS, "execution_gate_block_on_failed_status", True)),
            "block_on_risk_block": bool(getattr(SETTINGS, "execution_gate_block_on_risk_block", True)),
            "warn_on_pending_reviews": bool(getattr(SETTINGS, "execution_gate_warn_on_pending_reviews", True)),
            "warn_on_low_confidence_elements": bool(
                getattr(SETTINGS, "execution_gate_warn_on_low_confidence_elements", True)
            ),
            "warn_on_pending_test_points": bool(
                getattr(SETTINGS, "execution_gate_warn_on_pending_test_points", True)
            ),
            "block_missing_dependency_points_threshold": max(
                1,
                int(getattr(SETTINGS, "execution_gate_block_missing_dependency_points_threshold", 1) or 1),
            ),
            "warn_on_low_confidence_dependency_points": bool(
                getattr(SETTINGS, "execution_gate_warn_on_low_confidence_dependency_points", True)
            ),
            "decision_privileged_roles": [
                str(item).strip().lower()
                for item in getattr(SETTINGS, "execution_gate_decision_privileged_roles", [])
                if str(item).strip()
            ],
            "dual_approval_enabled": bool(getattr(SETTINGS, "execution_gate_dual_approval_enabled", False)),
            "dual_approval_bypass_roles": [
                str(item).strip().lower()
                for item in getattr(SETTINGS, "execution_gate_dual_approval_bypass_roles", [])
                if str(item).strip()
            ],
            "policy_baseline": policy_baseline,
            "updated_at": _now_iso(),
        }
    }




def save_case(case_id: str, payload: SaveCasePayload) -> dict[str, Any]:
    from . import workbench_assets

    return workbench_assets.save_case(case_id, payload)


def heal_run(run_id: str) -> dict[str, Any]:
    from . import workbench_runs

    return workbench_runs.heal_run(run_id)


def rerun_case(run_id: str) -> dict[str, Any]:
    from . import workbench_runs

    return workbench_runs.rerun_case(run_id)


def heal_and_rerun_case(
    run_id: str,
    wait_seconds: int = Query(default=180, ge=5, le=900),
) -> dict[str, Any]:
    from . import workbench_runs

    return workbench_runs.heal_and_rerun_case(run_id, wait_seconds=wait_seconds)


def save_review(payload: WorkbenchReviewPayload, request: Request) -> dict[str, Any]:
    from . import workbench_reviews

    return workbench_reviews.save_review(payload, request)


def save_execution_gate_decision(payload: ExecutionGateDecisionPayload, request: Request) -> dict[str, Any]:
    from . import workbench_gate

    return workbench_gate.save_execution_gate_decision(payload, request)


def approve_execution_gate_decision(payload: ExecutionGateDecisionActionPayload, request: Request) -> dict[str, Any]:
    from . import workbench_gate

    return workbench_gate.approve_execution_gate_decision(payload, request)


def revoke_execution_gate_decision(payload: ExecutionGateDecisionActionPayload, request: Request) -> dict[str, Any]:
    from . import workbench_gate

    return workbench_gate.revoke_execution_gate_decision(payload, request)



def report_allure_refresh(response: Response | None = None) -> dict[str, Any]:
    from . import workbench_reporting

    return workbench_reporting.report_allure_refresh(response or Response())




def _sync_stage_a_workbench_state() -> None:
    _workbench_state_store.WEB_UI_STATE_ROOT = WEB_UI_STATE_ROOT
    _workbench_state_store.WEB_UI_DEFAULT_STATE_DIR = WEB_UI_DEFAULT_STATE_DIR
    _workbench_state_store.WEB_UI_RUNS_DIR = WEB_UI_RUNS_DIR
    _workbench_state_store.WEB_UI_REPORTING_DIR = WEB_UI_REPORTING_DIR
    _workbench_state_store.TEST_POINTS_ROOT = TEST_POINTS_ROOT
    _workbench_state_store.ASSETS_CASES_ROOT = ASSETS_CASES_ROOT
    _workbench_state_store.AI_CASES_ROOT = AI_CASES_ROOT
    _workbench_state_store.ALLURE_SNAPSHOTS_ROOT = ALLURE_SNAPSHOTS_ROOT
    _workbench_state_store.HISTORY_FILE = HISTORY_FILE
    _workbench_state_store.RUNTIME_RUNS_FILE = RUNTIME_RUNS_FILE
    _workbench_state_store.DEFECT_LINKS_FILE = DEFECT_LINKS_FILE
    _workbench_state_store.REVIEW_DECISIONS_FILE = REVIEW_DECISIONS_FILE
    _workbench_state_store.EXECUTION_GATE_DECISIONS_FILE = EXECUTION_GATE_DECISIONS_FILE
    _workbench_state_store.FAILURE_SOURCE_CALIBRATIONS_FILE = FAILURE_SOURCE_CALIBRATIONS_FILE


def _ensure_dirs() -> None:
    _sync_stage_a_workbench_state()
    _workbench_state_store.ensure_dirs()


def _read_json_list(path: Path) -> list[dict[str, Any]]:
    _sync_stage_a_workbench_state()
    return _workbench_state_store.read_json_list(path)


def _write_json_list(path: Path, items: list[dict[str, Any]]) -> None:
    _sync_stage_a_workbench_state()
    _workbench_state_store.write_json_list(path, items)


def _append_history(entry: dict[str, Any]) -> None:
    _sync_stage_a_workbench_state()
    _workbench_state_store.append_history(entry)


def _append_runtime_run(entry: dict[str, Any]) -> None:
    _sync_stage_a_workbench_state()
    _workbench_state_store.append_runtime_run(entry)


def _update_runtime_run(run_id: str, updates: dict[str, Any]) -> None:
    _sync_stage_a_workbench_state()
    _workbench_state_store.update_runtime_run(run_id, updates)


def _normalize_review_type(value: str) -> str:
    return _workbench_review_service.normalize_review_type(value)


def _normalize_review_status(value: str) -> str:
    return _workbench_review_service.normalize_review_status(value)


def _extract_review_actor(request: Request) -> dict[str, str]:
    return _workbench_review_service.extract_review_actor(request)


def _require_authenticated_review_actor(actor: dict[str, str]) -> dict[str, str]:
    return _workbench_review_service.require_authenticated_review_actor(actor)


def _upsert_review_decision(payload: WorkbenchReviewPayload, *, actor: dict[str, str] | None = None) -> dict[str, Any]:
    _sync_stage_a_workbench_state()
    return _workbench_review_service.upsert_review_decision(payload, actor=actor)


def _build_review_audit_summary(review_state: dict[str, Any]) -> dict[str, Any]:
    return _workbench_review_service.build_review_audit_summary(review_state)


def _build_review_audit_timeline(*, run_id: str, page: str = "") -> list[dict[str, Any]]:
    _sync_stage_a_workbench_state()
    return _workbench_review_service.build_review_audit_timeline(
        run_id=run_id,
        page=page,
        read_history_items=lambda: _read_json_list(HISTORY_FILE),
        normalize_page_slug_fn=_normalize_page_slug,
    )
