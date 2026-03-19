import json
import logging
import os
import re
import socket
import shutil
import subprocess
import sys
import threading
import time
import uuid
import fnmatch
import ipaddress
from datetime_compat import UTC
from datetime import datetime, timedelta
from collections import defaultdict
from pathlib import Path
from typing import Any
from urllib import error as url_error
from urllib import parse as url_parse
from urllib import request as url_request

import yaml
from fastapi import APIRouter, HTTPException, Query, Request, Response, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core import page_analysis_rules
from app.core.security import decode_access_token
from apps.shared_backend.observability import get_request_id

router = APIRouter(tags=["legacy-workbench"])

REPO_ROOT = Path(__file__).resolve().parents[4]
APPS_ROOT = REPO_ROOT / "apps"
if str(APPS_ROOT) not in sys.path:
    sys.path.insert(0, str(APPS_ROOT))

from app.core.page_analysis_pipeline import (
    normalize_test_point_plan_model,
)
from app.services import workbench_analysis_service as _workbench_analysis_service
from app.services import workbench_gate_service as _workbench_gate_service
from app.services import workbench_asset_service as _workbench_asset_service
from app.services import workbench_history_service as _workbench_history_service
from app.services import workbench_review_service as _workbench_review_service
from app.services import workbench_runtime_service as _workbench_runtime_service
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
    normalize_evidence_manifest_v1 = None
    normalize_execution_record_v1 = None

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
    return datetime.now(UTC).isoformat()


def _normalize_failure_source_value(value: Any) -> str:
    source = str(value or "").strip().lower()
    if source in {"page_object", "page_analysis", "case_design", "app_bug", "environment", "unknown"}:
        return source
    return "unknown"


def _sanitize_review_items(items: list[dict[str, Any]], *, review_type: str) -> list[dict[str, Any]]:
    return _workbench_review_service.sanitize_review_items(items, review_type=review_type)


def _sanitize_failure_source_feedback(
    feedback: dict[str, Any] | None,
    *,
    predicted_source: str,
) -> dict[str, Any]:
    item = feedback if isinstance(feedback, dict) else {}
    corrected_source = _normalize_failure_source_value(
        item.get("corrected_failure_source", item.get("corrected_source", predicted_source))
    )
    decision = str(item.get("decision", "")).strip().lower()
    if decision not in {"accepted", "corrected", "rejected"}:
        decision = "accepted" if corrected_source == predicted_source else "corrected"
    if decision == "accepted":
        corrected_source = predicted_source
    if decision == "rejected" and corrected_source == predicted_source:
        corrected_source = ""
    reason = str(item.get("reason", item.get("note", ""))).strip()
    return {
        "decision": decision,
        "corrected_failure_source": corrected_source,
        "reason": reason,
    }


def _record_failure_source_calibration_sample(
    *,
    review_record: dict[str, Any],
    feedback: dict[str, Any] | None = None,
) -> dict[str, Any]:
    review_type = str(review_record.get("review_type", "")).strip().lower()
    review_status = str(review_record.get("status", "")).strip().lower()
    if review_status != "confirmed":
        return {}
    if review_type != "risk" and not isinstance(feedback, dict):
        return {}

    run_id = str(review_record.get("run_id", "")).strip()
    if not run_id:
        return {}
    failure_snapshot = _resolve_run_failure_snapshot(run_id)
    analysis = failure_snapshot.get("analysis") if isinstance(failure_snapshot.get("analysis"), dict) else {}
    if not analysis:
        return {}

    predicted_source = _normalize_failure_source_value(analysis.get("failure_source", "unknown"))
    normalized_feedback = _sanitize_failure_source_feedback(feedback, predicted_source=predicted_source)
    confirmed_source = str(normalized_feedback.get("corrected_failure_source", "")).strip()
    sample = {
        "version": "FailureSourceCalibrationV1",
        "sample_id": str(uuid.uuid4()),
        "project": str(review_record.get("project", "default")).strip() or "default",
        "run_id": run_id,
        "case_id": str(review_record.get("case_id", "")).strip(),
        "page": str(review_record.get("page", "")).strip(),
        "review_type": review_type,
        "review_status": review_status,
        "predicted_failure_source": predicted_source,
        "predicted_failure_source_reason": str(analysis.get("failure_source_reason", "")).strip(),
        "predicted_failure_source_confidence": _clamp_confidence(analysis.get("failure_source_confidence", 0)),
        "predicted_requires_manual_review": bool(analysis.get("requires_manual_review", False)),
        "predicted_source_evidence": analysis.get("source_evidence", []) if isinstance(analysis.get("source_evidence"), list) else [],
        "human_decision": normalized_feedback["decision"],
        "confirmed_failure_source": confirmed_source,
        "feedback_reason": normalized_feedback["reason"],
        "usable_for_training": bool(confirmed_source) and normalized_feedback["decision"] in {"accepted", "corrected"},
        "confirmed_by": str(review_record.get("confirmed_by", "")).strip() or "anonymous",
        "confirmed_by_role": str(review_record.get("confirmed_by_role", "")).strip() or "unknown",
        "confirmed_by_source": str(review_record.get("confirmed_by_source", "")).strip() or "fallback",
        "actor_display": _reviewer_display_name(review_record),
        "created_at": str(review_record.get("updated_at", "")).strip() or _now_iso(),
    }
    with _FILE_LOCK:
        items = _read_json_list(FAILURE_SOURCE_CALIBRATIONS_FILE)
        items.insert(0, sample)
        _write_json_list(FAILURE_SOURCE_CALIBRATIONS_FILE, items[:5000])
    return sample


def _review_decisions_for_run(run_id: str, *, project: str = "", page: str = "") -> dict[tuple[str, str], dict[str, Any]]:
    normalized_run_id = str(run_id or "").strip()
    normalized_project = str(project or "").strip()
    normalized_page = _normalize_page_slug(page) if str(page).strip() else ""
    results: dict[tuple[str, str], dict[str, Any]] = {}
    if not normalized_run_id:
        return results
    for item in _read_json_list(REVIEW_DECISIONS_FILE):
        if str(item.get("run_id", "")).strip() != normalized_run_id:
            continue
        if normalized_project and str(item.get("project", "")).strip() != normalized_project:
            continue
        item_page = _normalize_page_slug(str(item.get("page", "")).strip()) if str(item.get("page", "")).strip() else ""
        if normalized_page and item_page != normalized_page:
            continue
        try:
            review_type = _normalize_review_type(str(item.get("review_type", "")).strip())
        except HTTPException:
            continue
        results[(item_page, review_type)] = {
            "project": str(item.get("project", "default")).strip() or "default",
            "run_id": normalized_run_id,
            "case_id": str(item.get("case_id", "")).strip(),
            "page": item_page,
            "review_type": review_type,
            "status": _normalize_review_status(str(item.get("status", "confirmed")).strip() or "confirmed"),
            "items": _sanitize_review_items(item.get("items", []), review_type=review_type) if isinstance(item.get("items"), list) else [],
            "note": str(item.get("note", "")).strip(),
            "confirmed_by": str(item.get("confirmed_by", "")).strip() or "anonymous",
            "confirmed_by_role": str(item.get("confirmed_by_role", "")).strip() or "unknown",
            "confirmed_by_source": str(item.get("confirmed_by_source", "")).strip() or "fallback",
            "updated_at": str(item.get("updated_at", "")).strip(),
            "created_at": str(item.get("created_at", "")).strip(),
        }
    return results


def _reviewer_display_name(entry: dict[str, Any] | None) -> str:
    return _workbench_analysis_service.reviewer_display_name(entry)


def _normalize_history_text_list(value: Any, *, limit: int = 10) -> list[str]:
    items = value if isinstance(value, list) else []
    normalized = [str(item).strip() for item in items if str(item).strip()]
    return _dedup_keep_order(normalized)[:limit]


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
    text = str(raw).strip().upper()
    allowed = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in text)
    return allowed.strip("-_") or f"TC-AI-{datetime.now(UTC).strftime('%H%M%S')}"


def _normalize_page_slug(value: str) -> str:
    normalized = "".join(ch for ch in str(value).strip().lower() if ch.isalnum() or ch in {"-", "_"})
    normalized = PAGE_ALIAS_MAP.get(normalized, normalized)
    return normalized or "product"


def _extract_page_from_url(raw_url: str) -> tuple[str, str]:
    value = str(raw_url).strip()
    if not value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="page_urls contains empty value")

    parsed = url_parse.urlparse(value)
    path = parsed.fragment.split("?", 1)[0] if parsed.fragment else parsed.path
    segments = [item for item in path.split("/") if item]
    candidate = segments[-1] if segments else value
    page = _normalize_page_slug(candidate)
    return value, page


def _build_system_requirement(*, page: str, page_url: str = "", has_multisource_inputs: bool = False) -> str:
    normalized_page = _normalize_page_slug(page) if str(page).strip() else ""
    if has_multisource_inputs:
        return "多输入源需求驱动的页面核心流程验证"
    page_label = PAGE_FRIENDLY_NAME.get(normalized_page, normalized_page or "目标页面")
    route_label = str(page_url or "").strip()
    if route_label:
        return f"自动生成的页面测试目标：验证 {page_label} 页面可访问、关键区域可见、核心基础交互可执行。目标 URL：{route_label}"
    return f"自动生成的页面测试目标：验证 {page_label} 页面可访问、关键区域可见、核心基础交互可执行。"


def _resolve_page_url(raw_url: str, page: str) -> str:
    parsed = url_parse.urlparse(str(raw_url).strip())
    scheme = parsed.scheme or "http"
    netloc = parsed.netloc or "localhost:5173"
    base = f"{scheme}://{netloc}"
    canonical = PAGE_CANONICAL_HASH_ROUTE.get(page)
    if canonical:
        return f"{base}/#{canonical}"
    if parsed.fragment:
        fragment = parsed.fragment
        if not fragment.startswith("/"):
            fragment = "/" + fragment
        return f"{base}/#{fragment}"
    path = parsed.path or "/"
    return f"{base}{path}"


def _route_signature(raw_url: str) -> str:
    parsed = url_parse.urlparse(str(raw_url or "").strip())
    fragment = str(parsed.fragment or "").split("?", 1)[0].strip()
    if fragment:
        return fragment if fragment.startswith("/") else f"/{fragment}"
    path = str(parsed.path or "").strip()
    return path if path.startswith("/") else f"/{path}" if path else ""


def _is_allowed_host_pattern(hostname: str) -> bool:
    normalized = str(hostname or "").strip().lower()
    if not normalized:
        return False
    patterns = [str(item).strip().lower() for item in getattr(SETTINGS, "page_surface_allowed_hosts", []) if str(item).strip()]
    return any(fnmatch.fnmatch(normalized, pattern) for pattern in patterns)


def _is_private_or_local_hostname(hostname: str, port: int | None) -> bool:
    normalized = str(hostname or "").strip().lower()
    if not normalized:
        return True
    try:
        ip_obj = ipaddress.ip_address(normalized)
        return bool(
            ip_obj.is_private
            or ip_obj.is_loopback
            or ip_obj.is_link_local
            or ip_obj.is_reserved
            or ip_obj.is_multicast
        )
    except ValueError:
        pass

    if normalized in {"localhost", "localhost.localdomain"}:
        return True

    try:
        candidates = socket.getaddrinfo(normalized, port or 80, proto=socket.IPPROTO_TCP)
    except OSError:
        return True
    for candidate in candidates:
        try:
            resolved_ip = ipaddress.ip_address(candidate[4][0])
        except Exception:
            return True
        if (
            resolved_ip.is_private
            or resolved_ip.is_loopback
            or resolved_ip.is_link_local
            or resolved_ip.is_reserved
            or resolved_ip.is_multicast
        ):
            return True
    return False


def _validate_page_surface_url(raw_url: str) -> str:
    value = str(raw_url or "").strip()
    if not value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="page url must not be empty")

    parsed = url_parse.urlparse(value)
    scheme = str(parsed.scheme or "http").strip().lower()
    if scheme not in {"http", "https"}:
        raise HTTPException(status_code=422, detail="page url must use http or https")
    if parsed.username or parsed.password:
        raise HTTPException(status_code=422, detail="page url must not contain credentials")

    hostname = str(parsed.hostname or "").strip().lower()
    if not hostname:
        raise HTTPException(status_code=422, detail="page url hostname is required")

    if getattr(SETTINGS, "page_surface_allow_private_hosts", False):
        return value

    if _is_private_or_local_hostname(hostname, parsed.port) and not _is_allowed_host_pattern(hostname):
        raise HTTPException(
            status_code=422,
            detail=f"page url host is blocked by SSRF policy: {hostname}",
        )
    return value


def _default_page_elements(page: str) -> dict[str, dict[str, str]]:
    return _workbench_analysis_service.default_page_elements(page)


def _ensure_page_object(page: str) -> Path:
    page_object_path = PAGE_OBJECTS_ROOT / f"{page}.page-object.yaml"
    payload: dict[str, Any] = {"page": page, "elements": {}}
    if page_object_path.exists():
        try:
            loaded = yaml.safe_load(page_object_path.read_text(encoding="utf-8")) or {}
        except Exception:
            loaded = {}
        if isinstance(loaded, dict):
            payload = loaded

    payload["page"] = page
    elements = payload.get("elements")
    if not isinstance(elements, dict):
        elements = {}
    defaults = _workbench_analysis_service.default_page_elements(page)
    for element_name, element_def in defaults.items():
        if element_name not in elements:
            elements[element_name] = dict(element_def)
    payload["elements"] = elements

    page_object_path.parent.mkdir(parents=True, exist_ok=True)
    page_object_path.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return page_object_path


def _post_json(url: str, payload: dict[str, Any], timeout_seconds: int = 300) -> dict[str, Any]:
    request_id = get_request_id()
    request = url_request.Request(
        url=url,
        method="POST",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            **({"X-Request-Id": request_id} if request_id else {}),
        },
    )
    try:
        with url_request.urlopen(request, timeout=timeout_seconds) as response:
            text = response.read().decode("utf-8")
    except url_error.HTTPError as exc:
        raw_body = exc.read().decode("utf-8", errors="ignore")
        detail: Any = raw_body.strip() or str(exc)
        try:
            parsed = json.loads(raw_body or "{}")
            if isinstance(parsed, dict):
                detail = parsed.get("error", parsed)
        except Exception:
            pass
        raise HTTPException(status_code=exc.code, detail=detail) from exc
    except url_error.URLError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"orchestrator unavailable: {exc.reason}",
        ) from exc
    except TimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="orchestrator request timed out",
        ) from exc
    except socket.timeout as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="orchestrator request timed out",
        ) from exc

    try:
        data = json.loads(text or "{}")
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="orchestrator returned non-json payload",
        ) from exc
    if not isinstance(data, dict):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="orchestrator returned invalid response object",
        )
    return data


def _extract_quality_gate(payload: Any) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    direct = payload.get("quality_gate")
    if isinstance(direct, dict):
        return direct
    details = payload.get("details")
    if isinstance(details, dict):
        nested = details.get("quality_gate")
        if isinstance(nested, dict):
            return nested
    error = payload.get("error")
    if isinstance(error, dict):
        nested = _extract_quality_gate(error)
        if isinstance(nested, dict):
            return nested
    return None


def _is_quality_gate_blocked(payload: Any) -> tuple[bool, dict[str, Any] | None]:
    gate = _extract_quality_gate(payload)
    if not isinstance(gate, dict):
        return False, None
    decision = str(gate.get("decision", "")).strip().lower()
    if decision == "block":
        return True, gate
    blockers = gate.get("blockers")
    if isinstance(blockers, list) and len(blockers) > 0:
        return True, gate
    return False, gate


def _render_requirement_spec_markdown(requirement_spec: dict[str, Any]) -> str:
    spec = requirement_spec if isinstance(requirement_spec, dict) else {}
    page = str(spec.get("page", "")).strip() or "-"
    priority = str(spec.get("priority", "")).strip() or "P1"
    parse_confidence = spec.get("parse_confidence", 0)
    test_intents = spec.get("test_intents") if isinstance(spec.get("test_intents"), list) else []
    ambiguities = spec.get("ambiguities") if isinstance(spec.get("ambiguities"), list) else []
    business_rules = spec.get("business_rules") if isinstance(spec.get("business_rules"), list) else []
    quality_gate = spec.get("quality_gate") if isinstance(spec.get("quality_gate"), dict) else {}
    lines = [
        "# 需求测试点分析",
        "",
        f"- 页面: `{page}`",
        f"- 优先级: `{priority}`",
        f"- 解析置信度: `{parse_confidence}`",
        f"- 测试点数量: `{len(test_intents)}`",
        f"- 规则数量: `{len(business_rules)}`",
        f"- 消歧数量: `{len(ambiguities)}`",
    ]
    if quality_gate:
        blockers = quality_gate.get("blockers") if isinstance(quality_gate.get("blockers"), list) else []
        lines.extend(
            [
                "",
                "## 质量门禁",
                f"- 决策: `{str(quality_gate.get('decision', '')).strip() or '-'}`",
                f"- 阶段: `{str(quality_gate.get('stage', '')).strip() or '-'}`",
                f"- 阻断项数量: `{len(blockers)}`",
            ]
        )
    if test_intents:
        lines.extend(["", "## 测试点"])
        for index, intent in enumerate(test_intents[:20], start=1):
            if not isinstance(intent, dict):
                continue
            lines.append(
                f"{index}. [{str(intent.get('priority', 'P1')).strip() or 'P1'}/{str(intent.get('intent_type', 'functional')).strip() or 'functional'}] {str(intent.get('title', '')).strip() or f'intent-{index:02d}'}"
            )
    return "\n".join(lines).strip() + "\n"


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
    return {
        "page": page,
        "priority": "P1",
        "requirement": [requirement] if requirement else [],
        "quality_gate": quality_gate if isinstance(quality_gate, dict) else {},
    }


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
    status_value = str(final_status or "").strip().lower() or "unknown"
    coverage_status = str((coverage or {}).get("status", "full")).strip().lower() or "full"
    pending_sections = int((review_state or {}).get("pending_sections", 0) or 0)
    low_confidence_elements = int((page_surface_summary or {}).get("low_confidence_count", 0) or 0)
    semantic_requires_review = bool((page_semantic_summary or {}).get("requires_review", False))
    semantic_page_type = str((page_semantic_summary or {}).get("page_type", "")).strip().lower() or "unknown"
    semantic_business_domain = str((page_semantic_summary or {}).get("business_domain", "")).strip().lower() or "generic"
    semantic_primary_goal = str((page_semantic_summary or {}).get("primary_goal", "")).strip() or "inspect_page"
    missing_required = int((page_object_summary or {}).get("missing_required_count", 0) or 0)
    point_summary = (test_points or {}).get("review_summary", {}) if isinstance(test_points, dict) else {}
    asset_context = test_point_asset_context if isinstance(test_point_asset_context, dict) else {}
    asset_review_summary = asset_context.get("review_summary", {}) if isinstance(asset_context.get("review_summary"), dict) else {}
    asset_selection_summary = asset_context.get("selection_summary", {}) if isinstance(asset_context.get("selection_summary"), dict) else {}
    asset_traceability_summary = asset_context.get("traceability_summary", {}) if isinstance(asset_context.get("traceability_summary"), dict) else {}
    pending_test_points = int(point_summary.get("pending_review_count", asset_review_summary.get("pending_review_count", 0)) or 0)
    skip_suggestions = int(point_summary.get("skip_suggestion_count", asset_review_summary.get("skip_suggestion_count", 0)) or 0)
    dependency_review_points = int(point_summary.get("dependency_review_count", asset_review_summary.get("dependency_review_count", 0)) or 0)
    low_confidence_dependency_points = int(point_summary.get("low_confidence_dependency_point_count", asset_review_summary.get("low_confidence_dependency_point_count", 0)) or 0)
    missing_dependency_points = int(point_summary.get("missing_dependency_point_count", asset_review_summary.get("missing_dependency_point_count", 0)) or 0)
    dependency_skip_points = int(point_summary.get("dependency_skip_count", asset_review_summary.get("dependency_skip_count", 0)) or 0)
    asset_selection_state = str(asset_selection_summary.get("selection_state", "")).strip().lower()
    asset_ready_for_regression = bool(asset_selection_summary.get("ready_for_regression", False))
    asset_selection_reasons = asset_selection_summary.get("reasons", []) if isinstance(asset_selection_summary.get("reasons"), list) else []
    block_missing_required_threshold = max(1, int(getattr(SETTINGS, "execution_gate_block_missing_required_threshold", 2) or 2))
    block_missing_dependency_points_threshold = max(
        1,
        int(getattr(SETTINGS, "execution_gate_block_missing_dependency_points_threshold", 1) or 1),
    )
    block_on_failed_status = bool(getattr(SETTINGS, "execution_gate_block_on_failed_status", True))
    block_on_risk_block = bool(getattr(SETTINGS, "execution_gate_block_on_risk_block", True))
    warn_on_pending_reviews = bool(getattr(SETTINGS, "execution_gate_warn_on_pending_reviews", True))
    warn_on_low_confidence_elements = bool(getattr(SETTINGS, "execution_gate_warn_on_low_confidence_elements", True))
    warn_on_pending_test_points = bool(getattr(SETTINGS, "execution_gate_warn_on_pending_test_points", True))
    warn_on_low_confidence_dependency_points = bool(
        getattr(SETTINGS, "execution_gate_warn_on_low_confidence_dependency_points", True)
    )

    blockers: list[str] = []
    warnings: list[str] = []
    evidence: list[str] = []

    if block_on_failed_status and status_value in {"generate_failed", "failed"}:
        blockers.append(f"执行状态为 {status_value}。")
        evidence.append(f"执行状态={status_value}，按门禁规则直接阻断。")
    if missing_required >= block_missing_required_threshold:
        blockers.append(f"Page Object 缺失必需元素 {missing_required} 个。")
        evidence.append(f"Page Object 缺失必需元素 {missing_required} 个，达到阻断阈值 {block_missing_required_threshold}。")
    elif missing_required > 0:
        warnings.append(f"Page Object 缺失必需元素 {missing_required} 个。")
        evidence.append(f"Page Object 缺失必需元素 {missing_required} 个，低于阻断阈值 {block_missing_required_threshold}。")
    if missing_dependency_points >= block_missing_dependency_points_threshold:
        blockers.append(f"存在依赖元素未识别的测试点 {missing_dependency_points} 个。")
        evidence.append(
            f"页面分析未识别依赖元素影响测试点 {missing_dependency_points} 个，达到阻断阈值 {block_missing_dependency_points_threshold}。"
        )
    elif missing_dependency_points > 0:
        warnings.append(f"存在依赖元素未识别的测试点 {missing_dependency_points} 个。")
        evidence.append(
            f"页面分析未识别依赖元素影响测试点 {missing_dependency_points} 个，低于阻断阈值 {block_missing_dependency_points_threshold}。"
        )

    if coverage_status != "full":
        warnings.append(f"覆盖状态为 {coverage_status}。")
        evidence.append(f"覆盖状态={coverage_status}。")
    if warn_on_low_confidence_elements and low_confidence_elements > 0:
        warnings.append(f"存在低置信度页面元素 {low_confidence_elements} 个。")
        evidence.append(f"页面分析识别到低置信度元素 {low_confidence_elements} 个。")
    if semantic_requires_review:
        warnings.append("页面语义摘要仍要求人工复核。")
        evidence.append(
            f"页面语义为 page_type={semantic_page_type} / domain={semantic_business_domain} / goal={semantic_primary_goal}，当前仍要求人工复核。"
        )
    elif semantic_page_type != "unknown":
        evidence.append(
            f"页面语义判定为 {semantic_page_type}，业务域={semantic_business_domain}，主目标={semantic_primary_goal}。"
        )
    if warn_on_pending_test_points and pending_test_points > 0:
        warnings.append(f"存在待确认测试点 {pending_test_points} 个。")
        evidence.append(f"测试点层存在待确认项 {pending_test_points} 个。")
    if skip_suggestions > 0:
        warnings.append(f"存在建议跳过测试点 {skip_suggestions} 个。")
        evidence.append(f"测试点层存在建议跳过项 {skip_suggestions} 个。")
    if dependency_review_points > 0:
        evidence.append(f"共有 {dependency_review_points} 个测试点消费了页面元素依赖传播结果。")
    if warn_on_low_confidence_dependency_points and low_confidence_dependency_points > 0:
        warnings.append(f"存在受低置信度元素影响的测试点 {low_confidence_dependency_points} 个。")
        evidence.append(f"低置信度元素影响测试点 {low_confidence_dependency_points} 个。")
    if dependency_skip_points > 0:
        evidence.append(f"其中 {dependency_skip_points} 个 skip 建议由依赖传播直接触发。")
    if warn_on_pending_reviews and pending_sections > 0:
        warnings.append(f"存在待确认分组 {pending_sections} 个。")
        evidence.append(f"当前仍有待确认分组 {pending_sections} 个。")
    if asset_selection_state == "blocked":
        blockers.append("测试点资产选择摘要判定为 blocked。")
        evidence.extend([f"测试点资产选择摘要：{reason}" for reason in asset_selection_reasons[:3]] or ["测试点资产选择摘要为 blocked。"])
    elif asset_selection_state == "needs_review":
        warnings.append("测试点资产选择摘要要求人工复核。")
        evidence.extend([f"测试点资产选择摘要：{reason}" for reason in asset_selection_reasons[:3]] or ["测试点资产选择摘要为 needs_review。"])
    elif asset_selection_state == "ready" and asset_ready_for_regression:
        evidence.append("测试点资产选择摘要判定可直接进入回归。")

    if isinstance(risk_report, dict) and risk_report:
        risk_gate = str(risk_report.get("gate_decision", "")).strip().lower()
        if block_on_risk_block and risk_gate == "block":
            blockers.append("风险评估 gate_decision=block。")
            evidence.append("风险评估结果为 block，门禁按规则阻断。")
        elif risk_gate and risk_gate != "allow":
            warnings.append(f"风险评估 gate_decision={risk_gate}。")
            evidence.append(f"风险评估结果为 {risk_gate}。")

    if blockers:
        decision = "block"
    elif warnings:
        decision = "manual_review"
    else:
        decision = "allow"

    return {
        "version": "ExecutionGateV1",
        "page": page,
        "decision": decision,
        "effective_decision": decision,
        "decision_source": "system",
        "requires_review": decision != "allow",
        "blockers": _dedup_keep_order(blockers),
        "warnings": _dedup_keep_order(warnings),
        "evidence": _dedup_keep_order(evidence),
        "metrics": {
            "status": status_value,
            "coverage_status": coverage_status,
            "low_confidence_elements": low_confidence_elements,
            "semantic_requires_review": semantic_requires_review,
            "semantic_page_type": semantic_page_type,
            "semantic_business_domain": semantic_business_domain,
            "missing_page_object_elements": missing_required,
            "pending_test_points": pending_test_points,
            "skip_suggestions": skip_suggestions,
            "dependency_review_points": dependency_review_points,
            "low_confidence_dependency_points": low_confidence_dependency_points,
            "missing_dependency_points": missing_dependency_points,
            "dependency_skip_points": dependency_skip_points,
            "pending_review_sections": pending_sections,
            "asset_selection_state": asset_selection_state or "unknown",
            "asset_ready_for_regression": asset_ready_for_regression,
        },
        "config_snapshot": {
            "block_missing_required_threshold": block_missing_required_threshold,
            "block_missing_dependency_points_threshold": block_missing_dependency_points_threshold,
            "block_on_failed_status": block_on_failed_status,
            "block_on_risk_block": block_on_risk_block,
            "warn_on_pending_reviews": warn_on_pending_reviews,
            "warn_on_low_confidence_elements": warn_on_low_confidence_elements,
            "warn_on_pending_test_points": warn_on_pending_test_points,
            "warn_on_low_confidence_dependency_points": warn_on_low_confidence_dependency_points,
        },
        "test_point_asset_context": {
            "asset_id": str(asset_context.get("asset_id", "")).strip(),
            "selection_state": asset_selection_state or "unknown",
            "selection_reasons": _dedup_keep_order([str(item).strip() for item in asset_selection_reasons if str(item).strip()])[:5],
            "review_status": str((asset_traceability_summary.get("review", {}) if isinstance(asset_traceability_summary.get("review"), dict) else {}).get("test_point_status", "")).strip() or "unknown",
            "coverage_status": str((asset_traceability_summary.get("coverage", {}) if isinstance(asset_traceability_summary.get("coverage"), dict) else {}).get("asset_status", "")).strip() or "unknown",
        },
        "manual_decision": {},
    }


def _execution_gate_policy_baseline() -> dict[str, Any]:
    block_missing_required_threshold = max(
        1,
        int(getattr(SETTINGS, "execution_gate_block_missing_required_threshold", 2) or 2),
    )
    block_missing_dependency_points_threshold = max(
        1,
        int(getattr(SETTINGS, "execution_gate_block_missing_dependency_points_threshold", 1) or 1),
    )
    decision_privileged_roles = [
        str(item).strip().lower()
        for item in getattr(SETTINGS, "execution_gate_decision_privileged_roles", [])
        if str(item).strip()
    ] or ["admin"]
    dual_approval_bypass_roles = [
        str(item).strip().lower()
        for item in getattr(SETTINGS, "execution_gate_dual_approval_bypass_roles", [])
        if str(item).strip()
    ] or ["admin"]
    dual_approval_enabled = bool(getattr(SETTINGS, "execution_gate_dual_approval_enabled", False))
    return {
        "version": "ExecutionGatePolicyBaselineV1",
        "system_decision_rules": {
            "block": _dedup_keep_order(
                [
                    "执行状态为 failed/generate_failed 时直接阻断。"
                    if bool(getattr(SETTINGS, "execution_gate_block_on_failed_status", True))
                    else "",
                    f"Page Object 缺失必需元素达到 {block_missing_required_threshold} 个时阻断。",
                    f"未识别依赖元素影响测试点达到 {block_missing_dependency_points_threshold} 个时阻断。",
                    "风险评估 gate_decision=block 时阻断。"
                    if bool(getattr(SETTINGS, "execution_gate_block_on_risk_block", True))
                    else "",
                ]
            ),
            "manual_review": _dedup_keep_order(
                [
                    "存在待确认分组时进入人工复核。"
                    if bool(getattr(SETTINGS, "execution_gate_warn_on_pending_reviews", True))
                    else "",
                    "存在低置信度页面元素时进入人工复核。"
                    if bool(getattr(SETTINGS, "execution_gate_warn_on_low_confidence_elements", True))
                    else "",
                    "存在待确认测试点时进入人工复核。"
                    if bool(getattr(SETTINGS, "execution_gate_warn_on_pending_test_points", True))
                    else "",
                    "存在受低置信度依赖元素影响的测试点时进入人工复核。"
                    if bool(getattr(SETTINGS, "execution_gate_warn_on_low_confidence_dependency_points", True))
                    else "",
                    "覆盖状态非 full 时进入人工复核。",
                    "存在 skip 建议测试点时进入人工复核。",
                ]
            ),
            "allow": [
                "未命中阻断规则，且不存在需人工复核的 warning 时自动放行。"
            ],
        },
        "manual_override_boundary": {
            "allowed_decisions": ["manual_review", "allow", "block"],
            "authenticated_required": True,
            "manual_review_roles": ["any_authenticated_user"],
            "allow_block_roles": decision_privileged_roles,
            "dual_approval": {
                "enabled": dual_approval_enabled,
                "applies_to": ["block"] if dual_approval_enabled else [],
                "bypass_roles": dual_approval_bypass_roles if dual_approval_enabled else [],
                "rule": "当 dual approval 开启时，非豁免角色提交 block 需要二次审批。"
                if dual_approval_enabled
                else "当前未启用二次审批。",
            },
            "revoke_boundary": {
                "allowed_actors": [
                    "decision_maker",
                    "privileged_role",
                ],
                "rule": "撤销仅允许原决策人或具备 privileged role 的用户执行。",
            },
        },
        "non_goals": [
            "AI 不直接决定 pass/fail。",
            "AI 不直接决定 execution gate 最终人工 override。",
            "Self-healing 不允许修改业务断言和业务流程。",
        ],
    }


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
    point_summary = (test_points or {}).get("review_summary", {}) if isinstance(test_points, dict) else {}
    gate_check = _build_execution_gate(
        page=page,
        final_status=final_status,
        coverage=coverage if isinstance(coverage, dict) else {},
        page_surface_summary=page_surface_summary if isinstance(page_surface_summary, dict) else {},
        page_semantic_summary=page_semantic_summary if isinstance(page_semantic_summary, dict) else {},
        page_object_summary=page_object_summary if isinstance(page_object_summary, dict) else {},
        test_points=test_points if isinstance(test_points, dict) else {},
        review_state=review_state if isinstance(review_state, dict) else {},
    )
    return {
        "version": "ExecutionPlanV1",
        "page": page,
        "retry_policy": {"max_retries": 0},
        "gate_check": gate_check,
        "metadata": {
            "step_count": len(steps),
            "pending_test_point_reviews": int(point_summary.get("pending_review_count", 0) or 0),
            "skip_suggestions": int(point_summary.get("skip_suggestion_count", 0) or 0),
            "dependency_review_points": int(point_summary.get("dependency_review_count", 0) or 0),
            "missing_dependency_points": int(point_summary.get("missing_dependency_point_count", 0) or 0),
            "gate_decision": str(gate_check.get("decision", "")).strip() or "allow",
        },
    }


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
    analysis_context = _build_page_analysis_context(
        page=page,
        project=project,
        case_id=str((run_id or "")).strip(),
        page_url="",
        page_surface=page_surface if isinstance(page_surface, dict) else {"confidence_summary": page_surface_summary or {}},
        page_object=page_object if isinstance(page_object, dict) else {"summary": page_object_summary or {}},
        test_points=test_points,
    )
    consumed_surface_summary = analysis_context.get("page_surface_summary") if isinstance(analysis_context.get("page_surface_summary"), dict) else (page_surface_summary or {})
    consumed_page_semantic_summary = analysis_context.get("page_semantic_summary") if isinstance(analysis_context.get("page_semantic_summary"), dict) else {}
    consumed_page_object_summary = analysis_context.get("page_object_summary") if isinstance(analysis_context.get("page_object_summary"), dict) else (page_object_summary or {})
    consumed_test_points = analysis_context.get("test_points") if isinstance(analysis_context.get("test_points"), dict) else (test_points or {})
    consumed_model_versions = analysis_context.get("model_versions") if isinstance(analysis_context.get("model_versions"), dict) else {}
    local_requirement_spec = requirement_spec if isinstance(requirement_spec, dict) and requirement_spec else _build_requirement_spec_for_risk(
        page=page,
        requirement=requirement,
        quality_gate=quality_gate,
    )
    execution_plan = _build_execution_plan_for_risk(
        page=page,
        steps=steps,
        test_points=consumed_test_points,
        coverage=(consumed_test_points.get("coverage") if isinstance(consumed_test_points.get("coverage"), dict) else {}),
        page_surface_summary=consumed_surface_summary,
        page_semantic_summary=consumed_page_semantic_summary,
        page_object_summary=consumed_page_object_summary,
        review_state=review_state,
        final_status=final_status,
    )
    run_item = _find_run_item(run_id) if run_id else None
    execution_record = (
        run_item.get("execution_record", {})
        if isinstance(run_item, dict) and isinstance(run_item.get("execution_record"), dict)
        else _build_runtime_execution_record(
            run_id=run_id,
            case_id=str((run_item or {}).get("case_id", "")).strip(),
            project=project,
            source="auto-run",
            mode="generate_and_run",
            status=final_status,
            started_at=str((run_item or {}).get("started_at", "")).strip(),
            finished_at=str((run_item or {}).get("finished_at", "")).strip(),
            return_code=(run_item or {}).get("return_code") if isinstance(run_item, dict) else None,
            created_at=str((run_item or {}).get("created_at", "")).strip() if isinstance(run_item, dict) else "",
        )
    )
    failure_analysis = _build_failure_analysis_for_risk(
        final_status=final_status,
        page_object_summary=consumed_page_object_summary,
        test_points=consumed_test_points,
    )
    try:
        orchestrator_payload = _run_orchestrator_risk(
            requirement_spec=local_requirement_spec,
            execution_plan=execution_plan,
            execution_record=execution_record,
            failure_analysis=failure_analysis,
            failure_triage={},
        )
        risk_report = orchestrator_payload.get("risk_report", {}) if isinstance(orchestrator_payload, dict) else {}
        if isinstance(risk_report, dict) and risk_report:
            factor_rows = _normalize_risk_factors(
                risk_report.get("factors") if isinstance(risk_report.get("factors"), list) else [],
                source="risk-evaluation-agent",
            )
            evidence = _build_risk_evidence(factors=factor_rows)
            evidence.extend(_build_semantic_risk_evidence(page_semantic_summary=consumed_page_semantic_summary))
            pending_sections = int((review_state or {}).get("pending_sections", 0) or 0)
            risk_report["page"] = page
            risk_report["source"] = "risk-evaluation-agent"
            risk_report["factors"] = factor_rows
            risk_report["factor_summary"] = _build_risk_factor_summary(factors=factor_rows)
            risk_report["confidence"] = _clamp_confidence(0.88 if evidence else 0.76)
            risk_report["evidence"] = evidence
            risk_report["requires_review"] = (
                str(risk_report.get("gate_decision", "")).strip().lower() != "allow"
                or pending_sections > 0
                or float(risk_report.get("confidence", 0) or 0) < 0.75
            )
            risk_report["metadata"] = {
                **(risk_report.get("metadata", {}) if isinstance(risk_report.get("metadata"), dict) else {}),
                "final_status": str(final_status or "").strip().lower() or "unknown",
                "pending_review_sections": pending_sections,
                "provider": "orchestrator",
                "semantic_page_type": str((consumed_page_semantic_summary or {}).get("page_type", "")).strip() or "unknown",
                "semantic_business_domain": str((consumed_page_semantic_summary or {}).get("business_domain", "")).strip() or "generic",
                "semantic_primary_goal": str((consumed_page_semantic_summary or {}).get("primary_goal", "")).strip() or "inspect_page",
                "semantic_requires_review": bool((consumed_page_semantic_summary or {}).get("requires_review", False)),
                "semantic_confidence": _clamp_confidence((consumed_page_semantic_summary or {}).get("confidence", 0)),
                "factor_count": int((risk_report.get("factor_summary", {}) or {}).get("factor_count", 0) or 0),
                "top_factor": (risk_report.get("factor_summary", {}) or {}).get("top_factor", {}),
                "consumed_models": {
                    **consumed_model_versions,
                },
            }
            return risk_report
    except HTTPException as exc:
        fallback = _build_risk_report(
            page=page,
            final_status=final_status,
            page_surface_summary=consumed_surface_summary,
            page_semantic_summary=consumed_page_semantic_summary,
            page_object_summary=consumed_page_object_summary,
            test_points=consumed_test_points,
            review_state=review_state,
        )
        fallback["source"] = "local-fallback"
        fallback["warnings"] = [f"risk-evaluation-agent unavailable: {exc.detail}"]
        fallback["metadata"] = {
            **(fallback.get("metadata", {}) if isinstance(fallback.get("metadata"), dict) else {}),
            "consumed_models": consumed_model_versions,
        }
        return fallback
    except Exception as exc:  # pragma: no cover - keep risk path non-blocking
        fallback = _build_risk_report(
            page=page,
            final_status=final_status,
            page_surface_summary=consumed_surface_summary,
            page_semantic_summary=consumed_page_semantic_summary,
            page_object_summary=consumed_page_object_summary,
            test_points=consumed_test_points,
            review_state=review_state,
        )
        fallback["source"] = "local-fallback"
        fallback["warnings"] = [f"risk-evaluation-agent failed: {exc}"]
        fallback["metadata"] = {
            **(fallback.get("metadata", {}) if isinstance(fallback.get("metadata"), dict) else {}),
            "consumed_models": consumed_model_versions,
        }
        return fallback

    fallback = _build_risk_report(
        page=page,
        final_status=final_status,
        page_surface_summary=consumed_surface_summary,
        page_semantic_summary=consumed_page_semantic_summary,
        page_object_summary=consumed_page_object_summary,
        test_points=consumed_test_points,
        review_state=review_state,
    )
    fallback["metadata"] = {
        **(fallback.get("metadata", {}) if isinstance(fallback.get("metadata"), dict) else {}),
        "consumed_models": consumed_model_versions,
    }
    return fallback


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
        normalize_test_point_plan_payload=lambda payload, strict=False: _normalize_test_point_plan_payload(payload, strict=strict),
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
    counts = {"precondition_count": 0, "navigation_count": 0, "input_count": 0, "assertion_count": 0, "action_count": 0}
    for point in points:
        if not isinstance(point, dict):
            continue
        point_type = str(point.get("point_type", "")).strip().lower()
        action = str(point.get("action", "")).strip().lower()
        if point_type == "precondition" or action == "login":
            counts["precondition_count"] += 1
        elif point_type == "navigation" or action in {"click", "goto"}:
            counts["navigation_count"] += 1
        elif point_type == "input" or action in {"fill", "type"}:
            counts["input_count"] += 1
        elif point_type == "assertion" or action in {"assert_visible", "assert_url", "wait_for"}:
            counts["assertion_count"] += 1
        else:
            counts["action_count"] += 1
    return counts


def _build_test_point_asset_semantic_summary(
    *,
    page: str,
    normalized_plan: dict[str, Any],
) -> dict[str, Any]:
    page_value = _normalize_page_slug(page) if str(page).strip() else "unknown"
    source_type = str(normalized_plan.get("source_type", "")).strip().lower()
    point_types = {
        str(point.get("point_type", "")).strip().lower()
        for point in normalized_plan.get("points", [])
        if isinstance(point, dict) and str(point.get("point_type", "")).strip()
    }
    actions = {
        str(point.get("action", "")).strip().lower()
        for point in normalized_plan.get("points", [])
        if isinstance(point, dict) and str(point.get("action", "")).strip()
    }
    dependent_elements = {
        str(item).strip().lower()
        for item in normalized_plan.get("dependent_elements", [])
        if str(item).strip()
    }

    if page_value in {"product", "order", "returnapply"}:
        page_type = "list"
    elif page_value in {"addproduct"}:
        page_type = "form"
    elif "input" in point_types or "fill" in actions or "type" in actions:
        page_type = "form"
    elif "navigation" in point_types or "assertion" in point_types:
        page_type = "list"
    else:
        page_type = "unknown"

    if page_value in {"product", "addproduct"}:
        business_domain = "product"
    elif page_value == "order":
        business_domain = "order"
    elif page_value == "returnapply":
        business_domain = "aftersales"
    else:
        business_domain = "generic"

    primary_actions: list[str] = []
    if {"search_input", "search_button"} & dependent_elements:
        primary_actions.append("search")
    if "assert_visible" in actions or page_type == "list":
        primary_actions.append("view_results")
    if {"fill", "type"} & actions or page_type == "form":
        primary_actions.append("edit_form")
    if {"click", "submit"} & actions and page_type == "form":
        primary_actions.append("submit")
    primary_actions = _dedup_keep_order(primary_actions)

    if page_type == "list" and "search" in primary_actions:
        primary_goal = "query_and_browse"
    elif page_type == "form" and ("edit_form" in primary_actions or "submit" in primary_actions):
        primary_goal = "edit_and_submit"
    elif page_type == "list":
        primary_goal = "browse_list"
    elif page_type == "form":
        primary_goal = "fill_form"
    else:
        primary_goal = "inspect_page"

    reason_codes: list[str] = [f"asset_page={page_value}", f"asset_source_type={source_type or 'unknown'}"]
    warnings: list[str] = []
    confidence = 0.82
    if page_type == "unknown":
        confidence -= 0.18
        warnings.append("测试点资产未能稳定映射到明确页面类型。")
        reason_codes.append("asset_page_type_unknown")
    if business_domain == "generic":
        confidence -= 0.1
        warnings.append("测试点资产业务域仍偏泛化。")
        reason_codes.append("asset_domain_generic")
    if bool(normalized_plan.get("requires_review", False)):
        confidence -= 0.08
        warnings.append("测试点资产自身仍要求人工复核。")
        reason_codes.append("asset_requires_review")

    requires_review = confidence < 0.75 or bool(normalized_plan.get("requires_review", False))
    return {
        "page_type": page_type,
        "business_domain": business_domain,
        "primary_goal": primary_goal,
        "primary_actions": primary_actions,
        "reason_codes": _dedup_keep_order(reason_codes),
        "confidence": _clamp_confidence(confidence),
        "warnings": _dedup_keep_order(warnings),
        "requires_review": requires_review,
        "source": "asset_plan",
    }


def _build_test_point_asset_technique_summary(
    *,
    normalized_plan: dict[str, Any],
) -> dict[str, Any]:
    plan = normalized_plan if isinstance(normalized_plan, dict) else {}
    review_summary = plan.get("review_summary") if isinstance(plan.get("review_summary"), dict) else {}
    points = plan.get("points") if isinstance(plan.get("points"), list) else []
    total_points = int(review_summary.get("total_points", len(points)) or 0)
    mainline_point_count = int(review_summary.get("mainline_point_count", 0) or 0)
    design_only_point_count = int(review_summary.get("design_only_point_count", 0) or 0)
    technique_distribution_raw = review_summary.get("technique_distribution") if isinstance(review_summary.get("technique_distribution"), dict) else {}
    technique_distribution = {
        str(key).strip() or "normal": int(value or 0)
        for key, value in technique_distribution_raw.items()
        if str(key).strip()
    }
    if not technique_distribution:
        for point in points:
            if not isinstance(point, dict):
                continue
            technique_type = str(point.get("technique_type", "normal")).strip() or "normal"
            technique_distribution[technique_type] = technique_distribution.get(technique_type, 0) + 1
    if total_points <= 0:
        total_points = len([point for point in points if isinstance(point, dict)])
    if mainline_point_count <= 0 and total_points:
        mainline_point_count = len(
            [
                point
                for point in points
                if isinstance(point, dict)
                and str(point.get("execution_scope", "mainline")).strip().lower() != "design_only"
            ]
        )
    if design_only_point_count <= 0 and total_points:
        design_only_point_count = len(
            [
                point
                for point in points
                if isinstance(point, dict)
                and str(point.get("execution_scope", "mainline")).strip().lower() == "design_only"
            ]
        )
    return {
        "total_points": int(total_points),
        "mainline_point_count": int(mainline_point_count),
        "design_only_point_count": int(design_only_point_count),
        "technique_distribution": dict(sorted(technique_distribution.items())),
        "has_design_only_points": bool(design_only_point_count > 0),
        "mainline_ready": bool(mainline_point_count > 0),
    }


def _merge_reference_items(*reference_lists: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for reference_list in reference_lists:
        for item in reference_list:
            if not isinstance(item, dict):
                continue
            normalized = {
                "kind": str(item.get("kind", "")).strip() or "reference",
                "path": str(item.get("path", "")).strip(),
                "case_id": str(item.get("case_id", "")).strip(),
                "page": str(item.get("page", "")).strip(),
            }
            identity = (normalized["kind"], normalized["path"], normalized["case_id"])
            if identity in seen:
                continue
            seen.add(identity)
            merged.append({key: value for key, value in normalized.items() if value})
    return merged


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
    normalized_project = str(project or "default").strip() or "default"
    normalized_case_id = _safe_case_id(case_id)
    normalized_page = _normalize_page_slug(page) if str(page).strip() else ""
    candidates: list[dict[str, Any]] = []
    with _RUN_LOCK:
        candidates.extend(_runtime_view_with_execution_record_preferred(dict(item)) for item in _RUN_JOBS.values())
    candidates.extend(_runtime_view_with_execution_record_preferred(item) for item in _read_json_list(RUNTIME_RUNS_FILE))
    matched: list[dict[str, Any]] = []
    for item in candidates:
        if str(item.get("project", "default")).strip() != normalized_project:
            continue
        if _safe_case_id(str(item.get("case_id", "")).strip()) != normalized_case_id:
            continue
        item_page = _normalize_page_slug(str(item.get("page", "")).strip()) if str(item.get("page", "")).strip() else ""
        if normalized_page and item_page and item_page != normalized_page:
            continue
        matched.append(item)
    if not matched:
        return {}
    matched.sort(
        key=lambda item: (
            str(item.get("finished_at", "")).strip(),
            str(item.get("started_at", "")).strip(),
            str(item.get("run_id", "")).strip(),
        ),
        reverse=True,
    )
    latest = matched[0]
    review_state = latest.get("review_state", {}) if isinstance(latest.get("review_state"), dict) else {}
    review_audit_summary = latest.get("review_audit_summary") if isinstance(latest.get("review_audit_summary"), dict) else _build_review_audit_summary(review_state)
    execution_gate = latest.get("execution_gate", {}) if isinstance(latest.get("execution_gate"), dict) else {}
    risk_report = latest.get("risk_report", {}) if isinstance(latest.get("risk_report"), dict) else {}
    page_semantic_summary = (
        latest.get("page_semantic_summary")
        if isinstance(latest.get("page_semantic_summary"), dict)
        else _build_page_semantic_summary(latest.get("page_semantic") if isinstance(latest.get("page_semantic"), dict) else {})
    )
    return {
        "run_id": str(latest.get("run_id", "")).strip(),
        "status": str(latest.get("status", "")).strip(),
        "page": str(latest.get("page", "")).strip(),
        "started_at": str(latest.get("started_at", "")).strip(),
        "finished_at": str(latest.get("finished_at", "")).strip(),
        "page_semantic_summary": page_semantic_summary if isinstance(page_semantic_summary, dict) else {},
        "review_state": review_state,
        "review_audit_summary": review_audit_summary,
        "coverage": latest.get("coverage", {}) if isinstance(latest.get("coverage"), dict) else {},
        "execution_gate": execution_gate,
        "execution_gate_summary": _build_execution_gate_audit_snapshot(execution_gate),
        "risk_report": risk_report,
        "risk_summary": _build_risk_report_summary(risk_report),
    }


def _build_test_point_asset_traceability_summary(
    *,
    asset: dict[str, Any],
    latest_run: dict[str, Any] | None,
) -> dict[str, Any]:
    asset_payload = asset if isinstance(asset, dict) else {}
    latest_run_payload = latest_run if isinstance(latest_run, dict) else {}
    asset_semantic_summary = asset_payload.get("semantic_summary") if isinstance(asset_payload.get("semantic_summary"), dict) else {}
    asset_coverage = asset_payload.get("coverage", {}) if isinstance(asset_payload.get("coverage"), dict) else {}
    asset_review_summary = asset_payload.get("review_summary", {}) if isinstance(asset_payload.get("review_summary"), dict) else {}
    asset_technique_summary = asset_payload.get("technique_summary") if isinstance(asset_payload.get("technique_summary"), dict) else _build_test_point_asset_technique_summary(normalized_plan=asset_payload.get("plan", {}) if isinstance(asset_payload.get("plan"), dict) else {})
    run_review_state = latest_run_payload.get("review_state", {}) if isinstance(latest_run_payload.get("review_state"), dict) else {}
    run_review_audit_summary = (
        latest_run_payload.get("review_audit_summary")
        if isinstance(latest_run_payload.get("review_audit_summary"), dict)
        else _build_review_audit_summary(run_review_state)
    )
    run_execution_gate = latest_run_payload.get("execution_gate", {}) if isinstance(latest_run_payload.get("execution_gate"), dict) else {}
    run_page_semantic_summary = (
        latest_run_payload.get("page_semantic_summary")
        if isinstance(latest_run_payload.get("page_semantic_summary"), dict)
        else _build_page_semantic_summary(
            latest_run_payload.get("page_semantic") if isinstance(latest_run_payload.get("page_semantic"), dict) else {}
        )
    )
    semantic_summary = run_page_semantic_summary if isinstance(run_page_semantic_summary, dict) and run_page_semantic_summary else asset_semantic_summary
    run_coverage = latest_run_payload.get("coverage", {}) if isinstance(latest_run_payload.get("coverage"), dict) else {}
    risk_report = latest_run_payload.get("risk_report", {}) if isinstance(latest_run_payload.get("risk_report"), dict) else {}
    risk_summary = latest_run_payload.get("risk_summary") if isinstance(latest_run_payload.get("risk_summary"), dict) else _build_risk_report_summary(risk_report)
    derived_execution_gate_summary = {}
    run_page = str(latest_run_payload.get("page", "")).strip() or str(asset_payload.get("page", "")).strip()
    if run_page:
        derived_execution_gate_summary = _build_execution_gate(
            page=run_page,
            final_status=str(latest_run_payload.get("status", "")).strip(),
            coverage=run_coverage,
            page_surface_summary=latest_run_payload.get("page_surface_summary") if isinstance(latest_run_payload.get("page_surface_summary"), dict) else {},
            page_semantic_summary=run_page_semantic_summary,
            page_object_summary=latest_run_payload.get("page_object_summary") if isinstance(latest_run_payload.get("page_object_summary"), dict) else {},
            test_points=latest_run_payload.get("test_points") if isinstance(latest_run_payload.get("test_points"), dict) else {},
            review_state=run_review_state,
            risk_report=risk_report if isinstance(risk_report, dict) else {},
            test_point_asset_context={},
        )
    derived_execution_gate_audit_summary = (
        _build_execution_gate_audit_snapshot(derived_execution_gate_summary)
        if isinstance(derived_execution_gate_summary, dict) and derived_execution_gate_summary
        else {}
    )
    run_execution_gate_summary = (
        latest_run_payload.get("execution_gate_summary")
        if isinstance(latest_run_payload.get("execution_gate_summary"), dict)
        else _build_execution_gate_audit_snapshot(run_execution_gate)
    )
    gate_reason_summary = str(
        (derived_execution_gate_audit_summary or run_execution_gate_summary).get("gate_reason_summary", "")
    ).strip()
    return {
        "asset_review_required": bool(asset_payload.get("requires_review", False)),
        "asset_coverage_status": str(asset_coverage.get("status", "unknown")).strip() or "unknown",
        "asset_pending_review_count": int(asset_review_summary.get("pending_review_count", 0) or 0),
        "latest_run_id": str(latest_run_payload.get("run_id", "")).strip(),
        "latest_run_status": str(latest_run_payload.get("status", "")).strip(),
        "latest_run_at": str(latest_run_payload.get("finished_at", "")).strip() or str(latest_run_payload.get("started_at", "")).strip(),
        "coverage": {
            "asset_status": str(asset_coverage.get("status", "unknown")).strip() or "unknown",
            "latest_run_status": str(run_coverage.get("status", "unknown")).strip() or "unknown",
            "missing_count": int(run_coverage.get("missing_count", len(run_coverage.get("missing", []) if isinstance(run_coverage.get("missing"), list) else [])) or 0),
        },
        "review": {
            "requires_review": bool(run_review_state.get("requires_review", False)),
            "pending_sections": int(run_review_state.get("pending_sections", 0) or 0),
            "confirmed_sections": int(run_review_state.get("confirmed_sections", 0) or 0),
            "element_status": str((run_review_state.get("element", {}) if isinstance(run_review_state.get("element"), dict) else {}).get("status", "not_required")).strip() or "not_required",
            "test_point_status": str((run_review_state.get("test_point", {}) if isinstance(run_review_state.get("test_point"), dict) else {}).get("status", "not_required")).strip() or "not_required",
            "risk_status": str((run_review_state.get("risk", {}) if isinstance(run_review_state.get("risk"), dict) else {}).get("status", "not_required")).strip() or "not_required",
            "latest_actor_display": str(run_review_audit_summary.get("latest_actor_display", "")).strip(),
            "latest_updated_at": str(run_review_audit_summary.get("latest_updated_at", "")).strip(),
        },
        "gate": {
            "decision": str(run_execution_gate.get("decision", "")).strip() or "allow",
            "effective_decision": str(run_execution_gate.get("effective_decision", "")).strip() or str(run_execution_gate.get("decision", "")).strip() or "allow",
            "decision_source": str(run_execution_gate.get("decision_source", "")).strip() or "system",
            "approval_status": str(run_execution_gate.get("approval_status", "")).strip(),
            "record_status": str(run_execution_gate.get("record_status", "")).strip(),
            "requires_review": bool(run_execution_gate.get("requires_review", False)),
            "gate_reason_summary": gate_reason_summary,
        },
        "risk": {
            "risk_level": str(risk_report.get("risk_level", "")).strip(),
            "gate_decision": str(risk_report.get("gate_decision", "")).strip(),
            "requires_review": bool(risk_report.get("requires_review", False)),
            "factor_count": int(risk_summary.get("factor_count", 0) or 0),
            "top_factor": risk_summary.get("top_factor", {}) if isinstance(risk_summary.get("top_factor"), dict) else {},
            "provider": str(risk_summary.get("provider", "")).strip(),
        },
        "semantic": {
            "page_type": str(semantic_summary.get("page_type", "")).strip(),
            "business_domain": str(semantic_summary.get("business_domain", "")).strip(),
            "primary_goal": str(semantic_summary.get("primary_goal", "")).strip(),
            "primary_actions": semantic_summary.get("primary_actions", []) if isinstance(semantic_summary.get("primary_actions"), list) else [],
            "confidence": _clamp_confidence(semantic_summary.get("confidence", 0)),
            "requires_review": bool(semantic_summary.get("requires_review", False)),
            "source": str(semantic_summary.get("source", "run_snapshot" if run_page_semantic_summary else "asset_plan")).strip() or ("run_snapshot" if run_page_semantic_summary else "asset_plan"),
        },
        "technique": {
            "total_points": int(asset_technique_summary.get("total_points", 0) or 0),
            "mainline_point_count": int(asset_technique_summary.get("mainline_point_count", 0) or 0),
            "design_only_point_count": int(asset_technique_summary.get("design_only_point_count", 0) or 0),
            "technique_distribution": asset_technique_summary.get("technique_distribution", {}) if isinstance(asset_technique_summary.get("technique_distribution"), dict) else {},
            "has_design_only_points": bool(asset_technique_summary.get("has_design_only_points", False)),
            "mainline_ready": bool(asset_technique_summary.get("mainline_ready", False)),
            "source": "asset_plan",
        },
    }


def _build_test_point_asset_selection_summary(
    *,
    traceability_summary: dict[str, Any],
) -> dict[str, Any]:
    summary = traceability_summary if isinstance(traceability_summary, dict) else {}
    coverage = summary.get("coverage", {}) if isinstance(summary.get("coverage"), dict) else {}
    review = summary.get("review", {}) if isinstance(summary.get("review"), dict) else {}
    gate = summary.get("gate", {}) if isinstance(summary.get("gate"), dict) else {}
    risk = summary.get("risk", {}) if isinstance(summary.get("risk"), dict) else {}
    semantic = summary.get("semantic", {}) if isinstance(summary.get("semantic"), dict) else {}
    technique = summary.get("technique", {}) if isinstance(summary.get("technique"), dict) else {}

    reasons: list[str] = []
    selection_state = "ready"
    gate_decision = str(gate.get("effective_decision", gate.get("decision", "allow"))).strip() or "allow"
    asset_review_required = bool(summary.get("asset_review_required", False))
    coverage_asset_status = str(coverage.get("asset_status", "unknown")).strip() or "unknown"
    coverage_run_status = str(coverage.get("latest_run_status", "unknown")).strip() or "unknown"
    pending_sections = int(review.get("pending_sections", 0) or 0)
    review_requires = bool(review.get("requires_review", False))
    risk_requires = bool(risk.get("requires_review", False))
    semantic_requires = bool(semantic.get("requires_review", False))
    semantic_page_type = str(semantic.get("page_type", "")).strip() or "unknown"
    semantic_business_domain = str(semantic.get("business_domain", "")).strip() or "generic"
    design_only_point_count = int(technique.get("design_only_point_count", 0) or 0)
    mainline_point_count = int(technique.get("mainline_point_count", 0) or 0)

    if gate_decision == "block":
        selection_state = "blocked"
        reasons.append(str(gate.get("gate_reason_summary", "")).strip() or "执行门禁阻断。")
    else:
        if gate_decision == "manual_review":
            selection_state = "needs_review"
            reasons.append(str(gate.get("gate_reason_summary", "")).strip() or "执行门禁要求人工复核。")
        if asset_review_required:
            selection_state = "needs_review"
            reasons.append("测试点资产自身仍要求复核。")
        if review_requires or pending_sections > 0:
            selection_state = "needs_review"
            reasons.append(f"仍有待确认分组 {pending_sections} 个。")
        if coverage_asset_status != "full":
            selection_state = "needs_review"
            reasons.append(f"测试点资产 coverage={coverage_asset_status}。")
        if coverage_run_status not in {"full", "unknown"}:
            selection_state = "needs_review"
            reasons.append(f"最近运行 coverage={coverage_run_status}。")
        if risk_requires:
            selection_state = "needs_review"
            reasons.append("风险评估仍要求人工决策。")
        if semantic_requires:
            selection_state = "needs_review"
            reasons.append(f"页面语义仍需复核（type={semantic_page_type}, domain={semantic_business_domain}）。")
        if design_only_point_count > 0 and mainline_point_count <= 0:
            selection_state = "needs_review"
            reasons.append("当前仅有 design_only 设计点，尚未形成可执行主链测试点。")

    return {
        "selection_state": selection_state,
        "ready_for_regression": selection_state == "ready",
        "effective_gate_decision": gate_decision,
        "reasons": _dedup_keep_order([reason for reason in reasons if reason]),
    }


def _build_test_point_asset_gate_context(
    *,
    project: str,
    case_id: str,
    page: str,
    coverage: dict[str, Any],
    review_state: dict[str, Any],
    risk_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_case_id = _safe_case_id(case_id)
    if not normalized_case_id:
        return {}
    asset = _load_test_point_asset(project, normalized_case_id)
    if not asset:
        return {}
    latest_run = {
        "run_id": "",
        "status": "",
        "page": page,
        "review_state": review_state if isinstance(review_state, dict) else {},
        "review_audit_summary": _build_review_audit_summary(review_state if isinstance(review_state, dict) else {}),
        "coverage": coverage if isinstance(coverage, dict) else {},
        "execution_gate": {},
        "execution_gate_summary": {},
        "risk_report": risk_report if isinstance(risk_report, dict) else {},
    }
    traceability_summary = _build_test_point_asset_traceability_summary(asset=asset, latest_run=latest_run)
    return {
        "asset_id": str(asset.get("asset_id", normalized_case_id)).strip() or normalized_case_id,
        "page": str(asset.get("page", page)).strip() or page,
        "requires_review": bool(asset.get("requires_review", False)),
        "review_summary": asset.get("review_summary", {}) if isinstance(asset.get("review_summary"), dict) else {},
        "coverage": asset.get("coverage", {}) if isinstance(asset.get("coverage"), dict) else {},
        "technique_summary": asset.get("technique_summary", {}) if isinstance(asset.get("technique_summary"), dict) else {},
        "traceability_summary": traceability_summary,
        "selection_summary": _build_test_point_asset_selection_summary(traceability_summary=traceability_summary),
    }


def _build_test_point_asset_summary(project: str, case_id: str) -> dict[str, Any]:
    asset = _load_test_point_asset(project, case_id)
    if not asset:
        return {}
    latest_run = _latest_run_snapshot_for_case(
        project=project,
        case_id=str(asset.get("asset_id", case_id)).strip() or case_id,
        page=str(asset.get("page", "")).strip(),
    )
    traceability_summary = _build_test_point_asset_traceability_summary(asset=asset, latest_run=latest_run)
    return {
        "asset_id": str(asset.get("asset_id", case_id)).strip() or case_id,
        "title": str(asset.get("title", case_id)).strip() or case_id,
        "page": str(asset.get("page", "")).strip(),
        "priority": str(asset.get("priority", "P1")).strip() or "P1",
        "source_type": str(asset.get("source_type", "unknown")).strip() or "unknown",
        "point_count": int(asset.get("point_count", 0) or 0),
        "confidence": _clamp_confidence(asset.get("confidence", 0)),
        "requires_review": bool(asset.get("requires_review", False)),
        "plan_path": str(asset.get("plan_path", "")).strip(),
        "review_summary": asset.get("review_summary", {}) if isinstance(asset.get("review_summary"), dict) else {},
        "coverage": asset.get("coverage", {}) if isinstance(asset.get("coverage"), dict) else {},
        "semantic_summary": asset.get("semantic_summary", {}) if isinstance(asset.get("semantic_summary"), dict) else {},
        "technique_summary": asset.get("technique_summary", {}) if isinstance(asset.get("technique_summary"), dict) else {},
        "latest_run": latest_run,
        "traceability_summary": traceability_summary,
        "selection_summary": _build_test_point_asset_selection_summary(traceability_summary=traceability_summary),
    }


def _build_test_point_asset_coverage_summary(
    *,
    items: list[dict[str, Any]],
    filter_snapshot: dict[str, Any],
) -> dict[str, Any]:
    coverage_status_counts: dict[str, int] = defaultdict(int)
    latest_run_coverage_status_counts: dict[str, int] = defaultdict(int)
    selection_state_counts: dict[str, int] = defaultdict(int)
    page_counts: dict[str, int] = defaultdict(int)
    source_type_counts: dict[str, int] = defaultdict(int)
    total_points = 0
    regression_ready_points = 0

    for item in items:
        if not isinstance(item, dict):
            continue
        total_points += int(item.get("point_count", 0) or 0)
        coverage_payload = item.get("coverage", {}) if isinstance(item.get("coverage"), dict) else {}
        traceability_summary = item.get("traceability_summary", {}) if isinstance(item.get("traceability_summary"), dict) else {}
        selection_summary = item.get("selection_summary", {}) if isinstance(item.get("selection_summary"), dict) else {}
        traceability_coverage = traceability_summary.get("coverage", {}) if isinstance(traceability_summary.get("coverage"), dict) else {}
        coverage_status = str(coverage_payload.get("status", "unknown")).strip() or "unknown"
        latest_run_coverage_status = str(traceability_coverage.get("latest_run_status", "unknown")).strip() or "unknown"
        selection_state = str(selection_summary.get("selection_state", "unknown")).strip() or "unknown"
        page_value = str(item.get("page", "")).strip() or "unknown"
        source_type_value = str(item.get("source_type", "")).strip() or "unknown"
        coverage_status_counts[coverage_status] += 1
        latest_run_coverage_status_counts[latest_run_coverage_status] += 1
        selection_state_counts[selection_state] += 1
        page_counts[page_value] += 1
        source_type_counts[source_type_value] += 1
        if bool(selection_summary.get("ready_for_regression", False)):
            regression_ready_points += int(item.get("point_count", 0) or 0)

    return {
        "total_assets": len(items),
        "total_points": total_points,
        "regression_ready_asset_count": int(selection_state_counts.get("ready", 0) or 0),
        "regression_ready_point_count": regression_ready_points,
        "coverage_status_counts": dict(sorted(coverage_status_counts.items())),
        "latest_run_coverage_status_counts": dict(sorted(latest_run_coverage_status_counts.items())),
        "selection_state_counts": dict(sorted(selection_state_counts.items())),
        "page_counts": dict(sorted(page_counts.items())),
        "source_type_counts": dict(sorted(source_type_counts.items())),
        "filter_snapshot": filter_snapshot,
    }


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
    text = str(requirement or "")
    digit = re.search(r"([0-9]{1,20})", text)
    if digit:
        return digit.group(1)
    quoted = re.search(r"[\"'“”‘’]([^\"'“”‘’]{1,30})[\"'“”‘’]", text)
    if quoted:
        return quoted.group(1).strip()
    return "3"


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
    if not artifacts_dir.exists():
        return {}
    candidates = sorted(
        artifacts_dir.rglob("self_healing_result.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for path in candidates:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(payload, dict):
            return {
                **payload,
                "_result_path": str(path.resolve()),
            }
    return {}


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
    normalized_page = _normalize_page_slug(page)
    analysis_context = _build_page_analysis_context(
        page=normalized_page,
        project=project,
        case_id="",
        page_url="",
        page_surface=page_surface if isinstance(page_surface, dict) else {"confidence_summary": page_surface_summary or {}},
        page_object=page_object,
        test_points=test_points,
    )
    consumed_surface_summary = analysis_context.get("page_surface_summary") if isinstance(analysis_context.get("page_surface_summary"), dict) else (page_surface_summary or {})
    consumed_test_points = analysis_context.get("test_points") if isinstance(analysis_context.get("test_points"), dict) else (test_points or {})
    decisions = _review_decisions_for_run(run_id, project=project, page=normalized_page)
    element_items = (
        consumed_surface_summary.get("low_confidence_items")
        if isinstance(consumed_surface_summary, dict) and isinstance(consumed_surface_summary.get("low_confidence_items"), list)
        else []
    )
    test_point_items = _build_test_point_review_items(consumed_test_points)
    element_section = _build_review_section(
        review_type="element",
        items=element_items,
        existing_entry=decisions.get((normalized_page, "element")),
    )
    test_point_section = _build_review_section(
        review_type="test_point",
        items=test_point_items,
        existing_entry=decisions.get((normalized_page, "test_point")),
    )
    risk_items = _build_risk_review_items(risk_report or {})
    risk_section = _build_review_section(
        review_type="risk",
        items=risk_items if bool((risk_report or {}).get("requires_review")) else [],
        existing_entry=decisions.get((normalized_page, "risk")),
    )
    sections = [element_section, test_point_section, risk_section]
    return {
        "element": element_section,
        "test_point": test_point_section,
        "risk": risk_section,
        "requires_review": any(bool(section.get("required")) and str(section.get("status", "")).strip() == "pending" for section in sections),
        "pending_sections": sum(1 for section in sections if bool(section.get("required")) and str(section.get("status", "")).strip() == "pending"),
        "confirmed_sections": sum(1 for section in sections if str(section.get("status", "")).strip() == "confirmed"),
        "model_versions": analysis_context.get("model_versions") if isinstance(analysis_context.get("model_versions"), dict) else {},
    }


def _build_run_review_state_from_decisions(*, project: str, run_id: str, page: str = "") -> dict[str, Any]:
    decisions = _review_decisions_for_run(run_id, project=project, page=page)
    if not decisions:
        return {}
    normalized_page = _normalize_page_slug(page) if str(page).strip() else ""
    if not normalized_page:
        first_key = next(iter(decisions.keys()), ("", ""))
        normalized_page = first_key[0]
    element_section = _build_review_section(
        review_type="element",
        items=[],
        existing_entry=decisions.get((normalized_page, "element")),
    )
    test_point_section = _build_review_section(
        review_type="test_point",
        items=[],
        existing_entry=decisions.get((normalized_page, "test_point")),
    )
    risk_section = _build_review_section(
        review_type="risk",
        items=[],
        existing_entry=decisions.get((normalized_page, "risk")),
    )
    sections = [element_section, test_point_section, risk_section]
    return {
        "element": element_section,
        "test_point": test_point_section,
        "risk": risk_section,
        "requires_review": any(bool(section.get("required")) and str(section.get("status", "")).strip() == "pending" for section in sections),
        "pending_sections": sum(1 for section in sections if bool(section.get("required")) and str(section.get("status", "")).strip() == "pending"),
        "confirmed_sections": sum(1 for section in sections if str(section.get("status", "")).strip() == "confirmed"),
    }


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
    return _workbench_history_service.list_history(
        history_items,
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
    normalized: list[dict[str, int]] = []
    for sample in samples:
        if not isinstance(sample, dict):
            continue
        normalized.append(
            {
                "field_count": int(sample.get("field_count", 0) or 0),
                "button_count": int(sample.get("button_count", 0) or 0),
                "title_count": int(sample.get("title_count", 0) or 0),
                "loading_mask_count": int(sample.get("loading_mask_count", 0) or 0),
            }
        )
    if not normalized:
        return {"status": "unknown", "stable": False, "sample_count": 0}

    last = normalized[-1]
    previous = normalized[-2] if len(normalized) >= 2 else None
    stable = bool(previous) and previous == last and int(last.get("loading_mask_count", 0)) == 0
    status = "stable" if stable else "settling"
    if int(last.get("loading_mask_count", 0)) > 0:
        status = "loading"
    return {
        "status": status,
        "stable": stable,
        "sample_count": len(normalized),
        "latest": last,
        "previous": previous or {},
    }


def _wait_for_surface_stable(page: Any, *, attempts: int = 4, interval_ms: int = 400) -> dict[str, Any]:
    samples: list[dict[str, int]] = []
    for _ in range(max(1, attempts)):
        try:
            snapshot = page.evaluate(
                """() => ({
                    field_count: document.querySelectorAll('input,textarea,select').length,
                    button_count: document.querySelectorAll('button,[role="button"],.el-button').length,
                    title_count: document.querySelectorAll('h1,h2,h3,.el-breadcrumb__inner,.el-card__header,.el-page-header__title,.el-tabs__item').length,
                    loading_mask_count: document.querySelectorAll('.el-loading-mask, .loading, [aria-busy="true"]').length,
                })"""
            )
        except Exception:
            break
        if isinstance(snapshot, dict):
            samples.append(snapshot)
        stability = _compute_surface_stability(samples)
        if bool(stability.get("stable")):
            return stability
        try:
            page.wait_for_timeout(interval_ms)
        except Exception:
            break
    return _compute_surface_stability(samples)


def _collect_frame_surface(page: Any) -> dict[str, Any]:
    frames = getattr(page, "frames", None)
    if not callable(frames):
        return {"frames": [], "accessible_count": 0, "blocked_count": 0}

    items: list[dict[str, Any]] = []
    blocked_count = 0
    for frame in frames()[1:]:
        try:
            frame_url = str(frame.url or "").strip()
            snapshot = frame.evaluate(
                """() => ({
                    title: document.title || '',
                    field_placeholders: [...document.querySelectorAll('input,textarea,select')]
                        .map((el) => (el.getAttribute('placeholder') || '').trim())
                        .filter(Boolean)
                        .slice(0, 5),
                    button_texts: [...document.querySelectorAll('button,[role="button"],.el-button')]
                        .map((el) => (el.innerText || '').trim())
                        .filter(Boolean)
                        .slice(0, 5),
                    title_candidates: [...document.querySelectorAll('h1,h2,h3,.el-dialog__title,.el-card__header')]
                        .map((el) => (el.innerText || '').trim())
                        .filter(Boolean)
                        .slice(0, 5),
                    has_table: !!document.querySelector('.el-table'),
                    has_form: !!document.querySelector('.el-form, form'),
                })"""
            )
            if not isinstance(snapshot, dict):
                continue
            items.append(
                {
                    "url": frame_url,
                    "title": str(snapshot.get("title", "")).strip(),
                    "field_placeholders": [str(item).strip() for item in snapshot.get("field_placeholders", []) if str(item).strip()],
                    "button_texts": [str(item).strip() for item in snapshot.get("button_texts", []) if str(item).strip()],
                    "title_candidates": [str(item).strip() for item in snapshot.get("title_candidates", []) if str(item).strip()],
                    "has_table": bool(snapshot.get("has_table", False)),
                    "has_form": bool(snapshot.get("has_form", False)),
                }
            )
        except Exception:
            blocked_count += 1
            continue
    return {
        "frames": items,
        "accessible_count": len(items),
        "blocked_count": blocked_count,
    }


def _extract_page_surface(page_url: str) -> dict[str, Any]:
    _validate_page_surface_url(page_url)
    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright
    except Exception:
        return {}

    login_url = str(getattr(SETTINGS, "page_surface_login_url", "")).strip() or os.getenv("BASE_URL", "http://localhost:5173/login#/login")
    _validate_page_surface_url(login_url)
    username = os.getenv("TEST_USERNAME", "admin")
    password = os.getenv("TEST_PASSWORD", "macro123")

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            page.set_default_timeout(6000)
            login_network_idle_reached = False
            target_network_idle_reached = False
            login_attempted = False
            login_succeeded = False
            marker_selector = ""
            selector_wait_status = "not_started"
            page.goto(login_url, wait_until="domcontentloaded", timeout=60000)
            username_filled = False
            for locator in ["请输入用户名", "用户名", "账号", "请输入账号"]:
                try:
                    page.get_by_placeholder(locator).first.fill(username)
                    username_filled = True
                    break
                except Exception:
                    continue
            if not username_filled:
                page.locator("input").first.fill(username)

            password_filled = False
            for locator in ["请输入密码", "密码"]:
                try:
                    page.get_by_placeholder(locator).first.fill(password)
                    password_filled = True
                    break
                except Exception:
                    continue
            if not password_filled:
                page.locator("input[type='password']").first.fill(password)

            try:
                login_attempted = True
                page.get_by_role("button", name="登录").first.click()
            except Exception:
                login_attempted = True
                page.locator("button, .el-button").first.click()
            try:
                page.wait_for_load_state("networkidle", timeout=5000)
                login_network_idle_reached = True
            except Exception:
                login_network_idle_reached = False
            page.wait_for_timeout(1200)
            current_after_login = str(page.url or "").strip()
            login_succeeded = bool(current_after_login) and "#/login" not in current_after_login and "/login" not in current_after_login

            try:
                page.goto(page_url, wait_until="commit", timeout=20000)
            except PlaywrightTimeoutError:
                # Some hash pages keep long-polling requests that can block full load events.
                # Keep current document and continue surface extraction.
                pass
            try:
                page.wait_for_load_state("networkidle", timeout=5000)
                target_network_idle_reached = True
            except Exception:
                target_network_idle_reached = False
            stability = _wait_for_surface_stable(page, attempts=4, interval_ms=400)
            for selector in [".el-table", ".el-form", ".el-card", ".el-dialog__wrapper", "main", "[role='main']"]:
                try:
                    page.wait_for_selector(selector, state="attached", timeout=2500)
                    marker_selector = selector
                    selector_wait_status = "matched"
                    break
                except Exception:
                    continue
            if not marker_selector:
                selector_wait_status = "timeout"
            page.wait_for_timeout(1200)
            payload = page.evaluate(
                """() => {
                    const fields = [...document.querySelectorAll('input,textarea,select')].map((el) => ({
                        placeholder: el.getAttribute('placeholder') || '',
                        name: el.getAttribute('name') || '',
                        cls: el.className || '',
                    }));
                    const buttons = [...document.querySelectorAll('button,[role="button"],.el-button')].map((el) => ({
                        text: (el.innerText || '').trim(),
                        cls: el.className || '',
                    })).filter((item) => item.text);
                    const menuItems = [...document.querySelectorAll('[role="menuitem"],.el-menu-item')].map((el) => ({
                        text: (el.innerText || '').trim(),
                        cls: el.className || '',
                    })).filter((item) => item.text);
                    const titleCandidates = [...document.querySelectorAll('h1,h2,h3,.el-breadcrumb__inner,.el-card__header,.el-page-header__title,.el-tabs__item')]
                        .map((el) => (el.innerText || '').trim())
                        .filter(Boolean);
                    return {
                        url: location.href,
                        title: document.title,
                        fields,
                        buttons,
                        menuItems,
                        titleCandidates,
                        hasTable: !!document.querySelector('.el-table'),
                        hasForm: !!document.querySelector('.el-form, form'),
                        hasDialog: !!document.querySelector('.el-dialog, .el-dialog__wrapper, [role="dialog"]'),
                        dialogTitles: [...document.querySelectorAll('.el-dialog__title, [role="dialog"] [aria-label], [role="dialog"] h1, [role="dialog"] h2, [role="dialog"] h3')]
                            .map((el) => (el.innerText || el.getAttribute('aria-label') || '').trim())
                            .filter(Boolean)
                            .slice(0, 10),
                        iframeCount: document.querySelectorAll('iframe').length,
                        loadingMaskCount: document.querySelectorAll('.el-loading-mask, .loading, [aria-busy="true"]').length,
                        bodyTextLength: (document.body?.innerText || '').trim().length,
                    };
                }"""
            )
            frame_surface = _collect_frame_surface(page)
            browser.close()
    except Exception:
        return {}

    if not isinstance(payload, dict):
        return {}
    if not isinstance(frame_surface, dict):
        frame_surface = {"frames": [], "accessible_count": 0, "blocked_count": 0}

    final_url = str(payload.get("url", "")).strip()
    redirected_to_login = bool(final_url) and ("#/login" in final_url or "/login" in final_url)
    requested_route = _route_signature(page_url)
    final_route = _route_signature(final_url)
    route_mismatch = bool(requested_route and final_route and requested_route != final_route)
    surface_result = _build_surface_result_from_snapshot(
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
    element_candidates = _build_surface_element_candidates(_extract_page_from_url(page_url)[1], surface_result)
    surface_result["element_candidates"] = element_candidates
    surface_result["confidence_summary"] = _surface_confidence_summary(
        {
            **surface_result,
            "element_candidates": element_candidates,
        }
    )
    surface_result["confidence"] = surface_result["confidence_summary"]["confidence"]
    surface_result["requires_review"] = surface_result["confidence_summary"]["requires_review"]
    surface_result["warnings"] = _dedup_keep_order(surface_result["warnings"] + surface_result["confidence_summary"]["warnings"])

    return _normalize_page_surface(
        surface_result,
        page=_extract_page_from_url(page_url)[1],
        requested_url=page_url,
    )


def _enhance_page_object_from_surface(page: str, surface: dict[str, Any]) -> Path:
    page_object_path = _ensure_page_object(page)
    try:
        payload = yaml.safe_load(page_object_path.read_text(encoding="utf-8")) or {}
    except Exception:
        payload = {"page": page, "elements": {}}
    if not isinstance(payload, dict):
        payload = {"page": page, "elements": {}}
    payload["page"] = page
    elements = payload.get("elements")
    if not isinstance(elements, dict):
        elements = {}
    if "login_button" not in elements:
        elements["login_button"] = {"locator_type": "role", "role": "button", "locator_value": "登录"}

    for element_name, element_def in _surface_inferred_elements(page, surface).items():
        elements[element_name] = element_def

    payload["elements"] = elements
    page_object_path.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return page_object_path


def _build_requirement_steps(requirement: str, page: str, resolved_page_url: str, surface: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    steps: list[dict[str, Any]] = [
        {"action": "login"},
        {"action": "goto", "value": resolved_page_url},
        {"action": "assert_url", "value": resolved_page_url},
    ]
    coverage = {"status": "full", "missing": [], "notes": []}

    title_value = str(surface.get("page_title", "")).strip()
    requires_search = _requires_search_flow(requirement)

    if requires_search:
        search_placeholder = str(surface.get("search_placeholder", "")).strip()
        query_button = str(surface.get("query_button_text", "")).strip()
        if search_placeholder and query_button:
            search_value = _extract_requirement_search_value(requirement)
            steps.extend(
                [
                    {"action": "wait_for", "target": "search_input"},
                    {"action": "fill", "target": "search_input", "value": search_value},
                    {"action": "click", "target": "search_button"},
                ]
            )
            if surface.get("has_table"):
                steps.append({"action": "wait_for", "target": f"{page}_table"})
                steps.append({"action": "assert_visible", "target": f"{page}_table"})
            elif title_value:
                steps.append({"action": "wait_for", "target": f"{page}_list_title"})
                steps.append({"action": "assert_visible", "target": f"{page}_list_title"})
        else:
            coverage["status"] = "partial"
            coverage["missing"].append("search_input/search_button")
            coverage["notes"].append("Requirement asks for search/query but page surface did not provide stable search locators.")
            if surface.get("has_table"):
                steps.append({"action": "assert_visible", "target": f"{page}_table"})
    elif surface.get("has_table"):
        steps.append({"action": "wait_for", "target": f"{page}_table"})
        steps.append({"action": "assert_visible", "target": f"{page}_table"})
    elif title_value:
        steps.append({"action": "wait_for", "target": f"{page}_list_title"})
        steps.append({"action": "assert_visible", "target": f"{page}_list_title"})

    return steps, coverage


def _state_project_dir(project: str) -> Path:
    return TEST_POINTS_ROOT / project


def _state_case_file(project: str, case_id: str) -> Path:
    return _state_project_dir(project) / f"{case_id}.json"


def _state_case_versions_dir(project: str, case_id: str) -> Path:
    return _state_project_dir(project) / "versions" / case_id


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except Exception:
        return False


def _resolve_case_yaml_path(project: str, case_id: str) -> Path:
    state_path = _state_case_file(project, case_id)
    if state_path.exists():
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except Exception:
            state = {}
        source_ref = str((state or {}).get("source_ref", "")).strip()
        if source_ref:
            candidate = Path(source_ref).expanduser()
            if not candidate.is_absolute():
                candidate = REPO_ROOT / candidate
            candidate = candidate.resolve()
            if candidate.exists() and _is_within(candidate, ASSETS_CASES_ROOT):
                return candidate
    fallback = AI_CASES_ROOT / f"{case_id}.yaml"
    return fallback.resolve()


def _read_case_yaml(path: Path) -> tuple[dict[str, Any], str]:
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"case file not found: {path}")
    content = path.read_text(encoding="utf-8")
    try:
        payload = yaml.safe_load(content) or {}
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"invalid yaml: {exc}") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="yaml root must be an object")
    return payload, content


def _write_case_yaml(path: Path, payload: dict[str, Any]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = yaml.safe_dump(payload, allow_unicode=True, sort_keys=False)
    path.write_text(text, encoding="utf-8")
    return text


def _collect_case_items(project: str) -> list[dict[str, Any]]:
    project_dir = _state_project_dir(project)
    items: list[dict[str, Any]] = []
    if project_dir.exists():
        for file in sorted(project_dir.glob("*.json")):
            try:
                state = json.loads(file.read_text(encoding="utf-8")) or {}
            except Exception:
                state = {}
            case_id = str(state.get("asset_id", file.stem)).strip() or file.stem
            items.append(
                {
                    "case_id": case_id,
                    "title": str(state.get("title", case_id)).strip() or case_id,
                    "page": str(state.get("page", "product")).strip() or "product",
                    "priority": str(state.get("priority", "P1")).strip() or "P1",
                    "updated_at": str(state.get("updated_at", "")).strip(),
                    "path": str(_resolve_case_yaml_path(project, case_id)),
                }
            )

    known_ids = {item["case_id"] for item in items}
    for path in sorted(AI_CASES_ROOT.glob("*.yaml")):
        try:
            payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception:
            payload = {}
        case_id = str(payload.get("id", path.stem)).strip() or path.stem
        if case_id in known_ids:
            continue
        items.append(
            {
                "case_id": case_id,
                "title": str(payload.get("title", case_id)).strip() or case_id,
                "page": str((payload.get("execution") or {}).get("page", payload.get("module", "product"))).strip() or "product",
                "priority": str(payload.get("priority", "P1")).strip() or "P1",
                "updated_at": datetime.fromtimestamp(path.stat().st_mtime, tz=UTC).isoformat(),
                "path": str(path.resolve()),
            }
        )

    items.sort(key=lambda item: (str(item.get("updated_at", "")), str(item.get("case_id", ""))), reverse=True)
    return items


def _paginate_case_items(
    items: list[dict[str, Any]],
    *,
    page: int,
    page_size: int,
    focus_case_id: str = "",
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    total_items = len(items)
    total_pages = max(1, (total_items + page_size - 1) // page_size) if total_items else 1
    selected_page = page
    if focus_case_id:
        focus_index = next((index for index, item in enumerate(items) if str(item.get("case_id", "")) == focus_case_id), -1)
        if focus_index >= 0:
            selected_page = (focus_index // page_size) + 1
    selected_page = max(1, min(selected_page, total_pages))
    start = (selected_page - 1) * page_size
    end = start + page_size
    page_items = items[start:end]
    pagination = {
        "page": selected_page,
        "page_size": page_size,
        "total_items": total_items,
        "total_pages": total_pages,
        "has_prev": selected_page > 1,
        "has_next": selected_page < total_pages,
        "prev_page": selected_page - 1 if selected_page > 1 else None,
        "next_page": selected_page + 1 if selected_page < total_pages else None,
    }
    return page_items, pagination


def _infer_targets(page_name: str) -> tuple[str, str]:
    page_object_path = PAGE_OBJECTS_ROOT / f"{page_name}.page-object.yaml"
    menu_target = f"{page_name}_menu"
    assert_target = f"{page_name}_list_title"
    if not page_object_path.exists():
        return menu_target, assert_target

    try:
        payload = yaml.safe_load(page_object_path.read_text(encoding="utf-8")) or {}
    except Exception:
        return menu_target, assert_target
    elements = payload.get("elements", {})
    if not isinstance(elements, dict) or not elements:
        return menu_target, assert_target

    keys = list(elements.keys())
    for key in keys:
        if key.endswith("_menu") or "menu" in key:
            menu_target = key
            break
    for key in keys:
        if key.endswith("_list_title") or key.endswith("_table") or key.endswith("_list") or "title" in key:
            assert_target = key
            break
    return menu_target, assert_target


def _derive_points(case_yaml: dict[str, Any]) -> dict[str, Any]:
    execution = case_yaml.get("execution") or {}
    steps = execution.get("steps") or []
    if not isinstance(steps, list):
        steps = []
    point_types: list[str] = []
    point_keys: list[str] = []
    counts = {"precondition_count": 0, "navigation_count": 0, "input_count": 0, "assertion_count": 0, "action_count": 0}
    for index, step in enumerate(steps, start=1):
        action = str((step or {}).get("action", "")).strip()
        if action == "login":
            point_type = "precondition"
            counts["precondition_count"] += 1
        elif action in {"click", "goto"}:
            point_type = "navigation"
            counts["navigation_count"] += 1
        elif action in {"fill", "type"}:
            point_type = "input"
            counts["input_count"] += 1
        elif action in {"assert_visible", "assert_url", "wait_for"}:
            point_type = "assertion"
            counts["assertion_count"] += 1
        else:
            point_type = "action"
            counts["action_count"] += 1
        point_types.append(point_type)
        point_keys.append(f"{case_yaml.get('module', 'page')}-{index:02d}")
    return {
        "point_count": len(steps),
        "point_types": sorted(set(point_types)),
        "point_keys": point_keys,
        **counts,
    }


def _save_case_state(project: str, case_yaml: dict[str, Any], source_path: Path) -> dict[str, Any]:
    case_id = _safe_case_id(str(case_yaml.get("id", "")).strip())
    case_yaml["id"] = case_id
    state = {
        "asset_id": case_id,
        "version": 1,
        "updated_at": _now_iso(),
        "title": str(case_yaml.get("title", "")).strip() or case_id,
        "page": str((case_yaml.get("execution") or {}).get("page", case_yaml.get("module", "product"))).strip() or "product",
        "requirement": case_yaml.get("requirement") if isinstance(case_yaml.get("requirement"), list) else [],
        "priority": str(case_yaml.get("priority", "P1")).strip() or "P1",
        "source_type": "yaml_case",
        "source_name": case_id,
        "source_ref": str(source_path.resolve()),
        "references": [
            {
                "kind": "case_yaml",
                "path": str(source_path.resolve()),
                "case_id": case_id,
            }
        ],
    }
    state.update(_derive_points(case_yaml))

    state_file = _state_case_file(project, case_id)
    state_file.parent.mkdir(parents=True, exist_ok=True)
    if state_file.exists():
        try:
            previous = json.loads(state_file.read_text(encoding="utf-8")) or {}
        except Exception:
            previous = {}
        if isinstance(previous, dict):
            prev_version = int(previous.get("version", 1) or 1)
            state["version"] = prev_version + 1

    state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    versions_dir = _state_case_versions_dir(project, case_id)
    versions_dir.mkdir(parents=True, exist_ok=True)
    seq = len(list(versions_dir.glob("*.json"))) + 1
    version_file = versions_dir / f"{seq:04d}.json"
    version_file.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return state


def _parse_analysis_file(path: Path) -> dict[str, Any]:
    parsed: dict[str, Any] = {
        "summary": "",
        "failure_category": "",
        "failure_source": "",
        "failure_source_reason": "",
        "failure_source_confidence": "",
        "likely_cause": "",
        "risk_level": "",
        "recommended_action": "",
        "requires_manual_review": False,
        "confidence": "",
        "source_evidence": [],
        "source_file": str(path),
    }
    key_map = {
        "Summary": "summary",
        "Failure Category": "failure_category",
        "Failure Source": "failure_source",
        "Failure Source Reason": "failure_source_reason",
        "Failure Source Confidence": "failure_source_confidence",
        "Likely Cause": "likely_cause",
        "Risk Level": "risk_level",
        "Recommended Action": "recommended_action",
        "Requires Manual Review": "requires_manual_review",
        "Confidence": "confidence",
        "Source Evidence": "source_evidence",
    }
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return parsed
    for raw_line in text.splitlines():
        if ": " not in raw_line:
            continue
        prefix, value = raw_line.split(": ", 1)
        target = key_map.get(prefix.strip())
        if target:
            if target == "requires_manual_review":
                parsed[target] = value.strip().lower() in {"1", "true", "yes", "on", "y", "是"}
            elif target == "source_evidence":
                try:
                    loaded = json.loads(value.strip())
                except Exception:
                    loaded = []
                parsed[target] = loaded if isinstance(loaded, list) else []
            else:
                parsed[target] = value.strip()

    # 兼容 runner 在 analysis.txt 尾部附带完整 JSON 的格式，优先用于补齐来源字段。
    json_start = text.find("{")
    json_end = text.rfind("}")
    if json_start >= 0 and json_end > json_start:
        candidate = text[json_start : json_end + 1]
        try:
            payload = json.loads(candidate)
        except Exception:
            payload = {}
        if isinstance(payload, dict):
            for field in (
                "summary",
                "failure_category",
                "failure_source",
                "failure_source_reason",
                "failure_source_confidence",
                "likely_cause",
                "risk_level",
                "recommended_action",
                "confidence",
            ):
                if not str(parsed.get(field, "")).strip():
                    parsed[field] = payload.get(field, parsed.get(field, ""))
            if not parsed.get("requires_manual_review", False):
                parsed["requires_manual_review"] = bool(payload.get("requires_manual_review", False))
            if not isinstance(parsed.get("source_evidence"), list) or not parsed.get("source_evidence"):
                source_evidence = payload.get("source_evidence")
                if isinstance(source_evidence, list):
                    parsed["source_evidence"] = source_evidence
    return parsed


def _normalize_failure_analysis_view(analysis: dict[str, Any] | None) -> dict[str, Any]:
    source = analysis if isinstance(analysis, dict) else {}
    failure_source = str(source.get("failure_source", "")).strip().lower()
    failure_source_reason = str(source.get("failure_source_reason", "")).strip()
    risk_level = str(source.get("risk_level", "")).strip().lower()
    recommended_action = str(source.get("recommended_action", "")).strip()
    try:
        source_confidence = float(source.get("failure_source_confidence", source.get("confidence", 0)) or 0)
    except (TypeError, ValueError):
        source_confidence = 0.0
    source_confidence = max(0.0, min(1.0, source_confidence))
    try:
        confidence = float(source.get("confidence", 0) or 0)
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = max(0.0, min(1.0, confidence))
    requires_manual_review = bool(
        source.get("requires_manual_review", False)
        or failure_source in {"", "unknown"}
        or source_confidence < 0.7
        or confidence < 0.65
    )
    return {
        "summary": str(source.get("summary", "")).strip(),
        "failure_category": str(source.get("failure_category", "")).strip().lower(),
        "failure_source": failure_source or "unknown",
        "failure_source_reason": failure_source_reason or "Failure source reason not available.",
        "failure_source_confidence": source_confidence,
        "likely_cause": str(source.get("likely_cause", "")).strip(),
        "risk_level": risk_level,
        "recommended_action": recommended_action,
        "confidence": confidence if confidence else source.get("confidence", ""),
        "requires_manual_review": requires_manual_review,
        "evidence_used": source.get("evidence_used", []) if isinstance(source.get("evidence_used"), list) else [],
        "source_evidence": source.get("source_evidence", []) if isinstance(source.get("source_evidence"), list) else [],
        "source_file": str(source.get("source_file", "")).strip(),
    }


def _normalize_failure_entry_view(entry: dict[str, Any] | None) -> dict[str, Any]:
    source = entry if isinstance(entry, dict) else {}
    normalized = dict(source)
    normalized["analysis"] = _normalize_failure_analysis_view(source.get("analysis") if isinstance(source.get("analysis"), dict) else {})
    return normalized


def _build_run_failure_source_summary(failures: list[dict[str, Any]]) -> dict[str, Any]:
    source_counts: dict[str, int] = {}
    total = 0
    manual_review_count = 0
    low_confidence_count = 0
    confidence_sum = 0.0
    confidence_count = 0

    for item in failures:
        if not isinstance(item, dict):
            continue
        analysis = item.get("analysis") if isinstance(item.get("analysis"), dict) else {}
        source = str(analysis.get("failure_source", "")).strip().lower() or "unknown"
        source_counts[source] = int(source_counts.get(source, 0) or 0) + 1
        total += 1

        if bool(analysis.get("requires_manual_review", False)):
            manual_review_count += 1

        confidence = _clamp_confidence(
            analysis.get(
                "failure_source_confidence",
                analysis.get("confidence", 0),
            )
        )
        confidence_sum += confidence
        confidence_count += 1
        if confidence < 0.7:
            low_confidence_count += 1

    top_source = ""
    top_source_count = 0
    if source_counts:
        top_source = max(
            source_counts,
            key=lambda key: (
                int(source_counts.get(key, 0) or 0),
                key,
            ),
        )
        top_source_count = int(source_counts.get(top_source, 0) or 0)

    avg_confidence = round(confidence_sum / confidence_count, 3) if confidence_count > 0 else 0.0
    return {
        "version": "FailureSourceSummaryV1",
        "total_failures": total,
        "source_counts": dict(sorted(source_counts.items())),
        "top_source": top_source or "unknown",
        "top_source_count": top_source_count,
        "requires_manual_review_count": manual_review_count,
        "low_confidence_count": low_confidence_count,
        "average_failure_source_confidence": avg_confidence,
    }


def _resolve_run_failure_snapshot(run_id: str) -> dict[str, Any]:
    normalized_run_id = str(run_id or "").strip()
    if not normalized_run_id:
        return {}
    run_item = _find_run_item(normalized_run_id)
    if not isinstance(run_item, dict):
        return {}
    latest_failure = run_item.get("latest_failure") if isinstance(run_item.get("latest_failure"), dict) else {}
    if latest_failure:
        return _normalize_failure_entry_view(latest_failure)
    artifacts_dir = Path(str(run_item.get("artifacts_dir", "")).strip())
    if artifacts_dir.exists():
        failures = [_normalize_failure_entry_view(item) for item in _collect_failure_entries() if _is_within(Path(item.get("artifact_dir", "")), artifacts_dir)]
        if failures:
            return failures[0]
    return {}


def _resolve_run_governance_snapshot(run_id: str) -> dict[str, Any]:
    normalized_run_id = str(run_id or "").strip()
    if not normalized_run_id:
        return {}
    run_item = _find_run_item(normalized_run_id)
    if not isinstance(run_item, dict):
        return {}
    risk_summary = run_item.get("risk_summary") if isinstance(run_item.get("risk_summary"), dict) else _build_risk_report_summary(
        run_item.get("risk_report") if isinstance(run_item.get("risk_report"), dict) else {}
    )
    self_healing_summary = (
        run_item.get("self_healing_summary")
        if isinstance(run_item.get("self_healing_summary"), dict)
        else _build_self_healing_summary(
            execution_record=run_item.get("execution_record") if isinstance(run_item.get("execution_record"), dict) else {},
            artifacts_dir=str(run_item.get("artifacts_dir", "")).strip(),
        )
    )
    page_semantic_summary = (
        run_item.get("page_semantic_summary")
        if isinstance(run_item.get("page_semantic_summary"), dict)
        else _build_page_semantic_summary(
            run_item.get("page_semantic") if isinstance(run_item.get("page_semantic"), dict) else {},
        )
    )
    return {
        "risk_summary": risk_summary if isinstance(risk_summary, dict) else {},
        "self_healing_summary": self_healing_summary if isinstance(self_healing_summary, dict) else {},
        "page_semantic_summary": page_semantic_summary if isinstance(page_semantic_summary, dict) else {},
    }


def _resolve_manifest_entries(entries: Any, *, root: Path) -> list[Path]:
    if not isinstance(entries, list):
        return []
    resolved: list[Path] = []
    for item in entries:
        raw_text = str(item).strip()
        if not raw_text:
            continue
        candidate = Path(raw_text)
        if not candidate.is_absolute():
            candidate = root / candidate
        if candidate.exists() and candidate.is_file():
            resolved.append(candidate.resolve())
    return resolved


def _load_execution_record_payload(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}
    return _normalize_execution_record_payload(payload)


def _collect_failure_entries_with_meta() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    consumed_analysis_paths: set[Path] = set()
    compat_used_count = 0
    compat_disabled_skipped = 0
    invalid_manifest_count = 0
    missing_manifest_count = 0
    compat_scan_enabled = bool(getattr(SETTINGS, "evidence_manifest_compat_scan_enabled", True))
    for artifact_root in [RUNNER_ROOT / "artifacts"] + sorted(WEB_UI_RUNS_DIR.glob("*-artifacts")):
        if not artifact_root.exists():
            continue
        for manifest_path in sorted(artifact_root.rglob("evidence_manifest.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                raw_manifest = json.loads(manifest_path.read_text(encoding="utf-8")) or {}
            except Exception:
                LOGGER.warning("invalid evidence_manifest.json at %s; keep compatibility scan path", manifest_path)
                invalid_manifest_count += 1
                continue
            manifest = _normalize_evidence_manifest_payload(raw_manifest)
            manifest_root = manifest_path.parent
            analysis_paths = _resolve_manifest_entries(manifest.get("analysis_files"), root=manifest_root)
            if not analysis_paths:
                continue
            suggestion_paths = _resolve_manifest_entries(manifest.get("suggestion_files"), root=manifest_root)
            record_paths = _resolve_manifest_entries(manifest.get("execution_record_files"), root=manifest_root)
            for index, analysis_path in enumerate(analysis_paths):
                resolved_analysis_path = analysis_path.resolve()
                if resolved_analysis_path in consumed_analysis_paths:
                    continue
                consumed_analysis_paths.add(resolved_analysis_path)
                case_dir = analysis_path.parent
                suggestion_path = suggestion_paths[index] if index < len(suggestion_paths) else (suggestion_paths[0] if suggestion_paths else case_dir / "suggestion.json")
                execution_record_path = record_paths[index] if index < len(record_paths) else (record_paths[0] if record_paths else case_dir / "execution_record.json")
                execution_record = _load_execution_record_payload(execution_record_path)
                case_id = str(execution_record.get("case_id", case_dir.name)).strip() or case_dir.name
                case_title = str(execution_record.get("case_title", case_id)).strip() or case_id
                finished_at = str(execution_record.get("finished_at", "")).strip() or datetime.fromtimestamp(analysis_path.stat().st_mtime, tz=UTC).isoformat()
                screenshot_path = case_dir / "failed.png"
                html_path = case_dir / "page.html"
                meta_path = case_dir / "meta.txt"
                video_candidates = list(case_dir.glob("*.webm"))
                video_path = max(video_candidates, key=lambda p: p.stat().st_mtime) if video_candidates else None
                analysis = _parse_analysis_file(analysis_path)
                suggestion_payload: dict[str, Any] = {}
                if suggestion_path.exists():
                    try:
                        suggestion_payload = json.loads(suggestion_path.read_text(encoding="utf-8")) or {}
                    except Exception:
                        suggestion_payload = {}
                entries.append(
                    {
                        "case_id": case_id,
                        "case_title": case_title,
                        "finished_at": finished_at,
                        "analysis": analysis,
                        "suggestion": suggestion_payload,
                        "artifact_dir": str(case_dir.resolve()),
                        "analysis_path": str(analysis_path.resolve()),
                        "suggestion_path": str(suggestion_path.resolve()) if suggestion_path.exists() else "",
                        "screenshot_path": str(screenshot_path.resolve()) if screenshot_path.exists() else "",
                        "html_path": str(html_path.resolve()) if html_path.exists() else "",
                        "meta_path": str(meta_path.resolve()) if meta_path.exists() else "",
                        "video_path": str(video_path.resolve()) if video_path else "",
                        "evidence_source": "manifest",
                        "manifest_path": str(manifest_path.resolve()),
                    }
                )
        for analysis_path in sorted(artifact_root.rglob("analysis.txt"), key=lambda p: p.stat().st_mtime, reverse=True):
            resolved_analysis_path = analysis_path.resolve()
            if resolved_analysis_path in consumed_analysis_paths:
                continue
            missing_manifest_count += 1
            if not compat_scan_enabled:
                compat_disabled_skipped += 1
                LOGGER.warning(
                    "evidence_manifest missing for %s; compatibility scan disabled, entry skipped",
                    analysis_path.parent,
                )
                continue
            consumed_analysis_paths.add(resolved_analysis_path)
            LOGGER.warning("evidence_manifest missing for %s; using compatibility scan fallback", analysis_path.parent)
            compat_used_count += 1
            case_dir = analysis_path.parent
            execution_record_path = case_dir / "execution_record.json"
            suggestion_path = case_dir / "suggestion.json"
            screenshot_path = case_dir / "failed.png"
            html_path = case_dir / "page.html"
            meta_path = case_dir / "meta.txt"
            video_path = None
            video_candidates = list(case_dir.glob("*.webm"))
            if video_candidates:
                video_path = max(video_candidates, key=lambda p: p.stat().st_mtime)
            case_id = case_dir.name
            if execution_record_path.exists():
                execution_record = _load_execution_record_payload(execution_record_path)
                case_id = str(execution_record.get("case_id", case_id)).strip() or case_id
                case_title = str(execution_record.get("case_title", case_id)).strip() or case_id
                finished_at = str(execution_record.get("finished_at", "")).strip()
            else:
                case_title = case_id
                finished_at = datetime.fromtimestamp(analysis_path.stat().st_mtime, tz=UTC).isoformat()

            analysis = _parse_analysis_file(analysis_path)
            suggestion_payload: dict[str, Any] = {}
            if suggestion_path.exists():
                try:
                    suggestion_payload = json.loads(suggestion_path.read_text(encoding="utf-8")) or {}
                except Exception:
                    suggestion_payload = {}
            entries.append(
                {
                    "case_id": case_id,
                    "case_title": case_title,
                    "finished_at": finished_at,
                    "analysis": analysis,
                    "suggestion": suggestion_payload,
                    "artifact_dir": str(case_dir.resolve()),
                    "analysis_path": str(analysis_path.resolve()),
                    "suggestion_path": str(suggestion_path.resolve()) if suggestion_path.exists() else "",
                    "screenshot_path": str(screenshot_path.resolve()) if screenshot_path.exists() else "",
                    "html_path": str(html_path.resolve()) if html_path.exists() else "",
                    "meta_path": str(meta_path.resolve()) if meta_path.exists() else "",
                    "video_path": str(video_path.resolve()) if video_path else "",
                    "evidence_source": "compat_scan",
                    "manifest_path": "",
                }
            )
    entries.sort(key=lambda item: item.get("finished_at", ""), reverse=True)
    trimmed = entries[:200]
    manifest_count = sum(1 for item in trimmed if str(item.get("evidence_source", "")).strip().lower() == "manifest")
    compat_count = sum(1 for item in trimmed if str(item.get("evidence_source", "")).strip().lower() == "compat_scan")
    warnings: list[str] = []
    if invalid_manifest_count > 0:
        warnings.append(f"检测到 {invalid_manifest_count} 个无效 evidence_manifest.json，已跳过。")
    if compat_count > 0:
        warnings.append(f"检测到 {compat_count} 条证据通过兼容扫描回退读取，建议补齐 evidence_manifest。")
    if compat_disabled_skipped > 0:
        warnings.append(f"兼容扫描已禁用，跳过 {compat_disabled_skipped} 条缺少 manifest 的证据。")

    total_visible_entries = manifest_count + compat_count
    manifest_first_ratio = round((manifest_count / total_visible_entries), 3) if total_visible_entries else 1.0
    fallback_ratio = round((compat_count / total_visible_entries), 3) if total_visible_entries else 0.0
    policy_mode = "compat" if compat_scan_enabled else "strict"
    if compat_count > 0:
        health = "degraded"
    elif compat_disabled_skipped > 0 or invalid_manifest_count > 0:
        health = "warning"
    else:
        health = "healthy"

    meta = {
        "compat_scan_enabled": compat_scan_enabled,
        "policy_mode": policy_mode,
        "health": health,
        "manifest_entry_count": manifest_count,
        "compat_scan_entry_count": compat_count,
        "compat_scan_used_count": compat_used_count,
        "compat_scan_skipped_count": compat_disabled_skipped,
        "invalid_manifest_count": invalid_manifest_count,
        "missing_manifest_count": missing_manifest_count,
        "total_visible_entries": total_visible_entries,
        "manifest_first_ratio": manifest_first_ratio,
        "fallback_ratio": fallback_ratio,
        "warnings": warnings,
    }
    return trimmed, meta


def _collect_failure_entries() -> list[dict[str, Any]]:
    entries, _meta = _collect_failure_entries_with_meta()
    return entries


def _normalize_failure_evidence_meta(meta: dict[str, Any] | None) -> dict[str, Any]:
    source = meta if isinstance(meta, dict) else {}
    compat_scan_enabled = bool(source.get("compat_scan_enabled", True))
    manifest_entry_count = int(source.get("manifest_entry_count", 0) or 0)
    compat_scan_entry_count = int(source.get("compat_scan_entry_count", 0) or 0)
    compat_scan_used_count = int(source.get("compat_scan_used_count", compat_scan_entry_count) or 0)
    compat_scan_skipped_count = int(source.get("compat_scan_skipped_count", 0) or 0)
    invalid_manifest_count = int(source.get("invalid_manifest_count", 0) or 0)
    missing_manifest_count = int(source.get("missing_manifest_count", 0) or 0)
    total_visible_entries = int(source.get("total_visible_entries", manifest_entry_count + compat_scan_entry_count) or 0)
    manifest_first_ratio = source.get("manifest_first_ratio")
    if manifest_first_ratio is None:
        manifest_first_ratio = round((manifest_entry_count / total_visible_entries), 3) if total_visible_entries else 1.0
    fallback_ratio = source.get("fallback_ratio")
    if fallback_ratio is None:
        fallback_ratio = round((compat_scan_entry_count / total_visible_entries), 3) if total_visible_entries else 0.0
    policy_mode = str(source.get("policy_mode", "compat" if compat_scan_enabled else "strict")).strip() or (
        "compat" if compat_scan_enabled else "strict"
    )
    health = str(source.get("health", "")).strip().lower()
    if not health:
        if compat_scan_entry_count > 0:
            health = "degraded"
        elif compat_scan_skipped_count > 0 or invalid_manifest_count > 0:
            health = "warning"
        else:
            health = "healthy"
    warnings_raw = source.get("warnings")
    warnings = [str(item).strip() for item in warnings_raw] if isinstance(warnings_raw, list) else []
    warnings = [item for item in warnings if item]
    return {
        **source,
        "compat_scan_enabled": compat_scan_enabled,
        "policy_mode": policy_mode,
        "health": health,
        "manifest_entry_count": manifest_entry_count,
        "compat_scan_entry_count": compat_scan_entry_count,
        "compat_scan_used_count": compat_scan_used_count,
        "compat_scan_skipped_count": compat_scan_skipped_count,
        "invalid_manifest_count": invalid_manifest_count,
        "missing_manifest_count": missing_manifest_count,
        "total_visible_entries": total_visible_entries,
        "manifest_first_ratio": float(manifest_first_ratio),
        "fallback_ratio": float(fallback_ratio),
        "warnings": warnings,
    }


def _normalize_execution_meta(meta: dict[str, Any] | None) -> dict[str, Any]:
    source = meta if isinstance(meta, dict) else {}
    compat_scan_enabled = bool(source.get("compat_scan_enabled", True))
    manifest_record_count = int(source.get("manifest_record_count", 0) or 0)
    compat_scan_record_count = int(source.get("compat_scan_record_count", 0) or 0)
    runtime_realtime_count = int(source.get("runtime_realtime_count", 0) or 0)
    runtime_fallback_count = int(source.get("runtime_fallback_count", 0) or 0)
    compat_scan_used_count = int(source.get("compat_scan_used_count", compat_scan_record_count) or 0)
    compat_scan_skipped_count = int(source.get("compat_scan_skipped_count", 0) or 0)
    invalid_manifest_count = int(source.get("invalid_manifest_count", 0) or 0)
    invalid_execution_record_count = int(source.get("invalid_execution_record_count", 0) or 0)
    missing_manifest_count = int(source.get("missing_manifest_count", 0) or 0)
    runtime_fallback_used = bool(source.get("runtime_fallback_used", False))
    total_visible_records = int(
        source.get(
            "total_visible_records",
            manifest_record_count + compat_scan_record_count + runtime_realtime_count + runtime_fallback_count,
        )
        or 0
    )
    manifest_first_ratio = source.get("manifest_first_ratio")
    if manifest_first_ratio is None:
        manifest_first_ratio = round((manifest_record_count / max(1, (manifest_record_count + compat_scan_record_count))), 3)
    fallback_ratio = source.get("fallback_ratio")
    if fallback_ratio is None:
        fallback_ratio = round((compat_scan_record_count / max(1, (manifest_record_count + compat_scan_record_count))), 3)
    policy_mode = str(source.get("policy_mode", "compat" if compat_scan_enabled else "strict")).strip() or (
        "compat" if compat_scan_enabled else "strict"
    )
    health = str(source.get("health", "")).strip().lower()
    if not health:
        if runtime_fallback_used or runtime_fallback_count > 0:
            health = "critical"
        elif compat_scan_record_count > 0:
            health = "degraded"
        elif compat_scan_skipped_count > 0 or invalid_manifest_count > 0 or invalid_execution_record_count > 0:
            health = "warning"
        else:
            health = "healthy"
    warnings_raw = source.get("warnings")
    warnings = [str(item).strip() for item in warnings_raw] if isinstance(warnings_raw, list) else []
    warnings = [item for item in warnings if item]
    return {
        **source,
        "compat_scan_enabled": compat_scan_enabled,
        "policy_mode": policy_mode,
        "health": health,
        "manifest_record_count": manifest_record_count,
        "compat_scan_record_count": compat_scan_record_count,
        "runtime_realtime_count": runtime_realtime_count,
        "runtime_fallback_count": runtime_fallback_count,
        "compat_scan_used_count": compat_scan_used_count,
        "compat_scan_skipped_count": compat_scan_skipped_count,
        "invalid_manifest_count": invalid_manifest_count,
        "invalid_execution_record_count": invalid_execution_record_count,
        "missing_manifest_count": missing_manifest_count,
        "runtime_fallback_used": runtime_fallback_used,
        "total_visible_records": total_visible_records,
        "manifest_first_ratio": float(manifest_first_ratio),
        "fallback_ratio": float(fallback_ratio),
        "warnings": warnings,
    }


def _execution_record_time_value(record: dict[str, Any]) -> str:
    return (
        str(record.get("finished_at", "")).strip()
        or str(record.get("started_at", "")).strip()
        or str(record.get("created_at", "")).strip()
    )


def _collect_execution_records_with_meta(*, limit: int = 1000) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    items: list[dict[str, Any]] = []
    consumed_record_paths: set[Path] = set()
    compat_used_count = 0
    compat_disabled_skipped = 0
    invalid_manifest_count = 0
    invalid_record_count = 0
    missing_manifest_count = 0
    compat_scan_enabled = bool(getattr(SETTINGS, "evidence_manifest_compat_scan_enabled", True))
    artifact_roots = [RUNNER_ROOT / "artifacts"] + sorted(WEB_UI_RUNS_DIR.glob("*-artifacts"))
    for artifact_root in artifact_roots:
        if not artifact_root.exists():
            continue
        for manifest_path in sorted(artifact_root.rglob("evidence_manifest.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                raw_manifest = json.loads(manifest_path.read_text(encoding="utf-8")) or {}
            except Exception:
                invalid_manifest_count += 1
                LOGGER.warning("invalid evidence_manifest.json at %s while collecting execution records", manifest_path)
                continue
            manifest = _normalize_evidence_manifest_payload(raw_manifest)
            manifest_root = manifest_path.parent
            record_paths = _resolve_manifest_entries(manifest.get("execution_record_files"), root=manifest_root)
            if not record_paths:
                continue
            for record_path in record_paths:
                resolved_record_path = record_path.resolve()
                if resolved_record_path in consumed_record_paths:
                    continue
                consumed_record_paths.add(resolved_record_path)
                execution_record = _load_execution_record_payload(record_path)
                if not execution_record:
                    invalid_record_count += 1
                    continue
                finished_at = _execution_record_time_value(execution_record)
                if not finished_at:
                    finished_at = datetime.fromtimestamp(record_path.stat().st_mtime, tz=UTC).isoformat()
                items.append(
                    {
                        "run_id": str(execution_record.get("run_id", "")).strip(),
                        "case_id": str(execution_record.get("case_id", "")).strip(),
                        "status": str(execution_record.get("status", "queued")).strip() or "queued",
                        "finished_at": finished_at,
                        "execution_record": execution_record,
                        "execution_record_path": str(record_path.resolve()),
                        "manifest_path": str(manifest_path.resolve()),
                        "source": "manifest",
                    }
                )
        for record_path in sorted(artifact_root.rglob("execution_record.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            resolved_record_path = record_path.resolve()
            if resolved_record_path in consumed_record_paths:
                continue
            missing_manifest_count += 1
            if not compat_scan_enabled:
                compat_disabled_skipped += 1
                LOGGER.warning(
                    "execution_record missing manifest linkage for %s; compatibility scan disabled, record skipped",
                    record_path,
                )
                continue
            compat_used_count += 1
            consumed_record_paths.add(resolved_record_path)
            execution_record = _load_execution_record_payload(record_path)
            if not execution_record:
                invalid_record_count += 1
                continue
            finished_at = _execution_record_time_value(execution_record)
            if not finished_at:
                finished_at = datetime.fromtimestamp(record_path.stat().st_mtime, tz=UTC).isoformat()
            items.append(
                {
                    "run_id": str(execution_record.get("run_id", "")).strip(),
                    "case_id": str(execution_record.get("case_id", "")).strip(),
                    "status": str(execution_record.get("status", "queued")).strip() or "queued",
                    "finished_at": finished_at,
                    "execution_record": execution_record,
                    "execution_record_path": str(record_path.resolve()),
                    "manifest_path": "",
                    "source": "compat_scan",
                }
            )

    items.sort(key=lambda item: str(item.get("finished_at", "")), reverse=True)
    deduped: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for item in items:
        execution_record = item.get("execution_record") if isinstance(item.get("execution_record"), dict) else {}
        run_id = str(item.get("run_id", "")).strip() or str(execution_record.get("run_id", "")).strip()
        dedupe_key = run_id or str(item.get("execution_record_path", "")).strip()
        if not dedupe_key or dedupe_key in seen_ids:
            continue
        seen_ids.add(dedupe_key)
        deduped.append(item)
        if len(deduped) >= limit:
            break

    # runtime session实时补充：仅补充缺少落盘 execution_record 的 active 任务
    active_statuses = {"queued", "running", "pending"}
    runtime_items: list[dict[str, Any]] = []
    with _RUN_LOCK:
        runtime_items.extend([dict(item) for item in _RUN_JOBS.values()])
    runtime_items.extend(_read_json_list(RUNTIME_RUNS_FILE))
    for runtime_item in runtime_items:
        run_view = _runtime_view_from_entry(runtime_item)
        execution_record = run_view.get("execution_record")
        if not isinstance(execution_record, dict):
            continue
        status_value = str(execution_record.get("status", "")).strip().lower()
        run_id = str(execution_record.get("run_id", "")).strip()
        if status_value not in active_statuses:
            continue
        if run_id and run_id in seen_ids:
            continue
        finished_at = _execution_record_time_value(execution_record)
        dedupe_key = run_id or f"runtime:{run_view.get('case_id', '')}:{run_view.get('started_at', '')}"
        if dedupe_key in seen_ids:
            continue
        seen_ids.add(dedupe_key)
        deduped.append(
            {
                "run_id": run_id,
                "case_id": str(execution_record.get("case_id", "")).strip(),
                "status": str(execution_record.get("status", "queued")).strip() or "queued",
                "finished_at": finished_at,
                "execution_record": _normalize_execution_record_payload(
                    {
                        **execution_record,
                        "metadata": {
                            **(
                                execution_record.get("metadata", {})
                                if isinstance(execution_record.get("metadata"), dict)
                                else {}
                            ),
                            "runtime_realtime_supplement": True,
                        },
                    }
                ),
                "execution_record_path": "",
                "manifest_path": "",
                "source": "runtime_realtime",
            }
        )

    deduped.sort(
        key=lambda item: (
            str(item.get("finished_at", "")),
            str((item.get("execution_record") or {}).get("started_at", "")),
        ),
        reverse=True,
    )

    # 兼容：若 execution_record 为空，回退 runtime-runs 全量读取，避免历史数据直接消失。
    runtime_fallback_used = False
    if not deduped:
        runtime_fallback_used = True
        for runtime_item in _read_json_list(RUNTIME_RUNS_FILE):
            run_view = _runtime_view_from_entry(runtime_item)
            execution_record = run_view.get("execution_record")
            if not isinstance(execution_record, dict):
                continue
            deduped.append(
                {
                    "run_id": str(execution_record.get("run_id", "")).strip(),
                    "case_id": str(execution_record.get("case_id", "")).strip(),
                    "status": str(execution_record.get("status", "queued")).strip() or "queued",
                    "finished_at": _execution_record_time_value(execution_record),
                    "execution_record": execution_record,
                    "execution_record_path": "",
                    "manifest_path": "",
                    "source": "runtime_fallback",
                }
            )
        deduped.sort(
            key=lambda item: (
                str(item.get("finished_at", "")),
                str((item.get("execution_record") or {}).get("started_at", "")),
            ),
            reverse=True,
        )

    trimmed = deduped[:limit]
    source_counts: dict[str, int] = defaultdict(int)
    for item in trimmed:
        source_counts[str(item.get("source", "unknown")).strip() or "unknown"] += 1

    warnings: list[str] = []
    if invalid_manifest_count > 0:
        warnings.append(f"检测到 {invalid_manifest_count} 个无效 evidence_manifest.json，已跳过。")
    if invalid_record_count > 0:
        warnings.append(f"检测到 {invalid_record_count} 个无效 execution_record.json，已跳过。")
    if int(source_counts.get("compat_scan", 0)) > 0:
        warnings.append(
            f"检测到 {int(source_counts.get('compat_scan', 0))} 条 execution_record 通过兼容扫描回退读取，建议 runner 全量输出 manifest。"
        )
    if compat_disabled_skipped > 0:
        warnings.append(f"兼容扫描已禁用，跳过 {compat_disabled_skipped} 条未绑定 manifest 的 execution_record。")
    if runtime_fallback_used:
        warnings.append("未发现可用 execution_record 落盘记录，当前报告临时回退 runtime-runs.json。")

    manifest_record_count = int(source_counts.get("manifest", 0))
    compat_scan_record_count = int(source_counts.get("compat_scan", 0))
    runtime_realtime_count = int(source_counts.get("runtime_realtime", 0))
    runtime_fallback_count = int(source_counts.get("runtime_fallback", 0))
    total_visible_records = manifest_record_count + compat_scan_record_count + runtime_realtime_count + runtime_fallback_count
    manifest_first_ratio = round((manifest_record_count / max(1, (manifest_record_count + compat_scan_record_count))), 3)
    fallback_ratio = round((compat_scan_record_count / max(1, (manifest_record_count + compat_scan_record_count))), 3)
    policy_mode = "compat" if compat_scan_enabled else "strict"
    if runtime_fallback_used or runtime_fallback_count > 0:
        health = "critical"
    elif compat_scan_record_count > 0:
        health = "degraded"
    elif compat_disabled_skipped > 0 or invalid_manifest_count > 0 or invalid_record_count > 0:
        health = "warning"
    else:
        health = "healthy"

    meta = {
        "compat_scan_enabled": compat_scan_enabled,
        "policy_mode": policy_mode,
        "health": health,
        "manifest_record_count": manifest_record_count,
        "compat_scan_record_count": compat_scan_record_count,
        "runtime_realtime_count": runtime_realtime_count,
        "runtime_fallback_count": runtime_fallback_count,
        "compat_scan_used_count": compat_used_count,
        "compat_scan_skipped_count": compat_disabled_skipped,
        "invalid_manifest_count": invalid_manifest_count,
        "invalid_execution_record_count": invalid_record_count,
        "missing_manifest_count": missing_manifest_count,
        "runtime_fallback_used": runtime_fallback_used,
        "total_visible_records": total_visible_records,
        "manifest_first_ratio": manifest_first_ratio,
        "fallback_ratio": fallback_ratio,
        "warnings": warnings,
    }
    return trimmed, meta


def _build_execution_task_view(entry: dict[str, Any]) -> dict[str, Any]:
    source = entry if isinstance(entry, dict) else {}
    execution_record = _normalize_execution_record_payload(
        source.get("execution_record") if isinstance(source.get("execution_record"), dict) else {}
    )
    step_summary = execution_record.get("step_summary") if isinstance(execution_record.get("step_summary"), dict) else {}
    metadata = execution_record.get("metadata") if isinstance(execution_record.get("metadata"), dict) else {}
    embedded_execution_plan = metadata.get("execution_plan") if isinstance(metadata.get("execution_plan"), dict) else {}
    scheduling_hints = metadata.get("scheduling_hints") if isinstance(metadata.get("scheduling_hints"), dict) else {}
    retry_policy_raw = (
        source.get("retry_policy")
        if isinstance(source.get("retry_policy"), dict)
        else (
            metadata.get("retry_policy")
            if isinstance(metadata.get("retry_policy"), dict)
            else (
                embedded_execution_plan.get("retry_policy")
                if isinstance(embedded_execution_plan.get("retry_policy"), dict)
                else {}
            )
        )
    )
    dependencies_raw = (
        source.get("dependencies")
        if isinstance(source.get("dependencies"), list)
        else (
            metadata.get("dependencies")
            if isinstance(metadata.get("dependencies"), list)
            else (
                embedded_execution_plan.get("dependencies")
                if isinstance(embedded_execution_plan.get("dependencies"), list)
                else []
            )
        )
    )
    run_id = str(source.get("run_id", "")).strip() or str(execution_record.get("run_id", "")).strip()
    status_value = str(source.get("status", "")).strip() or str(execution_record.get("status", "queued")).strip() or "queued"
    queue_status = "queued" if status_value in {"queued", "pending"} else ("running" if status_value == "running" else "completed")
    task_source = str(source.get("source", "")).strip() or "unknown"
    runner = str(metadata.get("runner", "")).strip() or "playwright"
    queue_name = str(scheduling_hints.get("queue", "")).strip() or ("active-runtime" if task_source == "runtime_realtime" else "default")
    resource_profile = str(scheduling_hints.get("resource_profile", "")).strip() or "default"
    expected_total_seconds = int(scheduling_hints.get("expected_total_seconds", 0) or 0)
    evidence_index = execution_record.get("evidence_index", {}) if isinstance(execution_record.get("evidence_index"), dict) else {}
    total_files = int(evidence_index.get("total_files", 0) or 0)
    runner_exit_code = evidence_index.get("runner_exit_code")
    has_manifest = bool(str(source.get("manifest_path", "")).strip())
    try:
        retry_max_retries = max(0, int(retry_policy_raw.get("max_retries", 0) or 0))
    except Exception:
        retry_max_retries = 0
    try:
        retry_backoff_seconds = max(0, int(retry_policy_raw.get("backoff_seconds", 0) or 0))
    except Exception:
        retry_backoff_seconds = 0
    retry_enabled_raw = retry_policy_raw.get("enabled")
    retry_enabled = bool(retry_enabled_raw) if retry_enabled_raw is not None else retry_max_retries > 0
    dependencies: list[str] = []
    for item in dependencies_raw:
        dependency_value = str(item).strip()
        if dependency_value and dependency_value not in dependencies:
            dependencies.append(dependency_value)
    freshness = _build_task_evidence_freshness(
        task_source=task_source,
        queue_status=queue_status,
        started_at=str(execution_record.get("started_at", "")).strip(),
        finished_at=str(execution_record.get("finished_at", "")).strip(),
        created_at=str(execution_record.get("created_at", "")).strip(),
        has_manifest=has_manifest,
    )
    if has_manifest:
        evidence_health_status = "healthy"
        evidence_health_reason = "任务已绑定 evidence_manifest。"
        manifest_action = "ok"
    elif task_source == "compat_scan":
        evidence_health_status = "degraded"
        evidence_health_reason = "任务通过 execution_record 兼容扫描回退读取。"
        manifest_action = "backfill_manifest"
    elif task_source in {"runtime_realtime", "runtime_fallback"}:
        evidence_health_status = "warning"
        evidence_health_reason = "任务当前依赖 runtime 视图补充，证据落盘仍待完成。"
        manifest_action = "await_runtime_flush"
    else:
        evidence_health_status = "unknown"
        evidence_health_reason = "任务证据来源未明确。"
        manifest_action = "inspect_source"
    return {
        "task_id": run_id or str(source.get("execution_record_path", "")).strip(),
        "run_id": run_id,
        "case_id": str(source.get("case_id", "")).strip() or str(execution_record.get("case_id", "")).strip(),
        "project": str(execution_record.get("project", "default")).strip() or "default",
        "page": str(step_summary.get("page", "")).strip(),
        "runner": runner,
        "status": status_value,
        "queue_status": queue_status,
        "queue": queue_name,
        "resource_profile": resource_profile,
        "expected_total_seconds": expected_total_seconds,
        "source": task_source,
        "mode": str(execution_record.get("mode", "generate_and_run")).strip() or "generate_and_run",
        "started_at": str(execution_record.get("started_at", "")).strip(),
        "finished_at": str(execution_record.get("finished_at", "")).strip(),
        "created_at": str(execution_record.get("created_at", "")).strip(),
        "execution_record_path": str(source.get("execution_record_path", "")).strip(),
        "manifest_path": str(source.get("manifest_path", "")).strip(),
        "has_manifest": has_manifest,
        "runtime_realtime": bool(metadata.get("runtime_realtime_supplement", False)),
        "step_summary": step_summary,
        "evidence_index": evidence_index,
        "evidence_health": {
            "status": evidence_health_status,
            "reason": evidence_health_reason,
            "total_files": total_files,
            "runner_exit_code": runner_exit_code if isinstance(runner_exit_code, int) else None,
            "execution_requested": bool(evidence_index.get("execution_requested", False)),
            "has_manifest": has_manifest,
        },
        "evidence_freshness": freshness,
        "retry": {
            "enabled": retry_enabled,
            "max_retries": retry_max_retries,
            "backoff_seconds": retry_backoff_seconds,
        },
        "dependency": {
            "dependencies": dependencies,
            "dependency_count": len(dependencies),
            "has_dependencies": bool(dependencies),
        },
        "manifest_action": manifest_action,
        "scheduling_hints": scheduling_hints,
    }


def _parse_optional_bool_query(value: Any) -> bool | None:
    normalized = str(value or "").strip().lower()
    if not normalized:
        return None
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    return None


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
    row = item if isinstance(item, dict) else {}
    evidence_health = row.get("evidence_health", {}) if isinstance(row.get("evidence_health"), dict) else {}
    evidence_freshness = row.get("evidence_freshness", {}) if isinstance(row.get("evidence_freshness"), dict) else {}
    health_status = str(evidence_health.get("status", "unknown")).strip().lower() or "unknown"
    freshness_status = str(evidence_freshness.get("status", "unknown")).strip().lower() or "unknown"
    manifest_action = str(row.get("manifest_action", "inspect_source")).strip().lower() or "inspect_source"

    health_score = {
        "healthy": 0,
        "degraded": 3,
        "warning": 2,
        "unknown": 4,
    }.get(health_status, 2)
    freshness_score = {
        "fresh": 0,
        "live": 1,
        "aging": 2,
        "stale": 3,
        "unknown": 2,
    }.get(freshness_status, 2)
    action_score = {
        "ok": 0,
        "await_runtime_flush": 2,
        "backfill_manifest": 3,
        "inspect_source": 4,
    }.get(manifest_action, 2)

    total_score = health_score + freshness_score + action_score
    if total_score >= 6:
        level = "critical"
        reason = "证据健康、时效与 manifest 治理信号叠加后属于高优先治理任务。"
    elif total_score >= 4:
        level = "high"
        reason = "任务存在明显证据治理风险，建议优先关注。"
    elif total_score >= 2:
        level = "medium"
        reason = "任务存在一定治理风险，可纳入常规处理队列。"
    else:
        level = "low"
        reason = "任务证据治理状态整体稳定。"
    return {
        "level": level,
        "score": total_score,
        "reason": reason,
    }


def _build_execution_task_summary(
    *,
    items: list[dict[str, Any]],
    filter_snapshot: dict[str, Any],
    execution_meta: dict[str, Any],
) -> dict[str, Any]:
    status_counts: dict[str, int] = defaultdict(int)
    queue_counts: dict[str, int] = defaultdict(int)
    runner_counts: dict[str, int] = defaultdict(int)
    source_counts: dict[str, int] = defaultdict(int)
    evidence_health_counts: dict[str, int] = defaultdict(int)
    evidence_freshness_counts: dict[str, int] = defaultdict(int)
    manifest_action_counts: dict[str, int] = defaultdict(int)
    manifest_backfill_freshness_counts: dict[str, int] = defaultdict(int)
    governance_risk_counts: dict[str, int] = defaultdict(int)
    governance_risk_top_items: list[dict[str, Any]] = []
    has_manifest_count = 0
    retry_enabled_task_count = 0
    dependency_task_count = 0
    manifest_backfill_candidate_count = 0
    for item in items:
        if not isinstance(item, dict):
            continue
        status_counts[str(item.get("status", "unknown")).strip() or "unknown"] += 1
        queue_counts[str(item.get("queue_status", "unknown")).strip() or "unknown"] += 1
        runner_counts[str(item.get("runner", "unknown")).strip() or "unknown"] += 1
        source_counts[str(item.get("source", "unknown")).strip() or "unknown"] += 1
        evidence_health = item.get("evidence_health", {}) if isinstance(item.get("evidence_health"), dict) else {}
        evidence_health_counts[str(evidence_health.get("status", "unknown")).strip() or "unknown"] += 1
        evidence_freshness = item.get("evidence_freshness", {}) if isinstance(item.get("evidence_freshness"), dict) else {}
        freshness_status = str(evidence_freshness.get("status", "unknown")).strip() or "unknown"
        evidence_freshness_counts[freshness_status] += 1
        manifest_action = str(item.get("manifest_action", "unknown")).strip() or "unknown"
        manifest_action_counts[manifest_action] += 1
        governance_risk = _build_task_governance_risk(item)
        governance_risk_counts[str(governance_risk.get("level", "unknown")).strip() or "unknown"] += 1
        governance_risk_top_items.append(
            {
                "task_id": str(item.get("task_id", "")).strip(),
                "run_id": str(item.get("run_id", "")).strip(),
                "case_id": str(item.get("case_id", "")).strip(),
                "page": str(item.get("page", "")).strip(),
                "source": str(item.get("source", "")).strip(),
                "queue_status": str(item.get("queue_status", "")).strip(),
                "manifest_action": manifest_action,
                "evidence_health_status": str(evidence_health.get("status", "")).strip(),
                "evidence_freshness_status": freshness_status,
                "governance_risk_level": str(governance_risk.get("level", "")).strip(),
                "governance_risk_score": int(governance_risk.get("score", 0) or 0),
                "governance_risk_reason": str(governance_risk.get("reason", "")).strip(),
            }
        )
        if manifest_action == "backfill_manifest":
            manifest_backfill_candidate_count += 1
            manifest_backfill_freshness_counts[freshness_status] += 1
        if bool(item.get("has_manifest", False)):
            has_manifest_count += 1
        retry = item.get("retry", {}) if isinstance(item.get("retry"), dict) else {}
        if bool(retry.get("enabled", False)):
            retry_enabled_task_count += 1
        dependency = item.get("dependency", {}) if isinstance(item.get("dependency"), dict) else {}
        if bool(dependency.get("has_dependencies", False)):
            dependency_task_count += 1
    total_tasks = len(items)
    manifest_first_task_count = int(source_counts.get("manifest", 0) or 0)
    compat_fallback_task_count = int(source_counts.get("compat_scan", 0) or 0)
    runtime_supplement_task_count = int(source_counts.get("runtime_realtime", 0) or 0) + int(source_counts.get("runtime_fallback", 0) or 0)
    if int(manifest_backfill_freshness_counts.get("stale", 0) or 0) > 0:
        manifest_backfill_priority = "urgent"
    elif int(manifest_backfill_freshness_counts.get("aging", 0) or 0) > 0:
        manifest_backfill_priority = "normal"
    elif manifest_backfill_candidate_count > 0:
        manifest_backfill_priority = "low"
    else:
        manifest_backfill_priority = "none"
    if int(governance_risk_counts.get("critical", 0) or 0) > 0:
        governance_risk_priority = "critical"
    elif int(governance_risk_counts.get("high", 0) or 0) > 0:
        governance_risk_priority = "high"
    elif int(governance_risk_counts.get("medium", 0) or 0) > 0:
        governance_risk_priority = "medium"
    elif int(governance_risk_counts.get("low", 0) or 0) > 0:
        governance_risk_priority = "low"
    else:
        governance_risk_priority = "none"
    governance_risk_top_items.sort(
        key=lambda item: (
            -int(item.get("governance_risk_score", 0) or 0),
            str(item.get("task_id", "")),
            str(item.get("run_id", "")),
        )
    )
    return {
        "total_tasks": total_tasks,
        "status_counts": dict(sorted(status_counts.items())),
        "queue_status_counts": dict(sorted(queue_counts.items())),
        "runner_counts": dict(sorted(runner_counts.items())),
        "source_counts": dict(sorted(source_counts.items())),
        "evidence_health_counts": dict(sorted(evidence_health_counts.items())),
        "evidence_freshness_counts": dict(sorted(evidence_freshness_counts.items())),
        "manifest_action_counts": dict(sorted(manifest_action_counts.items())),
        "manifest_first_task_count": manifest_first_task_count,
        "compat_fallback_task_count": compat_fallback_task_count,
        "runtime_supplement_task_count": runtime_supplement_task_count,
        "manifest_backfill_candidate_count": manifest_backfill_candidate_count,
        "manifest_backfill_freshness_counts": dict(sorted(manifest_backfill_freshness_counts.items())),
        "manifest_backfill_priority": manifest_backfill_priority,
        "governance_risk_counts": dict(sorted(governance_risk_counts.items())),
        "governance_risk_priority": governance_risk_priority,
        "governance_risk_top_items": governance_risk_top_items[:5],
        "has_manifest_task_count": has_manifest_count,
        "no_manifest_task_count": max(total_tasks - has_manifest_count, 0),
        "retry_enabled_task_count": retry_enabled_task_count,
        "dependency_task_count": dependency_task_count,
        "manifest_first_ratio_visible": round((manifest_first_task_count / max(1, total_tasks)), 3),
        "compat_fallback_ratio_visible": round((compat_fallback_task_count / max(1, total_tasks)), 3),
        "runtime_supplement_ratio_visible": round((runtime_supplement_task_count / max(1, total_tasks)), 3),
        "retry_enabled_ratio_visible": round((retry_enabled_task_count / max(1, total_tasks)), 3),
        "dependency_ratio_visible": round((dependency_task_count / max(1, total_tasks)), 3),
        "filter_snapshot": filter_snapshot,
        "execution_meta": execution_meta if isinstance(execution_meta, dict) else {},
    }


def _load_defects() -> list[dict[str, Any]]:
    with _FILE_LOCK:
        return _read_json_list(DEFECT_LINKS_FILE)


def _get_python_bin() -> str:
    venv_python = REPO_ROOT / ".venv" / "bin" / "python"
    if venv_python.exists():
        return str(venv_python)
    return "python3"


def _apply_no_store_headers(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"


def _get_allure_index_version() -> int:
    candidates = [
        ALLURE_REPORT_ROOT / "index.html",
        ALLURE_REPORT_ROOT / "widgets" / "summary.json",
        ALLURE_REPORT_ROOT / "history" / "history-trend.json",
    ]
    versions: list[int] = []
    for path in candidates:
        if not path.exists():
            continue
        try:
            versions.append(int(path.stat().st_mtime_ns))
        except Exception:
            continue
    return max(versions) if versions else 0


def _read_allure_summary() -> dict[str, Any]:
    summary_path = ALLURE_REPORT_ROOT / "widgets" / "summary.json"
    if not summary_path.exists():
        return {}
    try:
        payload = json.loads(summary_path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _ensure_allure_snapshot(version: int) -> str:
    if version <= 0:
        return "/allure/index.html"
    target = ALLURE_SNAPSHOTS_ROOT / str(version)
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(ALLURE_REPORT_ROOT, target)
        snapshot_dirs = sorted(
            [item for item in ALLURE_SNAPSHOTS_ROOT.iterdir() if item.is_dir()],
            key=lambda p: p.name,
            reverse=True,
        )
        for stale in snapshot_dirs[10:]:
            shutil.rmtree(stale, ignore_errors=True)
    return f"/allure-snapshots/{version}/index.html"


def _build_run_command(case_path: Path) -> tuple[list[str], dict[str, str]]:
    command = [
        _get_python_bin(),
        "-m",
        "pytest",
        "-s",
        str(REPO_ROOT / "runners" / "web-playwright-python" / "tests" / "test_yaml_ai_generated.py"),
        "--alluredir",
        str(ALLURE_RESULTS_ROOT),
    ]
    env = os.environ.copy()
    current_pythonpath = env.get("PYTHONPATH", "").strip()
    runner_path = str(REPO_ROOT / "runners" / "web-playwright-python")
    env["PYTHONPATH"] = f"{runner_path}:{current_pythonpath}" if current_pythonpath else runner_path
    env["RUN_MODE"] = "ai"
    env["RUN_SOURCE"] = "web-ui"
    env["TEST_CASE_PATH"] = str(case_path.resolve())
    env["SELF_HEALING_ENABLED"] = "0"
    env.setdefault("BASE_URL", "http://localhost:5173/login#/login")
    return command, env


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
    if not artifacts_dir.exists():
        return {}
    manifest_candidates = sorted(
        artifacts_dir.rglob("evidence_manifest.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for manifest_path in manifest_candidates:
        try:
            raw_manifest = json.loads(manifest_path.read_text(encoding="utf-8")) or {}
        except Exception:
            continue
        manifest = _normalize_evidence_manifest_payload(raw_manifest)
        record_paths = _resolve_manifest_entries(manifest.get("execution_record_files"), root=manifest_path.parent)
        for record_path in record_paths:
            execution_record = _load_execution_record_payload(record_path)
            if execution_record:
                return execution_record

    candidates = sorted(
        artifacts_dir.rglob("execution_record.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        return {}
    return _load_execution_record_payload(candidates[0])


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
    text = text.strip()
    if not text:
        return {}
    try:
        payload = json.loads(text)
        return payload if isinstance(payload, dict) else {}
    except Exception:
        pass
    start = text.rfind("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        candidate = text[start : end + 1]
        try:
            payload = json.loads(candidate)
            return payload if isinstance(payload, dict) else {}
        except Exception:
            return {}
    return {}


@router.get("/api/workbench/projects")
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


@router.get("/api/workbench/tasks")
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


@router.get("/api/workbench/tasks/{task_id}")
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


@router.get("/api/workbench/execution-gate/config")
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
