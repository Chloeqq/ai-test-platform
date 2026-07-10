from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

import yaml

from app.core import page_analysis_rules
from app.core.page_analysis_pipeline import (
    consume_page_analysis_bundle,
    normalize_page_object_model,
    normalize_test_point_plan_model,
)
from app.services.workbench_page_surface_service import (
    _clamp_confidence,
    _dedup_keep_order,
    _list_value,
    surface_confidence_summary,
    surface_inferred_elements,
)
from shared_backend.type_utils import dict_value as _dict_value

LOGGER = logging.getLogger(__name__)


BuildExecutionPlanForRisk = Any
FindRunItem = Any
BuildRuntimeExecutionRecord = Any
RunOrchestratorRisk = Any
BuildRiskReport = Any



def default_page_elements(page: str) -> dict[str, dict[str, str]]:
    defaults = {
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
    page_key = str(page or "").strip()
    if page_key in defaults:
        return defaults[page_key]
    return {
        "login_button": {"locator_type": "role", "role": "button", "locator_value": "登录"},
        f"{page_key}_menu": {"locator_type": "role", "role": "menuitem", "locator_value": page_key},
        f"{page_key}_list_title": {"locator_type": "text", "locator_value": page_key},
    }



def load_latest_self_healing_result(artifacts_dir: Path) -> dict[str, Any]:
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


def ensure_page_object(
    page: str,
    *,
    page_objects_root: Path,
    default_page_elements_fn: Any,
) -> Path:
    page_object_path = page_objects_root / f"{page}.page-object.yaml"
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
    defaults = default_page_elements_fn(page)
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


def safe_element_key(value: str, fallback: str) -> str:
    return page_analysis_rules.safe_element_key(value, fallback)



def normalize_page_object_draft(
    payload: dict[str, Any] | None,
    *,
    page: str = "",
    path: str = "",
) -> dict[str, Any]:
    return normalize_page_object_model(payload, page=page, path=path)


def normalize_test_point_plan(
    payload: dict[str, Any] | None,
    *,
    strict: bool = False,
) -> dict[str, Any]:
    return normalize_test_point_plan_model(payload, strict=strict)


def consume_model_bundle(
    *,
    page: str,
    project: str = "default",
    case_id: str = "",
    page_url: str = "",
    page_surface: dict[str, Any] | None = None,
    page_object: dict[str, Any] | None = None,
    test_points: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return consume_page_analysis_bundle(
        page=page,
        project=project,
        case_id=case_id,
        page_url=page_url,
        page_surface=page_surface,
        page_object=page_object,
        test_points=test_points,
    )


def build_page_analysis_context(
    *,
    page: str,
    project: str = "default",
    case_id: str = "",
    page_url: str = "",
    page_surface: dict[str, Any] | None = None,
    page_object: dict[str, Any] | None = None,
    test_points: dict[str, Any] | None = None,
) -> dict[str, Any]:
    context = consume_model_bundle(
        page=page,
        project=project,
        case_id=case_id,
        page_url=page_url,
        page_surface=page_surface,
        page_object=page_object,
        test_points=test_points,
    )
    analysis_bundle = context.get("analysis_bundle") if isinstance(context.get("analysis_bundle"), dict) else {}
    return {
        "analysis_bundle": analysis_bundle,
        "page_surface": context.get("page_surface") if isinstance(context.get("page_surface"), dict) else {},
        "page_surface_summary": context.get("page_surface_summary") if isinstance(context.get("page_surface_summary"), dict) else {},
        "page_semantic": context.get("page_semantic") if isinstance(context.get("page_semantic"), dict) else {},
        "page_semantic_summary": context.get("page_semantic_summary") if isinstance(context.get("page_semantic_summary"), dict) else {},
        "page_object": context.get("page_object") if isinstance(context.get("page_object"), dict) else {},
        "page_object_summary": context.get("page_object_summary") if isinstance(context.get("page_object_summary"), dict) else {},
        "test_points": context.get("test_points") if isinstance(context.get("test_points"), dict) else {},
        "test_point_summary": context.get("test_point_summary") if isinstance(context.get("test_point_summary"), dict) else {},
        "model_versions": context.get("model_versions") if isinstance(context.get("model_versions"), dict) else {},
        "consumed_models": context.get("consumed_models") if isinstance(context.get("consumed_models"), dict) else {},
        "confidence": float(context.get("confidence", 0.0) or 0.0),
        "warnings": [str(item).strip() for item in context.get("warnings", []) if str(item).strip()] if isinstance(context.get("warnings"), list) else [],
        "requires_review": bool(context.get("requires_review", False)),
    }



def _requires_search_flow(requirement: str) -> bool:
    normalized = str(requirement or "").strip()
    if not normalized:
        return False
    keywords = ("search", "查询", "搜索", "筛选", "filter")
    return any(token.lower() in normalized.lower() for token in keywords)


def requires_search_flow(requirement: str) -> bool:
    return _requires_search_flow(requirement)


def extract_requirement_search_value(requirement: str) -> str:
    text = str(requirement or "")
    digit = re.search(r"([0-9]{1,20})", text)
    if digit:
        return digit.group(1)
    quoted = re.search(r"[\"'“”‘’]([^\"'“”‘’]{1,30})[\"'“”‘’]", text)
    if quoted:
        return quoted.group(1).strip()
    return "3"


def build_page_semantic_summary(
    page_semantic: dict[str, Any] | None,
    *,
    fallback_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = page_semantic if isinstance(page_semantic, dict) else {}
    summary = fallback_summary if isinstance(fallback_summary, dict) else {}
    if not payload and not summary:
        return {}
    primary_actions_raw = summary.get("primary_actions", payload.get("primary_actions", []))
    reason_codes_raw = summary.get("reason_codes", payload.get("reason_codes", []))
    warnings_raw = summary.get("warnings", payload.get("warnings", []))
    return {
        "page_type": str(summary.get("page_type", payload.get("page_type", ""))).strip(),
        "business_domain": str(summary.get("business_domain", payload.get("business_domain", ""))).strip(),
        "primary_goal": str(summary.get("primary_goal", payload.get("primary_goal", ""))).strip(),
        "primary_actions": [str(item).strip() for item in _list_value(primary_actions_raw) if str(item).strip()],
        "reason_codes": [str(item).strip() for item in _list_value(reason_codes_raw) if str(item).strip()],
        "confidence": _clamp_confidence(summary.get("confidence", payload.get("confidence", 0))),
        "requires_review": bool(summary.get("requires_review", payload.get("requires_review", False))),
        "warnings": [str(item).strip() for item in _list_value(warnings_raw) if str(item).strip()],
    }


def enhance_page_object_from_surface(
    page: str,
    surface: dict[str, Any],
    *,
    ensure_page_object_fn: Any,
    surface_inferred_elements_fn: Any,
) -> Path:
    page_object_path = ensure_page_object_fn(page)
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

    for element_name, element_def in surface_inferred_elements_fn(page, surface).items():
        elements[element_name] = element_def

    payload["elements"] = elements
    page_object_path.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return page_object_path


def build_requirement_steps(
    requirement: str,
    page: str,
    resolved_page_url: str,
    surface: dict[str, Any],
    *,
    requires_search_flow_fn: Any,
    extract_requirement_search_value_fn: Any,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    steps: list[dict[str, Any]] = [
        {"action": "login"},
        {"action": "goto", "value": resolved_page_url},
        {"action": "assert_url", "value": resolved_page_url},
    ]
    coverage: dict[str, Any] = {"status": "full", "missing": [], "notes": []}

    title_value = str(surface.get("page_title", "")).strip()
    requires_search = bool(requires_search_flow_fn(requirement))

    if requires_search:
        search_placeholder = str(surface.get("search_placeholder", "")).strip()
        query_button = str(surface.get("query_button_text", "")).strip()
        if search_placeholder and query_button:
            search_value = str(extract_requirement_search_value_fn(requirement)).strip() or "3"
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



def required_page_elements(page: str, requirement: str, surface: dict[str, Any]) -> list[str]:
    return page_analysis_rules.required_page_elements(page, requirement, surface)


def element_signature(element: Any) -> tuple[str, str, str]:
    if not isinstance(element, dict):
        return ("", "", "")
    locator_type = str(element.get("locator_type", "")).strip().lower()
    locator_value = str(element.get("locator_value", "")).strip()
    role = str(element.get("role", "")).strip().lower()
    return (locator_type, locator_value, role)


def steps_to_points(page: str, requirement: str, steps: list[dict[str, Any]]) -> dict[str, Any]:
    points: list[dict[str, Any]] = []
    for index, step in enumerate(steps, start=1):
        action = str((step or {}).get("action", "")).strip()
        if action == "login":
            point_type = "precondition"
            description = "Use the shared login entry step."
        elif action in {"goto", "click"}:
            point_type = "navigation"
            description = "Navigate to target page or element."
        elif action in {"assert_url", "assert_visible", "wait_for"}:
            point_type = "assertion"
            description = "Validate URL or element visibility."
        elif action == "fill":
            point_type = "input"
            description = "Fill search or form input."
        else:
            point_type = "action"
            description = "Execute interaction step."
        point_key = f"{page}-{index:02d}"
        point = {
            "key": point_key,
            "intent_id": point_key,
            "point_type": point_type,
            "action": action,
            "description": description,
            "step_index": index,
            "dependencies": [],
            "source_ids": [f"step:{index:02d}"],
            "steps": [{"action": action, "target": (step or {}).get("target", ""), "value": (step or {}).get("value")}],
            "warnings": [],
            "requires_review": False,
        }
        if "target" in step:
            point["target"] = step["target"]
        if "value" in step:
            point["value"] = step["value"]
        target_value = str(point.get("target", "")).strip()
        if target_value and not target_value.startswith(("http://", "https://", "/", "#")):
            point["involved_elements"] = [target_value]
        else:
            point["involved_elements"] = []
        confidence = 0.9
        point_warnings: list[str] = []
        if action == "login":
            confidence = 0.96
        elif action in {"goto", "assert_url"}:
            confidence = 0.94
        elif action in {"wait_for", "assert_visible"}:
            confidence = 0.86
        elif action == "fill":
            confidence = 0.8
        elif action == "click":
            confidence = 0.82
        if target_value.startswith("frame_"):
            confidence -= 0.22
            point_warnings.append("步骤依赖 iframe 内元素，建议人工确认。")
        if any(token in target_value for token in ["dialog", "pagination"]):
            confidence -= 0.15
            point_warnings.append("步骤依赖上下文敏感元素，建议确认定位稳定性。")
        if target_value in {"search_input", "search_button"} and not _requires_search_flow(requirement):
            confidence -= 0.12
            point_warnings.append("需求未显式声明搜索场景，但生成了搜索相关步骤。")
        confidence_value = _clamp_confidence(confidence)
        point["warnings"] = point_warnings
        point["confidence"] = confidence_value
        point["requires_review"] = confidence_value < 0.75 or bool(point_warnings)
        points.append(point)
    return annotate_test_point_plan_review(
        normalize_test_point_plan_model(
            {
                "version": "TestPointPlanV1",
                "project": "default",
                "case_id": "",
                "page": page,
                "source_type": "execution_steps",
                "requirement": [requirement],
                "generated_at": "",
                "points": points,
            },
            strict=False,
        )
    )



def annotate_test_point_plan_review(plan: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(plan, dict):
        return {}
    points = _list_value(plan.get("points"))
    confidence_values: list[float] = []
    warnings: list[str] = []
    requires_review = False
    pending_review_count = 0
    skip_suggestion_count = 0
    review_suggestion_count = 0
    execute_suggestion_count = 0
    dependency_review_count = 0
    low_confidence_dependency_point_count = 0
    missing_dependency_point_count = 0
    dependency_skip_count = 0
    involved_elements: list[str] = []
    for point in points:
        if not isinstance(point, dict):
            continue
        point_warnings = [str(item).strip() for item in _list_value(point.get("warnings")) if str(item).strip()]
        dependency_review = _dict_value(point.get("dependency_review"))
        low_confidence_dependencies = _list_value(dependency_review.get("low_confidence_dependencies"))
        missing_dependencies = [str(item).strip() for item in _list_value(dependency_review.get("missing_dependencies")) if str(item).strip()]
        dependency_propagated = bool(dependency_review.get("propagated"))
        confidence = point.get("confidence")
        if confidence is None:
            action = str(point.get("action", "")).strip()
            confidence = 0.9 if action in {"login", "goto", "assert_url"} else 0.82
            point["confidence"] = _clamp_confidence(confidence)
        else:
            point["confidence"] = _clamp_confidence(confidence)
        point["warnings"] = point_warnings
        point["requires_review"] = bool(point.get("requires_review")) or point["confidence"] < 0.75 or bool(point_warnings)
        if dependency_propagated:
            dependency_review_count += 1
        if low_confidence_dependencies:
            low_confidence_dependency_point_count += 1
        if missing_dependencies:
            missing_dependency_point_count += 1
        if missing_dependencies:
            point["suggestion"] = "skip"
            point["review_reason"] = f"测试点依赖元素未在页面分析中识别：{', '.join(missing_dependencies)}。"
            dependency_skip_count += 1
            skip_suggestion_count += 1
        elif low_confidence_dependencies or point["confidence"] < 0.6:
            point["suggestion"] = "skip"
            if low_confidence_dependencies:
                dependency_labels = [
                    f"{str(item.get('label', '')).strip() or str(item.get('key', '')).strip()}({int(_clamp_confidence(item.get('confidence', 0)) * 100)}%)"
                    for item in low_confidence_dependencies
                    if isinstance(item, dict)
                ]
                point["review_reason"] = f"测试点依赖低置信度元素：{', '.join(dependency_labels)}。"
                dependency_skip_count += 1
            else:
                point["review_reason"] = "测试点依赖低置信度元素或上下文，建议先人工确认后再执行。"
            skip_suggestion_count += 1
        elif point["requires_review"]:
            point["suggestion"] = "review"
            point["review_reason"] = "测试点存在低置信度信号，建议人工确认。"
            pending_review_count += 1
        else:
            point["suggestion"] = "execute"
            point["review_reason"] = ""
            execute_suggestion_count += 1
        if point.get("suggestion") == "review":
            review_suggestion_count += 1
        involved_elements.extend([str(item).strip() for item in _list_value(point.get("involved_elements")) if str(item).strip()])
        confidence_values.append(point["confidence"])
        warnings.extend(point_warnings)
        requires_review = requires_review or bool(point["requires_review"])
    plan["confidence"] = _clamp_confidence(sum(confidence_values) / len(confidence_values)) if confidence_values else 0.0
    plan["warnings"] = _dedup_keep_order(warnings)
    plan["requires_review"] = requires_review or bool(plan["warnings"]) or plan["confidence"] < 0.75
    plan["involved_elements"] = _dedup_keep_order(involved_elements)
    plan["review_summary"] = {
        "pending_review_count": pending_review_count,
        "skip_suggestion_count": skip_suggestion_count,
        "review_suggestion_count": review_suggestion_count,
        "execute_suggestion_count": execute_suggestion_count,
        "low_confidence_point_count": len([point for point in points if isinstance(point, dict) and _clamp_confidence(point.get("confidence", 0)) < 0.6]),
        "dependency_review_count": dependency_review_count,
        "low_confidence_dependency_point_count": low_confidence_dependency_point_count,
        "missing_dependency_point_count": missing_dependency_point_count,
        "dependency_skip_count": dependency_skip_count,
        "total_points": len([point for point in points if isinstance(point, dict)]),
        "involved_element_count": len(plan["involved_elements"]),
    }
    return normalize_test_point_plan_model(plan, strict=False)


def build_test_point_review_items(plan: dict[str, Any]) -> list[dict[str, Any]]:
    points = _list_value(plan.get("points")) if isinstance(plan, dict) else []
    review_items: list[dict[str, Any]] = []
    for point in points:
        if not isinstance(point, dict):
            continue
        confidence = _clamp_confidence(point.get("confidence", 0))
        warnings = [str(item).strip() for item in _list_value(point.get("warnings")) if str(item).strip()]
        requires_review = bool(point.get("requires_review")) or confidence < 0.75 or bool(warnings)
        suggestion = str(point.get("suggestion", "")).strip().lower()
        if not requires_review and suggestion not in {"review", "skip"}:
            continue
        review_items.append(
            {
                "key": str(point.get("intent_id") or point.get("key", "")).strip() or f"point-{len(review_items) + 1:02d}",
                "label": str(point.get("description", "")).strip() or str(point.get("key", "")).strip() or "测试点",
                "action": str(point.get("action", "")).strip(),
                "target": str(point.get("target", "")).strip(),
                "involved_elements": [str(item).strip() for item in _list_value(point.get("involved_elements")) if str(item).strip()],
                "description": str(point.get("description", "")).strip(),
                "confidence": confidence,
                "warnings": warnings,
                "suggestion": suggestion or ("skip" if confidence < 0.6 else "review"),
                "review_reason": str(point.get("review_reason", "")).strip()
                or ("测试点依赖低置信度元素或上下文。" if confidence < 0.6 else "测试点存在低置信度信号。"),
                "dependency_review": _dict_value(point.get("dependency_review")),
            }
        )
    return review_items


def build_page_object_quality(
    page: str,
    requirement: str,
    surface: dict[str, Any],
    page_object_path: Path,
    *,
    default_page_elements_fn: Any,
) -> dict[str, Any]:
    try:
        payload = yaml.safe_load(page_object_path.read_text(encoding="utf-8")) or {}
    except Exception:
        payload = {"page": page, "elements": default_page_elements_fn(page)}
    if not isinstance(payload, dict):
        payload = {}
    elements = payload.get("elements")
    if not isinstance(elements, dict):
        elements = default_page_elements_fn(page)

    required_elements = required_page_elements(page, requirement, surface)
    missing_required = [key for key in required_elements if key not in elements]

    surface_inferred = surface_inferred_elements(page, surface)
    inferred_candidates = list(surface_inferred.keys())
    added_from_surface = [
        key
        for key, expected in surface_inferred.items()
        if element_signature(elements.get(key)) == element_signature(expected)
    ]

    defaults = default_page_elements_fn(page)
    defaults_used = [
        key
        for key, expected in defaults.items()
        if element_signature(elements.get(key)) == element_signature(expected)
    ]

    next_actions: list[str] = []
    for key in missing_required:
        next_actions.append(f"补充 page object 元素：{key}")
    if _requires_search_flow(requirement):
        if not str(surface.get("search_placeholder", "")).strip():
            next_actions.append("页面分析器未识别到稳定搜索输入框，请补充页面对象 search_input。")
        if not str(surface.get("query_button_text", "")).strip():
            next_actions.append("页面分析器未识别到稳定查询按钮，请补充页面对象 search_button。")
    auth_state = _dict_value(surface.get("auth_state"))
    load_state = _dict_value(surface.get("load_state"))
    analysis = _dict_value(surface.get("analysis"))
    if bool(auth_state.get("redirected_to_login")):
        next_actions.append("页面分析器访问目标页时被重定向到登录页，请确认测试账号权限或页面 URL。")
    if not bool(auth_state.get("login_success", True)):
        next_actions.append("页面分析器登录状态不稳定，请检查测试账号或登录入口配置。")
    if not str(load_state.get("marker_selector", "")).strip():
        next_actions.append("页面分析器未等到稳定 DOM 标记，建议补充页面专属选择器或延长加载等待。")
    if bool(load_state.get("route_mismatch")):
        requested_route = str(load_state.get("requested_route", "")).strip() or "-"
        final_route = str(load_state.get("final_route", "")).strip() or "-"
        next_actions.append(f"页面分析器最终停留路由与预期不一致：expected={requested_route}, actual={final_route}。")
    iframe_count = int(surface.get("iframe_count", 0) or 0)
    if iframe_count > 0:
        next_actions.append(f"页面存在 {iframe_count} 个 iframe，当前分析结果可能未覆盖 iframe 内元素。")
    frame_surface = _dict_value(surface.get("frame_surface"))
    if int(frame_surface.get("accessible_count", 0) or 0) > 0:
        next_actions.append(f"已从 {int(frame_surface.get('accessible_count', 0) or 0)} 个可访问 iframe 中提取辅助元素，请优先复核这些元素。")
    if int(frame_surface.get("blocked_count", 0) or 0) > 0:
        next_actions.append(f"有 {int(frame_surface.get('blocked_count', 0) or 0)} 个 iframe 无法直接访问，建议补充 iframe 专属分析配置。")
    loading_mask_count = int(surface.get("loading_mask_count", 0) or 0)
    if loading_mask_count > 0:
        next_actions.append(f"页面仍存在 {loading_mask_count} 个加载态遮罩，请增加等待条件或稳定标记。")
    dialog_titles = [str(item).strip() for item in surface.get("dialog_titles", []) if str(item).strip()]
    if dialog_titles:
        next_actions.append(f"页面包含弹窗/对话框：{' / '.join(dialog_titles[:3])}，建议补充弹窗专属 page object 元素。")
    stability = _dict_value(load_state.get("stability"))
    if str(stability.get("status", "")).strip() not in {"", "stable"}:
        next_actions.append(
            f"页面 DOM 仍在变化（stability={str(stability.get('status', '')).strip() or 'unknown'}），建议增加异步组件稳定等待。"
        )
    next_actions = _dedup_keep_order(next_actions)
    surface_confidence = surface_confidence_summary(surface)
    candidate_map = {
        str(item.get("key", "")).strip(): item
        for item in _list_value(surface.get("element_candidates"))
        if isinstance(item, dict) and str(item.get("key", "")).strip()
    }
    low_confidence_items: list[dict[str, Any]] = []
    for key in required_elements:
        candidate = candidate_map.get(key)
        if not candidate:
            low_confidence_items.append(
                {
                    "key": key,
                    "label": key,
                    "confidence": 0.0,
                    "warnings": ["缺少对应的页面分析元素候选。"],
                    "reason": "missing_surface_candidate",
                }
            )
            continue
        confidence = _clamp_confidence(candidate.get("confidence", 0))
        if confidence < 0.75 or bool(candidate.get("requires_review")):
            low_confidence_items.append(
                {
                    "key": key,
                    "label": str(candidate.get("label", key)).strip() or key,
                    "confidence": confidence,
                    "warnings": [str(item).strip() for item in candidate.get("warnings", []) if str(item).strip()] if isinstance(candidate.get("warnings"), list) else [],
                    "reason": "candidate_low_confidence",
                }
            )
    confidence_factors = {
        "surface_confidence": surface_confidence.get("confidence", 0.0),
        "required_element_coverage": round((len(required_elements) - len(missing_required)) / max(1, len(required_elements)), 2) if required_elements else 1.0,
        "defaults_used_ratio": round(len(defaults_used) / max(1, len(elements)), 2) if elements else 0.0,
        "missing_required_ratio": round(len(missing_required) / max(1, len(required_elements)), 2) if required_elements else 0.0,
    }
    page_object_confidence = _clamp_confidence(
        (float(confidence_factors["surface_confidence"]) * 0.5)
        + (float(confidence_factors["required_element_coverage"]) * 0.3)
        + ((1.0 - float(confidence_factors["missing_required_ratio"])) * 0.2)
    )
    page_object_warnings = _dedup_keep_order(
        [str(item).strip() for item in surface_confidence.get("warnings", []) if str(item).strip()] + [
            "存在缺失的必需元素。" if missing_required else "",
            "存在低置信度页面元素，建议人工确认。" if low_confidence_items else "",
        ]
    )
    requires_review = bool(low_confidence_items) or bool(missing_required) or page_object_confidence < 0.75

    summary = {
        "status": "full" if not missing_required else "partial",
        "total_elements": len(elements),
        "required_elements": required_elements,
        "required_count": len(required_elements),
        "missing_required": missing_required,
        "missing_required_count": len(missing_required),
        "inferred_candidates": inferred_candidates,
        "inferred_candidate_count": len(inferred_candidates),
        "added_from_surface": added_from_surface,
        "added_from_surface_count": len(added_from_surface),
        "defaults_used": defaults_used,
        "defaults_used_count": len(defaults_used),
        "surface_health": str(analysis.get("surface_health", "ok")).strip() or "ok",
        "auth_state": auth_state,
        "load_state": load_state,
        "iframe_count": iframe_count,
        "loading_mask_count": loading_mask_count,
        "dialog_titles": dialog_titles,
        "frame_surface": frame_surface,
        "confidence": page_object_confidence,
        "confidence_factors": confidence_factors,
        "warnings": page_object_warnings,
        "low_confidence_items": low_confidence_items,
        "low_confidence_count": len(low_confidence_items),
        "requires_review": requires_review,
    }
    coverage = {
        "status": summary["status"],
        "missing_required": missing_required,
        "next_actions": next_actions,
        "confidence": page_object_confidence,
        "warnings": page_object_warnings,
        "requires_review": requires_review,
    }
    return normalize_page_object_draft(
        {
            "page": page,
            "path": str(page_object_path.resolve()),
            "elements": elements,
            "summary": summary,
            "coverage": coverage,
            "missing_elements": missing_required,
            "next_actions": next_actions,
            "confidence": page_object_confidence,
            "confidence_factors": confidence_factors,
            "warnings": page_object_warnings,
            "low_confidence_items": low_confidence_items,
            "requires_review": requires_review,
        },
        page=page,
        path=str(page_object_path.resolve()),
    )



# _normalize_risk_factors / build_risk_report / ... → 移至 workbench_analysis_risk.py
# 以下 import 保持向后兼容：所有外部调用者通过 workbench_analysis_service 访问这些函数。

from app.services.workbench_analysis_risk import (  # noqa: E402
    build_page_semantic_summary,
    build_review_section,
    build_risk_report_summary,
    build_risk_review_items,
    build_self_healing_summary,
    reviewer_display_name,
)
