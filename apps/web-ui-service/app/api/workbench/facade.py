"""Workbench API 门面层。

该模块负责将路由层请求编排到各个 service，并补齐跨模块流程中的
聚合逻辑、降级逻辑和部分运行态数据拼装。
"""
from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
from collections import defaultdict
from datetime import datetime, timedelta
from shared_backend.datetime_compat import UTC
from functools import partial
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Sequence
import yaml

from fastapi import HTTPException, Response, status
from shared_backend import get_dictionary_items
from shared_backend.case_ids import match_case_id, normalize_case_id
from shared_backend.element_binding import build_element_alias_map, resolve_element_code, resolve_involved_element_codes
from shared_backend.schemas.contracts import normalize_test_point_plan_v1
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.workbench import constants, store
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core import page_analysis_rules
from app.repositories.page_object_repository import PageObjectRepository
from app.repositories.test_case_repository import TestCaseRepository
from app.models.page_object import PageElement
from app.models.test_case import TestCase, TestCaseExecution
from app.services import (
    test_project_service,
    test_case_service,
    test_data_pool_service,
    workbench_analysis_service,
    workbench_asset_service,
    workbench_case_consistency_service,
    workbench_gate_service,
    workbench_governance_service,
    workbench_history_service,
    workbench_reporting_service,
    workbench_review_service,
    workbench_runtime_service,
    workbench_scheduler_service,
    workbench_task_service,
)
from app.services.workbench_generation_api.payloads import GenerateCasePayload as GenerationGenerateCasePayload
from app.services.workbench_generation_api.usecase_factory import build_generate_case_usecase

from ._http import get_json as _get_json
from ._helpers import (
    build_empty_trend as _build_empty_trend,
    default_overview as _default_overview,
    is_within as _is_within,
    normalize_generation_case_source as _normalize_generation_case_source,
    normalize_optional_project_code as _normalize_optional_project_code,
    normalize_test_point_review_status as _normalize_test_point_review_status,
    parse_iso_datetime as _parse_iso_datetime,
    python_literal as _python_literal,
    read_json_file as _read_json_file,
    safe_python_identifier as _safe_python_identifier,
    safe_rollback_or_invalidate as _safe_rollback_or_invalidate,
    text as _text,
    text_list as _text_list,
    to_utc as _to_utc,
    utc_now as _utc_now,
    validate_test_point_review_status as _validate_test_point_review_status,
    write_json_file as _write_json_file,
)
from .service import WorkbenchService
from .service import (
    _append_history,
    _append_runtime_run,
    _build_execution_task_summary,
    _build_execution_task_view,
    _collect_execution_records_with_meta,
    _collect_failure_entries,
    _collect_failure_entries_with_meta,
    _ensure_dirs,
    _execution_record_time_value,
    _load_runtime_execution_record_from_artifacts,
    _normalize_execution_record_payload,
    _normalize_failure_entry_view,
    _read_json_list,
    _runtime_run_id,
    _runtime_view_from_entry,
    _runtime_view_with_execution_record_preferred,
    _safe_case_id,
    _sync_stage_a_workbench_state,
    _sync_stage_b_workbench_gate,
    _update_runtime_run,
    _write_json_list,
)
import logging
LOGGER = logging.getLogger(__name__)
_RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{8,128}$")


def _settings() -> Any:
    """统一读取运行配置，避免在调用点重复导入配置对象。"""
    return get_settings()

# ---- 历史/项目解析 ----
def _resolve_history_project_code(item: dict[str, Any]) -> str:
    """优先从记录字段取 project，缺失时回退到 case_id 解析。"""
    normalized_project_code = _normalize_optional_project_code(item.get("project_code") or item.get("project"))
    if normalized_project_code:
        return normalized_project_code
    case_id = str(item.get("case_id", "")).strip().lower()
    matched = match_case_id(case_id)
    if not matched:
        return ""
    return _normalize_optional_project_code(matched.group("project"))

def _attach_test_point_asset_summary(item: dict[str, Any]) -> dict[str, Any]:
    """为用例记录补充关联测试点资产的汇总与可追溯信息。"""
    payload = dict(item) if isinstance(item, dict) else {}
    project = _text(payload.get("project")) or "mall"
    case_id = _safe_case_id(_text(payload.get("case_id")))
    if not case_id:
        return payload
    try:
        summary = workbench_asset_service.build_test_point_asset_summary(
            project=project,
            case_id=case_id,
            load_test_point_asset=workbench_asset_service.load_test_point_asset,
            latest_run_snapshot_for_case=lambda project, case_id, page="": workbench_asset_service.latest_run_snapshot_for_case(
                project=project,
                case_id=case_id,
                page=page,
                safe_case_id_fn=workbench_gate_service.safe_case_id,
                normalize_page_slug_fn=workbench_gate_service.normalize_page_slug,
                runtime_jobs=store.list_run_jobs(),
                runtime_runs_file=constants.RUNTIME_RUNS_FILE,
                runtime_view_with_execution_record_preferred_fn=lambda value: value if isinstance(value, dict) else {},
                read_json_list_fn=store.read_json_list,
                build_review_audit_summary_fn=workbench_review_service.build_review_audit_summary,
                build_page_semantic_summary_fn=workbench_analysis_service.build_page_semantic_summary,
                build_execution_gate_audit_snapshot_fn=workbench_gate_service.build_execution_gate_audit_snapshot,
                build_risk_report_summary_fn=workbench_analysis_service.build_risk_report_summary,
            ),
            build_traceability_summary=lambda asset, latest_run: workbench_asset_service.build_test_point_asset_traceability_summary(
                asset=asset,
                latest_run=latest_run,
                build_test_point_asset_technique_summary_fn=workbench_asset_service.build_test_point_asset_technique_summary,
                build_review_audit_summary_fn=workbench_review_service.build_review_audit_summary,
                build_page_semantic_summary_fn=workbench_analysis_service.build_page_semantic_summary,
                build_risk_report_summary_fn=workbench_analysis_service.build_risk_report_summary,
                build_execution_gate_fn=workbench_gate_service.build_execution_gate,
                build_execution_gate_audit_snapshot_fn=workbench_gate_service.build_execution_gate_audit_snapshot,
                clamp_confidence=page_analysis_rules.clamp_confidence,
            ),
            build_selection_summary=lambda traceability_summary: workbench_asset_service.build_test_point_asset_selection_summary(
                traceability_summary=traceability_summary,
            ),
            clamp_confidence=page_analysis_rules.clamp_confidence,
        )
    except Exception as exc:  # pragma: no cover - summary is best-effort metadata.
        logging.getLogger(__name__).warning("failed to attach test point asset summary: %s", exc)
        summary = {}
    if summary:
        payload["test_point_asset_summary"] = summary
        payload.setdefault("asset_id", summary.get("asset_id", ""))
        payload.setdefault("asset_title", summary.get("title", ""))
        payload.setdefault("page", summary.get("page", ""))
    return payload


_REVIEW_STATUS_ALIASES = {
    "": "pending",
    "pending": "pending",
    "pending_review": "pending",
    "needs_review": "pending",
    "review": "pending",
    "draft": "pending",
    "approved": "approved",
    "approve": "approved",
    "pass": "approved",
    "passed": "approved",
    "ready": "approved",
    "active": "approved",
    "rejected": "rejected",
    "reject": "rejected",
    "failed": "rejected",
}

_VIRTUAL_TEST_POINT_ELEMENTS = {"页面", "浏览器地址栏", "工作台URL", "登录页面", "工作台首页"}
_GENERATION_CASE_SOURCE_VALUES = {"manual", "ai", "regression"}




# ═══════════════════════════════════════════════════════════════
# Review helpers —— 测试点审核状态、快照、绑定明细
# ═══════════════════════════════════════════════════════════════
def _candidate_snapshot_from_point(point: dict[str, Any]) -> dict[str, Any]:
    """从测试点 metadata 中提取原始候选快照。"""
    metadata = point.get("metadata") if isinstance(point.get("metadata"), dict) else {}
    snapshot = metadata.get("candidate_snapshot") if isinstance(metadata.get("candidate_snapshot"), dict) else {}
    return snapshot if isinstance(snapshot, dict) else {}


def _review_status_from_point(point: dict[str, Any]) -> str:
    """从测试点当前字段解析评审状态，避免历史快照覆盖唯一事实源。"""
    return _normalize_test_point_review_status(
        point.get("review_status")
        or point.get("manual_review_status")
        or "pending"
    )


def _review_status_from_candidate(candidate: dict[str, Any]) -> str:
    """从候选测试点数据中解析评审状态。"""
    return _normalize_test_point_review_status(candidate.get("review_status") or candidate.get("manual_review_status") or "pending")


def _review_summary_from_points(points: list[dict[str, Any]]) -> dict[str, Any]:
    """按测试点评审状态汇总资产级评审概览。"""
    counts = {"pending": 0, "approved": 0, "rejected": 0}
    for point in points:
        counts[_review_status_from_point(point)] = int(counts.get(_review_status_from_point(point), 0) or 0) + 1
    return {
        "total_points": len(points),
        "pending_count": counts["pending"],
        "approved_count": counts["approved"],
        "rejected_count": counts["rejected"],
        "test_point_status": (
            "approved"
            if points and counts["approved"] == len(points)
            else "rejected"
            if points and counts["rejected"] == len(points)
            else "pending"
        ),
    }


def _is_virtual_test_point_element(value: Any) -> bool:
    """识别不需要真实页面元素治理的虚拟测试点元素。"""
    normalized = _text(value)
    return normalized in _VIRTUAL_TEST_POINT_ELEMENTS or normalized.endswith("URL")








def _test_point_asset_state_paths(project: str, asset_id: str) -> tuple[Path, Path]:
    """解析测试点资产文件及其计划文件的状态存储路径。"""
    project_dir = workbench_asset_service.state_project_dir(project, state_root=constants.TEST_POINTS_ROOT)
    raw_asset_id = _text(asset_id)
    normalized_asset_id = _safe_case_id(raw_asset_id)
    candidate_ids = [normalized_asset_id]
    if raw_asset_id and raw_asset_id not in candidate_ids:
        candidate_ids.append(raw_asset_id)
    asset_path = next(
        (project_dir / f"{candidate_id}.json" for candidate_id in candidate_ids if (project_dir / f"{candidate_id}.json").exists()),
        project_dir / f"{normalized_asset_id}.json",
    )
    plan_path = next(
        (
            project_dir / "plans" / f"{candidate_id}.json"
            for candidate_id in candidate_ids
            if (project_dir / "plans" / f"{candidate_id}.json").exists()
        ),
        project_dir / "plans" / f"{normalized_asset_id}.json",
    )
    return asset_path, plan_path


def _is_generation_qualified_element(element: PageElement) -> bool:
    """判断页面元素是否满足自动生成脚本所需的治理质量。"""
    element_status = _text(getattr(element, "status", "")).lower() or "active"
    review_status = _text(getattr(element, "review_status", "")).lower()
    stability_level = _text(getattr(element, "stability_level", "")).lower()
    return element_status == "active" and review_status == "approved" and stability_level in {"high", "medium"}


def _page_object_generation_context(db: Session, *, project: str, page: str) -> dict[str, Any]:
    """组装测试点生成脚本所需的页面对象、URL 和元素上下文。"""
    normalized_project = _text(project) or "mall"
    normalized_page = workbench_gate_service.normalize_page_slug(_text(page))
    if not normalized_page:
        return {
            "page_object_found": False,
            "page_url": "",
            "page_object": {},
            "base_blockers": ["页面为空，无法定位页面对象"],
        }
    repo = PageObjectRepository(db)
    page_object = repo.get_by_identity(normalized_project, "web", normalized_page)
    if page_object is None:
        return {
            "page_object_found": False,
            "page_url": "",
            "page_object": {},
            "base_blockers": [f"{normalized_project}/web/{normalized_page} 页面对象未治理，请先在页面对象管理中补齐"],
        }
    elements = repo.list_elements_by_page_object_id(int(page_object.id), order_by_id=True)
    qualified_elements = [element for element in elements if _is_generation_qualified_element(element)]
    mapping: dict[str, dict[str, Any]] = {}
    for element in qualified_elements:
        element_code = _text(getattr(element, "element_code", ""))
        locator_value = _text(getattr(element, "locator_value", ""))
        if not element_code or not locator_value:
            continue
        mapping[element_code] = {
            "selector": locator_value,
            "type": _text(getattr(element, "locator_type", "")) or "css",
            "role": _text(getattr(element, "role", "")),
            "name": _text(getattr(element, "element_name", "")),
            "aliases": _text_list(getattr(element, "aliases_json", [])),
            "business_type": _text(getattr(element, "business_type", "")).lower(),
            "business_domain": _text(getattr(element, "business_domain", "")).lower(),
            "review_status": _text(getattr(element, "review_status", "")).lower(),
            "stability_level": _text(getattr(element, "stability_level", "")).lower(),
            "status": _text(getattr(element, "status", "")).lower() or "active",
        }
    blockers: list[str] = []
    page_url = _text(getattr(page_object, "page_url", ""))
    if not page_url:
        blockers.append("请到页面对象管理补齐页面 URL")
    if not mapping:
        blockers.append("页面对象缺少可生成元素：需满足 status=active + review_status=approved + stability_level 为 high/medium")
    return {
        "page_object_found": True,
        "page_url": page_url,
        "page_object": {"page": normalized_page, "page_url": page_url, "elements": mapping},
        "base_blockers": blockers,
        "qualified_element_count": len(mapping),
        "formal_element_count": len(elements),
    }


def _test_point_generation_state(point: dict[str, Any], *, page_context: dict[str, Any]) -> dict[str, Any]:
    """根据测试点与页面对象上下文计算是否具备脚本生成条件。"""
    candidate = _candidate_from_asset_point(point, fallback_title="", fallback_priority="P1")
    review_status_value = _review_status_from_point(point)
    blockers = [str(item) for item in page_context.get("base_blockers", []) if str(item).strip()]
    if review_status_value != "approved":
        blockers.append("测试点未审核通过")
    involved_elements = _text_list(candidate.get("involved_elements"))
    real_elements = [item for item in involved_elements if not _is_virtual_test_point_element(item)]
    bound_codes: list[str] = []
    unknown_elements: list[str] = []
    page_object = page_context.get("page_object") if isinstance(page_context.get("page_object"), dict) else {}
    if real_elements and page_object:
        bound_codes, unknown_elements = resolve_involved_element_codes(real_elements, page_object)
    elif real_elements:
        unknown_elements = real_elements
    if unknown_elements:
        blockers.append(f"元素未在 Page Object 注册或未审核通过: {', '.join(unknown_elements)}")
    if not real_elements:
        element_binding_status = "not_required"
    elif unknown_elements and bound_codes:
        element_binding_status = "partial"
    elif unknown_elements:
        element_binding_status = "missing"
    else:
        element_binding_status = "bound"
    element_bindings = _element_bindings_for_review(involved_elements, page_context=page_context)
    return {
        "review_status": review_status_value,
        "element_binding_status": element_binding_status,
        "involved_element_codes": bound_codes,
        "unknown_elements": unknown_elements,
        "element_bindings": element_bindings,
        "generation_blockers": blockers,
        "can_generate": review_status_value == "approved" and not blockers,
    }


def _canonical_involved_elements_for_page(involved_elements: Any, *, page_context: dict[str, Any]) -> list[str]:
    """将测试点涉及元素收敛为页面对象 element_code，避免中文名与编码混存。"""
    raw_elements = _text_list(involved_elements)
    page_object = page_context.get("page_object") if isinstance(page_context.get("page_object"), dict) else {}
    if not raw_elements or not page_object:
        return raw_elements
    alias_map = build_element_alias_map(page_object)
    canonical: list[str] = []
    for raw in raw_elements:
        if _is_virtual_test_point_element(raw):
            if raw not in canonical:
                canonical.append(raw)
            continue
        element_code = resolve_element_code(raw, alias_map)
        normalized = element_code or raw
        if normalized and normalized not in canonical:
            canonical.append(normalized)
    return canonical


def _normalize_points_involved_elements(points: list[dict[str, Any]], *, page_context: dict[str, Any]) -> list[dict[str, Any]]:
    """规范化 plan.points[].involved_elements；旧 snapshot 只保留历史，不再作为正式事实源。"""
    normalized_points: list[dict[str, Any]] = []
    for point in points:
        current = _text_list(point.get("involved_elements"))
        canonical = _canonical_involved_elements_for_page(current, page_context=page_context)
        if canonical == current:
            normalized_points.append(point)
            continue
        copied = dict(point)
        copied["involved_elements"] = canonical
        normalized_points.append(copied)
    return normalized_points


def _element_bindings_for_review(involved_elements: list[str], *, page_context: dict[str, Any]) -> list[dict[str, Any]]:
    """为评审视图生成测试点涉及元素与页面对象元素的绑定明细。"""
    page_object = page_context.get("page_object") if isinstance(page_context.get("page_object"), dict) else {}
    elements = page_object.get("elements") if isinstance(page_object.get("elements"), dict) else {}
    alias_map = build_element_alias_map(page_object) if page_object else {}
    bindings: list[dict[str, Any]] = []
    for element_name in involved_elements:
        normalized_name = _text(element_name)
        if not normalized_name:
            continue
        if _is_virtual_test_point_element(normalized_name):
            bindings.append(
                {
                    "element_name": normalized_name,
                    "binding_status": "not_required",
                    "binding_label": "无需元素",
                    "element_code": "",
                    "locator_type": "",
                    "locator_value": "",
                    "blocker": "虚拟操作，不需要真实页面元素",
                }
            )
            continue
        element_code = resolve_element_code(normalized_name, alias_map)
        element_meta = elements.get(element_code) if element_code and isinstance(elements.get(element_code), dict) else {}
        if element_code and element_meta:
            bindings.append(
                {
                    "element_name": normalized_name,
                    "binding_status": "bound",
                    "binding_label": "已绑定",
                    "element_code": element_code,
                    "locator_type": _text(element_meta.get("type") or element_meta.get("locator_type")),
                    "locator_value": _text(element_meta.get("selector") or element_meta.get("locator_value")),
                    "blocker": "",
                }
            )
            continue
        bindings.append(
            {
                "element_name": normalized_name,
                "binding_status": "missing",
                "binding_label": "元素缺失",
                "element_code": "",
                "locator_type": "",
                "locator_value": "",
                "blocker": "元素未在 Page Object 注册或未审核通过",
            }
        )
    return bindings


def _review_history_from_point(point: dict[str, Any]) -> list[dict[str, Any]]:
    """从测试点 metadata 中提取人工评审历史。"""
    metadata = point.get("metadata") if isinstance(point.get("metadata"), dict) else {}
    raw_history = metadata.get("review_history") if isinstance(metadata.get("review_history"), list) else []
    history = [item for item in raw_history if isinstance(item, dict)]
    reviewed_at = _text(point.get("reviewed_at"))
    reviewed_by = _text(point.get("reviewed_by"))
    review_status_value = _review_status_from_point(point)
    review_note = _text(point.get("review_note"))
    if reviewed_at and not any(_text(item.get("reviewed_at")) == reviewed_at for item in history):
        history.append(
            {
                "reviewed_at": reviewed_at,
                "reviewed_by": reviewed_by,
                "status": review_status_value,
                "note": review_note,
            }
        )
    return history







# ═══════════════════════════════════════════════════════════════
# Script preview helpers —— Selenium 脚本生成
# ═══════════════════════════════════════════════════════════════
def _selenium_by_expression(locator_type: Any) -> str:
    """将页面对象定位器类型映射为 Selenium By 表达式。"""
    normalized = _text(locator_type).lower().replace("-", "_")
    mapping = {
        "css": "By.CSS_SELECTOR",
        "css_selector": "By.CSS_SELECTOR",
        "selector": "By.CSS_SELECTOR",
        "xpath": "By.XPATH",
        "id": "By.ID",
        "name": "By.NAME",
        "class": "By.CLASS_NAME",
        "class_name": "By.CLASS_NAME",
        "tag": "By.TAG_NAME",
        "tag_name": "By.TAG_NAME",
        "link_text": "By.LINK_TEXT",
        "partial_link_text": "By.PARTIAL_LINK_TEXT",
    }
    return mapping.get(normalized, "By.CSS_SELECTOR")


def _xpath_literal(value: Any) -> str:
    """将字符串转换为 XPath 表达式可安全引用的字面量。"""
    text = _text(value)
    if "'" not in text:
        return f"'{text}'"
    if '"' not in text:
        return f'"{text}"'
    parts = text.split("'")
    return "concat(" + ", \"'\", ".join(f"'{part}'" for part in parts) + ")"


def _selenium_locator(locator_type: Any, locator_value: Any, role: Any = "") -> tuple[str, str]:
    """将页面对象定位器标准化为 Selenium 查找参数。"""
    normalized = _text(locator_type).lower().replace("-", "_")
    value = _text(locator_value)
    role_value = _text(role).lower()
    if normalized == "placeholder":
        css_value = json.dumps(value, ensure_ascii=False)
        return "By.CSS_SELECTOR", f"input[placeholder*={css_value}], textarea[placeholder*={css_value}]"
    if normalized == "text":
        literal = _xpath_literal(value)
        return "By.XPATH", f"//*[normalize-space()={literal} or contains(normalize-space(), {literal})]"
    if normalized == "role":
        literal = _xpath_literal(value)
        if role_value == "button":
            return "By.XPATH", f"//*[self::button or @role='button'][normalize-space()={literal} or contains(normalize-space(), {literal})]"
        return "By.XPATH", f"//*[@role={_xpath_literal(role_value)} and (normalize-space()={literal} or contains(normalize-space(), {literal}))]"
    return _selenium_by_expression(locator_type), value


def _locator_preview_for_element(element_name: str, *, page_context: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """根据元素名称在页面对象上下文中预览可用定位器。"""
    page_object = page_context.get("page_object") if isinstance(page_context.get("page_object"), dict) else {}
    elements = page_object.get("elements") if isinstance(page_object.get("elements"), dict) else {}
    alias_map = build_element_alias_map(page_object) if page_object else {}
    element_code = resolve_element_code(element_name, alias_map)
    element_meta = elements.get(element_code) if element_code and isinstance(elements.get(element_code), dict) else {}
    return element_code, element_meta


def _element_name_from_step(step: str, involved_elements: list[str]) -> str:
    """从自然语言步骤中匹配最可能被操作的元素名称。"""
    normalized_step = _text(step)
    matches = [element for element in involved_elements if _text(element) and _text(element) in normalized_step]
    if matches:
        return max(matches, key=len)
    return involved_elements[0] if len(involved_elements) == 1 else ""


def _input_value_from_step(step: str, element_name: str) -> str:
    """从输入类步骤中提取要填写的测试数据占位值。"""
    normalized_step = _text(step)
    for marker in ("输入", "填写"):
        if marker in normalized_step:
            value = normalized_step.rsplit(marker, 1)[1].strip()
            if element_name and value.startswith(element_name):
                value = value[len(element_name):].strip()
            for prefix in ("正确账号", "正确密码", "账号", "密码", "内容", "值", "为"):
                if value.startswith(prefix):
                    value = value[len(prefix):].strip()
            return value or "TODO"
    return "TODO"


def _append_find_element_line(lines: list[str], *, indent: str, action: str, element_name: str, value: str, page_context: dict[str, Any]) -> None:
    """向脚本预览中追加 Selenium 元素查找与操作语句。"""
    element_code, element_meta = _locator_preview_for_element(element_name, page_context=page_context)
    locator_value = _text(element_meta.get("selector") or element_meta.get("locator_value"))
    locator_type = _text(element_meta.get("type") or element_meta.get("locator_type")) or "css"
    role = _text(element_meta.get("role"))
    if not element_code or not locator_value:
        lines.append(f"{indent}# TODO: 未找到元素定位器：{element_name}")
        return
    by_expression, selenium_value = _selenium_locator(locator_type, locator_value, role)
    finder = f"driver.find_element({by_expression}, {_python_literal(selenium_value)})"
    if action == "input":
        lines.append(f"{indent}{finder}.clear()")
        lines.append(f"{indent}{finder}.send_keys({_python_literal(value)})  # {element_name} -> {element_code}")
        return
    lines.append(f"{indent}{finder}.click()  # {element_name} -> {element_code}")


def _append_script_line_from_hint(lines: list[str], *, hint: str, page_context: dict[str, Any]) -> bool:
    """将结构化步骤提示转换为脚本预览中的 Selenium 语句。"""
    normalized = _text(hint)
    indent = "    "
    if not normalized:
        return False
    lower = normalized.lower()
    if lower.startswith("input:"):
        body = normalized.split(":", 1)[1]
        element_name, value = (body.split("=", 1) + [""])[:2] if "=" in body else (body, "")
        _append_find_element_line(lines, indent=indent, action="input", element_name=_text(element_name), value=_text(value), page_context=page_context)
        return True
    if lower.startswith("click:"):
        element_name = normalized.split(":", 1)[1]
        _append_find_element_line(lines, indent=indent, action="click", element_name=_text(element_name), value="", page_context=page_context)
        return True
    if lower.startswith("goto:"):
        target = normalized.split(":", 1)[1]
        lines.append(f"{indent}driver.get({_python_literal(target)})")
        return True
    if lower in {"reload", "refresh"} or lower.startswith("reload:") or lower.startswith("refresh:"):
        lines.append(f"{indent}driver.refresh()")
        return True
    return False


def _build_test_point_script_preview(*, asset: dict[str, Any], candidate: dict[str, Any], page_context: dict[str, Any]) -> str:
    """根据测试点候选信息生成 Selenium Python 预览脚本。"""
    page_url = _text(page_context.get("page_url"))
    intent_id = _text(candidate.get("intent_id"))
    function_name = f"test_{_safe_python_identifier(intent_id)}"
    involved_elements = _text_list(candidate.get("involved_elements"))
    lines = [
        "from selenium.webdriver.common.by import By",
        "",
        "",
        f"def {function_name}(driver):",
        f"    driver.get({_python_literal(page_url)})",
    ]
    precondition = _text(candidate.get("precondition"))
    if precondition:
        lines.append(f"    # 前置条件：{precondition}")

    hints = _text_list(candidate.get("steps_hint"))
    handled_any = False
    for hint in hints:
        handled_any = _append_script_line_from_hint(lines, hint=hint, page_context=page_context) or handled_any

    if not handled_any:
        for step in _text_list(candidate.get("steps")):
            if "点击" in step:
                element_name = _element_name_from_step(step, involved_elements)
                if element_name:
                    _append_find_element_line(lines, indent="    ", action="click", element_name=element_name, value="", page_context=page_context)
                    continue
            if "输入" in step or "填写" in step:
                element_name = _element_name_from_step(step, involved_elements)
                if element_name:
                    _append_find_element_line(
                        lines,
                        indent="    ",
                        action="input",
                        element_name=element_name,
                        value=_input_value_from_step(step, element_name),
                        page_context=page_context,
                    )
                    continue
            if "刷新" in step:
                lines.append("    driver.refresh()")
                continue
            lines.append(f"    # TODO: 请根据业务动作补充自动化步骤：{step}")

    expected = _text(candidate.get("expected") or candidate.get("expected_result"))
    if expected:
        lines.extend(
            [
                f"    # 预期结果：{expected}",
                "    # TODO: 将下面的页面源码断言替换为更稳定的 URL / 文案 / 元素断言。",
                f"    assert {_python_literal(expected)} in driver.page_source",
            ]
        )
    else:
        lines.append("    assert driver.current_url")
    return "\n".join(lines) + "\n"



# ═══════════════════════════════════════════════════════════════
# Case identity helpers —— case_id 解析、source identity、元数据
# ═══════════════════════════════════════════════════════════════
def _append_unique_intent_id(items: list[str], value: Any) -> None:
    """向 intent_id 列表追加去重后的有效测试点标识。"""
    intent_id = _text(value)
    if not intent_id or intent_id in {"login-00", "__page_entry__"}:
        return
    if intent_id not in items:
        items.append(intent_id)


def _intent_ids_from_case_steps(case: TestCase) -> list[str]:
    """从用例步骤或脚本 YAML 中提取来源测试点 intent_id。"""
    ids: list[str] = []
    steps = case.test_steps if isinstance(case.test_steps, list) else []
    for raw_step in steps:
        step = raw_step if isinstance(raw_step, dict) else {}
        _append_unique_intent_id(ids, step.get("intent_id"))
    if ids:
        return ids
    try:
        script_payload = yaml.safe_load(_text(case.script_code)) or {}
    except yaml.YAMLError:
        script_payload = {}
    if isinstance(script_payload, dict):
        execution = script_payload.get("execution") if isinstance(script_payload.get("execution"), dict) else {}
        for intent_id in _text_list(execution.get("selected_intent_ids")):
            _append_unique_intent_id(ids, intent_id)
    return ids


def _source_identity_from_case(case: TestCase) -> tuple[str, list[str]]:
    """解析用例关联的源测试点资产与 intent_id 集合。"""
    source_asset_id = ""
    intent_ids = _intent_ids_from_case_steps(case)
    try:
        script_payload = yaml.safe_load(_text(case.script_code)) or {}
    except yaml.YAMLError:
        script_payload = {}
    if isinstance(script_payload, dict):
        raw_requirement = script_payload.get("requirement")
        if isinstance(raw_requirement, dict):
            source_asset_id = _text(raw_requirement.get("source_asset_id"))
            _append_unique_intent_id(intent_ids, raw_requirement.get("intent_id"))
        elif isinstance(raw_requirement, list):
            for row in raw_requirement:
                text = _text(row).lstrip("-*•·").strip()
                if text.startswith(("来源资产：", "来源资产:")):
                    source_asset_id = text.split("：", 1)[-1].split(":", 1)[-1].strip()
                if text.startswith(("测试点ID：", "测试点ID:")):
                    _append_unique_intent_id(intent_ids, text.split("：", 1)[-1].split(":", 1)[-1].strip())
        source_asset_id = source_asset_id or _text(script_payload.get("source_asset_id"))
    return source_asset_id, intent_ids


def _structured_requirement_metadata_from_case(case: TestCase) -> dict[str, str]:
    """从 `script_code.requirement` 结构化对象中读取业务追踪元数据。"""
    try:
        script_payload = yaml.safe_load(_text(case.script_code)) or {}
    except yaml.YAMLError:
        return {}
    if not isinstance(script_payload, dict):
        return {}
    raw_requirement = script_payload.get("requirement")
    if not isinstance(raw_requirement, dict):
        return {}
    metadata = {
        "intent_id": _text(raw_requirement.get("intent_id")),
        "intent_type": _text(raw_requirement.get("type") or raw_requirement.get("intent_type")),
        "precondition": _text(raw_requirement.get("precondition")),
        "source_asset_id": _text(raw_requirement.get("source_asset_id")),
        "source_asset_title": _text(raw_requirement.get("source_asset_title")),
    }
    return {key: value for key, value in metadata.items() if value}


def _existing_case_id_for_source_intent(
    db: Session,
    *,
    project: str,
    page: str,
    source_asset_id: str,
    intent_id: str,
) -> str:
    """查找同一源资产和 intent_id 已生成的用例编号。"""
    normalized_project = _text(project)
    normalized_page = workbench_gate_service.normalize_page_slug(_text(page)) if _text(page) else ""
    normalized_asset = _safe_case_id(source_asset_id)
    normalized_intent = _text(intent_id)
    if not normalized_project or not normalized_asset or not normalized_intent:
        return ""
    repo = TestCaseRepository(db)
    candidates = repo.list_filtered(
        project_code=normalized_project,
        page_code=normalized_page if normalized_page else None,
        order_by=TestCase.updated_at.desc(),
    )
    legacy_intent_match = ""
    for case in candidates:
        case_asset_id, case_intent_ids = _source_identity_from_case(case)
        if _safe_case_id(case_asset_id) == normalized_asset and normalized_intent in case_intent_ids:
            return _text(case.case_id)
        if not _safe_case_id(case_asset_id) and normalized_intent in case_intent_ids and not legacy_intent_match:
            legacy_intent_match = _text(case.case_id)
    if legacy_intent_match:
        return legacy_intent_match
    return ""


def _case_family_prefix(case_id: str) -> str:
    """提取用例编号家族前缀，用于识别同源用例。"""
    normalized = _safe_case_id(case_id)
    matched = normalized.rsplit("-", 1)
    if len(matched) == 2 and matched[1].isdigit():
        return f"{matched[0]}-"
    return normalized


def _point_title(point: dict[str, Any]) -> str:
    """从测试点字段中解析用于展示和生成的标题。"""
    snapshot = point.get("metadata", {}) if isinstance(point.get("metadata"), dict) else {}
    candidate = snapshot.get("candidate_snapshot", {}) if isinstance(snapshot.get("candidate_snapshot"), dict) else {}
    return (
        _text(point.get("title"))
        or _text(point.get("description"))
        or _text(point.get("summary"))
        or _text(candidate.get("title"))
        or _text(candidate.get("summary"))
        or _text(point.get("intent_id") or point.get("key"))
    )


def _point_review_status(point: dict[str, Any]) -> str:
    """解析测试点当前评审状态并提供 pending 默认值。"""
    return _review_status_from_point(point)



# ═══════════════════════════════════════════════════════════════
# Generation diagnostics —— 生成失败记录、诊断信息
# ═══════════════════════════════════════════════════════════════
def _generated_case_plan_items(project: str) -> list[dict[str, Any]]:
    """读取项目下已生成用例计划项，供失败诊断和列表聚合使用。"""
    project_dir = Path(constants.GENERATED_CASES_STATE_ROOT) / (_text(project) or "mall") / "plans"
    if not project_dir.exists():
        return []
    items: list[dict[str, Any]] = []
    for path in sorted(project_dir.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(payload, dict):
            payload["_state_path"] = str(path)
            items.append(payload)
    return items


def _generation_failure_summary(detail: Any) -> dict[str, str]:
    """将生成失败详情归一化为类型、原因和建议。"""
    payload = detail if isinstance(detail, dict) else {}
    raw_text = _text(detail)
    code = _text(payload.get("code")) or ("generate_failed" if raw_text else "")
    message = _text(payload.get("message")) or raw_text or "生成失败，未返回具体原因"
    reason = _text(payload.get("reason") or payload.get("upstream_error")) or message
    stage = _text(payload.get("stage")) or ("compile" if code else "")
    normalized = f"{code} {message} {reason}".lower()
    failure_type = "编译失败"
    suggestion = "请补齐测试点步骤、目标元素或 DSL 语义后重新生成。"
    if "unsupported explicit step hint" in normalized or "刷新当前页面" in reason:
        failure_type = "语义步骤暂不支持"
        suggestion = "将“刷新当前页面”沉淀为 DSL 原子动作 refresh_page，或改写为可执行步骤后重新生成。"
    elif "target_binding_failed" in normalized or "business_type" in normalized:
        failure_type = "元素绑定失败"
        suggestion = "检查测试点步骤动作与页面对象元素类型是否匹配，例如输入框不能作为点击目标。"
    elif "input step requires explicit target" in normalized or "explicit target" in normalized:
        failure_type = "步骤目标缺失"
        suggestion = "为该测试点补充明确 target，例如页面 URL、地址栏或具体页面元素。"
    elif "intent_coverage" in normalized or "compiled steps do not strictly match" in normalized:
        failure_type = "意图覆盖不一致"
        suggestion = "检查 selected_intent_ids 与编译后步骤 intent_id 是否一致，避免脚本遗漏所选测试点。"
    return {
        "code": code,
        "message": message,
        "reason": reason,
        "stage": stage or "compile",
        "failure_type": failure_type,
        "suggestion": suggestion,
    }


def _record_generation_failure(
    *,
    project: str,
    asset_id: str,
    page: str,
    intent_id: str,
    title: str,
    detail: Any,
) -> dict[str, str]:
    """记录单个测试点资产生成失败信息，便于后续问题追踪。"""
    summary = _generation_failure_summary(detail)
    entry = {
        "timestamp": store.now_iso(),
        "action": "test_case_generation_failed",
        "project": _text(project) or "mall",
        "asset_id": _safe_case_id(asset_id),
        "page": workbench_gate_service.normalize_page_slug(_text(page)),
        "intent_id": _text(intent_id),
        "title": _text(title),
        "code": summary["code"],
        "message": summary["message"],
        "reason": summary["reason"],
        "stage": summary["stage"],
        "failure_type": summary["failure_type"],
        "suggestion": summary["suggestion"],
        "detail": detail if isinstance(detail, dict) else _text(detail),
    }
    store.append_history(entry)
    return summary


def _generation_failure_index(project: str, asset_id: str = "") -> dict[str, dict[str, Any]]:
    """构建项目维度的生成失败索引，可按资产过滤。"""
    normalized_project = _text(project) or "mall"
    normalized_asset = _safe_case_id(asset_id)
    failures: dict[str, dict[str, Any]] = {}
    for item in store.read_history_items():
        if _text(item.get("action")) != "test_case_generation_failed":
            continue
        if _text(item.get("project")) != normalized_project:
            continue
        item_asset = _safe_case_id(_text(item.get("asset_id")))
        if normalized_asset and item_asset != normalized_asset:
            continue
        intent_id = _text(item.get("intent_id"))
        if not item_asset or not intent_id:
            continue
        key = f"{item_asset}::{intent_id}"
        previous = failures.get(key)
        if previous and _text(previous.get("timestamp")) >= _text(item.get("timestamp")):
            continue
        failures[key] = dict(item)
    return failures


def _build_generation_diagnostics_for_asset(project: str, asset: dict[str, Any]) -> dict[str, Any]:
    """为测试点资产构建生成前诊断信息与阻塞原因。"""
    asset_payload = asset if isinstance(asset, dict) else {}
    asset_id = _safe_case_id(_text(asset_payload.get("asset_id") or asset_payload.get("case_id")))
    page = workbench_gate_service.normalize_page_slug(_text(asset_payload.get("page")))
    plan = asset_payload.get("plan", {}) if isinstance(asset_payload.get("plan"), dict) else {}
    raw_points = plan.get("points") if isinstance(plan.get("points"), list) else asset_payload.get("points")
    points = [point for point in (raw_points if isinstance(raw_points, list) else []) if isinstance(point, dict)]
    approved_points: list[dict[str, str]] = []
    for point in points:
        intent_id = _text(point.get("intent_id") or point.get("key"))
        if not intent_id or _point_review_status(point) != "approved":
            continue
        approved_points.append({"intent_id": intent_id, "title": _point_title(point)})

    family_prefix = _case_family_prefix(asset_id)
    generated_by_intent: dict[str, list[dict[str, str]]] = defaultdict(list)
    for generated in _generated_case_plan_items(project):
        generated_page = workbench_gate_service.normalize_page_slug(_text(generated.get("page")))
        generated_case_id = _safe_case_id(_text(generated.get("case_id") or generated.get("asset_id")))
        if page and generated_page and generated_page != page:
            continue
        generated_plan = generated.get("plan", {}) if isinstance(generated.get("plan"), dict) else {}
        points_payload = generated.get("points") if isinstance(generated.get("points"), list) else generated_plan.get("points")
        if not isinstance(points_payload, list):
            points_payload = []
        for point in points_payload:
            if not isinstance(point, dict):
                continue
            intent_id = _text(point.get("intent_id") or point.get("key"))
            if not intent_id:
                continue
            snapshot = point.get("metadata", {}) if isinstance(point.get("metadata"), dict) else {}
            candidate = snapshot.get("candidate_snapshot", {}) if isinstance(snapshot.get("candidate_snapshot"), dict) else {}
            source_asset_id = _safe_case_id(_text(candidate.get("source_asset_id") or generated.get("source_asset_id")))
            source_matches = source_asset_id == asset_id if source_asset_id else bool(family_prefix and generated_case_id.startswith(family_prefix))
            if not source_matches:
                continue
            generated_by_intent[intent_id].append(
                {
                    "case_id": generated_case_id,
                    "title": _text(generated.get("title")) or _point_title(point),
                    "state_path": _text(generated.get("_state_path")),
                }
            )

    approved_ids = [item["intent_id"] for item in approved_points]
    generated_ids = sorted(generated_by_intent.keys())
    failure_index = _generation_failure_index(project, asset_id)
    missing = []
    for item in approved_points:
        if item["intent_id"] in generated_by_intent:
            continue
        failure = failure_index.get(f"{asset_id}::{item['intent_id']}", {})
        missing_item = {
            "intent_id": item["intent_id"],
            "title": item["title"],
            "reason": _text(failure.get("code")) or "approved_but_not_generated",
            "message": _text(failure.get("message")) or "该测试点已审核通过，但当前生成状态中没有对应可用用例。",
            "failure_type": _text(failure.get("failure_type")),
            "failure_stage": _text(failure.get("stage")),
            "failed_at": _text(failure.get("timestamp")),
            "suggestion": _text(failure.get("suggestion")),
            "detail": failure.get("detail") if isinstance(failure.get("detail"), (dict, str)) else "",
        }
        missing.append(missing_item)
    duplicates = [
        {
            "intent_id": intent_id,
            "title": next((item["title"] for item in approved_points if item["intent_id"] == intent_id), intent_id),
            "case_ids": [item["case_id"] for item in rows],
            "items": rows,
            "message": "同一测试点意图存在多条生成用例，请保留最新或最可信的一条，其余标记废弃或删除。",
        }
        for intent_id, rows in sorted(generated_by_intent.items())
        if len(rows) > 1
    ]
    return {
        "asset_id": asset_id,
        "approved_intent_count": len(approved_points),
        "generated_unique_intent_count": len([intent_id for intent_id in generated_ids if intent_id in approved_ids]),
        "missing_count": len(missing),
        "duplicate_intent_count": len(duplicates),
        "missing": missing,
        "duplicates": duplicates,
    }



# ═══════════════════════════════════════════════════════════════
# Asset index helpers —— 测试点资产索引、用例列表补充
# ═══════════════════════════════════════════════════════════════
def _source_asset_index(project: str) -> dict[str, dict[str, str]]:
    """按来源资产和 intent_id 建立测试点资产索引。"""
    project_dir = workbench_asset_service.state_project_dir(project, state_root=constants.TEST_POINTS_ROOT)
    index: dict[str, dict[str, str]] = {}
    case_ids: set[str] = set()
    if project_dir.exists():
        case_ids.update(file.stem for file in project_dir.glob("*.json") if file.is_file())
        plans_dir = project_dir / "plans"
        if plans_dir.exists():
            case_ids.update(file.stem for file in plans_dir.glob("*.json") if file.is_file())
    prioritized_assets: list[tuple[int, str, dict[str, Any]]] = []
    for case_id in sorted(case_ids):
        asset = workbench_asset_service.load_test_point_asset_with_root(
            project,
            case_id,
            state_root=constants.TEST_POINTS_ROOT,
        )
        if not asset:
            continue
        source_type = _text(asset.get("source_type"))
        priority = 1 if source_type == "generate_chain" else 0
        prioritized_assets.append((priority, case_id, asset))
    for _priority, case_id, asset in sorted(prioritized_assets, key=lambda item: (item[0], item[1])):
        asset_id = _text(asset.get("asset_id")) or case_id
        asset_title = _text(asset.get("title")) or asset_id
        asset_page = workbench_gate_service.normalize_page_slug(_text(asset.get("page"))) if _text(asset.get("page")) else ""
        plan = asset.get("plan") if isinstance(asset.get("plan"), dict) else {}
        points = plan.get("points") if isinstance(plan.get("points"), list) else []
        for point in points:
            if not isinstance(point, dict):
                continue
            intent_id = _text(point.get("intent_id") or point.get("key"))
            if not intent_id:
                continue
            index_key = f"{asset_page}::{intent_id}"
            if index_key not in index:
                index[index_key] = {
                    "asset_id": asset_id,
                    "asset_title": asset_title,
                    "page": asset_page,
                    "intent_id": intent_id,
                    "intent_type": _text(_candidate_from_asset_point(point, fallback_title=asset_title, fallback_priority="P1").get("intent_type")),
                }
    return index


def _source_asset_for_case(case: TestCase, asset_index: dict[str, dict[str, str]]) -> dict[str, str]:
    """根据用例来源信息反查对应测试点资产摘要。"""
    page_code = workbench_gate_service.normalize_page_slug(_text(getattr(case, "page_code", ""))) if _text(getattr(case, "page_code", "")) else ""
    metadata = _structured_requirement_metadata_from_case(case)
    source_asset_id, intent_ids = _source_identity_from_case(case)
    for intent_id in intent_ids:
        hit = asset_index.get(f"{page_code}::{intent_id}")
        if hit:
            return hit
    if source_asset_id:
        return {
            "asset_id": source_asset_id,
            "asset_title": metadata.get("source_asset_title", "") or source_asset_id,
            "page": page_code,
            "intent_id": intent_ids[0] if intent_ids else metadata.get("intent_id", ""),
            "intent_type": metadata.get("intent_type", ""),
        }
    return {}


def _asset_title_index(project: str) -> dict[str, dict[str, str]]:
    """建立测试点资产标题索引，用于用例列表补充展示字段。"""
    project_dir = workbench_asset_service.state_project_dir(project, state_root=constants.TEST_POINTS_ROOT)
    index: dict[str, dict[str, str]] = {}
    if not project_dir.exists():
        return index
    for path in sorted(project_dir.glob("*.json")):
        asset = workbench_asset_service.load_test_point_asset_with_root(
            project,
            path.stem,
            state_root=constants.TEST_POINTS_ROOT,
        )
        if not asset:
            continue
        asset_id = _safe_case_id(_text(asset.get("asset_id") or path.stem))
        if not asset_id:
            continue
        index[asset_id] = {
            "asset_id": asset_id,
            "asset_title": _text(asset.get("title")) or asset_id,
            "page": workbench_gate_service.normalize_page_slug(_text(asset.get("page"))),
        }
    return index


def _intent_type_from_case(case: TestCase, source_asset: dict[str, str]) -> str:
    """从用例和来源资产中解析测试意图类型。"""
    if _text(source_asset.get("intent_type")):
        return _text(source_asset.get("intent_type"))
    scenario_types = case.scenario_types if isinstance(case.scenario_types, list) else []
    for item in scenario_types:
        if _text(item):
            return _text(item)
    tags = case.tags if isinstance(case.tags, list) else []
    for item in tags:
        value = _text(item)
        if value and value not in {"ai-generated", "login"}:
            return value
    return _text(case.case_type) or "functional"


def _active_state_from_case(case: TestCase) -> str:
    """将用例状态转换为列表视图使用的 active/deprecated 状态。"""
    return "deprecated" if _text(getattr(case, "status", "")).lower() == "deprecated" else "active"


def _page_object_url_map(db: Session, *, project: str, page_codes: list[str]) -> dict[str, str]:
    """批量查询页面对象 URL，供用例列表补充页面入口。"""
    repo = PageObjectRepository(db)
    normalized_codes = sorted({workbench_gate_service.normalize_page_slug(item) for item in page_codes if _text(item)})
    if not normalized_codes:
        return {}
    rows = repo.list_by_project_and_page_codes(_text(project) or "mall", "web", normalized_codes)
    return {str(row.page_code or "").strip(): _text(row.page_url) for row in rows}


def _latest_execution_map(db: Session, *, case_ids: list[int]) -> dict[int, TestCaseExecution]:
    """按用例数据库 ID 查询最近一次执行记录。"""
    if not case_ids:
        return {}
    repo = TestCaseRepository(db)
    rows = repo.list_executions_by_case_ids(case_ids)
    latest: dict[int, TestCaseExecution] = {}
    for row in rows:
        row_case_id = int(row.case_id or 0)
        if row_case_id and row_case_id not in latest:
            latest[row_case_id] = row
    return latest


def _persist_runtime_run_to_case_center(db: Session, run_item: dict[str, Any]) -> TestCaseExecution | None:
    """将运行态执行结果同步写入用例中心执行记录。

    委托给 workbench_runtime_service.persist_runtime_run_to_case_center。
    """
    return workbench_runtime_service.persist_runtime_run_to_case_center(db, run_item)


def _workbench_test_case_list_item(
    case: TestCase,
    *,
    source_asset: dict[str, str],
    page_url_map: dict[str, str],
    latest_execution: TestCaseExecution | None,
) -> dict[str, Any]:
    """将数据库用例模型转换为工作台用例列表项。"""
    page_code = _text(case.page_code or case.module)
    intent_type = _intent_type_from_case(case, source_asset)
    last_result = _text(getattr(latest_execution, "status", "")) or _text(case.last_execution_result) or "unknown"
    last_executed_at = getattr(latest_execution, "executed_at", None) if latest_execution else None
    return {
        "case_id": _text(case.case_id),
        "title": _text(case.name),
        "project": _text(case.project_code),
        "page": page_code,
        "page_name": _text(case.page_name or case.product_line),
        "page_url": page_url_map.get(page_code, ""),
        "intent_type": intent_type,
        "priority": _text(case.priority) or "P1",
        "source_asset_id": _text(source_asset.get("asset_id")),
        "source_asset_title": _text(source_asset.get("asset_title")),
        "intent_ids": _intent_ids_from_case_steps(case),
        "active_status": _active_state_from_case(case),
        "raw_status": _text(case.status),
        "automation_status": _text(case.automation_status),
        "last_execution_result": last_result,
        "last_executed_at": last_executed_at.isoformat() if hasattr(last_executed_at, "isoformat") else "",
        "last_report_url": _text(getattr(latest_execution, "report_url", "")) if latest_execution else _text(case.last_report_url),
        "updated_at": case.updated_at.isoformat() if hasattr(case.updated_at, "isoformat") else "",
        "created_at": case.created_at.isoformat() if hasattr(case.created_at, "isoformat") else "",
        "source_ref": _text(case.source_ref),
        "version": 0,
    }



# ═══════════════════════════════════════════════════════════════
# Candidate formatting —— 测试点→候选结构 转换
# ═══════════════════════════════════════════════════════════════
def _steps_from_candidate(candidate: dict[str, Any]) -> list[dict[str, Any]]:
    """将候选测试点步骤规范化为结构化用例步骤。"""
    steps = _text_list(candidate.get("steps"))
    if not steps:
        summary = _text(candidate.get("summary")) or _text(candidate.get("title")) or _text(candidate.get("intent_id"))
        steps = [summary] if summary else []
    if not steps:
        steps = ["手工维护测试点"]
    return [
        {
            "action": "candidate_step",
            "target": "",
            "value": step,
            "raw_text": step,
        }
        for step in steps
    ]


def _candidate_snapshot_from_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    """从候选测试点构造可落盘追踪的快照。"""
    snapshot: dict[str, Any] = {}
    for key in (
        "intent_id",
        "title",
        "summary",
        "intent_type",
        "priority",
        "precondition",
        "steps",
        "steps_hint",
        "expected",
        "expected_result",
        "involved_elements",
        "review_status",
        "review_note",
        "reviewed_at",
        "reviewed_by",
        "source_asset_id",
        "source_asset_title",
        "asset_id",
        "asset_title",
    ):
        value = candidate.get(key)
        if isinstance(value, list):
            rows = _text_list(value)
            if rows:
                snapshot[key] = rows
            continue
        text = _text(value)
        if text:
            snapshot[key] = text
    return snapshot


def _manual_point_from_candidate(candidate: dict[str, Any], *, index: int) -> dict[str, Any]:
    """将前端提交的候选项转换为手工维护测试点。"""
    intent_id = _text(candidate.get("intent_id")) or f"manual-intent-{index:02d}"
    title = _text(candidate.get("title")) or intent_id
    summary = _text(candidate.get("summary")) or title
    point_type = _text(candidate.get("intent_type")) or "functional"
    expected = _text(candidate.get("expected") or candidate.get("expected_result"))
    precondition = _text(candidate.get("precondition"))
    involved_elements = _text_list(candidate.get("involved_elements"))
    return {
        "key": intent_id,
        "intent_id": intent_id,
        "point_type": point_type,
        "action": "candidate",
        "description": summary,
        "step_index": index,
        "dependencies": [],
        "source_ids": [intent_id],
        "steps": _steps_from_candidate(candidate),
        "warnings": [],
        "requires_review": False,
        "involved_elements": involved_elements,
        "expected_result": expected,
        "precondition": precondition,
        "confidence": 0.8,
        "metadata": {
            "candidate_snapshot": _candidate_snapshot_from_candidate(candidate),
            "traceability": {
                "source_ids": [intent_id],
                "intent_ids": [intent_id],
            },
        },
    }


def _point_step_texts(point_steps: list[Any]) -> list[str]:
    """从测试点步骤结构中提取可读步骤文本。"""
    steps: list[str] = []
    for row in point_steps:
        if isinstance(row, str):
            text = _text(row)
        elif isinstance(row, dict):
            text = _text(row.get("raw_text") or row.get("value") or row.get("description") or row.get("action"))
        else:
            text = ""
        if text:
            steps.append(text)
    return steps


def _steps_hint_from_current_steps(point_steps: list[Any], involved_elements: list[str]) -> list[str]:
    """根据当前测试点步骤推导脚本生成可使用的步骤提示。"""
    hints: list[str] = []
    for row in point_steps:
        if not isinstance(row, dict):
            continue
        action = _text(row.get("action")).lower()
        target_name = _text(row.get("target_name") or row.get("target"))
        if target_name.startswith("element:"):
            target_name = target_name.split(":", 1)[1]
        if action in {"input", "fill"} and target_name:
            value = row.get("value")
            if value is not None and str(value) != " ":
                hints.append(f"input:{target_name}={value}")
            continue
        if action == "click" and target_name:
            hints.append(f"click:{target_name}")
            continue
        if action in {"assert_visible", "assert_text"} and target_name:
            prefix = "assert_text" if action == "assert_text" else "assert"
            value = _text(row.get("value"))
            hints.append(f"{prefix}:{target_name}={value}" if value else f"{prefix}:{target_name}")
            continue
        if action == "assert_url" and _text(row.get("value")):
            hints.append(f"assert_url:{_text(row.get('value'))}")
            continue
        if action == "goto" and _text(row.get("value")):
            hints.append(f"goto:{_text(row.get('value'))}")
            continue
    if hints:
        return _text_list(hints)

    for step in _point_step_texts(point_steps):
        if "点击" in step:
            element_name = _element_name_from_step(step, involved_elements)
            if element_name:
                hints.append(f"click:{element_name}")
                continue
        if "输入" in step or "填写" in step:
            element_name = _element_name_from_step(step, involved_elements)
            if element_name:
                value = _input_value_from_step(step, element_name).strip(" ，,。;；")
                hints.append(f"input:{element_name}={value}")
                continue
    return hints


def _candidate_from_asset_point(point: dict[str, Any], *, fallback_title: str, fallback_priority: str) -> dict[str, Any]:
    """将资产中的测试点转换为用例生成候选结构。"""
    snapshot = _candidate_snapshot_from_point(point)
    intent_id = _text(point.get("intent_id")) or _text(point.get("key"))
    if not intent_id:
        intent_id = _text(snapshot.get("intent_id"))
    title = (
        _text(point.get("title") or point.get("description") or point.get("summary"))
        or _text(snapshot.get("title") or snapshot.get("summary"))
        or fallback_title
        or intent_id
        or "测试点"
    )
    expected = _text(point.get("expected_result") or point.get("expected") or snapshot.get("expected") or snapshot.get("expected_result"))
    precondition = _text(point.get("precondition") or snapshot.get("precondition"))
    snapshot_steps = _text_list(snapshot.get("steps"))
    point_steps = point.get("steps") if isinstance(point.get("steps"), list) else []
    current_steps = _point_step_texts(point_steps)
    steps: list[str] = current_steps or _text_list(point.get("steps_hint")) or snapshot_steps or _text_list(snapshot.get("steps_hint"))
    involved_elements = _text_list(point.get("involved_elements")) or _text_list(snapshot.get("involved_elements"))
    current_steps_hint = _steps_hint_from_current_steps(point_steps, involved_elements)
    saved_steps_hint = _text_list(point.get("steps_hint")) or _text_list(snapshot.get("steps_hint"))
    merged_steps_hint = _text_list([*current_steps_hint, *saved_steps_hint])
    return {
        "intent_id": intent_id or "manual-intent",
        "title": title,
        "summary": title,
        "intent_type": _text(point.get("intent_type") or point.get("point_type") or snapshot.get("intent_type")) or "functional",
        "priority": _text(point.get("priority") or snapshot.get("priority")) or fallback_priority or "P1",
        "precondition": precondition,
        "steps": steps,
        "steps_hint": merged_steps_hint,
        "expected": expected,
        "expected_result": expected,
        "involved_elements": involved_elements,
        "review_status": _review_status_from_point(point),
        "review_note": _text(point.get("review_note") or snapshot.get("review_note")),
        "reviewed_at": _text(point.get("reviewed_at") or snapshot.get("reviewed_at")),
        "reviewed_by": _text(point.get("reviewed_by") or snapshot.get("reviewed_by")),
    }








class WorkbenchFacade:
    """Workbench 门面层：对外提供聚合后的业务接口。"""

    def __init__(self, service: WorkbenchService | None = None) -> None:
        """允许注入 service，便于测试替身和分层调用。"""
        self._service = service or WorkbenchService()

    def list_projects(self, db: Any) -> dict[str, Any]:
        """列出项目字典与可用项目视图。"""
        return self._service.list_projects(db)

    def list_execution_tasks(self, **kwargs: Any) -> dict[str, Any]:
        """查询执行任务列表（支持筛选参数透传）。"""
        return self._service.list_execution_tasks(**kwargs)

    def get_execution_task(self, task_id: str, db: Any) -> dict[str, Any]:
        """查询单个执行任务详情。"""
        return self._service.get_execution_task(task_id, db)

    def get_execution_gate_config(self) -> dict[str, Any]:
        """WorkbenchFacade.get_execution_gate_config 接口实现。"""
        return self._service.get_execution_gate_config()

    def heal_run(self, run_id: str) -> dict[str, Any]:
        """WorkbenchFacade.heal_run 接口实现。"""
        return self._service.heal_run(run_id)

    def heal_and_rerun_case(self, run_id: str, wait_seconds: int) -> dict[str, Any]:
        """WorkbenchFacade.heal_and_rerun_case 接口实现。"""
        return self._service.heal_and_rerun_case(run_id, wait_seconds)

    def save_review(self, payload: Any, request: Any, db: Session | None = None) -> dict[str, Any]:
        """保存评审记录；若传入 db 则附带 case center 一致性校验。"""
        if db is not None and str(getattr(payload, "case_id", "") or "").strip():
            case_center_case_ids = workbench_case_consistency_service.load_case_center_case_ids(db)
            if not workbench_case_consistency_service.is_case_tracked(
                getattr(payload, "case_id", ""),
                case_center_case_ids=case_center_case_ids,
            ):
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="case_id not found in case center")
        return self._service.save_review(payload, request)

    def save_execution_gate_decision(self, payload: Any, request: Any, db: Any) -> dict[str, Any]:
        """WorkbenchFacade.save_execution_gate_decision 接口实现。"""
        return self._service.save_execution_gate_decision(payload, request, db)

    def approve_execution_gate_decision(self, payload: Any, request: Any, db: Any) -> dict[str, Any]:
        """WorkbenchFacade.approve_execution_gate_decision 接口实现。"""
        return self._service.approve_execution_gate_decision(payload, request, db)

    def revoke_execution_gate_decision(self, payload: Any, request: Any, db: Any) -> dict[str, Any]:
        """WorkbenchFacade.revoke_execution_gate_decision 接口实现。"""
        return self._service.revoke_execution_gate_decision(payload, request, db)

    def report_allure_refresh(self, response: Any) -> dict[str, Any]:
        """WorkbenchFacade.report_allure_refresh 接口实现。"""
        return self._service.report_allure_refresh(response)

    def get_case_dictionaries(self) -> dict[str, Any]:
        """WorkbenchFacade.get_case_dictionaries 接口实现。"""
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

    def list_cases(
        self,
        *,
        project: str,
        page: int,
        page_size: int,
        focus_case_id: str,
        db: Session,
    ) -> dict[str, Any]:
        """分页查询用例列表，并按 case center 做一致性过滤。"""
        store.ensure_dirs()
        case_center_case_ids = workbench_case_consistency_service.load_case_center_case_ids(db)

        def _collect_case_items_filtered(project_code: str) -> list[dict[str, Any]]:
            """WorkbenchFacade._collect_case_items_filtered 接口实现。"""
            items = workbench_asset_service.collect_case_items(
                project_code,
                state_project_dir_fn=lambda code: workbench_asset_service.state_project_dir(
                    code,
                    state_root=constants.TEST_POINTS_ROOT,
                ),
                resolve_case_yaml_path_fn=lambda project_value, case_id_value: workbench_asset_service.resolve_case_yaml_path(
                    project_value,
                    case_id_value,
                    state_case_file_fn=lambda project_value_inner, case_value_inner: workbench_asset_service.state_case_file(
                        project_value_inner,
                        case_value_inner,
                        state_root=constants.TEST_POINTS_ROOT,
                    ),
                    repo_root=constants.REPO_ROOT,
                    assets_cases_root=constants.ASSETS_CASES_ROOT,
                    ai_cases_root=constants.AI_CASES_ROOT,
                    is_within_fn=_is_within,
                ),
                ai_cases_root=constants.AI_CASES_ROOT,
            )
            filtered_items, _filter_meta = workbench_case_consistency_service.filter_records_by_case_center(
                items,
                case_center_case_ids=case_center_case_ids,
            )
            return filtered_items

        return workbench_asset_service.build_cases_payload(
            project=project,
            page=page,
            page_size=page_size,
            focus_case_id=focus_case_id,
            collect_case_items=_collect_case_items_filtered,
            paginate_case_items=workbench_asset_service.paginate_case_items,
        )

    def get_case(self, *, case_id: str, project: str, db: Session) -> dict[str, Any]:
        """获取单个用例详情（含 case center 存在性校验）。"""
        store.ensure_dirs()
        case_center_case_ids = workbench_case_consistency_service.load_case_center_case_ids(db)
        if not workbench_case_consistency_service.is_case_tracked(
            case_id,
            case_center_case_ids=case_center_case_ids,
        ):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="case not found")
        return workbench_asset_service.build_case_detail(
            project=project,
            case_id=case_id,
            resolve_case_yaml_path=lambda project_value, case_id_value: workbench_asset_service.resolve_case_yaml_path(
                project_value,
                case_id_value,
                state_case_file_fn=lambda project_value_inner, case_value_inner: workbench_asset_service.state_case_file(
                    project_value_inner,
                    case_value_inner,
                    state_root=constants.TEST_POINTS_ROOT,
                ),
                repo_root=constants.REPO_ROOT,
                assets_cases_root=constants.ASSETS_CASES_ROOT,
                ai_cases_root=constants.AI_CASES_ROOT,
                is_within_fn=_is_within,
            ),
            read_case_yaml=workbench_asset_service.read_case_yaml,
        )

    def save_case(self, case_id: str, payload: Any, db: Session | None = None) -> dict[str, Any]:
        """保存用例内容；可选执行 case center 归属校验。"""
        if db is not None:
            case_center_case_ids = workbench_case_consistency_service.load_case_center_case_ids(db)
            if not workbench_case_consistency_service.is_case_tracked(
                case_id,
                case_center_case_ids=case_center_case_ids,
            ):
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="case not found")
        return self._service.save_case(case_id, payload)

    def list_test_point_assets(
        self,
        *,
        project: str,
        page: str,
        keyword: str,
        source_type: str,
        coverage_status: str,
        review_status: str,
        gate_decision: str,
        selection_state: str,
        db: Session,
    ) -> dict[str, Any]:
        """WorkbenchFacade.list_test_point_assets 接口实现。"""
        store.ensure_dirs()
        payload = workbench_asset_service.build_test_point_asset_items(
            project=project,
            page=page,
            keyword=keyword,
            source_type=source_type,
            coverage_status=coverage_status,
            review_status=review_status,
            gate_decision=gate_decision,
            selection_state=selection_state,
            state_project_dir=lambda code: workbench_asset_service.state_project_dir(code, state_root=constants.TEST_POINTS_ROOT),
            normalize_page_slug=workbench_gate_service.normalize_page_slug,
            load_test_point_asset=lambda project_value, case_id_value: workbench_asset_service.load_test_point_asset_with_root(
                project_value,
                case_id_value,
                state_root=constants.TEST_POINTS_ROOT,
            ),
            latest_run_snapshot_for_case=lambda project, case_id, page="": workbench_asset_service.latest_run_snapshot_for_case(
                project=project,
                case_id=case_id,
                page=page,
                safe_case_id_fn=workbench_gate_service.safe_case_id,
                normalize_page_slug_fn=workbench_gate_service.normalize_page_slug,
                runtime_jobs=store.list_run_jobs(),
                runtime_runs_file=constants.RUNTIME_RUNS_FILE,
                runtime_view_with_execution_record_preferred_fn=lambda item: item if isinstance(item, dict) else {},
                read_json_list_fn=store.read_json_list,
                build_review_audit_summary_fn=workbench_review_service.build_review_audit_summary,
                build_page_semantic_summary_fn=workbench_analysis_service.build_page_semantic_summary,
                build_execution_gate_audit_snapshot_fn=workbench_gate_service.build_execution_gate_audit_snapshot,
                build_risk_report_summary_fn=workbench_analysis_service.build_risk_report_summary,
            ),
            build_traceability_summary=lambda asset, latest_run: workbench_asset_service.build_test_point_asset_traceability_summary(
                asset=asset,
                latest_run=latest_run,
                build_test_point_asset_technique_summary_fn=workbench_asset_service.build_test_point_asset_technique_summary,
                build_review_audit_summary_fn=workbench_review_service.build_review_audit_summary,
                build_page_semantic_summary_fn=workbench_analysis_service.build_page_semantic_summary,
                build_risk_report_summary_fn=workbench_analysis_service.build_risk_report_summary,
                build_execution_gate_fn=workbench_gate_service.build_execution_gate,
                build_execution_gate_audit_snapshot_fn=workbench_gate_service.build_execution_gate_audit_snapshot,
                clamp_confidence=page_analysis_rules.clamp_confidence,
            ),
            build_selection_summary=lambda traceability_summary: workbench_asset_service.build_test_point_asset_selection_summary(
                traceability_summary=traceability_summary
            ),
            build_coverage_summary=lambda items, filter_snapshot: workbench_asset_service.build_test_point_asset_coverage_summary(
                items=items,
                filter_snapshot=filter_snapshot,
            ),
            clamp_confidence=page_analysis_rules.clamp_confidence,
        )
        payload["coverage_summary"] = workbench_asset_service.build_test_point_asset_coverage_summary(
            items=payload.get("items", []),
            filter_snapshot=payload["selection_summary"].get("filter_snapshot", {}),
        )
        return payload

    def get_test_point_asset_coverage_summary(self, *, project: str, page: str, keyword: str, source_type: str, coverage_status: str, review_status: str, gate_decision: str, selection_state: str, db: Session) -> dict[str, Any]:
        """WorkbenchFacade.get_test_point_asset_coverage_summary 接口实现。"""
        payload = self.list_test_point_assets(
            project=project,
            page=page,
            keyword=keyword,
            source_type=source_type,
            coverage_status=coverage_status,
            review_status=review_status,
            gate_decision=gate_decision,
            selection_state=selection_state,
            db=db,
        )
        return {"item": payload.get("coverage_summary", {})}

    def list_test_point_reviews(
        self,
        *,
        project: str,
        page: str,
        keyword: str,
        status_filter: str,
        intent_type: str,
        priority: str,
        can_generate: str,
        page_index: int,
        page_size: int,
        db: Session,
    ) -> dict[str, Any]:
        """WorkbenchFacade.list_test_point_reviews 接口实现。"""
        store.ensure_dirs()
        normalized_project = _text(project) or "mall"
        normalized_page = workbench_gate_service.normalize_page_slug(_text(page)) if _text(page) else ""
        normalized_status = _normalize_test_point_review_status(status_filter) if _text(status_filter) else ""
        normalized_type = _text(intent_type).lower()
        normalized_priority = _text(priority).upper()
        can_generate_filter = _text(can_generate).lower()
        keyword_value = _text(keyword).lower()
        project_dir = workbench_asset_service.state_project_dir(normalized_project, state_root=constants.TEST_POINTS_ROOT)
        case_ids: set[str] = set()
        if project_dir.exists():
            case_ids.update(file.stem for file in project_dir.glob("*.json") if file.is_file())
            plans_dir = project_dir / "plans"
            if plans_dir.exists():
                case_ids.update(file.stem for file in plans_dir.glob("*.json") if file.is_file())

        page_context_cache: dict[str, dict[str, Any]] = {}
        items: list[dict[str, Any]] = []
        for case_id in sorted(case_ids):
            asset = workbench_asset_service.load_test_point_asset_with_root(
                normalized_project,
                case_id,
                state_root=constants.TEST_POINTS_ROOT,
            )
            if not asset:
                continue
            asset_id = _text(asset.get("asset_id")) or case_id
            asset_page = workbench_gate_service.normalize_page_slug(_text(asset.get("page"))) if _text(asset.get("page")) else ""
            if normalized_page and asset_page != normalized_page:
                continue
            plan = asset.get("plan") if isinstance(asset.get("plan"), dict) else {}
            points = [point for point in plan.get("points", []) if isinstance(point, dict)] if isinstance(plan.get("points"), list) else []
            if asset_page not in page_context_cache:
                page_context_cache[asset_page] = _page_object_generation_context(db, project=normalized_project, page=asset_page)
            page_context = page_context_cache[asset_page]
            for point in points:
                candidate = _candidate_from_asset_point(
                    point,
                    fallback_title=_text(asset.get("title")) or asset_id,
                    fallback_priority=_text(asset.get("priority")) or "P1",
                )
                point_status = _review_status_from_candidate(candidate)
                if normalized_status and point_status != normalized_status:
                    continue
                row_type = _text(candidate.get("intent_type")).lower()
                row_priority = _text(candidate.get("priority")).upper()
                if normalized_type and row_type != normalized_type:
                    continue
                if normalized_priority and row_priority != normalized_priority:
                    continue
                generation_state = _test_point_generation_state(point, page_context=page_context)
                if can_generate_filter in {"true", "yes", "ready", "can_generate", "available"} and generation_state["can_generate"] is not True:
                    continue
                if can_generate_filter in {"false", "no", "blocked", "block"} and generation_state["can_generate"] is True:
                    continue
                steps = _text_list(candidate.get("steps"))
                row = {
                    "asset_id": asset_id,
                    "asset_title": _text(asset.get("title")) or asset_id,
                    "project": normalized_project,
                    "page": asset_page,
                    "page_url": _text(page_context.get("page_url")),
                    "intent_id": _text(candidate.get("intent_id")),
                    "title": _text(candidate.get("title") or candidate.get("summary")),
                    "summary": _text(candidate.get("summary") or candidate.get("title")),
                    "intent_type": _text(candidate.get("intent_type")) or "functional",
                    "priority": _text(candidate.get("priority")) or _text(asset.get("priority")) or "P1",
                    "precondition": _text(candidate.get("precondition")),
                    "steps": steps,
                    "steps_summary": " / ".join(steps[:3]),
                    "expected": _text(candidate.get("expected") or candidate.get("expected_result")),
                    "involved_elements": _text_list(candidate.get("involved_elements")),
                    "review_status": point_status,
                    "review_note": _text(candidate.get("review_note")),
                    "reviewed_at": _text(candidate.get("reviewed_at")),
                    "reviewed_by": _text(candidate.get("reviewed_by")),
                    "element_binding_status": generation_state["element_binding_status"],
                    "involved_element_codes": generation_state["involved_element_codes"],
                    "unknown_elements": generation_state["unknown_elements"],
                    "element_bindings": generation_state["element_bindings"],
                    "can_generate": generation_state["can_generate"],
                    "generation_blockers": generation_state["generation_blockers"],
                    "review_history": _review_history_from_point(point),
                    "updated_at": _text(asset.get("updated_at")),
                }
                haystack = " ".join(
                    [
                        row["asset_id"],
                        row["asset_title"],
                        row["page"],
                        row["intent_id"],
                        row["title"],
                        row["summary"],
                        row["steps_summary"],
                        row["expected"],
                        " ".join(row["generation_blockers"]),
                    ]
                ).lower()
                if keyword_value and keyword_value not in haystack:
                    continue
                items.append(row)

        items.sort(
            key=lambda item: (
                str(item.get("updated_at", "")).strip(),
                str(item.get("asset_id", "")).strip(),
                str(item.get("intent_id", "")).strip(),
            ),
            reverse=True,
        )
        total_items = len(items)
        safe_page_size = max(1, min(int(page_size or 20), 200))
        total_pages = max(1, (total_items + safe_page_size - 1) // safe_page_size) if total_items else 1
        safe_page = max(1, min(int(page_index or 1), total_pages))
        start = (safe_page - 1) * safe_page_size
        end = start + safe_page_size
        page_items = items[start:end]
        summary = {
            "total": total_items,
            "pending_count": sum(1 for item in items if item.get("review_status") == "pending"),
            "approved_count": sum(1 for item in items if item.get("review_status") == "approved"),
            "rejected_count": sum(1 for item in items if item.get("review_status") == "rejected"),
            "can_generate_count": sum(1 for item in items if item.get("can_generate") is True),
            "blocked_count": sum(1 for item in items if item.get("can_generate") is not True),
        }
        return {
            "items": page_items,
            "summary": summary,
            "filters": {
                "project": normalized_project,
                "page": normalized_page,
                "keyword": keyword_value,
                "status": normalized_status,
                "intent_type": normalized_type,
                "priority": normalized_priority,
                "can_generate": can_generate_filter,
            },
            "pagination": {
                "page": safe_page,
                "page_size": safe_page_size,
                "total_items": total_items,
                "total_pages": total_pages,
                "has_prev": safe_page > 1,
                "has_next": safe_page < total_pages,
            },
        }

    def batch_review_test_points(self, *, payload: Any, db: Session) -> dict[str, Any]:
        """WorkbenchFacade.batch_review_test_points 接口实现。"""
        store.ensure_dirs()
        normalized_project = _text(getattr(payload, "project", "")) or "mall"
        project_record = test_project_service.ensure_project_active_for_write(db, normalized_project)
        normalized_project = _text(getattr(project_record, "project_code", normalized_project)) or normalized_project
        next_status = _validate_test_point_review_status(getattr(payload, "status", ""))
        note = _text(getattr(payload, "note", ""))
        reviewed_by = _text(getattr(payload, "reviewed_by", "")) or "admin"
        reviewed_at = store.now_iso()
        grouped: dict[str, set[str]] = defaultdict(set)
        for decision in getattr(payload, "decisions", []) or []:
            asset_id = _safe_case_id(getattr(decision, "asset_id", "") if not isinstance(decision, dict) else decision.get("asset_id", ""))
            intent_id = _text(getattr(decision, "intent_id", "") if not isinstance(decision, dict) else decision.get("intent_id", ""))
            if asset_id and intent_id:
                grouped[asset_id].add(intent_id)
        if not grouped:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="decisions must not be empty")

        updated_count = 0
        affected_assets: list[str] = []
        missing: list[dict[str, str]] = []
        for asset_id, intent_ids in grouped.items():
            asset_path, plan_path = _test_point_asset_state_paths(normalized_project, asset_id)
            asset_payload = _read_json_file(asset_path)
            plan_payload = _read_json_file(plan_path)
            if not asset_payload and not plan_payload:
                missing.append({"asset_id": asset_id, "intent_id": "*", "reason": "asset_not_found"})
                continue
            plan = plan_payload if plan_payload else asset_payload.get("plan") if isinstance(asset_payload.get("plan"), dict) else {}
            if not isinstance(plan, dict) or not plan:
                missing.append({"asset_id": asset_id, "intent_id": "*", "reason": "plan_not_found"})
                continue
            points = [point for point in plan.get("points", []) if isinstance(point, dict)] if isinstance(plan.get("points"), list) else []
            changed_intent_ids: set[str] = set()
            for point in points:
                point_id = _text(point.get("intent_id") or point.get("key"))
                if point_id not in intent_ids:
                    continue
                point["review_status"] = next_status
                point["review_note"] = note if next_status == "rejected" else note
                point["reviewed_at"] = reviewed_at
                point["reviewed_by"] = reviewed_by
                metadata = point.get("metadata") if isinstance(point.get("metadata"), dict) else {}
                review_history = metadata.get("review_history") if isinstance(metadata.get("review_history"), list) else []
                review_history = [item for item in review_history if isinstance(item, dict)]
                review_history.append(
                    {
                        "reviewed_at": reviewed_at,
                        "reviewed_by": reviewed_by,
                        "status": next_status,
                        "note": note if next_status == "rejected" else note,
                    }
                )
                metadata["review_history"] = review_history
                point["metadata"] = metadata
                changed_intent_ids.add(point_id)
            metadata = plan.get("metadata") if isinstance(plan.get("metadata"), dict) else {}
            for intent_id in sorted(intent_ids - changed_intent_ids):
                missing.append({"asset_id": asset_id, "intent_id": intent_id, "reason": "intent_not_found"})
            if not changed_intent_ids:
                continue
            review_summary = {
                **(plan.get("review_summary") if isinstance(plan.get("review_summary"), dict) else {}),
                **_review_summary_from_points(points),
            }
            plan["review_summary"] = review_summary
            plan["updated_at"] = reviewed_at
            if metadata:
                metadata["review_updated_at"] = reviewed_at
                plan["metadata"] = metadata
            if plan_path.exists() or plan_payload:
                _write_json_file(plan_path, plan)
            if asset_payload:
                asset_payload["plan"] = plan
                asset_payload["review_summary"] = review_summary
                asset_payload["updated_at"] = reviewed_at
                asset_payload["version"] = int(asset_payload.get("version", 0) or 0) + 1
                _write_json_file(asset_path, asset_payload)
            updated_count += len(changed_intent_ids)
            affected_assets.append(asset_id)
        store.append_history(
            {
                "timestamp": reviewed_at,
                "action": "batch_review_test_points",
                "project": normalized_project,
                "status": next_status,
                "updated_count": updated_count,
                "asset_ids": affected_assets,
            },
            db=db,
        )
        return {
            "message": f"updated {updated_count} test points",
            "updated_count": updated_count,
            "status": next_status,
            "affected_assets": affected_assets,
            "missing": missing,
        }

    def list_workbench_test_cases(
        self,
        *,
        project: str,
        page: str,
        source_asset: str,
        intent_type: str,
        priority: str,
        execution_status: str,
        active_status: str,
        keyword: str,
        page_index: int,
        page_size: int,
        db: Session,
    ) -> dict[str, Any]:
        """WorkbenchFacade.list_workbench_test_cases 接口实现。"""
        normalized_project = _text(project) or "mall"
        normalized_page = workbench_gate_service.normalize_page_slug(_text(page)) if _text(page) else ""
        normalized_source_asset = _text(source_asset)
        normalized_intent_type = _text(intent_type).lower()
        normalized_priority = _text(priority).upper()
        normalized_execution_status = _text(execution_status).lower()
        normalized_active_status = _text(active_status).lower() or "active"
        keyword_value = _text(keyword).lower()
        stmt = select(TestCase).where(TestCase.project_code == normalized_project)
        if normalized_page:
            stmt = stmt.where(TestCase.page_code == normalized_page)
        if normalized_priority:
            stmt = stmt.where(TestCase.priority == normalized_priority)
        if normalized_execution_status:
            stmt = stmt.where(TestCase.last_execution_result == normalized_execution_status)
        if normalized_active_status == "deprecated":
            stmt = stmt.where(TestCase.status == "deprecated")
        elif normalized_active_status == "active":
            stmt = stmt.where(TestCase.status != "deprecated")
        cases = db.execute(stmt.order_by(TestCase.case_id.asc(), TestCase.id.asc())).scalars().all()
        asset_index = _source_asset_index(normalized_project)
        page_url_map = _page_object_url_map(
            db,
            project=normalized_project,
            page_codes=[_text(case.page_code) for case in cases],
        )
        latest_executions = _latest_execution_map(db, case_ids=[int(case.id) for case in cases])
        items: list[dict[str, Any]] = []
        for case in cases:
            source_asset_hit = _source_asset_for_case(case, asset_index)
            item = _workbench_test_case_list_item(
                case,
                source_asset=source_asset_hit,
                page_url_map=page_url_map,
                latest_execution=latest_executions.get(int(case.id)),
            )
            if normalized_source_asset and normalized_source_asset not in {
                _text(item.get("source_asset_id")),
                _text(item.get("source_asset_title")),
            }:
                continue
            if normalized_intent_type and _text(item.get("intent_type")).lower() != normalized_intent_type:
                continue
            haystack = " ".join(
                [
                    _text(item.get("case_id")),
                    _text(item.get("title")),
                    _text(item.get("source_asset_id")),
                    _text(item.get("source_asset_title")),
                    _text(item.get("page")),
                    _text(item.get("priority")),
                    _text(item.get("last_execution_result")),
                ]
            ).lower()
            if keyword_value and keyword_value not in haystack:
                continue
            items.append(item)
        total_items = len(items)
        safe_page_size = max(1, min(int(page_size or 20), 200))
        total_pages = max(1, (total_items + safe_page_size - 1) // safe_page_size) if total_items else 1
        safe_page = max(1, min(int(page_index or 1), total_pages))
        start = (safe_page - 1) * safe_page_size
        end = start + safe_page_size
        return {
            "items": items[start:end],
            "summary": {
                "total": total_items,
                "active_count": sum(1 for item in items if item.get("active_status") == "active"),
                "deprecated_count": sum(1 for item in items if item.get("active_status") == "deprecated"),
                "passed_count": sum(1 for item in items if item.get("last_execution_result") == "passed"),
                "failed_count": sum(1 for item in items if item.get("last_execution_result") == "failed"),
                "not_run_count": sum(1 for item in items if item.get("last_execution_result") in {"", "unknown"}),
            },
            "filters": {
                "project": normalized_project,
                "page": normalized_page,
                "source_asset": normalized_source_asset,
                "intent_type": normalized_intent_type,
                "priority": normalized_priority,
                "execution_status": normalized_execution_status,
                "active_status": normalized_active_status,
                "keyword": keyword_value,
            },
            "pagination": {
                "page": safe_page,
                "page_size": safe_page_size,
                "total_items": total_items,
                "total_pages": total_pages,
                "has_prev": safe_page > 1,
                "has_next": safe_page < total_pages,
            },
        }

    def list_test_case_generation_failures(
        self,
        *,
        project: str,
        asset_id: str,
        keyword: str,
        page_index: int,
        page_size: int,
    ) -> dict[str, Any]:
        """WorkbenchFacade.list_test_case_generation_failures 接口实现。"""
        normalized_project = _text(project) or "mall"
        normalized_asset = _safe_case_id(asset_id)
        keyword_value = _text(keyword).lower()
        asset_index = _asset_title_index(normalized_project)
        latest_failures = list(_generation_failure_index(normalized_project, normalized_asset).values())
        items: list[dict[str, Any]] = []
        for failure in sorted(latest_failures, key=lambda item: _text(item.get("timestamp")), reverse=True):
            item_asset_id = _safe_case_id(_text(failure.get("asset_id")))
            asset_meta = asset_index.get(item_asset_id, {})
            item = {
                "project": normalized_project,
                "asset_id": item_asset_id,
                "asset_title": _text(asset_meta.get("asset_title")) or item_asset_id,
                "page": _text(failure.get("page")) or _text(asset_meta.get("page")),
                "intent_id": _text(failure.get("intent_id")),
                "title": _text(failure.get("title")) or _text(failure.get("intent_id")),
                "failure_type": _text(failure.get("failure_type")) or "编译失败",
                "stage": _text(failure.get("stage")) or "compile",
                "code": _text(failure.get("code")),
                "message": _text(failure.get("message")),
                "reason": _text(failure.get("reason")),
                "suggestion": _text(failure.get("suggestion")),
                "failed_at": _text(failure.get("timestamp")),
                "detail": failure.get("detail") if isinstance(failure.get("detail"), (dict, str)) else "",
                "asset_url": f"/assets/test-points/{item_asset_id}?project={normalized_project}",
            }
            haystack = " ".join(
                [
                    item["asset_id"],
                    item["asset_title"],
                    item["page"],
                    item["intent_id"],
                    item["title"],
                    item["failure_type"],
                    item["stage"],
                    item["code"],
                    item["message"],
                    item["reason"],
                ]
            ).lower()
            if keyword_value and keyword_value not in haystack:
                continue
            items.append(item)
        total_items = len(items)
        safe_page_size = max(1, min(int(page_size or 20), 200))
        total_pages = max(1, (total_items + safe_page_size - 1) // safe_page_size) if total_items else 1
        safe_page = max(1, min(int(page_index or 1), total_pages))
        start = (safe_page - 1) * safe_page_size
        end = start + safe_page_size
        return {
            "items": items[start:end],
            "summary": {
                "total": total_items,
                "asset_count": len({_text(item.get("asset_id")) for item in items if _text(item.get("asset_id"))}),
                "intent_count": len({_text(item.get("intent_id")) for item in items if _text(item.get("intent_id"))}),
            },
            "filters": {
                "project": normalized_project,
                "asset_id": normalized_asset,
                "keyword": keyword_value,
            },
            "pagination": {
                "page": safe_page,
                "page_size": safe_page_size,
                "total_items": total_items,
                "total_pages": total_pages,
                "has_prev": safe_page > 1,
                "has_next": safe_page < total_pages,
            },
        }

    def get_workbench_test_case(self, *, case_id: str, project: str, db: Session) -> dict[str, Any]:
        """WorkbenchFacade.get_workbench_test_case 接口实现。"""
        normalized_project = _text(project) or "mall"
        normalized_case_id = _text(case_id)
        repo = TestCaseRepository(db)
        case = repo.get_by_case_id_and_project(normalized_case_id, normalized_project)
        if case is None:
            case = repo.get_by_case_id(normalized_case_id)
        if case is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="test case not found")
        detail = test_case_service.get_test_case_detail(db, str(case.id))
        case = detail.case
        source_asset_hit = _source_asset_for_case(case, _source_asset_index(_text(case.project_code) or normalized_project))
        page_url_map = _page_object_url_map(db, project=_text(case.project_code) or normalized_project, page_codes=[_text(case.page_code)])
        executions = (
            db.execute(
                select(TestCaseExecution)
                .where(TestCaseExecution.case_id == int(case.id))
                .order_by(TestCaseExecution.executed_at.desc(), TestCaseExecution.id.desc())
                .limit(5)
            )
            .scalars()
            .all()
        )
        versions = TestCaseRepository(db).list_versions_by_case_id(int(case.id), limit=10)
        latest_execution = executions[0] if executions else None
        requirement_metadata = _structured_requirement_metadata_from_case(case)
        item = _workbench_test_case_list_item(
            case,
            source_asset=source_asset_hit,
            page_url_map=page_url_map,
            latest_execution=latest_execution,
        )
        item.update(
            {
                "precondition": _text(case.precondition_state) or requirement_metadata.get("precondition", ""),
                "steps": case.test_steps if isinstance(case.test_steps, list) else [],
                "steps_text": _text(case.test_steps_text),
                "expected_result": _text(case.expected_result),
                "involved_elements": [
                    _text(step.get("target"))
                    for step in (case.test_steps if isinstance(case.test_steps, list) else [])
                    if isinstance(step, dict) and _text(step.get("target")) and _text(step.get("target")) != "element:"
                ],
                "script_code": _text(case.script_code),
                "source_ref": _text(case.source_ref),
                "versions": [
                    {
                        "version_no": int(version.version_no or 0),
                        "changed_by": _text(version.changed_by),
                        "change_summary": _text(version.change_summary),
                        "created_at": version.created_at.isoformat() if hasattr(version.created_at, "isoformat") else "",
                    }
                    for version in versions
                ],
                "executions": [
                    {
                        "status": _text(execution.status),
                        "duration_ms": int(execution.duration_ms or 0),
                        "report_url": _text(execution.report_url),
                        "executed_at": execution.executed_at.isoformat() if hasattr(execution.executed_at, "isoformat") else "",
                    }
                    for execution in executions
                ],
            }
        )
        return {"item": item}

    def delete_workbench_test_cases(
        self,
        *,
        project: str,
        case_ids: list[str],
        delete_all: bool,
        confirm_text: str = "",
        db: Session,
    ) -> dict[str, Any]:
        """WorkbenchFacade.delete_workbench_test_cases 接口实现。"""
        normalized_project = _text(project) or "mall"
        normalized_case_ids = [_text(item) for item in (case_ids or []) if _text(item)]
        if delete_all and _text(confirm_text) != f"清空{normalized_project}":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "delete_all_confirmation_required",
                    "message": f"请输入确认文本：清空{normalized_project}",
                },
            )
        if not delete_all and not normalized_case_ids:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="case_ids must not be empty",
            )

        stmt = select(TestCase.id, TestCase.case_id).where(TestCase.project_code == normalized_project)
        if not delete_all:
            stmt = stmt.where(TestCase.case_id.in_(normalized_case_ids))
        rows = db.execute(stmt.order_by(TestCase.id.asc())).all()
        found_case_ids = {_text(row_case_id) for _row_id, row_case_id in rows if _text(row_case_id)}
        missing_case_ids = [case_id for case_id in normalized_case_ids if case_id not in found_case_ids]

        if not rows:
            if not delete_all and len(normalized_case_ids) == 1:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="test case not found")
            return {
                "message": "no test cases deleted",
                "project": normalized_project,
                "deleted_count": 0,
                "deleted_case_ids": [],
                "missing_case_ids": missing_case_ids,
                "delete_all": bool(delete_all),
            }

        target_ids = [int(row_id) for row_id, _row_case_id in rows]
        deleted_case_ids = [_text(row_case_id) for _row_id, row_case_id in rows if _text(row_case_id)]
        deleted_count = int(test_case_service.batch_delete_test_cases(db, ids=target_ids) or 0)
        store.append_history(
            {
                "timestamp": _utc_now().isoformat(),
                "action": "delete_workbench_test_cases",
                "project": normalized_project,
                "delete_all": bool(delete_all),
                "deleted_count": deleted_count,
                "deleted_case_ids": deleted_case_ids,
                "missing_case_ids": missing_case_ids,
            },
            db=db,
        )
        return {
            "message": f"deleted {deleted_count} test cases",
            "project": normalized_project,
            "deleted_count": deleted_count,
            "deleted_case_ids": deleted_case_ids,
            "missing_case_ids": missing_case_ids,
            "delete_all": bool(delete_all),
        }

    def get_test_point_asset(self, *, asset_id: str, project: str, db: Session) -> dict[str, Any]:
        """WorkbenchFacade.get_test_point_asset 接口实现。"""
        store.ensure_dirs()
        payload = workbench_asset_service.build_test_point_asset_detail(
            project=project,
            asset_id=asset_id,
            load_test_point_asset=lambda project_value, case_id_value: workbench_asset_service.load_test_point_asset_with_root(
                project_value,
                case_id_value,
                state_root=constants.TEST_POINTS_ROOT,
            ),
            latest_run_snapshot_for_case=lambda project, case_id, page="": workbench_asset_service.latest_run_snapshot_for_case(
                project=project,
                case_id=case_id,
                page=page,
                safe_case_id_fn=workbench_gate_service.safe_case_id,
                normalize_page_slug_fn=workbench_gate_service.normalize_page_slug,
                runtime_jobs=store.list_run_jobs(),
                runtime_runs_file=constants.RUNTIME_RUNS_FILE,
                runtime_view_with_execution_record_preferred_fn=lambda item: item if isinstance(item, dict) else {},
                read_json_list_fn=store.read_json_list,
                build_review_audit_summary_fn=workbench_review_service.build_review_audit_summary,
                build_page_semantic_summary_fn=workbench_analysis_service.build_page_semantic_summary,
                build_execution_gate_audit_snapshot_fn=workbench_gate_service.build_execution_gate_audit_snapshot,
                build_risk_report_summary_fn=workbench_analysis_service.build_risk_report_summary,
            ),
            build_traceability_summary=lambda asset, latest_run: workbench_asset_service.build_test_point_asset_traceability_summary(
                asset=asset,
                latest_run=latest_run,
                build_test_point_asset_technique_summary_fn=workbench_asset_service.build_test_point_asset_technique_summary,
                build_review_audit_summary_fn=workbench_review_service.build_review_audit_summary,
                build_page_semantic_summary_fn=workbench_analysis_service.build_page_semantic_summary,
                build_risk_report_summary_fn=workbench_analysis_service.build_risk_report_summary,
                build_execution_gate_fn=workbench_gate_service.build_execution_gate,
                build_execution_gate_audit_snapshot_fn=workbench_gate_service.build_execution_gate_audit_snapshot,
                clamp_confidence=page_analysis_rules.clamp_confidence,
            ),
            build_selection_summary=lambda traceability_summary: workbench_asset_service.build_test_point_asset_selection_summary(
                traceability_summary=traceability_summary
            ),
            clamp_confidence=page_analysis_rules.clamp_confidence,
        )
        if not payload:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="test point asset not found")
        item = payload.get("item", {}) if isinstance(payload.get("item"), dict) else {}
        if item:
            item["generation_diagnostics"] = _build_generation_diagnostics_for_asset(project, item)
        return payload

    def get_test_point_asset_coverage_matrix(self, *, asset_id: str, project: str, db: Session) -> dict[str, Any]:
        """WorkbenchFacade.get_test_point_asset_coverage_matrix 接口实现。"""
        payload = self.get_test_point_asset(asset_id=asset_id, project=project, db=db)
        item = payload.get("item", {}) if isinstance(payload.get("item"), dict) else {}
        return {"item": item.get("coverage_matrix", {}) if isinstance(item.get("coverage_matrix"), dict) else {}}

    def upsert_test_point_asset(self, *, payload: Any, db: Session) -> dict[str, Any]:
        """WorkbenchFacade.upsert_test_point_asset 接口实现。"""
        store.ensure_dirs()
        project = _text(getattr(payload, "project", "")) or "mall"
        test_project_service.ensure_project_active_for_write(db, project)
        raw_asset_id = _text(getattr(payload, "asset_id", ""))
        if not raw_asset_id:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="asset_id must not be empty")
        asset_id = _safe_case_id(raw_asset_id)
        page = workbench_gate_service.normalize_page_slug(_text(getattr(payload, "page", "")))
        if not page:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="page must not be empty")
        title = _text(getattr(payload, "title", "")) or asset_id
        priority = _text(getattr(payload, "priority", "")) or "P1"
        source_type = _text(getattr(payload, "source_type", "")) or "manual"
        requirement = _text(getattr(payload, "requirement", "")) or title
        asset_path, existing_plan_path = _test_point_asset_state_paths(project, asset_id)
        existing_asset_payload = _read_json_file(asset_path)
        existing_plan_payload = _read_json_file(existing_plan_path)
        embedded_plan = (
            existing_asset_payload.get("plan")
            if isinstance(existing_asset_payload.get("plan"), dict)
            else {}
        )
        existing_plan = existing_plan_payload if isinstance(existing_plan_payload, dict) and existing_plan_payload else embedded_plan
        existing_points = (
            [point for point in existing_plan.get("points", []) if isinstance(point, dict)]
            if isinstance(existing_plan.get("points"), list)
            else []
        )
        incoming_points_raw = getattr(payload, "points", [])
        incoming_points = [item for item in incoming_points_raw if isinstance(item, dict)] if isinstance(incoming_points_raw, list) else []
        selected_candidates_raw = getattr(payload, "selected_candidates", [])
        selected_candidates = [item for item in selected_candidates_raw if isinstance(item, dict)]
        if incoming_points:
            points = incoming_points
        elif existing_points:
            points = existing_points
            if selected_candidates:
                LOGGER.warning(
                    "ignore selected_candidates for existing test point asset because plan.points is canonical: project=%s asset_id=%s",
                    project,
                    asset_id,
                )
                selected_candidates = []
        elif not selected_candidates:
            selected_candidates = [
                {
                    "intent_id": asset_id,
                    "title": title,
                    "summary": title,
                    "priority": priority,
                    "steps": [requirement],
                    "expected": "手工维护测试点",
                }
            ]
        if len(selected_candidates) > 200:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="selected_candidates exceeds max size 200")

        if not incoming_points and not existing_points:
            points = [_manual_point_from_candidate(candidate, index=index) for index, candidate in enumerate(selected_candidates, start=1)]
        page_context = _page_object_generation_context(db, project=project, page=page)
        points = _normalize_points_involved_elements(points, page_context=page_context)
        selected_intent_ids = [intent_id for intent_id in [_text(item.get("intent_id") or item.get("key")) for item in points] if intent_id]
        technique_distribution: dict[str, int] = {}
        for point in points:
            intent_type = _text(point.get("intent_type") or point.get("point_type")) or source_type or "manual"
            technique_distribution[intent_type] = int(technique_distribution.get(intent_type, 0) or 0) + 1
        existing_metadata = existing_plan.get("metadata") if isinstance(existing_plan.get("metadata"), dict) else {}
        selected_candidate_snapshots = (
            [_candidate_snapshot_from_candidate(candidate) for candidate in selected_candidates]
            if selected_candidates
            else existing_metadata.get("selected_candidates", [])
            if isinstance(existing_metadata.get("selected_candidates"), list)
            else []
        )
        plan = {
            "version": "TestPointPlanV1",
            "project": project,
            "case_id": asset_id,
            "page": page,
            "title": title,
            "priority": priority,
            "source_type": source_type,
            "requirement": [requirement],
            "generated_at": _text(existing_plan.get("generated_at")) or store.now_iso(),
            "points": points,
            "coverage": {
                "status": "preview",
                "coverage_ratio": 1.0 if points else 0.0,
                "generated_case_count": len(points),
                "expected_case_count": len(points),
                "missing_scenarios": [],
                "covered_scenarios": selected_intent_ids,
            },
            "review_summary": {
                "total_points": len(points),
                "mainline_point_count": len(points),
                "design_only_point_count": 0,
                "technique_distribution": technique_distribution,
            },
            "metadata": {
                **existing_metadata,
                "saved_by": "web-ui-service",
                "origin": source_type,
                "selected_intent_ids": selected_intent_ids,
                "selected_candidates": selected_candidate_snapshots,
                "asset_title": title,
                "normalized_requirement": requirement,
            },
            "involved_elements": _text_list(
                [
                    element
                    for point in points
                    for element in _text_list(point.get("involved_elements"))
                ]
            ),
            "confidence": 0.85,
            "warnings": [],
            "requires_review": False,
        }

        def _normalize_test_point_plan_payload(plan_payload: dict[str, Any], _strict: bool = False) -> dict[str, Any]:
            """WorkbenchFacade._normalize_test_point_plan_payload 接口实现。"""
            normalized_plan, _warnings = normalize_test_point_plan_v1(plan_payload)
            return normalized_plan

        def _upsert_test_point_asset_snapshot(**kwargs: Any) -> dict[str, Any]:
            """WorkbenchFacade._upsert_test_point_asset_snapshot 接口实现。"""
            return workbench_asset_service.upsert_test_point_asset_snapshot(
                **kwargs,
                now_iso_fn=store.now_iso,
                count_test_point_types_fn=workbench_asset_service.count_test_point_types,
                build_test_point_asset_semantic_summary_fn=lambda resolved_page, normalized_plan: workbench_asset_service.build_test_point_asset_semantic_summary(
                    page=resolved_page,
                    normalized_plan=normalized_plan,
                    normalize_page_slug_fn=workbench_gate_service.normalize_page_slug,
                    clamp_confidence=page_analysis_rules.clamp_confidence,
                ),
                build_test_point_asset_technique_summary_fn=lambda normalized_plan: workbench_asset_service.build_test_point_asset_technique_summary(
                    normalized_plan=normalized_plan
                ),
                merge_reference_items_fn=workbench_asset_service.merge_reference_items,
            )

        plan_path = workbench_asset_service.save_test_point_plan(
            project=project,
            case_id=asset_id,
            page=page,
            page_url="",
            requirement=requirement,
            plan=plan,
            now_iso_fn=store.now_iso,
            normalize_test_point_plan_payload=_normalize_test_point_plan_payload,
            upsert_test_point_asset_snapshot=_upsert_test_point_asset_snapshot,
            state_root=constants.TEST_POINTS_ROOT,
        )
        store.append_history(
            {
                "timestamp": store.now_iso(),
                "action": "upsert_test_point_asset",
                "project": project,
                "case_id": asset_id,
                "page": page,
                "path": str(plan_path.resolve()),
            },
            db=db,
        )
        detail = self.get_test_point_asset(asset_id=asset_id, project=project, db=db)
        item = detail.get("item", {}) if isinstance(detail.get("item"), dict) else {}
        return {
            "message": "test point asset saved",
            "count": 1 if item else 0,
            "item": item,
            "items": [item] if item else [],
        }

    def delete_test_point_asset(self, *, asset_id: str, project: str, db: Session, cascade_cases: bool = False) -> dict[str, Any]:
        """WorkbenchFacade.delete_test_point_asset 接口实现。"""
        store.ensure_dirs()
        normalized_project = _text(project) or "mall"
        project_record = test_project_service.ensure_project_active_for_write(db, normalized_project)
        normalized_project = _text(getattr(project_record, "project_code", normalized_project)) or normalized_project
        raw_asset_id = _text(asset_id)
        normalized_asset_id = _safe_case_id(raw_asset_id)
        candidate_asset_ids: list[str] = []
        for candidate in (normalized_asset_id, raw_asset_id):
            normalized_candidate = _text(candidate)
            if normalized_candidate and normalized_candidate not in candidate_asset_ids:
                candidate_asset_ids.append(normalized_candidate)
        removed_paths: list[str] = []
        removed_path_set: set[str] = set()

        def _remove_if_exists(path: Path) -> None:
            """WorkbenchFacade._remove_if_exists 接口实现。"""
            if not path.exists():
                return
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
            resolved_path = str(path.resolve())
            if resolved_path in removed_path_set:
                return
            removed_path_set.add(resolved_path)
            removed_paths.append(resolved_path)

        def _remove_asset_files_in_project(project_dir: Path) -> None:
            """WorkbenchFacade._remove_asset_files_in_project 接口实现。"""
            for candidate_asset_id in candidate_asset_ids:
                _remove_if_exists(project_dir / f"{candidate_asset_id}.json")
                _remove_if_exists(project_dir / "plans" / f"{candidate_asset_id}.json")
                _remove_if_exists(project_dir / "versions" / candidate_asset_id)

        # 1) Hard delete in current project.
        project_dir = workbench_asset_service.state_project_dir(normalized_project, state_root=constants.TEST_POINTS_ROOT)
        _remove_asset_files_in_project(project_dir)

        # 2) Linked cases are not deleted by default. Case deletion is a separate
        # destructive action and must be explicitly requested by a governance flow.
        deleted_case_count = 0
        if cascade_cases and Path(constants.ASSETS_CASES_ROOT).exists():
            for candidate_asset_id in candidate_asset_ids:
                for yaml_path in Path(constants.ASSETS_CASES_ROOT).rglob(f"{candidate_asset_id}.yaml"):
                    _remove_if_exists(yaml_path)

            try:
                deleted_case_count = int(test_case_service.batch_delete_test_cases(db, case_ids=candidate_asset_ids) or 0)
            except HTTPException as exc:
                if int(exc.status_code or 0) not in {status.HTTP_404_NOT_FOUND, status.HTTP_400_BAD_REQUEST}:
                    raise

        if not removed_paths and deleted_case_count <= 0:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="test point asset not found")
        store.append_history(
            {
                "timestamp": store.now_iso(),
                "action": "delete_test_point_asset",
                "project": normalized_project,
                "case_id": normalized_asset_id,
                "removed_paths": removed_paths,
                "cascade_cases": bool(cascade_cases),
                "deleted_case_count": deleted_case_count,
            },
            db=db,
        )
        return {
            "item": {
                "asset_id": normalized_asset_id,
                "project": normalized_project,
                "deleted": True,
                "deleted_count": len(removed_paths),
                "deleted_paths": removed_paths,
                "deleted_case_count": deleted_case_count,
                "cascade_cases": bool(cascade_cases),
                "asset_id_aliases": candidate_asset_ids,
            }
        }

    def batch_delete_test_point_assets(self, *, project: str, asset_ids: list[str], db: Session) -> dict[str, Any]:
        """WorkbenchFacade.batch_delete_test_point_assets 接口实现。"""
        normalized_project = _text(project) or "mall"
        deleted: list[str] = []
        missing: list[str] = []
        for raw_asset_id in asset_ids:
            candidate_asset_id = _text(raw_asset_id)
            if not candidate_asset_id:
                continue
            try:
                self.delete_test_point_asset(asset_id=candidate_asset_id, project=normalized_project, db=db)
                deleted.append(_safe_case_id(candidate_asset_id))
            except HTTPException as exc:
                if int(exc.status_code or 0) == status.HTTP_404_NOT_FOUND:
                    missing.append(_safe_case_id(candidate_asset_id))
                    continue
                raise
        return {
            "deleted_count": len(deleted),
            "deleted_asset_ids": deleted,
            "missing_count": len(missing),
            "missing_asset_ids": missing,
        }

    def generate_cases_from_test_point_assets(
        self,
        *,
        project: str,
        asset_ids: list[str],
        intent_ids: list[str] | None = None,
        source: str,
        db: Session,
    ) -> dict[str, Any]:
        """WorkbenchFacade.generate_cases_from_test_point_assets 接口实现。"""
        store.ensure_dirs()
        normalized_project = _text(project) or "mall"
        case_source = _normalize_generation_case_source(source)
        selected_asset_ids = [_safe_case_id(item) for item in asset_ids if _text(item)]
        selected_intent_filter = {_text(item) for item in (intent_ids or []) if _text(item)}
        if not selected_asset_ids:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="asset_ids must not be empty")
        usecase = build_generate_case_usecase(db)
        generated_items: list[dict[str, Any]] = []
        skipped_assets: list[dict[str, str]] = []
        processed_assets = 0

        for asset_id in selected_asset_ids:
            asset = workbench_asset_service.load_test_point_asset_with_root(
                normalized_project,
                asset_id,
                state_root=constants.TEST_POINTS_ROOT,
            )
            if not asset:
                skipped_assets.append({"asset_id": asset_id, "reason": "asset_not_found"})
                continue
            page = workbench_gate_service.normalize_page_slug(_text(asset.get("page")))
            if not page:
                skipped_assets.append({"asset_id": asset_id, "reason": "asset_page_empty"})
                continue
            page_context = _page_object_generation_context(db, project=normalized_project, page=page)
            if not bool(page_context.get("page_object_found")):
                skipped_assets.append(
                    {
                        "asset_id": asset_id,
                        "reason": "page_object_not_governed",
                        "message": "; ".join(str(item) for item in page_context.get("base_blockers", []) if str(item).strip()),
                    }
                )
                continue
            page_url = _text(page_context.get("page_url"))
            if not page_url:
                skipped_assets.append(
                    {
                        "asset_id": asset_id,
                        "reason": "page_object_url_missing",
                        "message": "请到页面对象管理补齐页面 URL",
                    }
                )
                continue
            if int(page_context.get("qualified_element_count", 0) or 0) <= 0:
                skipped_assets.append(
                    {
                        "asset_id": asset_id,
                        "reason": "page_object_no_qualified_elements",
                        "message": "页面对象缺少可生成元素：需满足 status=active + review_status=approved + stability_level 为 high/medium",
                    }
                )
                continue
            requirement_list = asset.get("requirement") if isinstance(asset.get("requirement"), list) else []
            requirement = _text(" ".join(_text(item) for item in requirement_list if _text(item))) or _text(asset.get("title")) or asset_id
            title = _text(asset.get("title")) or asset_id
            priority = _text(asset.get("priority")) or "P1"
            plan = asset.get("plan") if isinstance(asset.get("plan"), dict) else {}
            points = plan.get("points") if isinstance(plan.get("points"), list) else []
            approved_points = []
            for point in points:
                if not isinstance(point, dict) or _review_status_from_point(point) != "approved":
                    continue
                point_intent_id = _text(point.get("intent_id") or point.get("key"))
                if selected_intent_filter and point_intent_id not in selected_intent_filter:
                    continue
                approved_points.append(point)
            if not approved_points:
                message = "没有已通过测试点可生成"
                reason = "no_approved_test_points"
                if selected_intent_filter:
                    message = "所选测试点未通过审核或不存在，无法生成"
                    reason = "selected_intents_not_approved_or_missing"
                skipped_assets.append(
                    {
                        "asset_id": asset_id,
                        "reason": reason,
                        "message": message,
                    }
                )
                continue
            candidates = [
                _candidate_from_asset_point(point, fallback_title=title, fallback_priority=priority)
                for point in approved_points
                if isinstance(point, dict)
            ]
            for candidate in candidates:
                candidate["source_asset_id"] = asset_id
                candidate["source_asset_title"] = title
            if not candidates:
                skipped_assets.append(
                    {
                        "asset_id": asset_id,
                        "reason": "no_approved_test_points",
                        "message": "没有已通过测试点可生成",
                    }
                )
                continue
            # Generate one approved intent at a time. The compiler enforces strict
            # selected_intent_ids coverage, so a single bad test point must not
            # hide already generated cases or fail the whole asset batch.
            chunks = [[candidate] for candidate in candidates]
            if not chunks:
                chunks = [candidates]
            processed_assets += 1
            for chunk in chunks:
                selected_intent_ids = [
                    intent_id
                    for intent_id in [_text(item.get("intent_id")) for item in chunk]
                    if intent_id
                ]
                generation_payload = GenerationGenerateCasePayload(
                    project=normalized_project,
                    page=page,
                    requirement=requirement,
                    title=title,
                    case_id=_existing_case_id_for_source_intent(
                        db,
                        project=normalized_project,
                        page=page,
                        source_asset_id=asset_id,
                        intent_id=selected_intent_ids[0] if selected_intent_ids else "",
                    ),
                    priority=priority,
                    page_url=page_url,
                    source=case_source,
                    selected_candidates=chunk,
                    selected_intent_ids=selected_intent_ids,
                )
                try:
                    response = usecase.execute(generation_payload)
                except HTTPException as exc:
                    failure_summary = _record_generation_failure(
                        project=normalized_project,
                        asset_id=asset_id,
                        page=page,
                        intent_id=selected_intent_ids[0] if selected_intent_ids else "",
                        title=_text(chunk[0].get("title") or chunk[0].get("summary")) if chunk else "",
                        detail=exc.detail,
                    )
                    skipped_assets.append(
                        {
                            "asset_id": asset_id,
                            "intent_id": selected_intent_ids[0] if selected_intent_ids else "",
                            "reason": f"generate_failed:{_text(exc.detail) or exc.status_code}",
                            "message": failure_summary.get("message", ""),
                            "failure_type": failure_summary.get("failure_type", ""),
                            "suggestion": failure_summary.get("suggestion", ""),
                        }
                    )
                    _safe_rollback_or_invalidate(db)
                    continue
                response_items = response.get("items") if isinstance(response.get("items"), list) else []
                if response_items:
                    generated_items.extend([item for item in response_items if isinstance(item, dict)])
                    continue
                response_item = response.get("item")
                if isinstance(response_item, dict) and response_item:
                    generated_items.append(response_item)

        if not generated_items:
            primary = skipped_assets[0] if skipped_assets else {}
            detail_message = _text(primary.get("message")) or _text(primary.get("reason")) or "没有可生成的测试点"
            _safe_rollback_or_invalidate(db)
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": _text(primary.get("reason")) or "no_generated_cases",
                    "message": detail_message,
                    "skipped": skipped_assets,
                },
            )
        return {
            "message": f"generated {len(generated_items)} cases",
            "count": len(generated_items),
            "items": generated_items,
            "summary": {
                "total_assets": len(selected_asset_ids),
                "processed_assets": processed_assets,
                "skipped_assets": len(skipped_assets),
                "skipped": skipped_assets,
            },
        }

    def preview_test_point_script(
        self,
        *,
        project: str,
        asset_id: str,
        intent_id: str,
        db: Session,
    ) -> dict[str, Any]:
        """WorkbenchFacade.preview_test_point_script 接口实现。"""
        normalized_project = _text(project) or "mall"
        normalized_asset_id = _safe_case_id(asset_id)
        normalized_intent_id = _text(intent_id)
        if not normalized_asset_id or not normalized_intent_id:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="asset_id and intent_id are required")

        asset = workbench_asset_service.load_test_point_asset_with_root(
            normalized_project,
            normalized_asset_id,
            state_root=constants.TEST_POINTS_ROOT,
        )
        if not asset:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="test point asset not found")
        page = workbench_gate_service.normalize_page_slug(_text(asset.get("page")))
        plan = asset.get("plan") if isinstance(asset.get("plan"), dict) else {}
        points = [point for point in plan.get("points", []) if isinstance(point, dict)] if isinstance(plan.get("points"), list) else []
        point = next(
            (
                row
                for row in points
                if _text(row.get("intent_id") or row.get("key")) == normalized_intent_id
            ),
            None,
        )
        if point is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="test point intent not found")

        page_context = _page_object_generation_context(db, project=normalized_project, page=page)
        generation_state = _test_point_generation_state(point, page_context=page_context)
        if generation_state["can_generate"] is not True:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "test_point_not_generatable",
                    "message": "当前测试点不可生成脚本",
                    "blockers": generation_state["generation_blockers"],
                },
            )
        candidate = _candidate_from_asset_point(
            point,
            fallback_title=_text(asset.get("title")) or normalized_asset_id,
            fallback_priority=_text(asset.get("priority")) or "P1",
        )
        script_code = _build_test_point_script_preview(asset=asset, candidate=candidate, page_context=page_context)
        return {
            "item": {
                "project": normalized_project,
                "asset_id": _text(asset.get("asset_id")) or normalized_asset_id,
                "asset_title": _text(asset.get("title")) or normalized_asset_id,
                "intent_id": normalized_intent_id,
                "title": _text(candidate.get("title") or candidate.get("summary")),
                "page": page,
                "page_url": _text(page_context.get("page_url")),
                "can_generate": True,
                "script_code": script_code,
            }
        }

    def run_case(self, *, payload: Any, db: Session) -> dict[str, Any]:
        """WorkbenchFacade.run_case 接口实现。"""
        store.ensure_dirs()
        normalized_project = _text(getattr(payload, "project", "")) or "mall"
        normalized_case_id = _safe_case_id(getattr(payload, "case_id", ""))
        if not workbench_case_consistency_service.is_case_tracked(
            normalized_case_id,
            case_center_case_ids=workbench_case_consistency_service.load_case_center_case_ids(db),
        ):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="case_id not found in case center")

        case_for_run = TestCaseRepository(db).get_by_case_id_and_project(normalized_case_id, normalized_project)
        if case_for_run is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="case_id not found in project case center")
        case_for_run = test_case_service.get_test_case_detail(db, str(case_for_run.id)).case
        runtime_case_script = _text(case_for_run.script_code)

        def _safe_source_case_path() -> Path:
            """返回展示/历史记录用路径，但不把源 YAML 变成执行前置条件。

            `script_code` 是执行唯一事实源。只要它存在，这个路径只作为
            `start_run()` 的元数据传入，随后会被运行态 YAML 替换，因此源
            YAML 缺失不能阻断执行。这里仍尽量把路径收敛到
            `assets/test-cases` 下，避免运行记录落入任意用户传入路径。
            """
            source_ref = _text(getattr(case_for_run, "source_ref", ""))
            if source_ref:
                source_ref_path = Path(source_ref).expanduser()
                if not source_ref_path.is_absolute():
                    source_ref_path = constants.REPO_ROOT / source_ref_path
                source_ref_path = source_ref_path.resolve()
                if _is_within(source_ref_path, constants.ASSETS_CASES_ROOT):
                    return source_ref_path
            return (constants.AI_CASES_ROOT / f"{normalized_case_id}.yaml").resolve()

        def _resolve_fallback_case_path() -> Path:
            """仅在 DB `script_code` 为空时解析旧 YAML 兜底路径。

            这里刻意保留旧文件路径规则，但只有确认 DB 脚本缺失后才会调用。
            这样源 YAML 只是兼容兜底，而不会再次成为和 `script_code` 竞争
            的事实源。
            """
            if _text(getattr(payload, "case_path", "")):
                requested_case_path = Path(_text(getattr(payload, "case_path", ""))).expanduser()
                if not requested_case_path.is_absolute():
                    requested_case_path = constants.REPO_ROOT / requested_case_path
                return requested_case_path.resolve()
            if _text(getattr(case_for_run, "source_ref", "")):
                source_ref_path = Path(_text(getattr(case_for_run, "source_ref", ""))).expanduser()
                if not source_ref_path.is_absolute():
                    source_ref_path = constants.REPO_ROOT / source_ref_path
                return source_ref_path.resolve()
            return workbench_asset_service.resolve_case_yaml_path(
                normalized_project,
                normalized_case_id,
                state_case_file_fn=lambda project_value, case_value: workbench_asset_service.state_case_file(
                    project_value,
                    case_value,
                    state_root=constants.TEST_POINTS_ROOT,
                ),
                repo_root=constants.REPO_ROOT,
                assets_cases_root=constants.ASSETS_CASES_ROOT,
                ai_cases_root=constants.AI_CASES_ROOT,
                is_within_fn=_is_within,
            )

        source_case_path = _safe_source_case_path()
        if not runtime_case_script:
            # 旧链路兜底：只有 DB 脚本为空时才允许读取源 YAML，
            # 且路径必须仍位于受治理的测试用例资产根目录下。
            source_case_path = _resolve_fallback_case_path()
            if not _is_within(source_case_path, constants.ASSETS_CASES_ROOT):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="case_path must stay under assets/test-cases")
            if not source_case_path.exists():
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"case file not found: {source_case_path}")
            runtime_case_script = source_case_path.read_text(encoding="utf-8")
        if not runtime_case_script.strip():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "empty_case_script",
                    "message": "用例脚本为空，无法执行",
                    "case_id": normalized_case_id,
                },
            )

        def _build_runtime_execution_record(**kwargs: Any) -> dict[str, Any]:
            """WorkbenchFacade._build_runtime_execution_record 接口实现。"""
            return workbench_runtime_service.build_runtime_execution_record(
                **kwargs,
                normalize_execution_record_payload=_normalize_execution_record_payload,
            )

        def _runtime_view_from_entry(entry: dict[str, Any]) -> dict[str, Any]:
            """WorkbenchFacade._runtime_view_from_entry 接口实现。"""
            review_decisions_for_run = partial(
                workbench_review_service.review_decisions_for_run,
                read_json_list_fn=store.read_json_list,
                review_decisions_file=constants.REVIEW_DECISIONS_FILE,
                normalize_page_slug_fn=workbench_gate_service.normalize_page_slug,
                normalize_review_type_fn=workbench_review_service.normalize_review_type,
                normalize_review_status_fn=workbench_review_service.normalize_review_status,
                sanitize_review_items_fn=workbench_review_service.sanitize_review_items,
            )
            return workbench_runtime_service.runtime_view_from_entry(
                entry,
                normalize_execution_record_payload=_normalize_execution_record_payload,
                normalize_page_slug=workbench_gate_service.normalize_page_slug,
                build_page_analysis_context=workbench_analysis_service.build_page_analysis_context,
                build_item_review_state=partial(
                    workbench_review_service.build_item_review_state,
                    normalize_page_slug_fn=workbench_gate_service.normalize_page_slug,
                    build_page_analysis_context_fn=workbench_analysis_service.build_page_analysis_context,
                    review_decisions_for_run_fn=review_decisions_for_run,
                    build_test_point_review_items_fn=workbench_analysis_service.build_test_point_review_items,
                    build_review_section_fn=workbench_analysis_service.build_review_section,
                    build_risk_review_items_fn=workbench_analysis_service.build_risk_review_items,
                ),
                build_run_review_state_from_decisions=partial(
                    workbench_review_service.build_run_review_state_from_decisions,
                    review_decisions_for_run_fn=review_decisions_for_run,
                    normalize_page_slug_fn=workbench_gate_service.normalize_page_slug,
                    build_review_section_fn=workbench_analysis_service.build_review_section,
                ),
                build_test_point_asset_gate_context=workbench_asset_service.build_test_point_asset_gate_context,
                build_execution_gate=workbench_gate_service.build_execution_gate,
                build_review_audit_summary=workbench_review_service.build_review_audit_summary,
                build_review_audit_timeline=workbench_review_service.build_review_audit_timeline,
                build_risk_report_summary=workbench_analysis_service.build_risk_report_summary,
                build_self_healing_summary=workbench_analysis_service.build_self_healing_summary,
                execution_gate_decision_for_run=lambda *, run_id, project="", page="": workbench_gate_service.execution_gate_decision_for_run(
                    run_id=run_id,
                    project=project,
                    page=page,
                    read_json_list=store.read_json_list,
                ),
            )

        def _load_runtime_execution_record_from_artifacts(artifacts_dir: Path) -> dict[str, Any]:
            """WorkbenchFacade._load_runtime_execution_record_from_artifacts 接口实现。"""
            return workbench_runtime_service.load_runtime_execution_record_from_artifacts(
                artifacts_dir,
                normalize_evidence_manifest_payload=lambda payload: payload if isinstance(payload, dict) else {},
                resolve_manifest_entries_fn=lambda entries, root: workbench_runtime_service.resolve_manifest_entries(entries, root=root),
                load_execution_record_payload_fn=lambda path: workbench_runtime_service.load_execution_record_payload(
                    path,
                    normalize_execution_record_payload=_normalize_execution_record_payload,
                ),
            )

        def _collect_failure_entries_with_meta() -> tuple[list[dict[str, Any]], dict[str, Any]]:
            """WorkbenchFacade._collect_failure_entries_with_meta 接口实现。"""
            return workbench_reporting_service.collect_failure_entries_with_meta(
                compat_scan_enabled=False,
                artifact_roots=[constants.RUNNER_ROOT / "artifacts", *sorted(constants.WEB_UI_RUNS_DIR.glob("*-artifacts"))],
                logger=None,
                normalize_evidence_manifest_payload=lambda payload: payload if isinstance(payload, dict) else {},
                resolve_manifest_entries=lambda entries, root: workbench_runtime_service.resolve_manifest_entries(entries, root=root),
                load_execution_record_payload=lambda path: workbench_runtime_service.load_execution_record_payload(
                    path,
                    normalize_execution_record_payload=_normalize_execution_record_payload,
                ),
                parse_analysis_file=workbench_reporting_service.parse_analysis_file,
            )

        def _collect_failure_entries() -> list[dict[str, Any]]:
            """WorkbenchFacade._collect_failure_entries 接口实现。"""
            entries, _meta = _collect_failure_entries_with_meta()
            return entries

        def _build_run_command(case_path_value: Path) -> tuple[list[str], dict[str, str]]:
            """WorkbenchFacade._build_run_command 接口实现。"""
            runner_environ = os.environ.copy()
            runner_environ["DSL_DATA_POOL_JSON"] = test_data_pool_service.serialize_runner_data_pool_snapshot(db)
            return workbench_runtime_service.build_run_command(
                case_path_value,
                get_python_bin_fn=lambda: workbench_runtime_service.get_python_bin(repo_root=constants.REPO_ROOT),
                repo_root=constants.REPO_ROOT,
                allure_results_root=constants.ALLURE_RESULTS_ROOT,
                environ=runner_environ,
            )

        def _execute_run(job: dict[str, Any]) -> None:
            """WorkbenchFacade._execute_run 接口实现。"""
            try:
                workbench_runtime_service.execute_run(
                    job,
                    build_run_command_fn=_build_run_command,
                    now_iso_fn=store.now_iso,
                    update_job=store.update_run_job,
                    update_runtime_run=store.update_runtime_run,
                    load_runtime_execution_record_from_artifacts=_load_runtime_execution_record_from_artifacts,
                    collect_failure_entries=_collect_failure_entries,
                    is_within=_is_within,
                    repo_root=constants.REPO_ROOT,
                    runner_root=constants.RUNNER_ROOT,
                )
            finally:
                final_job = store.get_run_job(_text(job.get("run_id"))) or job
                with SessionLocal() as worker_db:
                    _persist_runtime_run_to_case_center(worker_db, final_job)

        job = workbench_runtime_service.start_run(
            project=normalized_project,
            case_id=normalized_case_id,
            case_path=source_case_path,
            source=getattr(payload, "source", "manual"),
            runs_dir=constants.WEB_UI_RUNS_DIR,
            now_iso_fn=store.now_iso,
            build_runtime_execution_record=_build_runtime_execution_record,
            runtime_view_from_entry_fn=_runtime_view_from_entry,
            store_run_job=store.store_run_job,
            append_runtime_run=store.append_runtime_run,
            append_history=store.append_history,
            execute_run_fn=_execute_run,
            runtime_case_script=runtime_case_script,
        )
        return {"item": job}

    def list_runs(self, *, limit: int, db: Session) -> dict[str, Any]:
        """WorkbenchFacade.list_runs 接口实现。"""
        store.ensure_dirs()
        case_center_case_ids = workbench_case_consistency_service.load_case_center_case_ids(db)
        items = [
            _attach_test_point_asset_summary(
                _runtime_view_from_entry(item)
            )
            for item in store.read_runtime_run_items()
        ]
        filtered_items, _filter_meta = workbench_case_consistency_service.filter_records_by_case_center(
            items,
            case_center_case_ids=case_center_case_ids,
        )
        return {"items": filtered_items[:limit]}

    def get_run(self, *, run_id: str, db: Session) -> dict[str, Any]:
        """WorkbenchFacade.get_run 接口实现。"""
        store.ensure_dirs()
        case_center_case_ids = workbench_case_consistency_service.load_case_center_case_ids(db)
        job = store.get_run_job(run_id)
        if job:
            item = _attach_test_point_asset_summary(_runtime_view_from_entry(job))
            if workbench_case_consistency_service.is_case_tracked(item.get("case_id", ""), case_center_case_ids=case_center_case_ids):
                return {"item": item}
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run not found")

        for item in store.read_runtime_run_items():
            if workbench_runtime_service.runtime_run_id(item) != run_id:
                continue
            response_item = _attach_test_point_asset_summary(_runtime_view_from_entry(item))
            if workbench_case_consistency_service.is_case_tracked(
                response_item.get("case_id", ""),
                case_center_case_ids=case_center_case_ids,
            ):
                return {"item": response_item}
            break
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run not found")

    def rerun_case(self, *, run_id: str, db: Session) -> dict[str, Any]:
        """WorkbenchFacade.rerun_case 接口实现。"""
        store.ensure_dirs()
        case_center_case_ids = workbench_case_consistency_service.load_case_center_case_ids(db)
        run_item = self._service._find_run_item(run_id) if hasattr(self._service, "_find_run_item") else None
        if not run_item:
            run_item = workbench_runtime_service.find_run_item(
                run_id,
                get_job=store.get_run_job,
                read_runtime_runs=store.read_runtime_run_items,
                runtime_run_id_fn=workbench_runtime_service.runtime_run_id,
                runtime_view_with_execution_record_preferred_fn=_runtime_view_with_execution_record_preferred,
            )
        if not run_item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run not found")
        if not workbench_case_consistency_service.is_case_tracked(
            run_item.get("case_id", ""),
            case_center_case_ids=case_center_case_ids,
        ):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run not found")
        project = _text(run_item.get("project")) or "mall"
        case_id = _safe_case_id(run_item.get("case_id", ""))
        if not case_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run case_id not found")
        response = self.run_case(
            payload=SimpleNamespace(project=project, case_id=case_id, source="rerun", case_path=""),
            db=db,
        )
        new_job = response.get("item", {}) if isinstance(response.get("item"), dict) else {}
        store.append_history(
            {
                "timestamp": store.now_iso(),
                "action": "rerun_case",
                "case_id": case_id,
                "from_run_id": run_id,
                "run_id": new_job.get("run_id", ""),
                "queue_status": "queued",
            },
            db=db,
        )
        return {"item": new_job}

    def list_defects(self, *, case_id: str, db: Session) -> dict[str, Any]:
        """WorkbenchFacade.list_defects 接口实现。"""
        store.ensure_dirs()
        case_center_case_ids = workbench_case_consistency_service.load_case_center_case_ids(db)
        items = workbench_reporting_service.list_defect_items(
            case_id,
            read_items=lambda: store.list_defect_items(case_id),
        )
        filtered_items, _filter_meta = workbench_case_consistency_service.filter_records_by_case_center(
            items,
            case_center_case_ids=case_center_case_ids,
        )
        return {"items": filtered_items}

    def add_defect(self, payload: Any, db: Session) -> dict[str, Any]:
        """WorkbenchFacade.add_defect 接口实现。"""
        store.ensure_dirs()
        case_center_case_ids = workbench_case_consistency_service.load_case_center_case_ids(db)
        if not workbench_case_consistency_service.is_case_tracked(
            payload.case_id,
            case_center_case_ids=case_center_case_ids,
        ):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="case_id not found in case center")
        with store.FILE_LOCK:
            entry = workbench_reporting_service.add_defect_item(
                case_id=payload.case_id,
                defect_id=payload.defect_id,
                defect_url=payload.defect_url,
                system=payload.system,
                note=payload.note,
                read_items=lambda: store.read_json_list(store.DEFECT_LINKS_FILE),
                write_items=lambda items: store.write_json_list(store.DEFECT_LINKS_FILE, items),
            )
        return {"item": entry}

    def report_overview(self, response: Response, db: Session) -> dict[str, Any]:
        """WorkbenchFacade.report_overview 接口实现。"""
        store.ensure_dirs()
        workbench_reporting_service.apply_no_store_headers(response)
        case_center_case_ids = workbench_case_consistency_service.load_case_center_case_ids(db)

        def _collect_execution_records_with_meta_filtered(*, limit: int = 1000) -> tuple[list[dict[str, Any]], dict[str, Any]]:
            """WorkbenchFacade._collect_execution_records_with_meta_filtered 接口实现。"""
            rows, meta = _collect_execution_records_with_meta(limit=limit)
            filtered_rows, _filter_meta = workbench_case_consistency_service.filter_records_by_case_center(
                rows,
                case_center_case_ids=case_center_case_ids,
                case_id_resolver=lambda row: (
                    row.get("case_id")
                    or (
                        row.get("execution_record", {}).get("case_id")
                        if isinstance(row.get("execution_record"), dict)
                        else ""
                    )
                ),
            )
            return filtered_rows, meta

        def _collect_failure_entries_filtered() -> list[dict[str, Any]]:
            """WorkbenchFacade._collect_failure_entries_filtered 接口实现。"""
            entries, _meta = _collect_failure_entries_with_meta()
            filtered_entries, _filter_meta = workbench_case_consistency_service.filter_records_by_case_center(
                entries,
                case_center_case_ids=case_center_case_ids,
            )
            return filtered_entries

        def _read_defect_items_filtered() -> list[dict[str, Any]]:
            """WorkbenchFacade._read_defect_items_filtered 接口实现。"""
            items = store.list_defect_items()
            filtered_items, _filter_meta = workbench_case_consistency_service.filter_records_by_case_center(
                items,
                case_center_case_ids=case_center_case_ids,
            )
            return filtered_items

        return workbench_reporting_service.build_report_overview(
            collect_execution_records_with_meta=_collect_execution_records_with_meta_filtered,
            normalize_execution_meta=workbench_reporting_service.normalize_execution_meta,
            collect_failure_entries=_collect_failure_entries_filtered,
            normalize_failure_analysis_view=workbench_reporting_service.normalize_failure_analysis_view,
            read_defect_items=_read_defect_items_filtered,
        )

    def report_failures(
        self,
        *,
        response: Response,
        case_id: str,
        keyword: str,
        defect_status: str,
        db: Session,
    ) -> dict[str, Any]:
        """WorkbenchFacade.report_failures 接口实现。"""
        store.ensure_dirs()
        workbench_reporting_service.apply_no_store_headers(response)
        case_center_case_ids = workbench_case_consistency_service.load_case_center_case_ids(db)

        def _collect_failure_entries_with_meta_filtered() -> tuple[list[dict[str, Any]], dict[str, Any]]:
            """WorkbenchFacade._collect_failure_entries_with_meta_filtered 接口实现。"""
            entries, meta = _collect_failure_entries_with_meta()
            filtered_entries, _filter_meta = workbench_case_consistency_service.filter_records_by_case_center(
                entries,
                case_center_case_ids=case_center_case_ids,
            )
            return filtered_entries, meta

        def _read_defect_items_filtered() -> list[dict[str, Any]]:
            """WorkbenchFacade._read_defect_items_filtered 接口实现。"""
            items = store.list_defect_items()
            filtered_items, _filter_meta = workbench_case_consistency_service.filter_records_by_case_center(
                items,
                case_center_case_ids=case_center_case_ids,
            )
            return filtered_items

        return workbench_reporting_service.build_report_failures(
            case_id=case_id,
            keyword=keyword,
            defect_status=defect_status,
            collect_failure_entries_with_meta=_collect_failure_entries_with_meta_filtered,
            normalize_failure_evidence_meta=workbench_reporting_service.normalize_failure_evidence_meta,
            read_defect_items=_read_defect_items_filtered,
        )

    def report_context(self, *, response: Response, db: Session) -> dict[str, Any]:
        """WorkbenchFacade.report_context 接口实现。"""
        store.ensure_dirs()
        workbench_reporting_service.apply_no_store_headers(response)
        case_center_case_ids = workbench_case_consistency_service.load_case_center_case_ids(db)
        commit_id = ""
        commit_message = ""
        branch_name = ""
        try:
            commit_id = (
                subprocess.run(["git", "rev-parse", "HEAD"],
                               cwd=str(constants.REPO_ROOT), capture_output=True, text=True, check=False, timeout=2)
                .stdout.strip()
            )
            commit_message = (
                subprocess.run(["git", "log", "-1", "--pretty=%s"],
                               cwd=str(constants.REPO_ROOT), capture_output=True, text=True, check=False, timeout=2)
                .stdout.strip()
            )
            branch_name = (
                subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"],
                               cwd=str(constants.REPO_ROOT), capture_output=True, text=True, check=False, timeout=2)
                .stdout.strip()
            )
        except Exception:
            logging.getLogger(__name__).warning(
                "report_context git metadata unavailable",
                exc_info=True,
            )

        def _collect_execution_records_with_meta_filtered(*, limit: int = 1000) -> tuple[list[dict[str, Any]], dict[str, Any]]:
            """WorkbenchFacade._collect_execution_records_with_meta_filtered 接口实现。"""
            rows, meta = _collect_execution_records_with_meta(limit=limit)
            filtered_rows, _filter_meta = workbench_case_consistency_service.filter_records_by_case_center(
                rows,
                case_center_case_ids=case_center_case_ids,
                case_id_resolver=lambda row: (
                    row.get("case_id")
                    or (
                        row.get("execution_record", {}).get("case_id")
                        if isinstance(row.get("execution_record"), dict)
                        else ""
                    )
                ),
            )
            return filtered_rows, meta

        return workbench_reporting_service.build_report_context(
            git_rev_parse_head=commit_id,
            git_log_subject=commit_message,
            git_branch=branch_name,
            collect_execution_records_with_meta=_collect_execution_records_with_meta_filtered,
            normalize_execution_meta=workbench_reporting_service.normalize_execution_meta,
            image_tag=os.getenv("IMAGE_TAG", ""),
            base_url=os.getenv("BASE_URL", "http://localhost:5174/#/login"),
            browser=os.getenv("PLAYWRIGHT_BROWSER", "chromium"),
            environment=os.getenv("APP_ENV", "local"),
        )

    def report_performance(self, *, response: Response, db: Session) -> dict[str, Any]:
        """WorkbenchFacade.report_performance 接口实现。"""
        store.ensure_dirs()
        workbench_reporting_service.apply_no_store_headers(response)
        case_center_case_ids = workbench_case_consistency_service.load_case_center_case_ids(db)

        def _collect_execution_records_with_meta_filtered(*, limit: int = 1000) -> tuple[list[dict[str, Any]], dict[str, Any]]:
            """WorkbenchFacade._collect_execution_records_with_meta_filtered 接口实现。"""
            rows, meta = _collect_execution_records_with_meta(limit=limit)
            filtered_rows, _filter_meta = workbench_case_consistency_service.filter_records_by_case_center(
                rows,
                case_center_case_ids=case_center_case_ids,
                case_id_resolver=lambda row: (
                    row.get("case_id")
                    or (
                        row.get("execution_record", {}).get("case_id")
                        if isinstance(row.get("execution_record"), dict)
                        else ""
                    )
                ),
            )
            return filtered_rows, meta

        return workbench_reporting_service.build_report_performance(
            collect_execution_records_with_meta=_collect_execution_records_with_meta_filtered,
            normalize_execution_meta=workbench_reporting_service.normalize_execution_meta,
        )

    def report_allure(self, response: Response) -> dict[str, Any]:
        """WorkbenchFacade.report_allure 接口实现。"""
        workbench_reporting_service.apply_no_store_headers(response)
        latest_results_dir = workbench_reporting_service.find_latest_run_allure_results(repo_root=constants.REPO_ROOT)
        return workbench_reporting_service.build_report_allure(
            available=(constants.ALLURE_REPORT_ROOT / "index.html").exists(),
            read_allure_summary=lambda: workbench_reporting_service.read_allure_summary(
                allure_report_root=constants.ALLURE_REPORT_ROOT
            ),
            read_allure_environment=lambda: workbench_reporting_service.read_allure_environment(
                allure_report_root=constants.ALLURE_REPORT_ROOT
            ),
            read_allure_executors=lambda: workbench_reporting_service.read_allure_executors(
                allure_report_root=constants.ALLURE_REPORT_ROOT
            ),
            ensure_allure_snapshot=lambda **kwargs: workbench_reporting_service.ensure_allure_snapshot(
                version=int(kwargs.get("version", 0) or 0),
                snapshot_slug=str(kwargs.get("snapshot_slug", "")),
                allure_report_root=constants.ALLURE_REPORT_ROOT,
                allure_snapshots_root=constants.ALLURE_SNAPSHOTS_ROOT,
            ),
            get_allure_index_version=lambda: workbench_reporting_service.get_allure_index_version(
                allure_report_root=constants.ALLURE_REPORT_ROOT
            ),
            current_results_dir=latest_results_dir,
        )

    def workbench_history(
        self,
        *,
        limit: int,
        page: int,
        page_size: int,
        project_code: str,
        keyword: str,
        sort: str,
        action: str,
        actor: str,
        status: str,
        risk_gate_decision: str,
        self_healing_status: str,
        db: Session,
    ) -> dict[str, Any]:
        """WorkbenchFacade.workbench_history 接口实现。"""
        store.ensure_dirs()
        project_code_value = _normalize_optional_project_code(project_code)
        history_items, _filter_meta = workbench_case_consistency_service.filter_records_by_case_center(
            store.read_history_items(),
            case_center_case_ids=workbench_case_consistency_service.load_case_center_case_ids(db),
        )
        if project_code_value:
            history_items = [item for item in history_items if _resolve_history_project_code(item) == project_code_value]

        project_status_cache: dict[str, str] = {}

        def resolve_project_status(project_code_value_raw: str) -> str:
            """WorkbenchFacade.resolve_project_status 接口实现。"""
            normalized_project_code = _normalize_optional_project_code(project_code_value_raw)
            if not normalized_project_code:
                return "active"
            if normalized_project_code not in project_status_cache:
                project_status_cache[normalized_project_code] = test_project_service.get_project_status(
                    db,
                    normalized_project_code,
                )
            return project_status_cache[normalized_project_code]

        def find_run_item_for_history(run_id: str) -> dict[str, Any]:
            run_item = self._service._find_run_item(run_id) if hasattr(self._service, "_find_run_item") else None
            if run_item:
                return run_item
            return workbench_runtime_service.find_run_item(
                run_id,
                get_job=store.get_run_job,
                read_runtime_runs=store.read_runtime_run_items,
                runtime_run_id_fn=workbench_runtime_service.runtime_run_id,
                runtime_view_with_execution_record_preferred_fn=_runtime_view_with_execution_record_preferred,
            ) or {}

        payload = workbench_history_service.list_history(
            history_items,
            resolve_governance_snapshot=lambda run_id: workbench_reporting_service.resolve_run_governance_snapshot(
                run_id,
                find_run_item=find_run_item_for_history,
                build_risk_report_summary=workbench_analysis_service.build_risk_report_summary,
                build_self_healing_summary=workbench_analysis_service.build_self_healing_summary,
                build_page_semantic_summary=workbench_analysis_service.build_page_semantic_summary,
            ),
            resolve_failure_snapshot=lambda run_id: workbench_reporting_service.resolve_run_failure_snapshot(
                run_id,
                find_run_item=find_run_item_for_history,
                normalize_failure_entry_view=_normalize_failure_entry_view,
                collect_failure_entries=lambda: _collect_failure_entries_with_meta()[0],
                is_within_fn=_is_within,
            ),
            normalize_page_slug=workbench_gate_service.normalize_page_slug,
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
        for item in payload.get("items", []):
            if not isinstance(item, dict):
                continue
            resolved_project_code = _resolve_history_project_code(item)
            item["project_code"] = resolved_project_code
            item["project_status"] = resolve_project_status(resolved_project_code)
        return payload

    def workbench_quality_gate_summary(
        self,
        *,
        limit: int,
        alert_code: str,
        page: str,
        db: Session,
    ) -> dict[str, Any]:
        """WorkbenchFacade.workbench_quality_gate_summary 接口实现。"""
        store.ensure_dirs()
        history_items, _filter_meta = workbench_case_consistency_service.filter_records_by_case_center(
            store.read_history_items(),
            case_center_case_ids=workbench_case_consistency_service.load_case_center_case_ids(db),
        )
        return {
            "item": workbench_history_service.summarize_quality_gate_events(
                history_items,
                limit=limit,
                alert_code=alert_code,
                page=page,
                normalize_page_slug=workbench_gate_service.normalize_page_slug,
            )
        }

    def cleanup_case_consistency(self, *, purge_all: bool, confirm_text: str = "", db: Session) -> dict[str, Any]:
        """WorkbenchFacade.cleanup_case_consistency 接口实现。"""
        store.ensure_dirs()
        if purge_all and _text(confirm_text) != "清理全部执行状态":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "purge_all_confirmation_required",
                    "message": "请输入确认文本：清理全部执行状态",
                },
            )
        case_center_case_ids = workbench_case_consistency_service.load_case_center_case_ids(db)

        with store.FILE_LOCK:
            history_items = store.read_history_items()
            runtime_items = store.read_runtime_run_items()
            defect_items = store.read_defect_items()
            review_items = store.read_review_items()
            gate_decision_items = store.read_gate_decision_items()
            calibration_items = store.read_failure_source_calibration_items()
            if purge_all:
                store.clear_state_files()
                history_filter_meta = {
                    "enforced": True,
                    "total_records": len(history_items),
                    "removed_count": len(history_items),
                    "removed_case_ids": [],
                    "purged_all": True,
                }
                runtime_filter_meta = {
                    "enforced": True,
                    "total_records": len(runtime_items),
                    "removed_count": len(runtime_items),
                    "removed_case_ids": [],
                    "purged_all": True,
                }
                defect_filter_meta = {
                    "enforced": True,
                    "total_records": len(defect_items),
                    "removed_count": len(defect_items),
                    "removed_case_ids": [],
                    "purged_all": True,
                }
                review_filter_meta = {
                    "enforced": True,
                    "total_records": len(review_items),
                    "removed_count": len(review_items),
                    "removed_case_ids": [],
                    "purged_all": True,
                }
                gate_filter_meta = {
                    "enforced": True,
                    "total_records": len(gate_decision_items),
                    "removed_count": len(gate_decision_items),
                    "removed_case_ids": [],
                    "purged_all": True,
                }
                calibration_filter_meta = {
                    "enforced": True,
                    "total_records": len(calibration_items),
                    "removed_count": len(calibration_items),
                    "removed_case_ids": [],
                    "purged_all": True,
                }
            else:
                filtered_history_items, history_filter_meta = workbench_case_consistency_service.filter_records_by_case_center(
                    history_items,
                    case_center_case_ids=case_center_case_ids,
                )
                filtered_runtime_items, runtime_filter_meta = workbench_case_consistency_service.filter_records_by_case_center(
                    runtime_items,
                    case_center_case_ids=case_center_case_ids,
                )
                filtered_defect_items, defect_filter_meta = workbench_case_consistency_service.filter_records_by_case_center(
                    defect_items,
                    case_center_case_ids=case_center_case_ids,
                )
                filtered_review_items, review_filter_meta = workbench_case_consistency_service.filter_records_by_case_center(
                    review_items,
                    case_center_case_ids=case_center_case_ids,
                )
                filtered_gate_decision_items, gate_filter_meta = workbench_case_consistency_service.filter_records_by_case_center(
                    gate_decision_items,
                    case_center_case_ids=case_center_case_ids,
                )
                filtered_calibration_items, calibration_filter_meta = workbench_case_consistency_service.filter_records_by_case_center(
                    calibration_items,
                    case_center_case_ids=case_center_case_ids,
                )

                if history_filter_meta.get("removed_count", 0):
                    store.write_history_items(filtered_history_items)
                if runtime_filter_meta.get("removed_count", 0):
                    store.write_runtime_run_items(filtered_runtime_items)
                if defect_filter_meta.get("removed_count", 0):
                    store.write_defect_items(filtered_defect_items)
                if review_filter_meta.get("removed_count", 0):
                    store.write_review_items(filtered_review_items)
                if gate_filter_meta.get("removed_count", 0):
                    store.write_gate_decision_items(filtered_gate_decision_items)
                if calibration_filter_meta.get("removed_count", 0):
                    store.write_failure_source_calibration_items(filtered_calibration_items)

        reports_cleanup = workbench_case_consistency_service.cleanup_execution_report_files(
            execution_reports_root=constants.EXECUTION_REPORTS_ROOT,
            case_center_case_ids=case_center_case_ids,
        )
        task_artifacts_cleanup = workbench_case_consistency_service.cleanup_execution_task_artifacts(
            runner_artifacts_root=constants.RUNNER_ROOT / "artifacts",
            web_ui_runs_root=constants.WEB_UI_RUNS_DIR,
        )
        allure_cleanup = workbench_case_consistency_service.cleanup_allure_artifacts(
            allure_results_root=constants.ALLURE_RESULTS_ROOT,
            allure_report_root=constants.ALLURE_REPORT_ROOT,
            allure_snapshots_root=constants.ALLURE_SNAPSHOTS_ROOT,
            clear_report_root=False,
        )

        return {
            "history": history_filter_meta,
            "runtime_runs": runtime_filter_meta,
            "defect_links": defect_filter_meta,
            "review_decisions": review_filter_meta,
            "execution_gate_decisions": gate_filter_meta,
            "failure_source_calibrations": calibration_filter_meta,
            "execution_reports": reports_cleanup,
            "execution_task_artifacts": task_artifacts_cleanup,
            "allure_artifacts": allure_cleanup,
            "case_center_case_count": len(case_center_case_ids or []),
            "purge_all": purge_all,
        }

    def download_log(self, run_id: str, db: Session) -> Response:
        """WorkbenchFacade.download_log 接口实现。"""
        store.ensure_dirs()
        normalized_run_id = _text(run_id)
        if not _RUN_ID_PATTERN.fullmatch(normalized_run_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run not found")
        case_center_case_ids = workbench_case_consistency_service.load_case_center_case_ids(db)
        run_item = self._service._find_run_item(normalized_run_id) if hasattr(self._service, "_find_run_item") else None
        if not run_item:
            run_item = workbench_runtime_service.find_run_item(
                normalized_run_id,
                get_job=store.get_run_job,
                read_runtime_runs=store.read_runtime_run_items,
                runtime_run_id_fn=workbench_runtime_service.runtime_run_id,
                runtime_view_with_execution_record_preferred_fn=_runtime_view_with_execution_record_preferred,
            )
        if not run_item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run not found")
        if not workbench_case_consistency_service.is_case_tracked(
            run_item.get("case_id", ""),
            case_center_case_ids=case_center_case_ids,
        ):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run not found")
        log_path = (constants.WEB_UI_RUNS_DIR / f"{normalized_run_id}.log").resolve()
        if not _is_within(log_path, constants.WEB_UI_RUNS_DIR):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="log not found")
        if not log_path.exists():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="log not found")
        return Response(
            content=log_path.read_text(encoding="utf-8", errors="ignore"),
            media_type="text/plain; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename={normalized_run_id}.log"},
        )

    def dashboard_overview(self, db: Session) -> dict[str, Any]:
        """WorkbenchFacade.dashboard_overview 接口实现。"""
        return workbench_governance_service.build_dashboard_overview(db)

    def dashboard_governance(self, db: Session) -> dict[str, Any]:
        """WorkbenchFacade.dashboard_governance 接口实现。"""
        now = datetime.now(UTC)
        degraded_sources: list[str] = []
        quality_gate_summary: dict[str, Any] = {}
        task_snapshot: dict[str, Any] = {"items": [], "summary": {}}
        cluster_payload: dict[str, Any] = {
            "generated_at": now.isoformat(),
            "total_failed_reports": 0,
            "total_clusters": 0,
            "clusters": [],
        }
        flaky_payload: dict[str, Any] = {"top_flaky": []}
        governance_trend: dict[str, Any] = {"items": [], "summary_7d": {}}

        try:
            history_items = store.read_history_items()
            quality_gate_summary = workbench_history_service.summarize_quality_gate_events(
                history_items,
                limit=2000,
                normalize_page_slug=lambda value: str(value).strip().lower(),
            )
        except Exception:
            LOGGER.exception("dashboard governance degraded: quality gate summary unavailable")
            degraded_sources.append("quality_gate")

        try:
            store.ensure_dirs()
            execution_rows, execution_meta_raw = _collect_execution_records_with_meta(limit=200)
            execution_meta = workbench_reporting_service.normalize_execution_meta(execution_meta_raw)
            items: list[dict[str, Any]] = []
            for row in execution_rows:
                items.append(_build_execution_task_view(row))
                if len(items) >= 200:
                    break
            task_snapshot = {
                "items": items,
                "summary": _build_execution_task_summary(items=items, filter_snapshot={}, execution_meta=execution_meta),
            }
        except Exception:
            LOGGER.exception("dashboard governance degraded: task snapshot unavailable")
            degraded_sources.append("tasks")

        try:
            settings = _settings()
            cluster_payload = _get_json(
                f"{settings.orchestrator_url.rstrip('/')}/failures/clusters?limit=200&max_clusters=8",
                timeout_seconds=settings.orchestrator_timeout_seconds,
            )
        except Exception:
            LOGGER.exception("dashboard governance degraded: failure clusters unavailable")
            degraded_sources.append("failure_clusters")

        try:
            history_items = store.read_history_items()
            governance_trend = workbench_governance_service.build_governance_trend(
                history_items=history_items,
                resolve_governance_snapshot=lambda run_id: workbench_reporting_service.resolve_run_governance_snapshot(
                    run_id,
                    find_run_item=lambda _run_id: {},
                    build_risk_report_summary=workbench_analysis_service.build_risk_report_summary,
                    build_self_healing_summary=workbench_analysis_service.build_self_healing_summary,
                    build_page_semantic_summary=workbench_analysis_service.build_page_semantic_summary,
                ),
                quality_gate_summary=quality_gate_summary,
                now=now,
                days=14,
            )
        except Exception:
            LOGGER.exception("dashboard governance degraded: governance trend unavailable")
            degraded_sources.append("governance_trend")

        try:
            test_case_service.ensure_seed_data(db)
            repo = TestCaseRepository(db)
            cases = repo.list_all()
            executions = repo.list_all_executions_ordered()
            flaky_payload = {"top_flaky": workbench_governance_service.build_flaky_top5(cases, executions)}
        except Exception:
            LOGGER.exception("dashboard governance degraded: flaky snapshot unavailable")
            degraded_sources.append("flaky")

        return workbench_governance_service.build_governance_overview(
            quality_gate_summary=quality_gate_summary,
            task_snapshot=task_snapshot,
            cluster_payload=cluster_payload,
            flaky_payload=flaky_payload,
            governance_trend=governance_trend,
            degraded_sources=degraded_sources,
            now=now,
        )

    def scheduler_summary(self, *, limit: int) -> dict[str, Any]:
        """WorkbenchFacade.scheduler_summary 接口实现。"""
        store.ensure_dirs()
        execution_rows, execution_meta_raw = _collect_execution_records_with_meta(limit=max(limit * 3, 200))
        execution_meta = workbench_reporting_service.normalize_execution_meta(execution_meta_raw)
        items = [
            _build_execution_task_view(row)
            for row in execution_rows
        ][:limit]
        task_summary = _build_execution_task_summary(items=items, filter_snapshot={}, execution_meta=execution_meta)
        return {"item": workbench_scheduler_service.build_scheduler_summary(items=items, task_summary=task_summary)}

    def scheduler_dispatch_plan(self, *, limit: int) -> dict[str, Any]:
        """WorkbenchFacade.scheduler_dispatch_plan 接口实现。"""
        store.ensure_dirs()
        execution_rows, _execution_meta_raw = _collect_execution_records_with_meta(limit=max(limit * 3, 200))
        items = [
            _build_execution_task_view(row)
            for row in execution_rows
        ][:limit]
        return {"item": workbench_scheduler_service.build_scheduler_dispatch_plan(items=items)}





# ═══════════════════════════════════════════════════════════════
# 构建函数
# ═══════════════════════════════════════════════════════════════
def build_workbench_facade(service: WorkbenchService | None = None) -> WorkbenchFacade:
    """build_workbench_facade 功能入口。"""
    return WorkbenchFacade(service=service)


__all__ = [
    "WorkbenchFacade",
    "build_workbench_facade",
    "_settings",
    "_sync_stage_a_workbench_state",
    "_sync_stage_b_workbench_gate",
    "_ensure_dirs",
    "_read_json_list",
    "_write_json_list",
    "_append_history",
    "_append_runtime_run",
    "_update_runtime_run",
    "_safe_case_id",
    "_runtime_run_id",
    "_runtime_view_from_entry",
    "_normalize_execution_record_payload",
    "_execution_record_time_value",
    "_collect_execution_records_with_meta",
    "_build_execution_task_view",
    "_build_execution_task_summary",
    "_load_runtime_execution_record_from_artifacts",
    "_runtime_view_with_execution_record_preferred",
    "_collect_failure_entries_with_meta",
    "_collect_failure_entries",
    "_normalize_failure_entry_view",
]
