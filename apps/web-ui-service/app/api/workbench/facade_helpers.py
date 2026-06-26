"""Workbench Facade 共用 helper 函数。

提取自 facade.py 以消除混入类的循环导入。
facade.py / facade_test_point_assets.py / facade_reporting.py 均从此导入。
"""
from __future__ import annotations

import json
import logging

import re
from collections import defaultdict
from functools import partial
from pathlib import Path
from typing import Any, Sequence
import yaml
from shared_backend.case_ids import match_case_id
from shared_backend.element_binding import build_element_alias_map, resolve_element_code, resolve_involved_element_codes
from sqlalchemy.orm import Session

from app.api.workbench import constants, store
from app.core.config import get_settings
from app.core import page_analysis_rules
from app.repositories.page_object_repository import PageObjectRepository
from app.repositories.test_case_repository import TestCaseRepository
from app.models.page_object import PageElement
from app.models.test_case import TestCase, TestCaseExecution
from app.services import (
    workbench_analysis_service,
    workbench_asset_service,
    workbench_gate_service,
    workbench_review_service,
    workbench_runtime_service,
)
from ._helpers import (
    normalize_optional_project_code as _normalize_optional_project_code,
    normalize_test_point_review_status as _normalize_test_point_review_status,
    python_literal as _python_literal,
    safe_python_identifier as _safe_python_identifier,
    text as _text,
    text_list as _text_list,
)
from .service import (
    _normalize_execution_record_payload,
    _safe_case_id,
)

LOGGER = logging.getLogger(__name__)
_RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{8,128}$")

def _settings() -> Any:
    """统一读取运行配置，避免在调用点重复导入配置对象。"""
    return get_settings()


__all__ = [
    "_GENERATION_CASE_SOURCE_VALUES",
    "_REVIEW_STATUS_ALIASES",
    "_RUN_ID_PATTERN",
    "_VIRTUAL_TEST_POINT_ELEMENTS",
    "_active_state_from_case",
    "_append_find_element_line",
    "_append_script_line_from_hint",
    "_append_unique_intent_id",
    "_asset_title_index",
    "_attach_test_point_asset_summary",
    "_build_generation_diagnostics_for_asset",
    "_build_runtime_view_from_entry",
    "_build_test_point_script_preview",
    "_candidate_from_asset_point",
    "_candidate_snapshot_from_candidate",
    "_candidate_snapshot_from_point",
    "_canonical_involved_elements_for_page",
    "_case_family_prefix",
    "_element_bindings_for_review",
    "_element_name_from_step",
    "_existing_case_id_for_source_intent",
    "_generated_case_plan_items",
    "_generation_failure_index",
    "_generation_failure_summary",
    "_input_value_from_step",
    "_intent_ids_from_case_steps",
    "_intent_type_from_case",
    "_is_generation_qualified_element",
    "_is_virtual_test_point_element",
    "_latest_execution_map",
    "_locator_preview_for_element",
    "_manual_point_from_candidate",
    "_normalize_points_involved_elements",
    "_page_object_generation_context",
    "_page_object_url_map",
    "_persist_runtime_run_to_case_center",
    "_point_review_status",
    "_point_step_texts",
    "_point_title",
    "_record_generation_failure",
    "_resolve_history_project_code",
    "_review_history_from_point",
    "_review_status_from_candidate",
    "_review_status_from_point",
    "_review_summary_from_points",
    "_selenium_by_expression",
    "_selenium_locator",
    "_settings",
    "_source_asset_for_case",
    "_source_asset_index",
    "_source_identity_from_case",
    "_steps_from_candidate",
    "_steps_hint_from_current_steps",
    "_structured_requirement_metadata_from_case",
    "_test_point_asset_state_paths",
    "_test_point_generation_state",
    "_workbench_test_case_list_item",
    "_xpath_literal",
]

# ---- 运行时视图构建 ----
def _build_runtime_view_from_entry(entry: dict[str, Any]) -> dict[str, Any]:
    """为 run_case 构建运行时视图回调：将 store 函数注入 service 调用。
    从 run_case 的闭包提取到模块级别——不依赖任何 run_case 局部变量。
    """
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
            run_id=run_id, project=project, page=page,
            read_json_list=store.read_json_list,
        ),
    )


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
    if normalized in _VIRTUAL_TEST_POINT_ELEMENTS or normalized.endswith("URL"):
        return True
    # URL 路径模式: /dashboard, #/login, http://...
    if normalized and (normalized.startswith("/") or normalized.startswith("#/") or normalized.startswith("http")):
        return True
    return False

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
    """Facade 的页面对象解析（Path B 使用）。

    通过 PageObjectRepository 查 DB，返回生成诊断结构。
    对应的 orchestrator: OrchestratorService._resolve_page_object()
    对应的 pipeline:   generate_pipeline.resolve_page_object()
    """
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
        if element_code and element_code not in canonical:
            canonical.append(element_code)
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


_ASSET_ID_LIKE_RE = re.compile(r"^[a-z0-9]+-web-[a-z0-9][a-z0-9-]*-(?:fn|sm|api|e2e)-ai-\d{4}$")


def _asset_display_title(incoming_title: str, *, page: str, asset_id: str, candidates: Any = None) -> str:
    """为测试点资产生成展示标题，避免 asset_id 直接作为标题显示。"""
    if incoming_title and not _ASSET_ID_LIKE_RE.match(incoming_title) and incoming_title != asset_id:
        return incoming_title
    if isinstance(candidates, list):
        for c in candidates:
            if isinstance(c, dict):
                t = _text(c.get("title") or c.get("summary"))
                if t and t != asset_id:
                    return t
    if page:
        return f"{page} 页面测试点资产集"
    return "测试点资产集"


def _normalize_asset_involved_elements_on_read(item: dict[str, Any], *, project: str, db: Session | None = None) -> None:
    """读取测试点资产时动态规范化 involved_elements，过滤无法映射到页面对象的 AI 原始名称。"""
    page = _text(item.get("page", ""))
    if not page:
        return
    if db is None:
        return
    page_context = _page_object_generation_context(db, project=project, page=page)
    if not page_context.get("page_object_found"):
        return
    # Normalize asset-level involved_elements
    raw_asset_elements = item.get("involved_elements", [])
    if isinstance(raw_asset_elements, list):
        item["involved_elements"] = _canonical_involved_elements_for_page(raw_asset_elements, page_context=page_context)
    # Normalize plan.points[].involved_elements
    plan = item.get("plan", {})
    if isinstance(plan.get("points"), list):
        plan["points"] = _normalize_points_involved_elements(plan["points"], page_context=page_context)
        # Normalize plan-level involved_elements (aggregate from points)
        plan_elements = plan.get("involved_elements", [])
        if isinstance(plan_elements, list):
            plan["involved_elements"] = _canonical_involved_elements_for_page(plan_elements, page_context=page_context)
        item["plan"] = plan


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








