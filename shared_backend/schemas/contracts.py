"""各 pipeline 契约（PageSurface、TestPointPlan 等）的 v1 归一化与版本常量。"""
from __future__ import annotations

from copy import deepcopy
from datetime_compat import UTC
from datetime import datetime
from typing import Any, cast


PAGE_SURFACE_VERSION = "PageSurfaceV1"
PAGE_SEMANTIC_MODEL_VERSION = "PageSemanticModelV1"
PAGE_OBJECT_DRAFT_VERSION = "PageObjectDraftV1"
TEST_POINT_PLAN_VERSION = "TestPointPlanV1"
PAGE_ANALYSIS_BUNDLE_VERSION = "PageAnalysisBundleV1"
EXECUTION_RECORD_VERSION = "ExecutionRecordV1"
EVIDENCE_MANIFEST_VERSION = "EvidenceManifestV1"
LEGACY_EVIDENCE_SCHEMA_VERSION = "evidence-manifest.v1"

_EVIDENCE_LIST_KEYS = (
    "screenshots",
    "html_pages",
    "meta_files",
    "analysis_files",
    "suggestion_files",
    "execution_record_files",
    "self_healing_result_files",
    "videos",
    "other_files",
)


def _string(value: Any, default: str = "") -> str:
    text = str(value if value is not None else "").strip()
    return text or default


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    results: list[str] = []
    for item in value:
        text = _string(item)
        if text:
            results.append(text)
    return results


def _dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return cast(dict[str, Any], value)
    return {}


def _list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return cast(list[Any], value)
    return []


def _dict_copy(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    copied = deepcopy(value)
    if isinstance(copied, dict):
        return cast(dict[str, Any], copied)
    return {}


def _dedup_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    results: list[str] = []
    for value in values:
        text = _string(value)
        if not text or text in seen:
            continue
        seen.add(text)
        results.append(text)
    return results


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return default


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _confidence(value: Any, default: float = 0.0) -> float:
    numeric = _float(value, default=default)
    return round(max(0.0, min(1.0, numeric)), 2)


def normalize_page_surface_v1(
    payload: dict[str, Any] | None,
    *,
    page: str = "",
    requested_url: str = "",
    strict: bool = False,
) -> tuple[dict[str, Any], list[str]]:
    """归一化 PageSurfaceV1，返回 (payload, warnings)。"""
    warnings: list[str] = []
    raw = payload if isinstance(payload, dict) else {}
    if not isinstance(payload, dict):
        warnings.append("page_surface payload is not an object; fallback defaults applied")

    version = _string(raw.get("version") or raw.get("schema_version"))
    if version and version not in {PAGE_SURFACE_VERSION, "page-surface.v1"}:
        warnings.append(f"unexpected page_surface version '{version}', coerced to {PAGE_SURFACE_VERSION}")

    normalized_page = _string(raw.get("page") or page)
    normalized_requested_url = _string(raw.get("requested_url") or requested_url)
    normalized_final_url = _string(raw.get("final_url") or raw.get("url"))

    frame_surface_raw = _dict(raw.get("frame_surface"))
    normalized_frames: list[dict[str, Any]] = []
    raw_frames = frame_surface_raw.get("frames")
    if isinstance(raw_frames, list):
        for index, item in enumerate(raw_frames, start=1):
            if not isinstance(item, dict):
                warnings.append(f"frame_surface.frames[{index}] is not an object; dropped")
                continue
            normalized_frames.append(
                {
                    "url": _string(item.get("url")),
                    "title": _string(item.get("title")),
                    "field_placeholders": _string_list(item.get("field_placeholders")),
                    "button_texts": _string_list(item.get("button_texts")),
                    "title_candidates": _string_list(item.get("title_candidates")),
                    "has_table": _bool(item.get("has_table"), default=False),
                    "has_form": _bool(item.get("has_form"), default=False),
                    "warnings": _string_list(item.get("warnings")),
                    "metadata": _dict_copy(item.get("metadata")),
                }
            )
    elif raw_frames is not None:
        warnings.append("frame_surface.frames is not an array; reset to empty list")

    auth_state_raw = _dict(raw.get("auth_state"))
    load_state_raw = _dict(raw.get("load_state"))
    stability_raw = _dict(load_state_raw.get("stability"))
    analysis_raw = _dict(raw.get("analysis"))

    normalized_candidates: list[dict[str, Any]] = []
    raw_candidates = raw.get("element_candidates")
    if isinstance(raw_candidates, list):
        for index, item in enumerate(raw_candidates, start=1):
            if not isinstance(item, dict):
                warnings.append(f"element_candidates[{index}] is not an object; dropped")
                continue
            confidence = _confidence(item.get("confidence"), default=0.0)
            candidate_warnings = _string_list(item.get("warnings"))
            locator_value = _string(item.get("locator_value"))
            if not locator_value:
                warnings.append(f"element_candidates[{index}] missing locator_value")
            normalized_candidates.append(
                {
                    "key": _string(item.get("key"), default=f"candidate-{index:02d}"),
                    "label": _string(item.get("label"), default=f"元素{index}"),
                    "locator_type": _string(item.get("locator_type"), default="css"),
                    "locator_value": locator_value,
                    "role": _string(item.get("role")),
                    "confidence": confidence,
                    "warnings": candidate_warnings,
                    "requires_review": _bool(item.get("requires_review"), default=(confidence < 0.75 or bool(candidate_warnings))),
                    "source": _string(item.get("source")),
                    "metadata": _dict_copy(item.get("metadata")),
                }
            )
    elif raw_candidates is not None:
        warnings.append("element_candidates is not an array; reset to empty list")

    summary_raw = _dict(raw.get("confidence_summary"))
    normalized_low_confidence_items: list[dict[str, Any]] = []
    raw_low_confidence_items = summary_raw.get("low_confidence_items")
    if isinstance(raw_low_confidence_items, list):
        for index, item in enumerate(raw_low_confidence_items, start=1):
            if not isinstance(item, dict):
                warnings.append(f"confidence_summary.low_confidence_items[{index}] is not an object; dropped")
                continue
            normalized_low_confidence_items.append(
                {
                    "key": _string(item.get("key"), default=f"candidate-{index:02d}"),
                    "label": _string(item.get("label"), default=f"元素{index}"),
                    "confidence": _confidence(item.get("confidence"), default=0.0),
                    "locator_type": _string(item.get("locator_type"), default="css"),
                    "locator_value": _string(item.get("locator_value")),
                    "warnings": _string_list(item.get("warnings")),
                }
            )
    elif raw_low_confidence_items is not None:
        warnings.append("confidence_summary.low_confidence_items is not an array; reset to empty list")

    if not normalized_low_confidence_items:
        for item in normalized_candidates:
            confidence = _confidence(item.get("confidence"), default=0.0)
            item_warnings = _string_list(item.get("warnings"))
            if confidence < 0.75 or _bool(item.get("requires_review"), default=False):
                normalized_low_confidence_items.append(
                    {
                        "key": _string(item.get("key")),
                        "label": _string(item.get("label")) or _string(item.get("key")),
                        "confidence": confidence,
                        "locator_type": _string(item.get("locator_type"), default="css"),
                        "locator_value": _string(item.get("locator_value")),
                        "warnings": item_warnings,
                    }
                )

    top_level_warnings = _string_list(raw.get("warnings"))
    summary_warnings = _string_list(summary_raw.get("warnings"))
    confidence_value = _confidence(
        summary_raw.get("confidence") if summary_raw else raw.get("confidence"),
        default=(
            sum(_confidence(item.get("confidence"), default=0.0) for item in normalized_candidates) / len(normalized_candidates)
            if normalized_candidates
            else 0.0
        ),
    )
    requires_review = _bool(
        raw.get("requires_review"),
        default=_bool(summary_raw.get("requires_review"), default=(confidence_value < 0.75 or bool(normalized_low_confidence_items))),
    )

    frame_surface = {
        "accessible_count": _int(frame_surface_raw.get("accessible_count"), default=len(normalized_frames)),
        "blocked_count": _int(frame_surface_raw.get("blocked_count")),
        "frames": normalized_frames[:5],
    }

    auth_state = {
        "login_url": _string(auth_state_raw.get("login_url")),
        "login_attempted": _bool(auth_state_raw.get("login_attempted"), default=False),
        "login_success": _bool(auth_state_raw.get("login_success"), default=True),
        "redirected_to_login": _bool(auth_state_raw.get("redirected_to_login"), default=False),
    }

    load_state = {
        "login_network_idle_reached": _bool(load_state_raw.get("login_network_idle_reached"), default=False),
        "target_network_idle_reached": _bool(load_state_raw.get("target_network_idle_reached"), default=False),
        "marker_selector": _string(load_state_raw.get("marker_selector")),
        "selector_wait_status": _string(load_state_raw.get("selector_wait_status"), default="unknown"),
        "requested_route": _string(load_state_raw.get("requested_route")),
        "final_route": _string(load_state_raw.get("final_route")),
        "route_mismatch": _bool(load_state_raw.get("route_mismatch"), default=False),
        "stability": {
            "status": _string(stability_raw.get("status"), default="unknown"),
            "stable": _bool(stability_raw.get("stable"), default=False),
            "sample_count": _int(stability_raw.get("sample_count")),
            "latest": _dict_copy(stability_raw.get("latest")),
            "previous": _dict_copy(stability_raw.get("previous")),
        },
    }
    frame_accessible_count = _int(frame_surface.get("accessible_count"), default=len(normalized_frames))
    frame_blocked_count = _int(frame_surface.get("blocked_count"))
    load_stability = _dict(load_state.get("stability"))
    stability_status = _string(load_stability.get("status"), default="unknown")

    dialog_titles = _string_list(raw.get("dialog_titles"))
    iframe_count = _int(raw.get("iframe_count"))
    loading_mask_count = _int(raw.get("loading_mask_count"))
    analysis = {
        "field_count": _int(analysis_raw.get("field_count")),
        "button_count": _int(analysis_raw.get("button_count")),
        "menu_count": _int(analysis_raw.get("menu_count")),
        "title_candidate_count": _int(analysis_raw.get("title_candidate_count")),
        "dialog_count": _int(analysis_raw.get("dialog_count"), default=len(dialog_titles)),
        "iframe_count": _int(analysis_raw.get("iframe_count"), default=iframe_count),
        "frame_accessible_count": _int(analysis_raw.get("frame_accessible_count"), default=frame_accessible_count),
        "frame_blocked_count": _int(analysis_raw.get("frame_blocked_count"), default=frame_blocked_count),
        "loading_mask_count": _int(analysis_raw.get("loading_mask_count"), default=loading_mask_count),
        "stability_status": _string(analysis_raw.get("stability_status"), default=stability_status),
        "warnings": _string_list(analysis_raw.get("warnings")),
        "surface_health": _string(analysis_raw.get("surface_health"), default="warn" if top_level_warnings else "ok"),
    }

    metadata = _dict_copy(raw.get("metadata"))
    normalized: dict[str, Any] = {
        "version": PAGE_SURFACE_VERSION,
        "schema_version": "page-surface.v1",
        "page": normalized_page,
        "requested_url": normalized_requested_url,
        "final_url": normalized_final_url,
        "url": normalized_final_url,
        "title": _string(raw.get("title")),
        "page_title": _string(raw.get("page_title")),
        "active_menu": _string(raw.get("active_menu")),
        "search_placeholder": _string(raw.get("search_placeholder")),
        "query_button_text": _string(raw.get("query_button_text")),
        "primary_button_text": _string(raw.get("primary_button_text")),
        "has_table": _bool(raw.get("has_table"), default=False),
        "has_form": _bool(raw.get("has_form"), default=False),
        "has_dialog": _bool(raw.get("has_dialog"), default=False),
        "dialog_titles": dialog_titles,
        "iframe_count": iframe_count,
        "frame_surface": frame_surface,
        "loading_mask_count": loading_mask_count,
        "body_text_length": _int(raw.get("body_text_length")),
        "structure": {
            "has_table": _bool(raw.get("has_table"), default=False),
            "has_form": _bool(raw.get("has_form"), default=False),
            "has_dialog": _bool(raw.get("has_dialog"), default=False),
            "dialog_titles": dialog_titles,
            "iframe_count": iframe_count,
            "loading_mask_count": loading_mask_count,
            "body_text_length": _int(raw.get("body_text_length")),
        },
        "auth_state": auth_state,
        "load_state": load_state,
        "analysis": analysis,
        "element_candidates": normalized_candidates,
        "confidence_summary": {
            "confidence": confidence_value,
            "warnings": _dedup_strings(summary_warnings),
            "low_confidence_items": normalized_low_confidence_items,
            "low_confidence_count": len(normalized_low_confidence_items),
            "requires_review": requires_review,
        },
        "confidence": confidence_value,
        "warnings": _dedup_strings(top_level_warnings + summary_warnings),
        "requires_review": requires_review,
        "metadata": metadata,
    }

    metadata.setdefault("normalizer", "shared_backend.schemas.normalize_page_surface_v1")
    metadata.setdefault("contract_stage", "rule_first_surface")

    if strict:
        if not normalized["page"]:
            raise ValueError("page_surface.page is required")
        if not (normalized["requested_url"] or normalized["final_url"]):
            raise ValueError("page_surface.requested_url or page_surface.final_url is required")
    return normalized, warnings


def normalize_page_object_draft_v1(
    payload: dict[str, Any] | None,
    *,
    page: str = "",
    path: str = "",
    strict: bool = False,
) -> tuple[dict[str, Any], list[str]]:
    """归一化 PageObjectDraftV1。"""
    warnings: list[str] = []
    raw = payload if isinstance(payload, dict) else {}
    if not isinstance(payload, dict):
        warnings.append("page_object payload is not an object; fallback defaults applied")

    version = _string(raw.get("version") or raw.get("schema_version"))
    if version and version not in {PAGE_OBJECT_DRAFT_VERSION, "page-object-draft.v1"}:
        warnings.append(f"unexpected page_object version '{version}', coerced to {PAGE_OBJECT_DRAFT_VERSION}")

    normalized_page = _string(raw.get("page") or page)
    normalized_path = _string(raw.get("path") or path)

    elements_raw = _dict(raw.get("elements"))
    normalized_elements: dict[str, dict[str, Any]] = {}
    for key, item in elements_raw.items():
        element_key = _string(key)
        if not element_key:
            warnings.append("page_object.elements contains blank key; dropped")
            continue
        if not isinstance(item, dict):
            warnings.append(f"page_object.elements['{element_key}'] is not an object; dropped")
            continue
        normalized_elements[element_key] = {
            "locator_type": _string(item.get("locator_type"), default="css"),
            "locator_value": _string(item.get("locator_value")),
            "role": _string(item.get("role")),
            "warnings": _string_list(item.get("warnings")),
            "metadata": _dict_copy(item.get("metadata")),
        }

    summary_raw = _dict(raw.get("summary"))
    coverage_raw = _dict(raw.get("coverage"))

    required_elements = _string_list(summary_raw.get("required_elements"))
    missing_required = _string_list(summary_raw.get("missing_required"))
    inferred_candidates = _string_list(summary_raw.get("inferred_candidates"))
    added_from_surface = _string_list(summary_raw.get("added_from_surface"))
    defaults_used = _string_list(summary_raw.get("defaults_used"))
    dialog_titles = _string_list(summary_raw.get("dialog_titles"))

    auth_state_raw = _dict(summary_raw.get("auth_state"))
    load_state_raw = _dict(summary_raw.get("load_state"))
    frame_surface_raw = _dict(summary_raw.get("frame_surface"))
    confidence_factors_raw = _dict(summary_raw.get("confidence_factors"))

    normalized_low_confidence_items: list[dict[str, Any]] = []
    raw_low_confidence_items = summary_raw.get("low_confidence_items") if isinstance(summary_raw.get("low_confidence_items"), list) else raw.get("low_confidence_items")
    if isinstance(raw_low_confidence_items, list):
        for index, item in enumerate(raw_low_confidence_items, start=1):
            if not isinstance(item, dict):
                warnings.append(f"page_object.low_confidence_items[{index}] is not an object; dropped")
                continue
            normalized_low_confidence_items.append(
                {
                    "key": _string(item.get("key"), default=f"element-{index:02d}"),
                    "label": _string(item.get("label"), default=f"元素{index}"),
                    "confidence": _confidence(item.get("confidence"), default=0.0),
                    "warnings": _string_list(item.get("warnings")),
                    "reason": _string(item.get("reason")),
                }
            )

    next_actions = _string_list(raw.get("next_actions") if isinstance(raw.get("next_actions"), list) else coverage_raw.get("next_actions"))
    top_level_warnings = _string_list(raw.get("warnings"))
    summary_warnings = _string_list(summary_raw.get("warnings"))
    coverage_warnings = _string_list(coverage_raw.get("warnings"))

    confidence_value = _confidence(
        raw.get("confidence"),
        default=_confidence(summary_raw.get("confidence"), default=0.0),
    )
    requires_review = _bool(
        raw.get("requires_review"),
        default=_bool(summary_raw.get("requires_review"), default=(bool(missing_required) or bool(normalized_low_confidence_items) or confidence_value < 0.75)),
    )

    coverage_status = _string(coverage_raw.get("status"), default=_string(summary_raw.get("status"), default="partial" if missing_required else "full"))
    coverage_missing_required = _string_list(coverage_raw.get("missing_required"))
    if not coverage_missing_required:
        coverage_missing_required = missing_required[:]

    missing_elements = _string_list(raw.get("missing_elements"))
    if not missing_elements:
        missing_elements = missing_required[:]

    normalized_element_inventory: list[dict[str, Any]] = []
    for key, element in normalized_elements.items():
        source_hint = "manual_or_existing"
        if key in added_from_surface:
            source_hint = "surface_inferred"
        elif key in defaults_used:
            source_hint = "default_match"
        normalized_element_inventory.append(
            {
                "key": key,
                "locator_type": _string(element.get("locator_type"), default="css"),
                "locator_value": _string(element.get("locator_value")),
                "role": _string(element.get("role")),
                "required": key in required_elements,
                "source_hint": source_hint,
                "risk_level": (
                    "HIGH"
                    if any(item.get("key") == key and _confidence(item.get("confidence"), default=0.0) < 0.6 for item in normalized_low_confidence_items)
                    else "LOW"
                ),
                "warnings": _string_list(element.get("warnings")),
                "metadata": _dict_copy(element.get("metadata")),
            }
        )

    normalized_summary = {
        "status": _string(summary_raw.get("status"), default="full" if not missing_required else "partial"),
        "total_elements": _int(summary_raw.get("total_elements"), default=len(normalized_elements)),
        "required_elements": required_elements,
        "required_count": _int(summary_raw.get("required_count"), default=len(required_elements)),
        "missing_required": missing_required,
        "missing_required_count": _int(summary_raw.get("missing_required_count"), default=len(missing_required)),
        "inferred_candidates": inferred_candidates,
        "inferred_candidate_count": _int(summary_raw.get("inferred_candidate_count"), default=len(inferred_candidates)),
        "added_from_surface": added_from_surface,
        "added_from_surface_count": _int(summary_raw.get("added_from_surface_count"), default=len(added_from_surface)),
        "defaults_used": defaults_used,
        "defaults_used_count": _int(summary_raw.get("defaults_used_count"), default=len(defaults_used)),
        "surface_health": _string(summary_raw.get("surface_health"), default="ok"),
        "auth_state": {
            "login_url": _string(auth_state_raw.get("login_url")),
            "login_attempted": _bool(auth_state_raw.get("login_attempted"), default=False),
            "login_success": _bool(auth_state_raw.get("login_success"), default=True),
            "redirected_to_login": _bool(auth_state_raw.get("redirected_to_login"), default=False),
        },
        "load_state": {
            "marker_selector": _string(load_state_raw.get("marker_selector")),
            "selector_wait_status": _string(load_state_raw.get("selector_wait_status"), default="unknown"),
            "requested_route": _string(load_state_raw.get("requested_route")),
            "final_route": _string(load_state_raw.get("final_route")),
            "route_mismatch": _bool(load_state_raw.get("route_mismatch"), default=False),
            "stability": _dict_copy(load_state_raw.get("stability")),
        },
        "iframe_count": _int(summary_raw.get("iframe_count")),
        "loading_mask_count": _int(summary_raw.get("loading_mask_count")),
        "dialog_titles": dialog_titles,
        "frame_surface": {
            "accessible_count": _int(frame_surface_raw.get("accessible_count")),
            "blocked_count": _int(frame_surface_raw.get("blocked_count")),
            "frames": list(_list(frame_surface_raw.get("frames"))),
        },
        "confidence": confidence_value,
        "confidence_factors": {
            "surface_confidence": _confidence(confidence_factors_raw.get("surface_confidence"), default=0.0),
            "required_element_coverage": _confidence(confidence_factors_raw.get("required_element_coverage"), default=0.0),
            "defaults_used_ratio": _confidence(confidence_factors_raw.get("defaults_used_ratio"), default=0.0),
            "missing_required_ratio": _confidence(confidence_factors_raw.get("missing_required_ratio"), default=0.0),
        },
        "warnings": _dedup_strings(summary_warnings),
        "low_confidence_items": normalized_low_confidence_items,
        "low_confidence_count": len(normalized_low_confidence_items),
        "requires_review": requires_review,
    }

    normalized_coverage = {
        "status": coverage_status,
        "missing_required": coverage_missing_required,
        "next_actions": next_actions,
        "confidence": _confidence(coverage_raw.get("confidence"), default=confidence_value),
        "warnings": _dedup_strings(coverage_warnings),
        "requires_review": _bool(coverage_raw.get("requires_review"), default=requires_review),
    }

    metadata = _dict_copy(raw.get("metadata"))
    normalized: dict[str, Any] = {
        "version": PAGE_OBJECT_DRAFT_VERSION,
        "schema_version": "page-object-draft.v1",
        "page": normalized_page,
        "path": normalized_path,
        "elements": normalized_elements,
        "element_inventory": normalized_element_inventory,
        "element_count": len(normalized_elements),
        "summary": normalized_summary,
        "coverage": normalized_coverage,
        "missing_elements": missing_elements,
        "next_actions": next_actions,
        "confidence": confidence_value,
        "warnings": _dedup_strings(top_level_warnings + summary_warnings + coverage_warnings),
        "low_confidence_items": normalized_low_confidence_items,
        "requires_review": requires_review,
        "metadata": metadata,
    }

    metadata.setdefault("normalizer", "shared_backend.schemas.normalize_page_object_draft_v1")
    metadata.setdefault("contract_stage", "rule_first_page_object")

    if strict:
        if not normalized["page"]:
            raise ValueError("page_object.page is required")
        if not normalized["path"]:
            raise ValueError("page_object.path is required")
    return normalized, warnings


def normalize_page_semantic_model_v1(
    payload: dict[str, Any] | None,
    *,
    page: str = "",
    requested_url: str = "",
    strict: bool = False,
) -> tuple[dict[str, Any], list[str]]:
    """归一化 PageSemanticModelV1。"""
    warnings: list[str] = []
    raw = payload if isinstance(payload, dict) else {}
    if not isinstance(payload, dict):
        warnings.append("page_semantic payload is not an object; fallback defaults applied")

    version = _string(raw.get("version") or raw.get("schema_version"))
    if version and version not in {PAGE_SEMANTIC_MODEL_VERSION, "page-semantic-model.v1"}:
        warnings.append(f"unexpected page_semantic version '{version}', coerced to {PAGE_SEMANTIC_MODEL_VERSION}")

    normalized_page = _string(raw.get("page") or page)
    normalized_requested_url = _string(raw.get("requested_url") or requested_url)
    top_level_warnings = _string_list(raw.get("warnings"))
    summary_raw = _dict(raw.get("summary"))
    signals_raw = _dict(raw.get("signals"))
    primary_actions = _dedup_strings(_string_list(raw.get("primary_actions")) or _string_list(summary_raw.get("primary_actions")))
    reason_codes = _dedup_strings(_string_list(raw.get("reason_codes")) or _string_list(summary_raw.get("reason_codes")))
    confidence_value = _confidence(
        raw.get("confidence"),
        default=_confidence(summary_raw.get("confidence"), default=0.0),
    )
    requires_review = _bool(
        raw.get("requires_review"),
        default=_bool(summary_raw.get("requires_review"), default=(confidence_value < 0.75 or bool(top_level_warnings))),
    )

    normalized_summary = {
        "page_type": _string(summary_raw.get("page_type"), default=_string(raw.get("page_type"), default="unknown")),
        "business_domain": _string(summary_raw.get("business_domain"), default=_string(raw.get("business_domain"), default="generic")),
        "primary_goal": _string(summary_raw.get("primary_goal"), default=_string(raw.get("primary_goal"), default="inspect_page")),
        "primary_actions": primary_actions,
        "reason_codes": reason_codes,
        "confidence": confidence_value,
        "warnings": _dedup_strings(_string_list(summary_raw.get("warnings")) + top_level_warnings),
        "requires_review": requires_review,
    }

    metadata = _dict_copy(raw.get("metadata"))
    normalized: dict[str, Any] = {
        "version": PAGE_SEMANTIC_MODEL_VERSION,
        "schema_version": "page-semantic-model.v1",
        "page": normalized_page,
        "requested_url": normalized_requested_url,
        "page_type": normalized_summary["page_type"],
        "business_domain": normalized_summary["business_domain"],
        "primary_goal": normalized_summary["primary_goal"],
        "primary_actions": primary_actions,
        "reason_codes": reason_codes,
        "signals": {
            "has_table": _bool(signals_raw.get("has_table"), default=False),
            "has_form": _bool(signals_raw.get("has_form"), default=False),
            "has_dialog": _bool(signals_raw.get("has_dialog"), default=False),
            "has_search": _bool(signals_raw.get("has_search"), default=False),
            "has_primary_action": _bool(signals_raw.get("has_primary_action"), default=False),
            "route_mismatch": _bool(signals_raw.get("route_mismatch"), default=False),
        },
        "summary": normalized_summary,
        "confidence": confidence_value,
        "warnings": _dedup_strings(top_level_warnings),
        "requires_review": requires_review,
        "metadata": metadata,
    }
    metadata.setdefault("normalizer", "shared_backend.schemas.normalize_page_semantic_model_v1")
    metadata.setdefault("contract_stage", "rule_first_page_semantic")

    if strict and not normalized["page"]:
        raise ValueError("page_semantic.page is required")
    return normalized, warnings


def normalize_test_point_plan_v1(payload: dict[str, Any] | None, *, strict: bool = False) -> tuple[dict[str, Any], list[str]]:
    """归一化 TestPointPlanV1（含 points、review_summary、coverage）。"""
    warnings: list[str] = []
    raw = payload if isinstance(payload, dict) else {}
    if not isinstance(payload, dict):
        warnings.append("test_point_plan payload is not an object; normalized to empty payload")

    version = _string(raw.get("version") or raw.get("schema_version"))
    if version and version not in {TEST_POINT_PLAN_VERSION, "test-point-plan.v1"}:
        warnings.append(f"unexpected test_point_plan version '{version}', coerced to {TEST_POINT_PLAN_VERSION}")

    requirement = raw.get("requirement")
    if isinstance(requirement, str):
        requirement_list = [_string(requirement)]
    else:
        requirement_list = _string_list(requirement)

    points_raw = raw.get("points")
    points: list[dict[str, Any]] = []
    if isinstance(points_raw, list):
        for index, item in enumerate(points_raw, start=1):
            if not isinstance(item, dict):
                warnings.append(f"points[{index}] is not an object; dropped")
                continue
            target = _string(item.get("target"))
            involved_elements_raw = _string_list(item.get("involved_elements"))
            confidence_raw = item.get("confidence")
            confidence_value = _confidence(confidence_raw) if confidence_raw is not None else None
            point_warnings = _string_list(item.get("warnings"))
            suggestion = _string(item.get("suggestion"))
            inferred_requires_review = bool(point_warnings) or (confidence_value is not None and confidence_value < 0.75)
            dependency_review_raw = _dict(item.get("dependency_review"))
            low_confidence_dependencies_raw = dependency_review_raw.get("low_confidence_dependencies")
            normalized_low_confidence_dependencies: list[dict[str, Any]] = []
            if isinstance(low_confidence_dependencies_raw, list):
                for dep_index, dep in enumerate(low_confidence_dependencies_raw, start=1):
                    if not isinstance(dep, dict):
                        warnings.append(f"points[{index}].dependency_review.low_confidence_dependencies[{dep_index}] is not an object; dropped")
                        continue
                    normalized_low_confidence_dependencies.append(
                        {
                            "key": _string(dep.get("key"), default=f"dependency-{dep_index:02d}"),
                            "label": _string(dep.get("label")) or _string(dep.get("key"), default=f"dependency-{dep_index:02d}"),
                            "confidence": _confidence(dep.get("confidence"), default=0.0),
                            "warnings": _string_list(dep.get("warnings")),
                        }
                    )
            key_value = _string(item.get("key"), default=f"point-{index:02d}")
            intent_id_value = _string(item.get("intent_id"))
            involved_elements = _string_list(item.get("involved_elements"))
            raw_steps = item.get("steps")
            normalized_steps: list[dict[str, Any]] | None = None
            if isinstance(raw_steps, list) and raw_steps:
                normalized_steps = []
                for step_item in raw_steps:
                    if isinstance(step_item, dict):
                        normalized_steps.append({
                            "action": _string(step_item.get("action")),
                            "target": _string(step_item.get("target")),
                            "target_name": _string(step_item.get("target_name")),
                            "data_ref": _string(step_item.get("data_ref")),
                            "value": step_item.get("value"),
                            "attribute": _string(step_item.get("attribute")),
                            "expected_result": _string(step_item.get("expected_result") or step_item.get("expected")),
                            "raw_text": _string(
                                step_item.get("raw_text")
                                or step_item.get("description")
                                or step_item.get("summary")
                                or step_item.get("action")
                            ),
                        })
                    elif step_item is not None:
                        text = _string(step_item)
                        if text:
                            normalized_steps.append({"raw_text": text})
            point = {
                "key": key_value,
                "intent_id": intent_id_value,
                "point_type": _string(item.get("point_type"), default="action"),
                "action": _string(item.get("action")),
                "description": _string(item.get("description"), default=""),
                "field_key": _string(item.get("field_key")),
                "target": target,
                "value": item.get("value"),
                "parameter_location": _string(item.get("parameter_location")),
                "api_method": _string(item.get("api_method")),
                "api_path": _string(item.get("api_path")),
                "priority": _string(item.get("priority"), default="P1"),
                "expected_result": _string(item.get("expected_result") or item.get("expected")),
                "precondition": _string(item.get("precondition")),
                "steps_hint": _string_list(item.get("steps_hint")),
                "data": _dict_copy(item.get("data")),
                "dependencies": _string_list(item.get("dependencies")),
                "source_ids": _string_list(item.get("source_ids")),
                "involved_elements": _dedup_strings(involved_elements),
                "steps": normalized_steps,
                "step_index": _int(item.get("step_index"), default=index),
                "confidence": confidence_value,
                "technique_type": _string(item.get("technique_type"), default="normal"),
                "technique_source": _string(item.get("technique_source")),
                "technique_confidence": _confidence(
                    item.get("technique_confidence"),
                    default=(confidence_value if confidence_value is not None else 0.0),
                ),
                "execution_scope": _string(item.get("execution_scope"), default="mainline"),
                "warnings": point_warnings,
                "requires_review": _bool(item.get("requires_review"), default=inferred_requires_review),
                "suggestion": suggestion,
                "review_reason": _string(item.get("review_reason")),
                "dependency_review": {
                    "mode": _string(dependency_review_raw.get("mode"), default="none"),
                    "propagated": _bool(dependency_review_raw.get("propagated"), default=False),
                    "involved_elements": _dedup_strings(_string_list(dependency_review_raw.get("involved_elements")) or involved_elements_raw),
                    "matched_elements": _dedup_strings(_string_list(dependency_review_raw.get("matched_elements"))),
                    "low_confidence_dependencies": normalized_low_confidence_dependencies,
                    "low_confidence_dependency_count": _int(
                        dependency_review_raw.get("low_confidence_dependency_count"),
                        default=len(normalized_low_confidence_dependencies),
                    ),
                    "missing_dependencies": _dedup_strings(_string_list(dependency_review_raw.get("missing_dependencies"))),
                    "missing_dependency_count": _int(
                        dependency_review_raw.get("missing_dependency_count"),
                        default=len(_dedup_strings(_string_list(dependency_review_raw.get("missing_dependencies")))),
                    ),
                    "base_confidence": _confidence(
                        dependency_review_raw.get("base_confidence"),
                        default=confidence_value if confidence_value is not None else 0.0,
                    ),
                    "inherited_confidence": _confidence(
                        dependency_review_raw.get("inherited_confidence"),
                        default=confidence_value if confidence_value is not None else 0.0,
                    ),
                    "requires_review": _bool(
                        dependency_review_raw.get("requires_review"),
                        default=bool(normalized_low_confidence_dependencies or _string_list(dependency_review_raw.get("missing_dependencies"))),
                    ),
                    "evidence": _string_list(dependency_review_raw.get("evidence")),
                },
                "metadata": _dict_copy(item.get("metadata")),
            }
            points.append(point)
    elif points_raw is not None:
        warnings.append("points is not an array; reset to empty list")

    coverage_raw = _dict(raw.get("coverage"))
    review_summary_raw = _dict(raw.get("review_summary"))

    point_confidences = [float(item["confidence"]) for item in points if isinstance(item.get("confidence"), (int, float))]
    point_warnings = [warning for item in points for warning in _string_list(item.get("warnings"))]
    low_confidence_count = sum(
        1
        for item in points
        if isinstance(item.get("confidence"), (int, float)) and _float(item.get("confidence")) < 0.6
    )
    pending_review_count = sum(
        1
        for item in points
        if _bool(item.get("requires_review"), default=False)
        and _string(item.get("suggestion")).lower() != "skip"
    )
    skip_suggestion_count = sum(1 for item in points if _string(item.get("suggestion")).lower() == "skip")
    review_suggestion_count = sum(1 for item in points if _string(item.get("suggestion")).lower() == "review")
    execute_suggestion_count = sum(1 for item in points if _string(item.get("suggestion")).lower() == "execute")
    dependency_review_count = sum(
        1
        for item in points
        if isinstance(item.get("dependency_review"), dict) and _bool(item["dependency_review"].get("propagated"), default=False)
    )
    low_confidence_dependency_point_count = sum(
        1
        for item in points
        if isinstance(item.get("dependency_review"), dict)
        and _int(item["dependency_review"].get("low_confidence_dependency_count"), default=0) > 0
    )
    missing_dependency_point_count = sum(
        1
        for item in points
        if isinstance(item.get("dependency_review"), dict)
        and _int(item["dependency_review"].get("missing_dependency_count"), default=0) > 0
    )
    dependency_skip_count = sum(
        1
        for item in points
        if _string(item.get("suggestion")).lower() == "skip"
        and isinstance(item.get("dependency_review"), dict)
        and (
            _int(item["dependency_review"].get("low_confidence_dependency_count"), default=0) > 0
            or _int(item["dependency_review"].get("missing_dependency_count"), default=0) > 0
        )
    )
    mainline_point_count = sum(1 for item in points if _string(item.get("execution_scope")).lower() != "design_only")
    design_only_point_count = sum(1 for item in points if _string(item.get("execution_scope")).lower() == "design_only")
    technique_distribution: dict[str, int] = {}
    for item in points:
        technique_type = _string(item.get("technique_type"), default="normal").lower() or "normal"
        technique_distribution[technique_type] = technique_distribution.get(technique_type, 0) + 1
    involved_elements = _dedup_strings(
        [element for item in points for element in _string_list(item.get("involved_elements"))]
    )
    top_level_confidence = _confidence(
        raw.get("confidence"),
        default=(sum(point_confidences) / len(point_confidences) if point_confidences else 0.0),
    )
    top_level_requires_review = _bool(
        raw.get("requires_review"),
        default=(pending_review_count > 0 or skip_suggestion_count > 0 or top_level_confidence < 0.75),
    )

    metadata = _dict_copy(raw.get("metadata"))
    normalized: dict[str, Any] = {
        "version": TEST_POINT_PLAN_VERSION,
        "schema_version": "test-point-plan.v1",
        "project": _string(raw.get("project"), default="default"),
        "case_id": _string(raw.get("case_id")),
        "page": _string(raw.get("page"), default="product"),
        "page_url": _string(raw.get("page_url")),
        "title": _string(raw.get("title")),
        "priority": _string(raw.get("priority"), default="P1"),
        "source_name": _string(raw.get("source_name")),
        "source_ref": _string(raw.get("source_ref")),
        "source_type": _string(raw.get("source_type"), default="execution_steps"),
        "requirement": [item for item in requirement_list if item],
        "generated_at": _string(raw.get("generated_at"), default=datetime.now(UTC).isoformat()),
        "points": points,
        "point_count": len(points),
        "involved_elements": involved_elements,
        "coverage": {
            "status": _string(coverage_raw.get("status"), default="unknown"),
            "required_coverage": _string_list(coverage_raw.get("required_coverage")),
            "missing_coverage": _string_list(coverage_raw.get("missing_coverage")),
            "missing": _string_list(coverage_raw.get("missing")),
            "notes": _string_list(coverage_raw.get("notes")),
            "missing_required": _string_list(coverage_raw.get("missing_required")),
            "next_actions": _string_list(coverage_raw.get("next_actions")),
            "confidence": _confidence(coverage_raw.get("confidence"), default=top_level_confidence),
            "warnings": _string_list(coverage_raw.get("warnings")),
            "requires_review": _bool(coverage_raw.get("requires_review"), default=top_level_requires_review),
        },
        "review_summary": {
            "pending_review_count": _int(review_summary_raw.get("pending_review_count"), default=pending_review_count),
            "skip_suggestion_count": _int(review_summary_raw.get("skip_suggestion_count"), default=skip_suggestion_count),
            "review_suggestion_count": _int(review_summary_raw.get("review_suggestion_count"), default=review_suggestion_count),
            "execute_suggestion_count": _int(review_summary_raw.get("execute_suggestion_count"), default=execute_suggestion_count),
            "low_confidence_point_count": _int(review_summary_raw.get("low_confidence_point_count"), default=low_confidence_count),
            "dependency_review_count": _int(review_summary_raw.get("dependency_review_count"), default=dependency_review_count),
            "low_confidence_dependency_point_count": _int(
                review_summary_raw.get("low_confidence_dependency_point_count"),
                default=low_confidence_dependency_point_count,
            ),
            "missing_dependency_point_count": _int(
                review_summary_raw.get("missing_dependency_point_count"),
                default=missing_dependency_point_count,
            ),
            "dependency_skip_count": _int(review_summary_raw.get("dependency_skip_count"), default=dependency_skip_count),
            "total_points": _int(review_summary_raw.get("total_points"), default=len(points)),
            "involved_element_count": _int(review_summary_raw.get("involved_element_count"), default=len(involved_elements)),
            "mainline_point_count": _int(review_summary_raw.get("mainline_point_count"), default=mainline_point_count),
            "design_only_point_count": _int(review_summary_raw.get("design_only_point_count"), default=design_only_point_count),
            "technique_distribution": deepcopy(review_summary_raw.get("technique_distribution"))
            if isinstance(review_summary_raw.get("technique_distribution"), dict)
            else dict(sorted(technique_distribution.items())),
        },
        "metadata": metadata,
        "confidence": top_level_confidence,
        "warnings": _dedup_strings(_string_list(raw.get("warnings")) + point_warnings),
        "requires_review": top_level_requires_review,
    }
    if strict:
        if not normalized["case_id"]:
            raise ValueError("test_point_plan.case_id is required")
        if not normalized["points"]:
            raise ValueError("test_point_plan.points must not be empty")
    return normalized, warnings


def normalize_page_analysis_bundle_v1(
    payload: dict[str, Any] | None,
    *,
    strict: bool = False,
) -> tuple[dict[str, Any], list[str]]:
    """归一化 PageAnalysisBundleV1（聚合 surface/semantic/object/test_points）。"""
    warnings: list[str] = []
    raw = payload if isinstance(payload, dict) else {}
    if not isinstance(payload, dict):
        warnings.append("page_analysis_bundle payload is not an object; fallback defaults applied")

    version = _string(raw.get("version") or raw.get("schema_version"))
    if version and version not in {PAGE_ANALYSIS_BUNDLE_VERSION, "page-analysis-bundle.v1"}:
        warnings.append(f"unexpected page_analysis_bundle version '{version}', coerced to {PAGE_ANALYSIS_BUNDLE_VERSION}")

    page = _string(raw.get("page"))
    project = _string(raw.get("project"), default="default")
    case_id = _string(raw.get("case_id"))
    page_url = _string(raw.get("page_url"))

    surface_payload = _dict(raw.get("page_surface"))
    semantic_payload = _dict(raw.get("page_semantic"))
    object_payload = _dict(raw.get("page_object"))
    test_points_payload = _dict(raw.get("test_points"))

    normalized_surface, surface_warnings = normalize_page_surface_v1(
        surface_payload,
        page=page,
        requested_url=page_url,
        strict=strict,
    )
    normalized_object, object_warnings = normalize_page_object_draft_v1(
        object_payload,
        page=page,
        path=_string(object_payload.get("path")) if isinstance(object_payload, dict) else "",
        strict=strict,
    )
    normalized_semantic, semantic_warnings = normalize_page_semantic_model_v1(
        semantic_payload,
        page=page,
        requested_url=page_url,
        strict=strict,
    )
    normalized_points, point_warnings = normalize_test_point_plan_v1(
        test_points_payload,
        strict=strict,
    )

    surface_summary = _dict(normalized_surface.get("confidence_summary"))
    semantic_summary = _dict(normalized_semantic.get("summary"))
    object_summary = _dict(normalized_object.get("summary"))
    point_summary = _dict(normalized_points.get("review_summary"))

    model_versions = {
        "page_surface": _string(normalized_surface.get("version")),
        "page_semantic": _string(normalized_semantic.get("version")),
        "page_object": _string(normalized_object.get("version")),
        "test_points": _string(normalized_points.get("version")),
    }
    consumed_models = {
        "page_surface": _string(surface_summary.get("version"), default=model_versions["page_surface"]),
        "page_semantic": _string(semantic_summary.get("version"), default=model_versions["page_semantic"]),
        "page_object": _string(object_summary.get("version"), default=model_versions["page_object"]),
        "test_points": _string(point_summary.get("version"), default=model_versions["test_points"]),
    }

    surface_confidence = _confidence(normalized_surface.get("confidence"), default=0.0)
    semantic_confidence = _confidence(normalized_semantic.get("confidence"), default=0.0)
    object_confidence = _confidence(normalized_object.get("confidence"), default=0.0)
    points_confidence = _confidence(normalized_points.get("confidence"), default=0.0)
    confidence_values = [surface_confidence, semantic_confidence, object_confidence, points_confidence]
    bundle_confidence = _confidence(sum(confidence_values) / len(confidence_values) if any(confidence_values) else 0.0)
    bundle_requires_review = bool(
        normalized_surface.get("requires_review")
        or normalized_semantic.get("requires_review")
        or normalized_object.get("requires_review")
        or normalized_points.get("requires_review")
    )
    bundle_warnings = _dedup_strings(
        _string_list(raw.get("warnings"))
        + _string_list(normalized_surface.get("warnings"))
        + _string_list(normalized_semantic.get("warnings"))
        + _string_list(normalized_object.get("warnings"))
        + _string_list(normalized_points.get("warnings"))
        + surface_warnings
        + semantic_warnings
        + object_warnings
        + point_warnings
    )

    metadata = _dict_copy(raw.get("metadata"))
    normalized: dict[str, Any] = {
        "version": PAGE_ANALYSIS_BUNDLE_VERSION,
        "schema_version": "page-analysis-bundle.v1",
        "page": page,
        "project": project,
        "case_id": case_id,
        "page_url": page_url,
        "page_surface": normalized_surface,
        "page_surface_summary": surface_summary,
        "page_semantic": normalized_semantic,
        "page_semantic_summary": semantic_summary,
        "page_object": normalized_object,
        "page_object_summary": object_summary,
        "test_points": normalized_points,
        "test_point_summary": point_summary,
        "model_versions": model_versions,
        "consumed_models": consumed_models,
        "confidence": bundle_confidence,
        "warnings": bundle_warnings,
        "requires_review": bundle_requires_review,
        "metadata": metadata,
    }

    if strict:
        if not normalized["page"]:
            raise ValueError("page_analysis_bundle.page is required")
        if not normalized["page_surface"]:
            raise ValueError("page_analysis_bundle.page_surface is required")
        if not normalized["page_semantic"]:
            raise ValueError("page_analysis_bundle.page_semantic is required")
        if not normalized["page_object"]:
            raise ValueError("page_analysis_bundle.page_object is required")
        if not normalized["test_points"]:
            raise ValueError("page_analysis_bundle.test_points is required")
    return normalized, warnings


def normalize_execution_record_v1(payload: dict[str, Any] | None, *, strict: bool = False) -> tuple[dict[str, Any], list[str]]:
    """归一化 ExecutionRecordV1。"""
    warnings: list[str] = []
    raw = payload if isinstance(payload, dict) else {}
    if not isinstance(payload, dict):
        warnings.append("execution_record payload is not an object; fallback defaults applied")

    version = _string(raw.get("version") or raw.get("schema_version"))
    if version and version not in {EXECUTION_RECORD_VERSION, "execution-record.v1"}:
        warnings.append(f"unexpected execution_record version '{version}', coerced to {EXECUTION_RECORD_VERSION}")

    step_summary_raw = _dict(raw.get("step_summary"))
    evidence_raw = _dict(raw.get("evidence_index"))
    artifact_raw = _dict(evidence_raw.get("artifact_categories"))

    artifact_categories = {
        "screenshots": _int(artifact_raw.get("screenshots")),
        "html_pages": _int(artifact_raw.get("html_pages")),
        "meta_files": _int(artifact_raw.get("meta_files")),
        "analysis_files": _int(artifact_raw.get("analysis_files")),
        "suggestion_files": _int(artifact_raw.get("suggestion_files")),
        "execution_record_files": _int(artifact_raw.get("execution_record_files")),
        "self_healing_result_files": _int(artifact_raw.get("self_healing_result_files")),
        "videos": _int(artifact_raw.get("videos")),
        "other_files": _int(artifact_raw.get("other_files")),
    }

    metadata = _dict_copy(raw.get("metadata"))
    normalized: dict[str, Any] = {
        "version": EXECUTION_RECORD_VERSION,
        "schema_version": "execution-record.v1",
        "run_id": _string(raw.get("run_id")),
        "case_id": _string(raw.get("case_id")),
        "project": _string(raw.get("project"), default="default"),
        "source": _string(raw.get("source"), default="manual"),
        "mode": _string(raw.get("mode"), default="generate_only"),
        "status": _string(raw.get("status"), default="generated"),
        "started_at": _string(raw.get("started_at")),
        "finished_at": _string(raw.get("finished_at")),
        "step_summary": {
            "page": _string(step_summary_raw.get("page"), default=""),
            "requirement_count": _int(step_summary_raw.get("requirement_count")),
            "total_steps": _int(step_summary_raw.get("total_steps")),
            "action_types": sorted(set(_string_list(step_summary_raw.get("action_types")))),
        },
        "evidence_index": {
            "total_files": _int(evidence_raw.get("total_files")),
            "artifact_categories": artifact_categories,
            "runner_exit_code": evidence_raw.get("runner_exit_code"),
            "execution_requested": _bool(evidence_raw.get("execution_requested"), default=False),
        },
        "duration_seconds": raw.get("duration_seconds"),
        "artifact_dir": _string(raw.get("artifact_dir")),
        "metadata": metadata,
    }

    if strict:
        if not normalized["run_id"]:
            raise ValueError("execution_record.run_id is required")
        if not normalized["case_id"]:
            raise ValueError("execution_record.case_id is required")
    return normalized, warnings


def normalize_evidence_manifest_v1(payload: dict[str, Any] | None, *, strict: bool = False) -> tuple[dict[str, Any], list[str]]:
    """归一化 EvidenceManifestV1 及各证据文件列表。"""
    warnings: list[str] = []
    raw = payload if isinstance(payload, dict) else {}
    if not isinstance(payload, dict):
        warnings.append("evidence_manifest payload is not an object; fallback defaults applied")

    version = _string(raw.get("version"))
    legacy_version = _string(raw.get("schema_version"))
    if version and version not in {EVIDENCE_MANIFEST_VERSION}:
        warnings.append(f"unexpected evidence_manifest version '{version}', coerced to {EVIDENCE_MANIFEST_VERSION}")
    if legacy_version and legacy_version != LEGACY_EVIDENCE_SCHEMA_VERSION:
        warnings.append(f"unexpected legacy evidence schema_version '{legacy_version}', coerced to {LEGACY_EVIDENCE_SCHEMA_VERSION}")

    evidence_lists: dict[str, list[str]] = {}
    for key in _EVIDENCE_LIST_KEYS:
        evidence_lists[key] = _string_list(raw.get(key))
    total_files = sum(len(items) for items in evidence_lists.values())
    normalized: dict[str, Any] = {
        "version": EVIDENCE_MANIFEST_VERSION,
        "schema_version": LEGACY_EVIDENCE_SCHEMA_VERSION,
        "generated_at": _string(raw.get("generated_at"), default=datetime.now(UTC).isoformat()),
        "artifact_root": _string(raw.get("artifact_root")),
        "metadata": _dict_copy(raw.get("metadata")),
        **evidence_lists,
        "total_files": total_files,
    }

    if strict:
        if not normalized["artifact_root"]:
            raise ValueError("evidence_manifest.artifact_root is required")
    return normalized, warnings
