from __future__ import annotations

from datetime_compat import UTC
from datetime import datetime
from typing import Any

from fastapi import HTTPException, Request, status
from shared_backend.case_ids import normalize_case_id
from shared_backend.type_utils import dict_value as _dict_value, list_value as _list_value

from app.core.security import decode_access_token

from . import workbench_state_store as state_store

PAGE_ALIAS_MAP = {
    "addprouct": "addproduct",
    "add-product": "addproduct",
}


from shared_backend.type_utils import dedup_keep_order as _dedup_keep_order


def _clamp_confidence(value: Any) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def _safe_case_id(raw: str) -> str:
    text = str(raw).strip()
    if not text:
        return f"case-general-{datetime.now(UTC).strftime('%H%M%S')}"
    return normalize_case_id(text)


def _normalize_page_slug(value: str) -> str:
    normalized = "".join(ch for ch in str(value).strip().lower() if ch.isalnum() or ch in {"-", "_"})
    normalized = PAGE_ALIAS_MAP.get(normalized, normalized)
    return normalized or "product"


def _normalize_history_text_list(value: Any, *, limit: int = 10) -> list[str]:
    items = value if isinstance(value, list) else []
    normalized = [str(item).strip() for item in items if str(item).strip()]
    return _dedup_keep_order(normalized)[:limit]


def _payload_value(payload: Any, key: str, default: Any = "") -> Any:
    if isinstance(payload, dict):
        return payload.get(key, default)
    return getattr(payload, key, default)


def _sanitize_review_items(items: list[dict[str, Any]], *, review_type: str) -> list[dict[str, Any]]:
    sanitized: list[dict[str, Any]] = []
    for index, raw in enumerate(items, start=1):
        if not isinstance(raw, dict):
            continue
        key = str(raw.get("intent_id") or raw.get("key") or raw.get("id") or f"{review_type}-{index:02d}").strip()
        label = str(raw.get("label") or raw.get("description") or key).strip() or key
        warnings = [str(item).strip() for item in raw.get("warnings", []) if str(item).strip()] if isinstance(raw.get("warnings"), list) else []
        entry = {
            "key": key,
            "label": label,
            "decision": str(raw.get("decision", "confirmed")).strip().lower() or "confirmed",
            "confidence": _clamp_confidence(raw.get("confidence", 0)),
            "warnings": _dedup_keep_order(warnings),
        }
        for field in ("locator_type", "locator_value", "action", "target", "description", "suggestion", "review_reason"):
            value = raw.get(field)
            if value is None:
                continue
            text = str(value).strip()
            if text:
                entry[field] = text
        raw_involved = raw.get("involved_elements")
        if isinstance(raw_involved, list):
            entry["involved_elements"] = [
                str(item).strip()
                for item in raw_involved
                if str(item).strip()
            ]
        dependency_review = _dict_value(raw.get("dependency_review"))
        if dependency_review:
            low_confidence_dependencies = _list_value(dependency_review.get("low_confidence_dependencies"))
            entry["dependency_review"] = {
                "mode": str(dependency_review.get("mode", "")).strip() or "none",
                "propagated": bool(dependency_review.get("propagated")),
                "involved_elements": [
                    str(item).strip()
                    for item in _list_value(dependency_review.get("involved_elements"))
                    if str(item).strip()
                ],
                "matched_elements": [
                    str(item).strip()
                    for item in _list_value(dependency_review.get("matched_elements"))
                    if str(item).strip()
                ],
                "low_confidence_dependencies": [
                    {
                        "key": str(item.get("key", "")).strip(),
                        "label": str(item.get("label", "")).strip(),
                        "confidence": _clamp_confidence(item.get("confidence", 0)),
                        "warnings": [
                            str(warning).strip()
                            for warning in item.get("warnings", [])
                            if str(warning).strip()
                        ] if isinstance(item.get("warnings"), list) else [],
                    }
                    for item in low_confidence_dependencies
                    if isinstance(item, dict)
                ],
                "missing_dependencies": [
                    str(item).strip()
                    for item in _list_value(dependency_review.get("missing_dependencies"))
                    if str(item).strip()
                ],
                "evidence": [
                    str(item).strip()
                    for item in _list_value(dependency_review.get("evidence"))
                    if str(item).strip()
                ],
            }
        sanitized.append(entry)
    return sanitized


def sanitize_review_items(items: list[dict[str, Any]], *, review_type: str) -> list[dict[str, Any]]:
    return _sanitize_review_items(items, review_type=review_type)


def review_decisions_for_run(
    run_id: str,
    *,
    project: str = "",
    page: str = "",
    read_json_list_fn: Any,
    review_decisions_file: Any,
    normalize_page_slug_fn: Any,
    normalize_review_type_fn: Any,
    normalize_review_status_fn: Any,
    sanitize_review_items_fn: Any,
) -> dict[tuple[str, str], dict[str, Any]]:
    normalized_run_id = str(run_id or "").strip()
    normalized_project = str(project or "").strip()
    normalized_page = normalize_page_slug_fn(page) if str(page).strip() else ""
    results: dict[tuple[str, str], dict[str, Any]] = {}
    if not normalized_run_id:
        return results
    for item in read_json_list_fn(review_decisions_file):
        if str(item.get("run_id", "")).strip() != normalized_run_id:
            continue
        if normalized_project and str(item.get("project", "")).strip() != normalized_project:
            continue
        item_page = normalize_page_slug_fn(str(item.get("page", "")).strip()) if str(item.get("page", "")).strip() else ""
        if normalized_page and item_page != normalized_page:
            continue
        try:
            review_type = normalize_review_type_fn(str(item.get("review_type", "")).strip())
        except HTTPException:
            continue
        results[(item_page, review_type)] = {
            "project": str(item.get("project", "mall")).strip() or "mall",
            "run_id": normalized_run_id,
            "case_id": _safe_case_id(str(item.get("case_id", "")).strip()) if str(item.get("case_id", "")).strip() else "",
            "page": item_page,
            "review_type": review_type,
            "status": normalize_review_status_fn(str(item.get("status", "confirmed")).strip() or "confirmed"),
            "items": sanitize_review_items_fn(item.get("items", []), review_type=review_type)
            if isinstance(item.get("items"), list)
            else [],
            "note": str(item.get("note", "")).strip(),
            "confirmed_by": str(item.get("confirmed_by", "")).strip() or "anonymous",
            "confirmed_by_role": str(item.get("confirmed_by_role", "")).strip() or "unknown",
            "confirmed_by_source": str(item.get("confirmed_by_source", "")).strip() or "system_default",
            "updated_at": str(item.get("updated_at", "")).strip(),
            "created_at": str(item.get("created_at", "")).strip(),
        }
    return results


def build_run_review_state_from_decisions(
    *,
    project: str,
    run_id: str,
    page: str = "",
    review_decisions_for_run_fn: Any,
    normalize_page_slug_fn: Any,
    build_review_section_fn: Any,
) -> dict[str, Any]:
    decisions = review_decisions_for_run_fn(run_id, project=project, page=page)
    if not decisions:
        return {}
    normalized_page = normalize_page_slug_fn(page) if str(page).strip() else ""
    if not normalized_page:
        first_key = next(iter(decisions.keys()), ("", ""))
        normalized_page = first_key[0]
    element_section = build_review_section_fn(
        review_type="element",
        items=[],
        existing_entry=decisions.get((normalized_page, "element")),
    )
    test_point_section = build_review_section_fn(
        review_type="test_point",
        items=[],
        existing_entry=decisions.get((normalized_page, "test_point")),
    )
    risk_section = build_review_section_fn(
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


def build_item_review_state(
    *,
    project: str,
    run_id: str,
    page: str,
    page_surface_summary: dict[str, Any],
    test_points: dict[str, Any],
    page_surface: dict[str, Any] | None = None,
    page_object: dict[str, Any] | None = None,
    risk_report: dict[str, Any] | None = None,
    normalize_page_slug_fn: Any,
    build_page_analysis_context_fn: Any,
    review_decisions_for_run_fn: Any,
    build_test_point_review_items_fn: Any,
    build_review_section_fn: Any,
    build_risk_review_items_fn: Any,
) -> dict[str, Any]:
    normalized_page = normalize_page_slug_fn(page)
    analysis_context = build_page_analysis_context_fn(
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
    decisions = review_decisions_for_run_fn(run_id, project=project, page=normalized_page)
    element_items = (
        consumed_surface_summary.get("low_confidence_items")
        if isinstance(consumed_surface_summary, dict) and isinstance(consumed_surface_summary.get("low_confidence_items"), list)
        else []
    )
    test_point_items = build_test_point_review_items_fn(consumed_test_points)
    element_section = build_review_section_fn(
        review_type="element",
        items=element_items,
        existing_entry=decisions.get((normalized_page, "element")),
    )
    test_point_section = build_review_section_fn(
        review_type="test_point",
        items=test_point_items,
        existing_entry=decisions.get((normalized_page, "test_point")),
    )
    risk_items = build_risk_review_items_fn(risk_report or {})
    risk_section = build_review_section_fn(
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


def normalize_review_type(value: str) -> str:
    review_type = str(value or "").strip().lower()
    if review_type in {"element", "test_point", "risk"}:
        return review_type
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="review_type must be one of: element, test_point, risk")


def normalize_review_status(value: str) -> str:
    review_status = str(value or "").strip().lower() or "confirmed"
    if review_status in {"pending", "confirmed", "skipped"}:
        return review_status
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="status must be one of: pending, confirmed, skipped")


def extract_review_actor(request: Request) -> dict[str, str]:
    auth_header = str(request.headers.get("authorization", "")).strip()
    if auth_header.lower().startswith("bearer "):
        token = auth_header[7:].strip()
        if token:
            try:
                payload = decode_access_token(token)
                username = str(payload.get("username", "")).strip()
                role = str(payload.get("role", "")).strip()
                if username:
                    return {
                        "confirmed_by": username,
                        "confirmed_by_role": role or "unknown",
                        "confirmed_by_source": "bearer_token",
                    }
            except HTTPException:
                pass

    for header_name, source_name in (
        ("x-user-name", "x-user-name"),
        ("x-forwarded-user", "x-forwarded-user"),
        ("remote-user", "remote-user"),
    ):
        username = str(request.headers.get(header_name, "")).strip()
        if username:
            return {
                "confirmed_by": username,
                "confirmed_by_role": str(request.headers.get("x-user-role", "")).strip() or "unknown",
                "confirmed_by_source": source_name,
            }

    return {
        "confirmed_by": "anonymous",
        "confirmed_by_role": "unknown",
        "confirmed_by_source": "system_default",
    }


def require_authenticated_review_actor(actor: dict[str, str]) -> dict[str, str]:
    source = str(actor.get("confirmed_by_source", "")).strip().lower()
    username = str(actor.get("confirmed_by", "")).strip()
    if source != "system_default" and username and username.lower() != "anonymous":
        return actor
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={
            "code": "review_auth_required",
            "message": "确认点属于审计动作，提交前请先登录。",
            "allowed_identity_sources": ["bearer_token", "x-user-name", "x-forwarded-user", "remote-user"],
        },
    )


def _review_entry_identity(item: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(item.get("project", "mall")).strip() or "mall",
        str(item.get("run_id", "")).strip(),
        _normalize_page_slug(str(item.get("page", "")).strip()) if str(item.get("page", "")).strip() else "",
        normalize_review_type(str(item.get("review_type", "")).strip()),
    )


def upsert_review_decision(payload: Any, *, actor: dict[str, str] | None = None) -> dict[str, Any]:
    review_type = normalize_review_type(_payload_value(payload, "review_type", ""))
    review_status = normalize_review_status(_payload_value(payload, "status", ""))
    normalized_page = _normalize_page_slug(_payload_value(payload, "page", ""))
    actor_info = actor if isinstance(actor, dict) else {}
    entry = {
        "project": str(_payload_value(payload, "project", "mall") or "mall").strip() or "mall",
        "run_id": str(_payload_value(payload, "run_id", "")).strip(),
        "case_id": _safe_case_id(str(_payload_value(payload, "case_id", "")).strip()) if str(_payload_value(payload, "case_id", "")).strip() else "",
        "page": normalized_page,
        "review_type": review_type,
        "status": review_status,
        "items": _sanitize_review_items(_payload_value(payload, "items", []) or [], review_type=review_type),
        "note": str(_payload_value(payload, "note", "") or "").strip(),
        "confirmed_by": str(actor_info.get("confirmed_by", "")).strip() or "anonymous",
        "confirmed_by_role": str(actor_info.get("confirmed_by_role", "")).strip() or "unknown",
        "confirmed_by_source": str(actor_info.get("confirmed_by_source", "")).strip() or "system_default",
        "updated_at": datetime.now(UTC).isoformat(),
    }
    identity = _review_entry_identity(entry)
    with state_store.FILE_LOCK:
        items = state_store.read_json_list(state_store.REVIEW_DECISIONS_FILE)
        for item in items:
            try:
                if _review_entry_identity(item) != identity:
                    continue
            except HTTPException:
                continue
            created_at = str(item.get("created_at", "")).strip() or entry["updated_at"]
            item.clear()
            item.update({**entry, "created_at": created_at})
            state_store.write_json_list(state_store.REVIEW_DECISIONS_FILE, items[:1000])
            return dict(item)
        record = {**entry, "created_at": entry["updated_at"]}
        items.insert(0, record)
        state_store.write_json_list(state_store.REVIEW_DECISIONS_FILE, items[:1000])
        return record


def build_review_audit_summary(review_state: dict[str, Any]) -> dict[str, Any]:
    state = review_state if isinstance(review_state, dict) else {}

    def _section_summary(review_type: str, label: str) -> dict[str, Any]:
        section = _dict_value(state.get(review_type))
        return {
            "review_type": review_type,
            "label": label,
            "status": str(section.get("status", "not_required")).strip() or "not_required",
            "candidate_count": int(section.get("candidate_count", 0) or 0),
            "confirmed_by": str(section.get("confirmed_by", "")).strip(),
            "confirmed_by_role": str(section.get("confirmed_by_role", "")).strip(),
            "actor_display": str(section.get("actor_display", "")).strip(),
            "updated_at": str(section.get("updated_at", "")).strip(),
        }

    sections = [
        _section_summary("element", "元素确认"),
        _section_summary("test_point", "测试点确认"),
        _section_summary("risk", "风险决策"),
    ]
    latest = sorted(
        [section for section in sections if section.get("updated_at")],
        key=lambda item: str(item.get("updated_at", "")),
        reverse=True,
    )
    return {
        "sections": sections,
        "pending_sections": int(state.get("pending_sections", 0) or 0),
        "confirmed_sections": int(state.get("confirmed_sections", 0) or 0),
        "latest_actor_display": str(latest[0].get("actor_display", "")).strip() if latest else "",
        "latest_updated_at": str(latest[0].get("updated_at", "")).strip() if latest else "",
    }


def build_review_audit_timeline(
    *,
    run_id: str,
    page: str = "",
    read_history_items: Any | None = None,
    normalize_page_slug_fn: Any | None = None,
) -> list[dict[str, Any]]:
    normalized_run_id = str(run_id or "").strip()
    normalize_page_slug = normalize_page_slug_fn if callable(normalize_page_slug_fn) else _normalize_page_slug
    normalized_page = normalize_page_slug(page) if str(page).strip() else ""
    if not normalized_run_id:
        return []

    history_items = read_history_items() if callable(read_history_items) else state_store.read_json_list(state_store.HISTORY_FILE)
    timeline: list[dict[str, Any]] = []
    for item in history_items:
        if not isinstance(item, dict):
            continue
        if str(item.get("run_id", "")).strip() != normalized_run_id:
            continue
        item_page = normalize_page_slug(str(item.get("page", "")).strip()) if str(item.get("page", "")).strip() else ""
        if normalized_page and item_page != normalized_page:
            continue
        action = str(item.get("action", "")).strip().lower()
        is_review_event = action.startswith("review_")
        is_execution_gate_event = action.startswith("execution_gate_")
        if not is_review_event and not is_execution_gate_event:
            continue
        matched_rules = _list_value(item.get("matched_rules"))
        review_items = _list_value(item.get("review_items"))
        timeline.append(
            {
                "timestamp": str(item.get("timestamp", "")).strip(),
                "action": str(item.get("action", "")).strip(),
                "review_type": str(item.get("review_type", "")).strip() or ("execution_gate" if is_execution_gate_event else ""),
                "status": str(item.get("status", "")).strip(),
                "page": item_page,
                "case_id": str(item.get("case_id", "")).strip(),
                "actor_display": str(item.get("actor_display", "")).strip(),
                "confirmed_by": str(item.get("confirmed_by", "")).strip(),
                "confirmed_by_role": str(item.get("confirmed_by_role", "")).strip(),
                "detail_summary": str(item.get("detail_summary", "")).strip(),
                "note": str(item.get("note", "")).strip(),
                "decision": str(item.get("decision", "")).strip(),
                "approval_status": str(item.get("approval_status", "")).strip(),
                "record_status": str(item.get("record_status", "")).strip(),
                "gate_reason_summary": str(item.get("gate_reason_summary", "")).strip(),
                "matched_rules": [
                    {
                        "level": str(rule.get("level", "")).strip(),
                        "message": str(rule.get("message", "")).strip(),
                    }
                    for rule in matched_rules
                    if isinstance(rule, dict) and str(rule.get("message", "")).strip()
                ][:10],
                "evidence": _normalize_history_text_list(item.get("evidence"), limit=10),
                "metrics": item.get("metrics") if isinstance(item.get("metrics"), dict) else {},
                "config_snapshot": item.get("config_snapshot") if isinstance(item.get("config_snapshot"), dict) else {},
                "review_item_count": int(item.get("review_item_count", 0) or 0),
                "review_items": [
                    str(value).strip()
                    for value in review_items
                    if str(value).strip()
                ][:10],
            }
        )
    timeline.sort(key=lambda entry: str(entry.get("timestamp", "")))
    return timeline
