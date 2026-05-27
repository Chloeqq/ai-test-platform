from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Callable

import yaml

from shared_backend.type_utils import dict_value as _dict_value

from app.core import page_analysis_rules
from app.core.page_analysis_pipeline import (
    consume_page_analysis_bundle,
    normalize_page_object_model,
    normalize_test_point_plan_model,
)

from app.services.workbench_page_surface_service import (
    _dedup_keep_order,
    _clamp_confidence,
    _list_value,
    extract_page_from_url,
    resolve_page_url,
    route_signature,
    is_allowed_host_pattern,
    is_private_or_local_hostname,
    validate_page_surface_url,
    build_surface_element_candidate,
    build_surface_element_candidates,
    surface_confidence_summary,
    surface_inferred_elements,
    build_surface_result_from_snapshot,
    normalize_page_surface,
    compute_surface_stability,
    wait_for_surface_stable,
    collect_frame_surface,
    extract_page_surface,
    _surface_candidate_confidence_index,
    surface_candidate_confidence_index,
    inherit_test_point_confidence_from_surface,
)

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


def _normalize_risk_factors(
    factors: list[Any] | None,
    *,
    source: str,
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    if not isinstance(factors, list):
        return normalized
    for item in factors[:20]:
        if not isinstance(item, dict):
            continue
        factor = str(item.get("factor", item.get("name", ""))).strip() or "factor"
        reason = str(item.get("reason", item.get("detail", ""))).strip() or "-"
        category = str(item.get("category", "")).strip() or "unknown"
        try:
            factor_score = int(float(item.get("score", 0) or 0))
        except (TypeError, ValueError):
            factor_score = 0
        normalized.append(
            {
                "factor": factor,
                "score": factor_score,
                "reason": reason,
                "category": category,
                "source": source,
            }
        )
    return normalized


def normalize_risk_factors(
    factors: list[Any] | None,
    *,
    source: str,
) -> list[dict[str, Any]]:
    return _normalize_risk_factors(factors, source=source)


def _build_risk_evidence(*, factors: list[dict[str, Any]]) -> list[str]:
    evidence: list[str] = []
    for item in factors[:20]:
        if not isinstance(item, dict):
            continue
        factor = str(item.get("factor", "")).strip() or "factor"
        reason = str(item.get("reason", "")).strip() or "-"
        score = int(item.get("score", 0) or 0)
        evidence.append(f"{factor}={score} ({reason})")
    return evidence


def build_risk_evidence(*, factors: list[dict[str, Any]]) -> list[str]:
    return _build_risk_evidence(factors=factors)


def _build_semantic_risk_evidence(
    *,
    page_semantic_summary: dict[str, Any] | None,
) -> list[str]:
    payload = page_semantic_summary if isinstance(page_semantic_summary, dict) else {}
    if not payload:
        return []
    page_type = str(payload.get("page_type", "")).strip() or "unknown"
    business_domain = str(payload.get("business_domain", "")).strip() or "generic"
    primary_goal = str(payload.get("primary_goal", "")).strip() or "inspect_page"
    confidence = _clamp_confidence(payload.get("confidence", 0))
    requires_review = bool(payload.get("requires_review", False))
    return [
        "page_semantic="
        f"type:{page_type},domain:{business_domain},goal:{primary_goal},"
        f"confidence:{confidence:.2f},requires_review:{str(requires_review).lower()}"
    ]


def build_semantic_risk_evidence(
    *,
    page_semantic_summary: dict[str, Any] | None,
) -> list[str]:
    return _build_semantic_risk_evidence(page_semantic_summary=page_semantic_summary)


def _build_risk_factor_summary(*, factors: list[dict[str, Any]]) -> dict[str, Any]:
    if not factors:
        return {
            "factor_count": 0,
            "positive_factor_count": 0,
            "category_counts": {},
            "top_factor": {},
            "total_factor_score": 0,
        }
    category_counts: dict[str, int] = {}
    positive_factor_count = 0
    total_factor_score = 0
    top_factor: dict[str, Any] = {}
    top_score = -1
    for item in factors:
        if not isinstance(item, dict):
            continue
        category = str(item.get("category", "")).strip() or "unknown"
        factor_score = int(item.get("score", 0) or 0)
        category_counts[category] = category_counts.get(category, 0) + 1
        total_factor_score += factor_score
        if factor_score > 0:
            positive_factor_count += 1
        if factor_score > top_score:
            top_score = factor_score
            top_factor = {
                "factor": str(item.get("factor", "")).strip() or "factor",
                "score": factor_score,
                "reason": str(item.get("reason", "")).strip() or "-",
                "category": category,
            }
    return {
        "factor_count": len(factors),
        "positive_factor_count": positive_factor_count,
        "category_counts": dict(sorted(category_counts.items())),
            "top_factor": top_factor,
            "total_factor_score": total_factor_score,
        }


def build_risk_factor_summary(*, factors: list[dict[str, Any]]) -> dict[str, Any]:
    return _build_risk_factor_summary(factors=factors)


def build_risk_report_summary(risk_report: dict[str, Any] | None) -> dict[str, Any]:
    payload = risk_report if isinstance(risk_report, dict) else {}
    factor_summary = _dict_value(payload.get("factor_summary"))
    metadata = _dict_value(payload.get("metadata"))
    top_factor = _dict_value(factor_summary.get("top_factor"))
    return {
        "risk_level": str(payload.get("risk_level", "")).strip(),
        "gate_decision": str(payload.get("gate_decision", "")).strip(),
        "requires_review": bool(payload.get("requires_review", False)),
        "risk_score": int(payload.get("risk_score", 0) or 0),
        "factor_count": int(factor_summary.get("factor_count", metadata.get("factor_count", 0)) or 0),
        "positive_factor_count": int(factor_summary.get("positive_factor_count", 0) or 0),
        "top_factor": {
            "factor": str(top_factor.get("factor", "")).strip(),
            "score": int(top_factor.get("score", 0) or 0),
            "reason": str(top_factor.get("reason", "")).strip(),
            "category": str(top_factor.get("category", "")).strip(),
        }
        if top_factor
        else (
            metadata.get("top_factor")
            if isinstance(metadata.get("top_factor"), dict)
            else {}
        ),
        "provider": str(metadata.get("provider", payload.get("source", ""))).strip(),
        "source": str(payload.get("source", "")).strip(),
    }


def build_self_healing_summary(
    *,
    execution_record: dict[str, Any] | None,
    artifacts_dir: str = "",
    load_latest_self_healing_result_fn: Any | None = None,
) -> dict[str, Any]:
    record = execution_record if isinstance(execution_record, dict) else {}
    evidence_index = _dict_value(record.get("evidence_index"))
    artifact_categories = _dict_value(evidence_index.get("artifact_categories"))
    result_file_count = int(artifact_categories.get("self_healing_result_files", 0) or 0)
    attempted = result_file_count > 0
    result_payload = {}
    artifacts_dir_value = str(artifacts_dir or "").strip()
    if artifacts_dir_value and callable(load_latest_self_healing_result_fn):
        result_payload = load_latest_self_healing_result_fn(Path(artifacts_dir_value))
        if result_payload:
            attempted = True

    boundary = _dict_value(result_payload.get("boundary"))
    plan = _dict_value(result_payload.get("plan"))
    if not boundary:
        boundary = _dict_value(plan.get("boundary"))

    summary = {
        "attempted": attempted,
        "result_file_count": result_file_count,
        "status": str(result_payload.get("status", "")).strip(),
        "healed": bool(result_payload.get("healed", False)),
        "rolled_back": bool(result_payload.get("rolled_back", False)),
        "reason": str(result_payload.get("reason", "")).strip(),
        "result_path": str(result_payload.get("_result_path", "")).strip(),
        "plan_path": str(result_payload.get("plan_path", "")).strip(),
        "boundary": {
            "version": str(boundary.get("version", "")).strip(),
            "allowed": bool(boundary.get("allowed", False)),
            "advice_type": str(boundary.get("advice_type", "")).strip(),
            "reason": str(boundary.get("reason", "")).strip(),
        }
        if boundary
        else {},
    }
    if not attempted:
        summary["status"] = summary["status"] or "not_attempted"
    elif attempted and not summary["status"]:
        summary["status"] = "result_detected"
    return summary


def build_failure_analysis_for_risk(*, final_status: str, page_object_summary: dict[str, Any], test_points: dict[str, Any]) -> dict[str, Any]:
    status_value = str(final_status or "").strip().lower() or "unknown"
    point_summary = (test_points or {}).get("review_summary", {}) if isinstance(test_points, dict) else {}
    missing_required_count = int((page_object_summary or {}).get("missing_required_count", 0) or 0)
    skip_suggestions = int(point_summary.get("skip_suggestion_count", 0) or 0)
    if status_value in {"generate_failed", "failed"}:
        risk_level = "high"
        category = "execution_failure"
        summary = "执行失败，需优先人工处理。"
    elif status_value == "coverage_gap":
        risk_level = "medium"
        category = "coverage_gap"
        summary = "存在覆盖缺口，建议人工复核后再放行。"
    elif missing_required_count > 0 or skip_suggestions > 0:
        risk_level = "medium"
        category = "confidence_gap"
        summary = "关键元素或测试点存在不确定性，建议人工复核。"
    else:
        risk_level = "low"
        category = "stable"
        summary = "当前批次未发现高风险信号。"
    return {
        "summary": summary,
        "failure_category": category,
        "failure_source": "page_analysis" if category == "confidence_gap" else ("app_bug" if category == "execution_failure" else "unknown"),
        "failure_source_reason": "auto-generated from execution status and review metadata",
        "failure_source_confidence": 0.72 if category == "confidence_gap" else (0.68 if category == "execution_failure" else 0.55),
        "likely_cause": "auto-generated from execution status and review metadata",
        "risk_level": risk_level,
        "recommended_action": "manual_review" if risk_level in {"medium", "high"} else "allow",
        "confidence": "0.82",
        "requires_manual_review": risk_level in {"medium", "high"},
    }


def evaluate_risk_report(
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
    build_page_analysis_context_fn: Any = None,
    build_requirement_spec_for_risk_fn: Any = None,
    build_execution_plan_for_risk_fn: BuildExecutionPlanForRisk = None,
    find_run_item_fn: FindRunItem = None,
    build_runtime_execution_record_fn: BuildRuntimeExecutionRecord = None,
    run_orchestrator_risk_fn: RunOrchestratorRisk = None,
    build_risk_report_fn: BuildRiskReport = None,
    http_exception_cls: type[Exception] = Exception,
) -> dict[str, Any]:
    analysis_context = build_page_analysis_context_fn(
        page=page,
        project=project,
        case_id=str((run_id or "")).strip(),
        page_url="",
        page_surface=page_surface if isinstance(page_surface, dict) else {"confidence_summary": page_surface_summary or {}},
        page_object=page_object if isinstance(page_object, dict) else {"summary": page_object_summary or {}},
        test_points=test_points,
    )
    consumed_surface_summary = analysis_context.get("page_surface_summary") if isinstance(analysis_context.get("page_surface_summary"), dict) else (page_surface_summary or {})
    consumed_page_semantic_summary = _dict_value(analysis_context.get("page_semantic_summary"))
    consumed_page_object_summary = analysis_context.get("page_object_summary") if isinstance(analysis_context.get("page_object_summary"), dict) else (page_object_summary or {})
    consumed_test_points = analysis_context.get("test_points") if isinstance(analysis_context.get("test_points"), dict) else (test_points or {})
    consumed_model_versions = _dict_value(analysis_context.get("model_versions"))
    local_requirement_spec = requirement_spec if isinstance(requirement_spec, dict) and requirement_spec else build_requirement_spec_for_risk_fn(
        page=page,
        requirement=requirement,
        quality_gate=quality_gate,
    )
    execution_plan = build_execution_plan_for_risk_fn(
        page=page,
        steps=steps,
        test_points=consumed_test_points,
        coverage=_dict_value(consumed_test_points.get("coverage")),
        page_surface_summary=consumed_surface_summary,
        page_semantic_summary=consumed_page_semantic_summary,
        page_object_summary=consumed_page_object_summary,
        review_state=review_state,
        final_status=final_status,
    )
    run_item = find_run_item_fn(run_id) if run_id else None
    execution_record = (
        run_item.get("execution_record", {})
        if isinstance(run_item, dict) and isinstance(run_item.get("execution_record"), dict)
        else build_runtime_execution_record_fn(
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
    failure_analysis = build_failure_analysis_for_risk(
        final_status=final_status,
        page_object_summary=consumed_page_object_summary,
        test_points=consumed_test_points,
    )
    try:
        orchestrator_payload = run_orchestrator_risk_fn(
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
    except http_exception_cls as exc:
        default_report = build_risk_report_fn(
            page=page,
            final_status=final_status,
            page_surface_summary=consumed_surface_summary,
            page_semantic_summary=consumed_page_semantic_summary,
            page_object_summary=consumed_page_object_summary,
            test_points=consumed_test_points,
            review_state=review_state,
        )
        default_report["source"] = "local_default"
        default_report["warnings"] = [f"risk-evaluation-agent unavailable: {getattr(exc, 'detail', str(exc))}"]
        default_report["metadata"] = {
            **(default_report.get("metadata", {}) if isinstance(default_report.get("metadata"), dict) else {}),
            "consumed_models": consumed_model_versions,
        }
        return default_report
    except Exception as exc:  # pragma: no cover - keep risk path non-blocking
        default_report = build_risk_report_fn(
            page=page,
            final_status=final_status,
            page_surface_summary=consumed_surface_summary,
            page_semantic_summary=consumed_page_semantic_summary,
            page_object_summary=consumed_page_object_summary,
            test_points=consumed_test_points,
            review_state=review_state,
        )
        default_report["source"] = "local_default"
        default_report["warnings"] = [f"risk-evaluation-agent failed: {exc}"]
        default_report["metadata"] = {
            **(default_report.get("metadata", {}) if isinstance(default_report.get("metadata"), dict) else {}),
            "consumed_models": consumed_model_versions,
        }
        return default_report

    default_report = build_risk_report_fn(
        page=page,
        final_status=final_status,
        page_surface_summary=consumed_surface_summary,
        page_semantic_summary=consumed_page_semantic_summary,
        page_object_summary=consumed_page_object_summary,
        test_points=consumed_test_points,
        review_state=review_state,
    )
    default_report["metadata"] = {
        **(default_report.get("metadata", {}) if isinstance(default_report.get("metadata"), dict) else {}),
        "consumed_models": consumed_model_versions,
    }
    return default_report


def build_risk_review_items(risk_report: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(risk_report, dict) or not risk_report:
        return []
    evidence = [str(item).strip() for item in risk_report.get("evidence", []) if str(item).strip()] if isinstance(risk_report.get("evidence"), list) else []
    return [
        {
            "key": "risk_decision",
            "label": "风险决策确认",
            "confidence": _clamp_confidence(risk_report.get("confidence", 0)),
            "description": str(risk_report.get("recommendation", "")).strip(),
            "gate_decision": str(risk_report.get("gate_decision", "")).strip(),
            "risk_level": str(risk_report.get("risk_level", "")).strip(),
            "risk_score": int(risk_report.get("risk_score", 0) or 0),
            "warnings": evidence,
        }
    ]


def _reviewer_display_name(entry: dict[str, Any] | None) -> str:
    item = entry if isinstance(entry, dict) else {}
    username = str(item.get("confirmed_by", "")).strip()
    role = str(item.get("confirmed_by_role", "")).strip()
    if username and role and role != "unknown":
        return f"{username} ({role})"
    if username:
        return username
    return "anonymous"


def reviewer_display_name(entry: dict[str, Any] | None) -> str:
    return _reviewer_display_name(entry)


def build_review_section(
    *,
    review_type: str,
    items: list[dict[str, Any]],
    existing_entry: dict[str, Any] | None,
) -> dict[str, Any]:
    candidate_count = len([item for item in items if isinstance(item, dict)])
    if existing_entry:
        status_value = str(existing_entry.get("status", "confirmed")).strip() or "confirmed"
        reviewed_items = existing_entry.get("items") if isinstance(existing_entry.get("items"), list) else items
        return {
            "review_type": review_type,
            "required": candidate_count > 0,
            "status": status_value,
            "candidate_count": candidate_count,
            "items": reviewed_items,
            "updated_at": str(existing_entry.get("updated_at", "")).strip(),
            "note": str(existing_entry.get("note", "")).strip(),
            "confirmed_by": str(existing_entry.get("confirmed_by", "")).strip() or "anonymous",
            "confirmed_by_role": str(existing_entry.get("confirmed_by_role", "")).strip() or "unknown",
            "actor_display": _reviewer_display_name(existing_entry),
        }
    if candidate_count == 0:
        return {
            "review_type": review_type,
            "required": False,
            "status": "not_required",
            "candidate_count": 0,
            "items": [],
            "updated_at": "",
            "note": "",
            "confirmed_by": "",
            "confirmed_by_role": "",
            "actor_display": "",
        }
    return {
        "review_type": review_type,
        "required": True,
        "status": "pending",
        "candidate_count": candidate_count,
        "items": items,
        "updated_at": "",
        "note": "",
        "confirmed_by": "",
        "confirmed_by_role": "",
        "actor_display": "",
    }


def build_risk_report(
    *,
    page: str,
    final_status: str,
    page_surface_summary: dict[str, Any],
    page_semantic_summary: dict[str, Any] | None,
    page_object_summary: dict[str, Any],
    test_points: dict[str, Any],
    review_state: dict[str, Any],
) -> dict[str, Any]:
    status_value = str(final_status or "").strip().lower() or "unknown"
    score = 0
    factors: list[dict[str, Any]] = []

    def append_factor(*, factor: str, factor_score: int, reason: str, category: str) -> None:
        factors.append(
            {
                "factor": str(factor).strip() or "factor",
                "score": int(factor_score),
                "reason": str(reason).strip() or "-",
                "category": str(category).strip() or "unknown",
                "source": "local-rules",
            }
        )

    status_score_map = {
        "generate_failed": 95,
        "failed": 88,
        "coverage_gap": 72,
        "passed": 24,
        "running": 40,
    }
    status_score = status_score_map.get(status_value, 45)
    score += status_score
    append_factor(
        factor="execution_status",
        factor_score=status_score,
        reason=f"执行状态={status_value}",
        category="execution",
    )

    low_confidence_elements = int((page_surface_summary or {}).get("low_confidence_count", 0) or 0)
    if low_confidence_elements:
        element_penalty = min(18, low_confidence_elements * 4)
        score += element_penalty
        append_factor(
            factor="low_confidence_elements",
            factor_score=element_penalty,
            reason=f"低置信度元素 {low_confidence_elements} 个",
            category="page_surface",
        )

    page_object_missing = int((page_object_summary or {}).get("missing_required_count", 0) or 0)
    if page_object_missing:
        po_penalty = min(18, page_object_missing * 6)
        score += po_penalty
        append_factor(
            factor="missing_page_object_elements",
            factor_score=po_penalty,
            reason=f"Page Object 缺失必需元素 {page_object_missing} 个",
            category="page_object",
        )

    point_review_summary = (test_points or {}).get("review_summary", {}) if isinstance(test_points, dict) else {}
    pending_test_points = int(point_review_summary.get("pending_review_count", 0) or 0)
    skip_suggestions = int(point_review_summary.get("skip_suggestion_count", 0) or 0)
    if pending_test_points:
        point_penalty = min(12, pending_test_points * 3)
        score += point_penalty
        append_factor(
            factor="pending_test_points",
            factor_score=point_penalty,
            reason=f"待确认测试点 {pending_test_points} 个",
            category="test_point",
        )
    if skip_suggestions:
        skip_penalty = min(12, skip_suggestions * 4)
        score += skip_penalty
        append_factor(
            factor="skip_suggestions",
            factor_score=skip_penalty,
            reason=f"建议跳过测试点 {skip_suggestions} 个",
            category="test_point",
        )

    pending_sections = int((review_state or {}).get("pending_sections", 0) or 0)
    if pending_sections:
        review_penalty = min(12, pending_sections * 5)
        score += review_penalty
        append_factor(
            factor="pending_review_sections",
            factor_score=review_penalty,
            reason=f"仍有 {pending_sections} 个确认分组待处理",
            category="review",
        )

    score = max(0, min(score, 100))
    if score >= 75:
        risk_level = "high"
    elif score >= 45:
        risk_level = "medium"
    else:
        risk_level = "low"

    if status_value in {"generate_failed", "failed"}:
        gate_decision = "block"
    elif score >= 45 or pending_sections > 0:
        gate_decision = "manual_review"
    else:
        gate_decision = "allow"

    if gate_decision == "block":
        recommendation = "当前运行存在失败或生成阻断，建议先修复后再决定是否放行。"
    elif gate_decision == "manual_review":
        recommendation = "当前风险需要人工确认后再决定是否继续扩大发布或回归范围。"
    else:
        recommendation = "当前风险可控，可继续执行后续回归或放行。"

    confidence_inputs = 4
    confidence_hits = 0
    if isinstance(page_surface_summary, dict) and page_surface_summary:
        confidence_hits += 1
    if isinstance(page_object_summary, dict) and page_object_summary:
        confidence_hits += 1
    if isinstance(test_points, dict) and test_points.get("points"):
        confidence_hits += 1
    if isinstance(review_state, dict):
        confidence_hits += 1
    confidence = _clamp_confidence((confidence_hits / confidence_inputs) * 0.75 + 0.15)
    factor_summary = _build_risk_factor_summary(factors=factors)
    evidence = _build_risk_evidence(factors=factors)
    evidence.extend(_build_semantic_risk_evidence(page_semantic_summary=page_semantic_summary))

    return {
        "version": "RiskReportV1",
        "page": page,
        "risk_score": score,
        "risk_level": risk_level,
        "gate_decision": gate_decision,
        "recommendation": recommendation,
        "confidence": confidence,
        "factors": factors,
        "factor_summary": factor_summary,
        "evidence": evidence,
        "source": "local-rules",
        "warnings": [],
        "requires_review": gate_decision != "allow" or pending_sections > 0 or confidence < 0.75,
        "metadata": {
            "final_status": status_value,
            "low_confidence_elements": low_confidence_elements,
            "missing_page_object_elements": page_object_missing,
            "pending_test_points": pending_test_points,
            "skip_suggestions": skip_suggestions,
            "pending_review_sections": pending_sections,
            "semantic_page_type": str((page_semantic_summary or {}).get("page_type", "")).strip() or "unknown",
            "semantic_business_domain": str((page_semantic_summary or {}).get("business_domain", "")).strip() or "generic",
            "semantic_primary_goal": str((page_semantic_summary or {}).get("primary_goal", "")).strip() or "inspect_page",
            "semantic_requires_review": bool((page_semantic_summary or {}).get("requires_review", False)),
            "semantic_confidence": _clamp_confidence((page_semantic_summary or {}).get("confidence", 0)),
            "factor_count": int(factor_summary.get("factor_count", 0) or 0),
            "top_factor": factor_summary.get("top_factor", {}),
        },
    }


_build_failure_analysis_for_risk = build_failure_analysis_for_risk
_build_risk_review_items = build_risk_review_items
_build_review_section = build_review_section
