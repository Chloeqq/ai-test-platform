from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import HTTPException, status
from shared_backend.case_ids import normalize_client_code
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models.page_object import (
    PageElement,
    PageElementHealthCheck,
    PageElementLocator,
    PageElementVersion,
    PageObject,
    PageObjectCandidateElement,
    PageObjectCandidateGroup,
    PageObjectGovernanceLog,
    PageObjectRecorderSession,
    PageObjectRef,
)
from app.schemas.page_object import (
    CandidateGroupMergePayload,
    CandidateGroupPromotePayload,
    CandidateRejectPayload,
    PageElementCreate,
    PageElementUpdate,
    PageElementVersionCreate,
    PageObjectCreate,
    PageObjectRefCreate,
    PageObjectUpdate,
)
from app.services.page_element_code_policy import require_valid_element_code, suggest_business_element_code
from app.services import test_project_service

PAGE_OBJECT_STATUS_VALUES = {"draft", "review", "published", "retired"}
PAGE_ELEMENT_STATUS_VALUES = {"active", "inactive", "deprecated"}
LOCATOR_TYPE_VALUES = {"id", "name", "css", "xpath", "text", "placeholder", "role", "data-testid", "data-qa"}
REFERENCE_TYPE_VALUES = {"test_case", "script", "test_point", "plan", "suite"}
GOVERNANCE_STATUS_VALUES = {"draft", "active", "governing", "retired"}
ELEMENT_REVIEW_STATUS_VALUES = {"approved", "pending", "rejected"}
ELEMENT_STABILITY_LEVEL_VALUES = {"high", "medium", "low"}
ELEMENT_MATCH_STRATEGY_VALUES = {"exact", "alias", "derived", "composite", "template"}
ELEMENT_LOCATOR_SOURCE_VALUES = {"", "testid", "qa", "role_name", "placeholder", "id", "name", "css", "xpath", "manual"}
CANDIDATE_PROMOTION_STATUS_VALUES = {"pending", "partially_promoted", "promoted", "rejected"}
CANDIDATE_STATUS_VALUES = {"pending", "reviewed", "promoted", "rejected", "merged"}
BUSINESS_TYPE_VALUES = {
    "input",
    "button",
    "link",
    "menu",
    "tab",
    "switch",
    "checkbox",
    "radio",
    "dialog",
    "table",
    "container",
    "metric_label",
    "metric_value",
    "password_toggle",
}
BUSINESS_DOMAIN_VALUES = {"", "auth", "navigation", "dashboard", "search", "table", "form", "detail", "common"}
_RECORDER_ROOT = (Path(__file__).resolve().parents[4] / "artifacts" / "page-recorder").resolve()
_RECORDER_CLEANABLE_STATUSES = {"stopped", "failed"}


@dataclass(frozen=True)
class PageElementMutationResult:
    element: PageElement
    latest_version_no: int


def _normalize_project_code(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "", str(value or "").strip()).lower()
    if len(normalized) < 2 or len(normalized) > 20:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="project_code must be 2-20 letters or digits",
        )
    return normalized


def _normalize_identifier(value: str, *, field_name: str, min_length: int = 2, max_length: int = 80) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9_-]+", "-", str(value or "").strip()).strip("-").lower()
    if len(normalized) < min_length or len(normalized) > max_length:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{field_name} must be {min_length}-{max_length} chars and use letters/digits/_/-",
        )
    return normalized


def _normalize_page_object_status(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized not in PAGE_OBJECT_STATUS_VALUES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"page object status must be one of: {', '.join(sorted(PAGE_OBJECT_STATUS_VALUES))}",
        )
    return normalized


def _normalize_page_element_status(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized not in PAGE_ELEMENT_STATUS_VALUES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"page element status must be one of: {', '.join(sorted(PAGE_ELEMENT_STATUS_VALUES))}",
        )
    return normalized


def _normalize_governance_status(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized not in GOVERNANCE_STATUS_VALUES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"governance_status must be one of: {', '.join(sorted(GOVERNANCE_STATUS_VALUES))}",
        )
    return normalized


def _normalize_review_status(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized not in ELEMENT_REVIEW_STATUS_VALUES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"review_status must be one of: {', '.join(sorted(ELEMENT_REVIEW_STATUS_VALUES))}",
        )
    return normalized


def _normalize_stability_level(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized not in ELEMENT_STABILITY_LEVEL_VALUES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"stability_level must be one of: {', '.join(sorted(ELEMENT_STABILITY_LEVEL_VALUES))}",
        )
    return normalized


def _normalize_match_strategy(value: str) -> str:
    normalized = str(value or "").strip().lower() or "exact"
    if normalized not in ELEMENT_MATCH_STRATEGY_VALUES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"match_strategy must be one of: {', '.join(sorted(ELEMENT_MATCH_STRATEGY_VALUES))}",
        )
    return normalized


def _normalize_locator_source(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized not in ELEMENT_LOCATOR_SOURCE_VALUES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"locator_source must be one of: {', '.join(sorted(ELEMENT_LOCATOR_SOURCE_VALUES - {''}))}",
        )
    return normalized


def _normalize_locator_type(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized not in LOCATOR_TYPE_VALUES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"locator_type must be one of: {', '.join(sorted(LOCATOR_TYPE_VALUES))}",
        )
    return normalized


def _locator_source_from_type(locator_type: str) -> str:
    normalized = str(locator_type or "").strip().lower()
    if normalized == "data-testid":
        return "testid"
    if normalized == "data-qa":
        return "qa"
    if normalized == "role":
        return "role_name"
    if normalized in {"placeholder", "id", "name", "css", "xpath"}:
        return normalized
    return "manual"


def _stability_from_locator_source(locator_source: str, *, review_status: str = "approved") -> str:
    normalized = str(locator_source or "").strip().lower()
    if review_status == "approved" and normalized in {"testid", "qa"}:
        return "high"
    if normalized in {"role_name", "placeholder", "id", "name"}:
        return "medium"
    return "low"


def _validate_formal_element_governance_qualification(element: PageElement) -> None:
    """Keep approved high/medium elements aligned with the governance mapping contract."""
    review_status = str(element.review_status or "").strip().lower()
    stability_level = str(element.stability_level or "").strip().lower()
    locator_source = str(element.locator_source or "").strip().lower()
    locator_type = str(element.locator_type or "").strip().lower()
    testid_value = str(element.testid_value or "").strip()
    qa_value = str(element.qa_value or "").strip()

    if review_status != "approved":
        return

    if bool(element.is_key_element) and not testid_value and not qa_value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="approved key element requires testid_value or qa_value",
        )

    if stability_level == "high":
        if locator_source not in {"testid", "qa"}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="approved high stability element requires locator_source testid or qa",
            )
        if locator_source == "testid" and (locator_type != "data-testid" or not testid_value):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="approved high testid element requires locator_type data-testid and testid_value",
            )
        if locator_source == "qa" and (locator_type != "data-qa" or not qa_value):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="approved high qa element requires locator_type data-qa and qa_value",
            )
        return

    if stability_level == "medium":
        expected_locator_type_by_source = {
            "role_name": "role",
            "placeholder": "placeholder",
            "id": "id",
            "name": "name",
        }
        expected_locator_type = expected_locator_type_by_source.get(locator_source)
        if expected_locator_type is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="approved medium stability element requires locator_source role_name, placeholder, id, or name",
            )
        if locator_type != expected_locator_type:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"approved medium {locator_source} element requires locator_type {expected_locator_type}",
            )


def _normalize_business_type(value: str, fallback: str = "") -> str:
    normalized = str(value or fallback or "").strip().lower()
    if normalized and normalized not in BUSINESS_TYPE_VALUES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"business_type must be one of: {', '.join(sorted(BUSINESS_TYPE_VALUES))}",
        )
    return normalized


def _normalize_business_domain(value: str, fallback: str = "") -> str:
    normalized = str(value or fallback or "").strip().lower()
    if normalized not in BUSINESS_DOMAIN_VALUES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"business_domain must be one of: {', '.join(sorted(item for item in BUSINESS_DOMAIN_VALUES if item))}",
        )
    return normalized


def _normalize_formal_element_code(
    value: str,
    *,
    page_code: str = "",
    business_type: str = "",
    locator_source: str = "",
    locator_type: str = "",
    testid_value: str = "",
) -> str:
    return require_valid_element_code(
        value,
        page_code=page_code,
        business_type=business_type,
        locator_source=locator_source,
        locator_type=locator_type,
        testid_value=testid_value,
    )


def _locator_identity_key(locator_type: str, locator_value: str, role: str) -> tuple[str, str, str]:
    return (
        str(locator_type or "").strip().lower(),
        str(locator_value or "").strip(),
        str(role or "").strip().lower(),
    )


def _locator_relaxed_key(locator_type: str, locator_value: str) -> tuple[str, str]:
    return (
        str(locator_type or "").strip().lower(),
        str(locator_value or "").strip(),
    )


def _normalize_reference_type(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized not in REFERENCE_TYPE_VALUES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"reference_type must be one of: {', '.join(sorted(REFERENCE_TYPE_VALUES))}",
        )
    return normalized


def _normalize_binary_health_status(value: int) -> int:
    normalized = int(value)
    if normalized not in {0, 1}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="health_status must be 0 or 1",
        )
    return normalized


def _json_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _json_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _json_safe(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    return value


def _bounded_score(value: int | None) -> int:
    return max(0, min(100, int(value or 0)))


def _element_governance_payload(element: PageElement) -> dict[str, Any]:
    return {
        "element_code": element.element_code,
        "business_type": element.business_type,
        "business_domain": element.business_domain,
        "aliases_json": _json_list(element.aliases_json),
        "semantic_tags_json": _json_list(element.semantic_tags_json),
        "locator_source": element.locator_source,
        "match_strategy": element.match_strategy,
        "stability_level": element.stability_level,
        "review_status": element.review_status,
        "origin_candidate_key": element.origin_candidate_key,
        "route_scope": element.route_scope,
        "anchor_required": bool(element.anchor_required),
        "is_key_element": bool(element.is_key_element),
        "testid_value": element.testid_value,
        "qa_value": element.qa_value,
        "governance_note": element.governance_note,
    }


def _append_governance_note(existing: str | None, note: str) -> str:
    normalized_existing = str(existing or "").strip()
    normalized_note = str(note or "").strip()
    if not normalized_note:
        return normalized_existing
    if normalized_note in normalized_existing:
        return normalized_existing
    if not normalized_existing:
        return normalized_note[:4000]
    return f"{normalized_existing}\n{normalized_note}"[:4000]


def _write_governance_log(
    db: Session,
    *,
    page_object: PageObject,
    entity_type: str,
    entity_key: str,
    action: str,
    before_payload: dict[str, Any] | None = None,
    after_payload: dict[str, Any] | None = None,
    operator: str = "system",
) -> None:
    db.add(
        PageObjectGovernanceLog(
            project_code=page_object.project_code,
            client=page_object.client,
            page_code=page_object.page_code,
            entity_type=str(entity_type or "").strip(),
            entity_key=str(entity_key or "").strip(),
            action=str(action or "").strip(),
            before_payload=_json_safe(before_payload or {}),
            after_payload=_json_safe(after_payload or {}),
            operator=str(operator or "").strip() or "system",
        )
    )


def _page_object_governance_counts(db: Session, page_object: PageObject) -> dict[str, Any]:
    formal_element_count = int(
        db.execute(
            select(func.count()).select_from(PageElement).where(PageElement.page_object_id == page_object.id)
        ).scalar_one()
        or 0
    )
    approved_element_count = int(
        db.execute(
            select(func.count()).select_from(PageElement).where(
                PageElement.page_object_id == page_object.id,
                PageElement.status == "active",
                PageElement.review_status == "approved",
            )
        ).scalar_one()
        or 0
    )
    key_element_count = int(
        db.execute(
            select(func.count()).select_from(PageElement).where(
                PageElement.page_object_id == page_object.id,
                PageElement.is_key_element.is_(True),
            )
        ).scalar_one()
        or 0
    )
    pending_candidate_group_count = int(
        db.execute(
            select(func.count()).select_from(PageObjectCandidateGroup).where(
                PageObjectCandidateGroup.project_code == page_object.project_code,
                PageObjectCandidateGroup.client == page_object.client,
                PageObjectCandidateGroup.page_code == page_object.page_code,
                PageObjectCandidateGroup.promotion_status == "pending",
            )
        ).scalar_one()
        or 0
    )
    return {
        "formal_element_count": formal_element_count,
        "approved_element_count": approved_element_count,
        "key_element_count": key_element_count,
        "pending_candidate_group_count": pending_candidate_group_count,
        "key_element_coverage": round(key_element_count / approved_element_count, 4) if approved_element_count else 0.0,
    }


def _safe_unlink(path: Path) -> bool:
    try:
        if path.exists():
            path.unlink()
            return True
    except OSError:
        return False
    return False


def _resolve_recorder_artifact_path(raw_script_path: str) -> Path | None:
    normalized_raw = str(raw_script_path or "").strip()
    if not normalized_raw:
        return None
    try:
        resolved = Path(normalized_raw).expanduser().resolve()
    except OSError:
        return None
    try:
        resolved.relative_to(_RECORDER_ROOT)
    except ValueError:
        # Safety guard: never unlink outside recorder artifact root.
        return None
    return resolved


def _cleanup_page_recorder_assets(
    db: Session,
    *,
    project_code: str,
    client: str,
    page_code: str,
) -> dict[str, int]:
    sessions = list(
        db.execute(
            select(PageObjectRecorderSession).where(
                PageObjectRecorderSession.project_code == project_code,
                PageObjectRecorderSession.client == client,
                PageObjectRecorderSession.page_code == page_code,
            )
        ).scalars().all()
    )
    if not sessions:
        return {"recorder_sessions_removed_count": 0, "recorder_artifacts_removed_count": 0}

    removed_sessions = 0
    removed_artifacts = 0
    for item in sessions:
        if str(item.status or "").strip().lower() not in _RECORDER_CLEANABLE_STATUSES:
            continue
        script_path = _resolve_recorder_artifact_path(item.script_path)
        if script_path is not None:
            if _safe_unlink(script_path):
                removed_artifacts += 1
            if _safe_unlink(script_path.with_suffix(".steps.json")):
                removed_artifacts += 1
        db.delete(item)
        removed_sessions += 1

    if removed_sessions > 0:
        db.commit()
    return {
        "recorder_sessions_removed_count": removed_sessions,
        "recorder_artifacts_removed_count": removed_artifacts,
    }


def _serialize_page_object(item: PageObject, *, element_count: int = 0) -> dict[str, Any]:
    effective_element_count = int(element_count) if element_count >= 0 else int(item.element_count or 0)
    return {
        "id": item.id,
        "page_id": item.id,
        "project_code": item.project_code,
        "client": item.client,
        "page_code": item.page_code,
        "page_name": item.page_name,
        "page_url": item.page_url,
        "precondition_state": item.precondition_state,
        "route_pattern": item.route_pattern,
        "anchor_config_json": _json_dict(item.anchor_config_json),
        "governance_status": item.governance_status,
        "testability_score": _bounded_score(item.testability_score),
        "key_element_count": int(item.key_element_count or 0),
        "approved_element_count": int(item.approved_element_count or 0),
        "candidate_pending_count": int(item.candidate_pending_count or 0),
        "module_id": int(item.module_id or 0),
        "description": item.description,
        "status": item.status,
        "health_status": int(item.health_status if item.health_status is not None else 1),
        "created_by": item.created_by,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
        "create_time": item.created_at,
        "update_time": item.updated_at,
        "element_count": effective_element_count,
    }


def _serialize_page_element(
    item: PageElement,
    *,
    latest_version_no: int = 0,
    reference_count: int = 0,
    locators: list[PageElementLocator] | None = None,
) -> dict[str, Any]:
    serialized = {
        "id": item.id,
        "element_id": item.id,
        "page_object_id": item.page_object_id,
        "page_id": item.page_object_id,
        "element_code": item.element_code,
        "element_name": item.element_name,
        "locator_type": item.locator_type,
        "locator_value": item.locator_value,
        "backup_locator": item.backup_locator,
        "business_type": item.business_type,
        "business_domain": item.business_domain,
        "aliases_json": _json_list(item.aliases_json),
        "semantic_tags_json": _json_list(item.semantic_tags_json),
        "locator_source": item.locator_source,
        "match_strategy": item.match_strategy,
        "stability_level": item.stability_level,
        "review_status": item.review_status,
        "origin_candidate_key": item.origin_candidate_key,
        "route_scope": item.route_scope,
        "anchor_required": bool(item.anchor_required),
        "is_key_element": bool(item.is_key_element),
        "testid_value": item.testid_value,
        "qa_value": item.qa_value,
        "governance_note": item.governance_note,
        "health_status": int(item.health_status if item.health_status is not None else 1),
        "version": int(item.version if item.version is not None else 1),
        "role": item.role,
        "status": item.status,
        "is_primary": bool(item.is_primary),
        "owner": item.owner,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
        "create_time": item.created_at,
        "update_time": item.updated_at,
        "latest_version_no": int(latest_version_no),
        "reference_count": int(reference_count),
    }
    if locators is not None:
        serialized_locators = [_serialize_element_locator(locator) for locator in locators]
        serialized["locators"] = serialized_locators
        serialized["locator_count"] = len(serialized_locators)
        serialized["alternate_locator_count"] = len([locator for locator in serialized_locators if not locator["is_primary"]])
    return serialized


def _serialize_element_locator(item: PageElementLocator) -> dict[str, Any]:
    return {
        "id": item.id,
        "page_element_id": item.page_element_id,
        "locator_type": item.locator_type,
        "locator_value": item.locator_value,
        "role": item.role,
        "locator_source": item.locator_source,
        "priority": int(item.priority if item.priority is not None else 100),
        "is_primary": bool(item.is_primary),
        "health_status": item.health_status,
        "verification_status": item.verification_status,
        "last_verified_at": item.last_verified_at,
        "created_by": item.created_by,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


def _element_locators_for_serialization(db: Session, *, page_element_id: int) -> list[PageElementLocator]:
    return list(
        db.execute(
            select(PageElementLocator)
            .where(PageElementLocator.page_element_id == page_element_id)
            .order_by(PageElementLocator.is_primary.desc(), PageElementLocator.priority.asc(), PageElementLocator.id.asc())
        ).scalars().all()
    )


def _serialize_element_version(item: PageElementVersion) -> dict[str, Any]:
    return {
        "id": item.id,
        "page_element_id": item.page_element_id,
        "version_no": item.version_no,
        "locator_type": item.locator_type,
        "locator_value": item.locator_value,
        "role": item.role,
        "status": item.status,
        "is_primary": bool(item.is_primary),
        "changed_by": item.changed_by,
        "change_summary": item.change_summary,
        "created_at": item.created_at,
        "create_time": item.created_at,
    }


def _serialize_ref(item: PageObjectRef) -> dict[str, Any]:
    return {
        "id": item.id,
        "page_element_id": item.page_element_id,
        "reference_type": item.reference_type,
        "reference_key": item.reference_key,
        "source": item.source,
        "created_by": item.created_by,
        "created_at": item.created_at,
        "create_time": item.created_at,
    }


def _serialize_candidate_group(item: PageObjectCandidateGroup) -> dict[str, Any]:
    proposed_element_code = str(item.proposed_element_code or "").strip()
    if not proposed_element_code:
        proposed_element_code = suggest_business_element_code(
            str(item.proposed_element_name or item.top_locator_value or ""),
            page_code=str(item.page_code or ""),
            business_type=str(item.business_type_guess or ""),
        )
    return {
        "id": item.id,
        "project_code": item.project_code,
        "client": item.client,
        "page_code": item.page_code,
        "group_key": item.group_key,
        "proposed_element_code": proposed_element_code,
        "proposed_element_name": item.proposed_element_name,
        "business_type_guess": item.business_type_guess,
        "business_domain_guess": item.business_domain_guess,
        "quality_tier": item.quality_tier,
        "max_score": int(item.max_score or 0),
        "avg_score": int(item.avg_score or 0),
        "session_count": int(item.session_count or 0),
        "candidate_count": int(item.candidate_count or 0),
        "recommended_action": item.recommended_action,
        "promotion_status": item.promotion_status,
        "route_scope": item.route_scope,
        "top_locator_source": item.top_locator_source,
        "top_locator_type": item.top_locator_type,
        "top_locator_value": item.top_locator_value,
        "top_role": item.top_role,
        "risk_tags_json": _json_list(item.risk_tags_json),
        "sample_texts_json": _json_list(item.sample_texts_json),
        "matched_existing_element_code": item.matched_existing_element_code,
        "reviewed_by": item.reviewed_by,
        "reviewed_at": item.reviewed_at,
        "review_note": item.review_note,
        "latest_session_id": item.latest_session_id,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


def _serialize_candidate_element(item: PageObjectCandidateElement) -> dict[str, Any]:
    proposed_element_code = str(item.proposed_element_code or "").strip()
    if not proposed_element_code:
        proposed_element_code = suggest_business_element_code(
            str(item.proposed_element_name or item.raw_text or item.raw_locator_value or ""),
            page_code=str(item.page_code or ""),
            business_type=str(item.business_type_guess or ""),
        )
    return {
        "id": item.id,
        "project_code": item.project_code,
        "client": item.client,
        "page_code": item.page_code,
        "session_id": item.session_id,
        "candidate_key": item.candidate_key,
        "group_key": item.group_key,
        "raw_locator_type": item.raw_locator_type,
        "raw_locator_value": item.raw_locator_value,
        "raw_role": item.raw_role,
        "raw_text": item.raw_text,
        "dom_signature": item.dom_signature,
        "route": item.route,
        "step_hit_count": int(item.step_hit_count or 0),
        "quality_score": int(item.quality_score or 0),
        "quality_tier": item.quality_tier,
        "risk_tags_json": _json_list(item.risk_tags_json),
        "recommended_action": item.recommended_action,
        "candidate_status": item.candidate_status,
        "ingest_block_reason": item.ingest_block_reason,
        "proposed_element_code": proposed_element_code,
        "proposed_element_name": item.proposed_element_name,
        "business_type_guess": item.business_type_guess,
        "probe_status": item.probe_status,
        "probe_match_count": int(item.probe_match_count or 0),
        "probe_visible": bool(item.probe_visible),
        "probe_interactable": bool(item.probe_interactable),
        "merged_to_element_code": item.merged_to_element_code,
        "promoted_element_code": item.promoted_element_code,
        "reviewed_by": item.reviewed_by,
        "reviewed_at": item.reviewed_at,
        "review_note": item.review_note,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


def _candidate_group_or_404(
    db: Session,
    *,
    project_code: str,
    client: str,
    page_code: str,
    group_key: str,
) -> PageObjectCandidateGroup:
    item = db.execute(
        select(PageObjectCandidateGroup).where(
            PageObjectCandidateGroup.project_code == project_code,
            PageObjectCandidateGroup.client == client,
            PageObjectCandidateGroup.page_code == page_code,
            PageObjectCandidateGroup.group_key == group_key,
        )
    ).scalar_one_or_none()
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"candidate group not found: {group_key}",
        )
    return item


def _candidate_element_or_404(
    db: Session,
    *,
    project_code: str,
    client: str,
    page_code: str,
    candidate_key: str,
) -> PageObjectCandidateElement:
    item = db.execute(
        select(PageObjectCandidateElement).where(
            PageObjectCandidateElement.project_code == project_code,
            PageObjectCandidateElement.client == client,
            PageObjectCandidateElement.page_code == page_code,
            PageObjectCandidateElement.candidate_key == candidate_key,
        )
    ).scalar_one_or_none()
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"candidate element not found: {candidate_key}",
        )
    return item


def _page_object_or_404(
    db: Session,
    *,
    project_code: str,
    client: str,
    page_code: str,
) -> PageObject:
    item = db.execute(
        select(PageObject).where(
            PageObject.project_code == project_code,
            PageObject.client == client,
            PageObject.page_code == page_code,
        )
    ).scalar_one_or_none()
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"page object not found: {project_code}/{client}/{page_code}",
        )
    return item


def _page_element_or_404(db: Session, *, page_object_id: int, element_code: str) -> PageElement:
    item = db.execute(
        select(PageElement).where(
            PageElement.page_object_id == page_object_id,
            PageElement.element_code == element_code,
        )
    ).scalar_one_or_none()
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"page element not found: {element_code}",
        )
    return item


def _next_element_version_no(db: Session, *, page_element_id: int) -> int:
    latest = db.execute(
        select(func.max(PageElementVersion.version_no)).where(PageElementVersion.page_element_id == page_element_id)
    ).scalar_one()
    return int(latest or 0) + 1


def _snapshot_element(
    db: Session,
    *,
    element: PageElement,
    changed_by: str,
    change_summary: str,
) -> int:
    next_version_no = _next_element_version_no(db, page_element_id=element.id)
    element.version = next_version_no
    db.add(element)
    db.add(
        PageElementVersion(
            page_element_id=element.id,
            version_no=next_version_no,
            locator_type=element.locator_type,
            locator_value=element.locator_value,
            role=element.role,
            status=element.status,
            is_primary=bool(element.is_primary),
            changed_by=str(changed_by or "").strip() or "system",
            change_summary=str(change_summary or "").strip() or "snapshot",
        )
    )
    db.flush()
    return next_version_no


def _sync_page_object_metrics(db: Session, *, page_object_id: int) -> None:
    page_object = db.get(PageObject, page_object_id)
    if page_object is None:
        return
    governance_counts = _page_object_governance_counts(db, page_object)
    next_element_count = int(governance_counts["formal_element_count"])
    unhealthy_count = int(
        db.execute(
            select(func.count()).select_from(PageElement).where(
                PageElement.page_object_id == page_object_id,
                PageElement.health_status == 0,
            )
        ).scalar_one()
        or 0
    )
    next_health_status = 0 if unhealthy_count > 0 else 1
    approved_count = int(governance_counts["approved_element_count"])
    key_count = int(governance_counts["key_element_count"])
    pending_candidate_count = int(governance_counts["pending_candidate_group_count"])
    changed = False
    if int(page_object.element_count or 0) != next_element_count:
        page_object.element_count = next_element_count
        changed = True
    if int(page_object.approved_element_count or 0) != approved_count:
        page_object.approved_element_count = approved_count
        changed = True
    if int(page_object.key_element_count or 0) != key_count:
        page_object.key_element_count = key_count
        changed = True
    if int(page_object.candidate_pending_count or 0) != pending_candidate_count:
        page_object.candidate_pending_count = pending_candidate_count
        changed = True
    if int(page_object.health_status if page_object.health_status is not None else 1) != next_health_status:
        page_object.health_status = next_health_status
        changed = True
    if changed:
        db.add(page_object)
        db.flush()


def _purge_duplicate_page_elements(db: Session, *, page_object_id: int) -> dict[str, int]:
    rows = list(
        db.execute(
            select(PageElement)
            .where(PageElement.page_object_id == page_object_id)
            .order_by(PageElement.updated_at.desc(), PageElement.id.desc())
        ).scalars().all()
    )
    if not rows:
        return {"kept_count": 0, "duplicate_deleted_count": 0}

    keep_ids: list[int] = []
    keep_id_set: set[int] = set()
    duplicate_id_set: set[int] = set()
    seen_locator_keys: set[tuple[str, str, str]] = set()
    seen_role_locator_keys: dict[tuple[str, str], int] = {}
    kept_role_by_id: dict[int, str] = {}
    for row in rows:
        row_id = int(row.id)
        locator_type = str(row.locator_type or "").strip().lower()
        locator_value = str(row.locator_value or "").strip()
        role_value = str(row.role or "").strip().lower()
        locator_key = _locator_identity_key(locator_type, locator_value, role_value)
        if locator_key in seen_locator_keys:
            duplicate_id_set.add(row_id)
            continue

        if locator_type == "role":
            relaxed_key = _locator_relaxed_key(locator_type, locator_value)
            kept_id = seen_role_locator_keys.get(relaxed_key)
            if kept_id is not None:
                kept_role = kept_role_by_id.get(kept_id, "")
                if not kept_role and role_value:
                    duplicate_id_set.add(kept_id)
                    if kept_id in keep_id_set:
                        keep_id_set.remove(kept_id)
                        keep_ids = [item for item in keep_ids if item != kept_id]
                    seen_role_locator_keys[relaxed_key] = row_id
                else:
                    duplicate_id_set.add(row_id)
                    continue
            else:
                seen_role_locator_keys[relaxed_key] = row_id

        seen_locator_keys.add(locator_key)
        keep_ids.append(row_id)
        keep_id_set.add(row_id)
        kept_role_by_id[row_id] = role_value

    duplicate_ids = sorted(duplicate_id_set)

    if duplicate_ids:
        db.execute(delete(PageElementLocator).where(PageElementLocator.page_element_id.in_(duplicate_ids)))
        db.execute(delete(PageElementVersion).where(PageElementVersion.page_element_id.in_(duplicate_ids)))
        db.execute(delete(PageObjectRef).where(PageObjectRef.page_element_id.in_(duplicate_ids)))
        db.execute(delete(PageElementHealthCheck).where(PageElementHealthCheck.page_element_id.in_(duplicate_ids)))
        db.execute(delete(PageElement).where(PageElement.id.in_(duplicate_ids)))
        db.commit()
        _sync_page_object_metrics(db, page_object_id=page_object_id)
        db.commit()

    return {
        "kept_count": len(keep_ids),
        "duplicate_deleted_count": len(duplicate_ids),
    }


def list_page_objects(
    db: Session,
    *,
    project_code: str = "",
    client: str = "",
    status_value: str = "",
) -> list[dict[str, Any]]:
    stmt = select(PageObject).order_by(PageObject.updated_at.desc(), PageObject.id.desc())
    normalized_project_code = str(project_code or "").strip().lower()
    if normalized_project_code:
        stmt = stmt.where(PageObject.project_code == normalized_project_code)
    normalized_client = str(client or "").strip().lower()
    if normalized_client:
        stmt = stmt.where(PageObject.client == normalize_client_code(normalized_client))
    normalized_status = str(status_value or "").strip().lower()
    if normalized_status:
        normalized_status = _normalize_page_object_status(normalized_status)
        stmt = stmt.where(PageObject.status == normalized_status)
    rows = list(db.execute(stmt).scalars().all())
    if not rows:
        return []
    object_ids = [item.id for item in rows]
    element_counts = {
        int(page_object_id): int(count or 0)
        for page_object_id, count in db.execute(
            select(PageElement.page_object_id, func.count())
            .where(PageElement.page_object_id.in_(object_ids))
            .group_by(PageElement.page_object_id)
        ).all()
    }
    recorder_stmt = (
        select(
            PageObjectRecorderSession.project_code,
            PageObjectRecorderSession.client,
            PageObjectRecorderSession.page_code,
            func.max(PageObjectRecorderSession.stopped_at),
        )
        .where(PageObjectRecorderSession.page_code.in_([item.page_code for item in rows]))
        .group_by(PageObjectRecorderSession.project_code, PageObjectRecorderSession.client, PageObjectRecorderSession.page_code)
    )
    if normalized_project_code:
        recorder_stmt = recorder_stmt.where(PageObjectRecorderSession.project_code == normalized_project_code)
    if normalized_client:
        recorder_stmt = recorder_stmt.where(PageObjectRecorderSession.client == normalize_client_code(normalized_client))
    latest_recorded_at_by_page = {
        (str(project or ""), str(client_value or ""), str(page_code or "")): latest_recorded_at
        for project, client_value, page_code, latest_recorded_at in db.execute(recorder_stmt).all()
    }
    serialized: list[dict[str, Any]] = []
    for item in rows:
        governance_counts = _page_object_governance_counts(db, item)
        payload = _serialize_page_object(item, element_count=element_counts.get(item.id, 0))
        payload["approved_element_count"] = int(governance_counts["approved_element_count"])
        payload["key_element_count"] = int(governance_counts["key_element_count"])
        payload["candidate_pending_count"] = int(governance_counts["pending_candidate_group_count"])
        payload["latest_recorded_at"] = latest_recorded_at_by_page.get((str(item.project_code or ""), str(item.client or ""), str(item.page_code or "")))
        serialized.append(payload)
    return serialized


def deduplicate_page_elements(
    db: Session,
    *,
    project_code: str = "",
    client: str = "",
) -> dict[str, Any]:
    stmt = select(PageObject)
    normalized_project_code = str(project_code or "").strip().lower()
    if normalized_project_code:
        stmt = stmt.where(PageObject.project_code == _normalize_project_code(normalized_project_code))
    normalized_client = str(client or "").strip().lower()
    if normalized_client:
        stmt = stmt.where(PageObject.client == normalize_client_code(normalized_client))
    rows = list(db.execute(stmt).scalars().all())
    scanned_page_count = len(rows)
    affected_page_count = 0
    duplicate_deleted_count = 0
    for page_object in rows:
        result = _purge_duplicate_page_elements(db, page_object_id=int(page_object.id))
        deleted_count = int(result.get("duplicate_deleted_count", 0))
        duplicate_deleted_count += deleted_count
        if deleted_count > 0:
            affected_page_count += 1
    return {
        "scanned_page_count": scanned_page_count,
        "affected_page_count": affected_page_count,
        "duplicate_deleted_count": duplicate_deleted_count,
        "project_code": normalized_project_code,
        "client": normalize_client_code(normalized_client) if normalized_client else "",
    }


def create_page_object(db: Session, payload: PageObjectCreate) -> dict[str, Any]:
    normalized_project_code = _normalize_project_code(payload.project_code)
    test_project_service.ensure_project_active_for_write(db, normalized_project_code)
    normalized_client = normalize_client_code(payload.client)
    normalized_page_code = _normalize_identifier(payload.page_code, field_name="page_code", max_length=40)
    existing = db.execute(
        select(PageObject).where(
            PageObject.project_code == normalized_project_code,
            PageObject.client == normalized_client,
            PageObject.page_code == normalized_page_code,
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"page object already exists: {normalized_project_code}/{normalized_client}/{normalized_page_code}",
        )
    item = PageObject(
        project_code=normalized_project_code,
        client=normalized_client,
        page_code=normalized_page_code,
        page_name=str(payload.page_name).strip(),
        page_url=str(payload.page_url or "").strip(),
        precondition_state=str(payload.precondition_state or "").strip(),
        route_pattern=str(payload.route_pattern or "").strip(),
        anchor_config_json=_json_dict(payload.anchor_config_json),
        governance_status=_normalize_governance_status(payload.governance_status),
        testability_score=_bounded_score(payload.testability_score),
        module_id=int(payload.module_id or 0),
        element_count=0,
        health_status=_normalize_binary_health_status(payload.health_status),
        description=str(payload.description or "").strip(),
        status=_normalize_page_object_status(payload.status),
        created_by=str(payload.created_by or "").strip() or "system",
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return _serialize_page_object(item, element_count=0)


def get_page_object(
    db: Session,
    *,
    page_code: str,
    project_code: str = "mall",
    client: str = "web",
) -> dict[str, Any]:
    item = _page_object_or_404(
        db,
        project_code=_normalize_project_code(project_code),
        client=normalize_client_code(client),
        page_code=_normalize_identifier(page_code, field_name="page_code", max_length=40),
    )
    element_count = int(
        db.execute(select(func.count()).select_from(PageElement).where(PageElement.page_object_id == item.id)).scalar_one()
        or 0
    )
    governance_counts = _page_object_governance_counts(db, item)
    payload = _serialize_page_object(item, element_count=element_count)
    payload["approved_element_count"] = int(governance_counts["approved_element_count"])
    payload["key_element_count"] = int(governance_counts["key_element_count"])
    payload["candidate_pending_count"] = int(governance_counts["pending_candidate_group_count"])
    return payload


def get_page_object_governance_summary(
    db: Session,
    *,
    page_code: str,
    project_code: str = "mall",
    client: str = "web",
) -> dict[str, Any]:
    page_object = _page_object_or_404(
        db,
        project_code=_normalize_project_code(project_code),
        client=normalize_client_code(client),
        page_code=_normalize_identifier(page_code, field_name="page_code", max_length=40),
    )
    governance_counts = _page_object_governance_counts(db, page_object)
    return {
        "project_code": page_object.project_code,
        "client": page_object.client,
        "page_code": page_object.page_code,
        "formal_element_count": int(governance_counts["formal_element_count"]),
        "approved_element_count": int(governance_counts["approved_element_count"]),
        "pending_candidate_group_count": int(governance_counts["pending_candidate_group_count"]),
        "key_element_count": int(governance_counts["key_element_count"]),
        "key_element_coverage": float(governance_counts["key_element_coverage"]),
        "testability_score": _bounded_score(page_object.testability_score),
        "governance_status": page_object.governance_status,
    }


def update_page_object(
    db: Session,
    *,
    page_code: str,
    project_code: str,
    client: str,
    payload: PageObjectUpdate,
) -> dict[str, Any]:
    normalized_project_code = _normalize_project_code(project_code)
    test_project_service.ensure_project_active_for_write(db, normalized_project_code)
    item = _page_object_or_404(
        db,
        project_code=normalized_project_code,
        client=normalize_client_code(client),
        page_code=_normalize_identifier(page_code, field_name="page_code", max_length=40),
    )
    changed = False
    if payload.page_name is not None:
        next_name = str(payload.page_name or "").strip()
        if next_name and item.page_name != next_name:
            item.page_name = next_name
            changed = True
    if payload.page_url is not None:
        next_page_url = str(payload.page_url or "").strip()
        if item.page_url != next_page_url:
            item.page_url = next_page_url
            changed = True
    if payload.precondition_state is not None:
        next_precondition_state = str(payload.precondition_state or "").strip()
        if item.precondition_state != next_precondition_state:
            item.precondition_state = next_precondition_state
            changed = True
    if payload.route_pattern is not None:
        next_route_pattern = str(payload.route_pattern or "").strip()
        if item.route_pattern != next_route_pattern:
            item.route_pattern = next_route_pattern
            changed = True
    if payload.anchor_config_json is not None:
        next_anchor_config = _json_dict(payload.anchor_config_json)
        if _json_dict(item.anchor_config_json) != next_anchor_config:
            item.anchor_config_json = next_anchor_config
            changed = True
    if payload.governance_status is not None:
        next_governance_status = _normalize_governance_status(payload.governance_status)
        if item.governance_status != next_governance_status:
            item.governance_status = next_governance_status
            changed = True
    if payload.testability_score is not None:
        next_score = _bounded_score(payload.testability_score)
        if int(item.testability_score or 0) != next_score:
            item.testability_score = next_score
            changed = True
    if payload.module_id is not None:
        next_module_id = int(payload.module_id)
        if next_module_id < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="module_id must be >= 0",
            )
        if int(item.module_id or 0) != next_module_id:
            item.module_id = next_module_id
            changed = True
    if payload.health_status is not None:
        next_health_status = _normalize_binary_health_status(payload.health_status)
        if int(item.health_status if item.health_status is not None else 1) != next_health_status:
            item.health_status = next_health_status
            changed = True
    if payload.description is not None:
        next_description = str(payload.description or "").strip()
        if item.description != next_description:
            item.description = next_description
            changed = True
    if payload.status is not None:
        next_status = _normalize_page_object_status(payload.status)
        if item.status != next_status:
            item.status = next_status
            changed = True
    if changed:
        db.add(item)
        db.commit()
        db.refresh(item)
    element_count = int(
        db.execute(select(func.count()).select_from(PageElement).where(PageElement.page_object_id == item.id)).scalar_one()
        or 0
    )
    return _serialize_page_object(item, element_count=element_count)


def delete_page_object(
    db: Session,
    *,
    page_code: str,
    project_code: str,
    client: str,
    cascade_elements: bool,
) -> dict[str, Any]:
    item = _page_object_or_404(
        db,
        project_code=_normalize_project_code(project_code),
        client=normalize_client_code(client),
        page_code=_normalize_identifier(page_code, field_name="page_code", max_length=40),
    )
    element_ids = [int(value) for value in db.execute(
        select(PageElement.id).where(PageElement.page_object_id == item.id)
    ).scalars().all()]
    if element_ids and not cascade_elements:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"page object still has {len(element_ids)} element(s); set cascade_elements=true to delete",
        )
    deleted_element_count = len(element_ids)
    if element_ids:
        db.execute(delete(PageElementLocator).where(PageElementLocator.page_element_id.in_(element_ids)))
        db.execute(delete(PageElementVersion).where(PageElementVersion.page_element_id.in_(element_ids)))
        db.execute(delete(PageObjectRef).where(PageObjectRef.page_element_id.in_(element_ids)))
        db.execute(delete(PageElementHealthCheck).where(PageElementHealthCheck.page_element_id.in_(element_ids)))
        db.execute(delete(PageElement).where(PageElement.id.in_(element_ids)))
    db.execute(
        delete(PageObjectCandidateElement).where(
            PageObjectCandidateElement.project_code == item.project_code,
            PageObjectCandidateElement.client == item.client,
            PageObjectCandidateElement.page_code == item.page_code,
        )
    )
    db.execute(
        delete(PageObjectCandidateGroup).where(
            PageObjectCandidateGroup.project_code == item.project_code,
            PageObjectCandidateGroup.client == item.client,
            PageObjectCandidateGroup.page_code == item.page_code,
        )
    )
    db.execute(
        delete(PageObjectGovernanceLog).where(
            PageObjectGovernanceLog.project_code == item.project_code,
            PageObjectGovernanceLog.client == item.client,
            PageObjectGovernanceLog.page_code == item.page_code,
        )
    )
    db.delete(item)
    db.commit()
    cleanup_result = _cleanup_page_recorder_assets(
        db,
        project_code=item.project_code,
        client=item.client,
        page_code=item.page_code,
    )
    return {
        "page_id": item.id,
        "project_code": item.project_code,
        "client": item.client,
        "page_code": item.page_code,
        "deleted_element_count": deleted_element_count,
        **cleanup_result,
    }


def list_page_elements(
    db: Session,
    *,
    page_code: str,
    project_code: str = "mall",
    client: str = "web",
    purge_duplicates: bool = False,
) -> list[dict[str, Any]]:
    page_object = _page_object_or_404(
        db,
        project_code=_normalize_project_code(project_code),
        client=normalize_client_code(client),
        page_code=_normalize_identifier(page_code, field_name="page_code", max_length=40),
    )
    if purge_duplicates:
        _purge_duplicate_page_elements(db, page_object_id=int(page_object.id))
    rows = list(
        db.execute(
            select(PageElement)
            .where(PageElement.page_object_id == page_object.id)
            .order_by(PageElement.updated_at.desc(), PageElement.id.desc())
        ).scalars().all()
    )
    if not rows:
        return []
    element_ids = [item.id for item in rows]
    version_map = {
        int(element_id): int(version_no or 0)
        for element_id, version_no in db.execute(
            select(PageElementVersion.page_element_id, func.max(PageElementVersion.version_no))
            .where(PageElementVersion.page_element_id.in_(element_ids))
            .group_by(PageElementVersion.page_element_id)
        ).all()
    }
    ref_count_map = {
        int(element_id): int(count or 0)
        for element_id, count in db.execute(
            select(PageObjectRef.page_element_id, func.count())
            .where(PageObjectRef.page_element_id.in_(element_ids))
            .group_by(PageObjectRef.page_element_id)
        ).all()
    }
    return [
        _serialize_page_element(
            item,
            latest_version_no=max(version_map.get(item.id, 0), int(item.version if item.version is not None else 1)),
            reference_count=ref_count_map.get(item.id, 0),
        )
        for item in rows
    ]


def get_page_element(
    db: Session,
    *,
    page_code: str,
    element_code: str,
    project_code: str = "mall",
    client: str = "web",
) -> dict[str, Any]:
    page_object = _page_object_or_404(
        db,
        project_code=_normalize_project_code(project_code),
        client=normalize_client_code(client),
        page_code=_normalize_identifier(page_code, field_name="page_code", max_length=40),
    )
    element = _page_element_or_404(
        db,
        page_object_id=page_object.id,
        element_code=_normalize_identifier(element_code, field_name="element_code"),
    )
    latest_version_no = int(
        db.execute(
            select(func.max(PageElementVersion.version_no)).where(PageElementVersion.page_element_id == element.id)
        ).scalar_one()
        or 0
    )
    latest_version_no = max(latest_version_no, int(element.version if element.version is not None else 1))
    reference_count = int(
        db.execute(select(func.count()).select_from(PageObjectRef).where(PageObjectRef.page_element_id == element.id)).scalar_one()
        or 0
    )
    return _serialize_page_element(
        element,
        latest_version_no=latest_version_no,
        reference_count=reference_count,
        locators=_element_locators_for_serialization(db, page_element_id=element.id),
    )


def create_page_element(
    db: Session,
    *,
    page_code: str,
    project_code: str,
    client: str,
    payload: PageElementCreate,
) -> dict[str, Any]:
    normalized_project_code = _normalize_project_code(project_code)
    test_project_service.ensure_project_active_for_write(db, normalized_project_code)
    page_object = _page_object_or_404(
        db,
        project_code=normalized_project_code,
        client=normalize_client_code(client),
        page_code=_normalize_identifier(page_code, field_name="page_code", max_length=40),
    )
    business_type = _normalize_business_type(payload.business_type)
    business_domain = _normalize_business_domain(payload.business_domain)
    locator_type = _normalize_locator_type(payload.locator_type)
    locator_source = _normalize_locator_source(payload.locator_source)
    testid_value = str(payload.testid_value or "").strip()
    if locator_type == "data-testid" and not testid_value:
        testid_value = str(payload.locator_value or "").strip()
    normalized_element_code = _normalize_formal_element_code(
        payload.element_code,
        page_code=page_object.page_code,
        business_type=business_type,
        locator_source=locator_source,
        locator_type=locator_type,
        testid_value=testid_value,
    )
    existing = db.execute(
        select(PageElement).where(
            PageElement.page_object_id == page_object.id,
            PageElement.element_code == normalized_element_code,
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"page element already exists: {normalized_element_code}",
        )
    item = PageElement(
        page_object_id=page_object.id,
        element_code=normalized_element_code,
        element_name=str(payload.element_name).strip(),
        locator_type=locator_type,
        locator_value=str(payload.locator_value).strip(),
        backup_locator=str(payload.backup_locator or "").strip(),
        business_type=business_type,
        business_domain=business_domain,
        aliases_json=_json_list(payload.aliases_json),
        semantic_tags_json=_json_list(payload.semantic_tags_json),
        locator_source=locator_source,
        match_strategy=_normalize_match_strategy(payload.match_strategy),
        stability_level="low",
        review_status="pending",
        origin_candidate_key=str(payload.origin_candidate_key or "").strip(),
        route_scope=str(payload.route_scope or "").strip(),
        anchor_required=bool(payload.anchor_required),
        is_key_element=bool(payload.is_key_element),
        testid_value=testid_value,
        qa_value=str(payload.qa_value or "").strip(),
        governance_note=str(payload.governance_note or "").strip(),
        health_status=_normalize_binary_health_status(payload.health_status),
        version=1,
        role=str(payload.role or "").strip(),
        status=_normalize_page_element_status(payload.status),
        is_primary=bool(payload.is_primary),
        owner=str(payload.owner or "").strip(),
    )
    db.add(item)
    db.flush()
    version_no = _snapshot_element(
        db,
        element=item,
        changed_by=payload.changed_by,
        change_summary=payload.change_summary,
    )
    _sync_page_object_metrics(db, page_object_id=page_object.id)
    db.commit()
    db.refresh(item)
    return _serialize_page_element(item, latest_version_no=version_no, reference_count=0)


def update_page_element(
    db: Session,
    *,
    page_code: str,
    element_code: str,
    project_code: str,
    client: str,
    payload: PageElementUpdate,
) -> dict[str, Any]:
    normalized_project_code = _normalize_project_code(project_code)
    test_project_service.ensure_project_active_for_write(db, normalized_project_code)
    page_object = _page_object_or_404(
        db,
        project_code=normalized_project_code,
        client=normalize_client_code(client),
        page_code=_normalize_identifier(page_code, field_name="page_code", max_length=40),
    )
    element = _page_element_or_404(
        db,
        page_object_id=page_object.id,
        element_code=_normalize_identifier(element_code, field_name="element_code"),
    )
    governance_before = _element_governance_payload(element)
    changed = False
    if payload.element_code is not None:
        target_business_type = (
            _normalize_business_type(payload.business_type)
            if payload.business_type is not None
            else str(element.business_type or "").strip().lower()
        )
        target_locator_type = payload.locator_type if payload.locator_type is not None else element.locator_type
        target_locator_source = payload.locator_source if payload.locator_source is not None else element.locator_source
        target_testid_value = payload.testid_value if payload.testid_value is not None else element.testid_value
        if str(target_locator_type or "").strip().lower() == "data-testid" and not str(target_testid_value or "").strip():
            target_testid_value = payload.locator_value if payload.locator_value is not None else element.locator_value
        next_value = _normalize_formal_element_code(
            payload.element_code,
            page_code=page_object.page_code,
            business_type=target_business_type,
            locator_source=target_locator_source,
            locator_type=target_locator_type,
            testid_value=target_testid_value,
        )
        if element.element_code != next_value:
            existing = db.execute(
                select(PageElement).where(
                    PageElement.page_object_id == page_object.id,
                    PageElement.element_code == next_value,
                    PageElement.id != element.id,
                )
            ).scalar_one_or_none()
            if existing is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"page element already exists: {next_value}",
                )
            element.element_code = next_value
            changed = True
    if payload.element_name is not None:
        next_value = str(payload.element_name or "").strip()
        if next_value and element.element_name != next_value:
            element.element_name = next_value
            changed = True
    if payload.locator_type is not None:
        next_value = _normalize_locator_type(payload.locator_type)
        if element.locator_type != next_value:
            element.locator_type = next_value
            changed = True
    if payload.locator_value is not None:
        next_value = str(payload.locator_value or "").strip()
        if next_value and element.locator_value != next_value:
            element.locator_value = next_value
            changed = True
    if payload.backup_locator is not None:
        next_value = str(payload.backup_locator or "").strip()
        if element.backup_locator != next_value:
            element.backup_locator = next_value
            changed = True
    if payload.business_type is not None:
        next_value = _normalize_business_type(payload.business_type)
        _normalize_formal_element_code(
            element.element_code,
            page_code=page_object.page_code,
            business_type=next_value,
            locator_source=element.locator_source,
            locator_type=element.locator_type,
            testid_value=element.testid_value,
        )
        if element.business_type != next_value:
            element.business_type = next_value
            changed = True
    if payload.business_domain is not None:
        next_value = _normalize_business_domain(payload.business_domain)
        if element.business_domain != next_value:
            element.business_domain = next_value
            changed = True
    if payload.aliases_json is not None:
        next_value = _json_list(payload.aliases_json)
        if _json_list(element.aliases_json) != next_value:
            element.aliases_json = next_value
            changed = True
    if payload.semantic_tags_json is not None:
        next_value = _json_list(payload.semantic_tags_json)
        if _json_list(element.semantic_tags_json) != next_value:
            element.semantic_tags_json = next_value
            changed = True
    if payload.locator_source is not None:
        next_value = _normalize_locator_source(payload.locator_source)
        if element.locator_source != next_value:
            element.locator_source = next_value
            changed = True
    if payload.match_strategy is not None:
        next_value = _normalize_match_strategy(payload.match_strategy)
        if element.match_strategy != next_value:
            element.match_strategy = next_value
            changed = True
    if payload.stability_level is not None:
        next_value = _normalize_stability_level(payload.stability_level)
        if element.stability_level != next_value:
            element.stability_level = next_value
            changed = True
    if payload.review_status is not None:
        next_value = _normalize_review_status(payload.review_status)
        if next_value == "approved":
            _normalize_formal_element_code(
                element.element_code,
                page_code=page_object.page_code,
                business_type=element.business_type,
                locator_source=element.locator_source,
                locator_type=element.locator_type,
                testid_value=element.testid_value,
            )
        if element.review_status != next_value:
            element.review_status = next_value
            changed = True
    if payload.origin_candidate_key is not None:
        next_value = str(payload.origin_candidate_key or "").strip()
        if element.origin_candidate_key != next_value:
            element.origin_candidate_key = next_value
            changed = True
    if payload.route_scope is not None:
        next_value = str(payload.route_scope or "").strip()
        if element.route_scope != next_value:
            element.route_scope = next_value
            changed = True
    if payload.anchor_required is not None and element.anchor_required != bool(payload.anchor_required):
        element.anchor_required = bool(payload.anchor_required)
        changed = True
    if payload.is_key_element is not None and element.is_key_element != bool(payload.is_key_element):
        element.is_key_element = bool(payload.is_key_element)
        changed = True
    if payload.testid_value is not None:
        next_value = str(payload.testid_value or "").strip()
        if element.testid_value != next_value:
            element.testid_value = next_value
            changed = True
    if payload.qa_value is not None:
        next_value = str(payload.qa_value or "").strip()
        if element.qa_value != next_value:
            element.qa_value = next_value
            changed = True
    if payload.governance_note is not None:
        next_value = str(payload.governance_note or "").strip()
        if element.governance_note != next_value:
            element.governance_note = next_value
            changed = True
    if payload.health_status is not None:
        next_health_status = _normalize_binary_health_status(payload.health_status)
        if int(element.health_status if element.health_status is not None else 1) != next_health_status:
            element.health_status = next_health_status
            changed = True
    if payload.role is not None:
        next_value = str(payload.role or "").strip()
        if element.role != next_value:
            element.role = next_value
            changed = True
    if payload.status is not None:
        next_value = _normalize_page_element_status(payload.status)
        if element.status != next_value:
            element.status = next_value
            changed = True
    if payload.is_primary is not None and element.is_primary != bool(payload.is_primary):
        element.is_primary = bool(payload.is_primary)
        changed = True
    if payload.owner is not None:
        next_value = str(payload.owner or "").strip()
        if element.owner != next_value:
            element.owner = next_value
            changed = True

    if changed:
        _validate_formal_element_governance_qualification(element)
        db.add(element)
        db.flush()
        version_no = _snapshot_element(
            db,
            element=element,
            changed_by=payload.changed_by,
            change_summary=payload.change_summary,
        )
        governance_after = _element_governance_payload(element)
        if governance_before != governance_after:
            _write_governance_log(
                db,
                page_object=page_object,
                entity_type="page_element",
                entity_key=element.element_code,
                action="edit",
                before_payload=governance_before,
                after_payload=governance_after,
                operator=payload.changed_by,
            )
        _sync_page_object_metrics(db, page_object_id=page_object.id)
        db.commit()
        db.refresh(element)
    else:
        version_no = max(
            int(element.version if element.version is not None else 1),
            db.execute(
                select(func.max(PageElementVersion.version_no)).where(PageElementVersion.page_element_id == element.id)
            ).scalar_one()
            or 0,
        )

    reference_count = int(
        db.execute(select(func.count()).select_from(PageObjectRef).where(PageObjectRef.page_element_id == element.id)).scalar_one()
        or 0
    )
    return _serialize_page_element(element, latest_version_no=version_no, reference_count=reference_count)


def delete_page_element(
    db: Session,
    *,
    page_code: str,
    element_code: str,
    project_code: str,
    client: str,
) -> dict[str, Any]:
    page_object = _page_object_or_404(
        db,
        project_code=_normalize_project_code(project_code),
        client=normalize_client_code(client),
        page_code=_normalize_identifier(page_code, field_name="page_code", max_length=40),
    )
    element = _page_element_or_404(
        db,
        page_object_id=page_object.id,
        element_code=_normalize_identifier(element_code, field_name="element_code"),
    )
    db.execute(delete(PageElementVersion).where(PageElementVersion.page_element_id == element.id))
    db.execute(delete(PageElementLocator).where(PageElementLocator.page_element_id == element.id))
    db.execute(delete(PageObjectRef).where(PageObjectRef.page_element_id == element.id))
    db.execute(delete(PageElementHealthCheck).where(PageElementHealthCheck.page_element_id == element.id))
    db.delete(element)
    db.commit()
    _sync_page_object_metrics(db, page_object_id=page_object.id)
    db.commit()
    remaining_element_count = int(
        db.execute(
            select(func.count()).select_from(PageElement).where(PageElement.page_object_id == page_object.id)
        ).scalar_one()
        or 0
    )
    cleanup_result = (
        _cleanup_page_recorder_assets(
            db,
            project_code=page_object.project_code,
            client=page_object.client,
            page_code=page_object.page_code,
        )
        if remaining_element_count == 0
        else {"recorder_sessions_removed_count": 0, "recorder_artifacts_removed_count": 0}
    )
    return {
        "page_object_id": page_object.id,
        "element_code": element.element_code,
        "deleted": True,
        **cleanup_result,
    }


def _unique_non_empty(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        normalized = str(value or "").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def batch_delete_page_elements(
    db: Session,
    *,
    page_code: str,
    element_codes: list[str],
    project_code: str,
    client: str,
) -> dict[str, Any]:
    page_object = _page_object_or_404(
        db,
        project_code=_normalize_project_code(project_code),
        client=normalize_client_code(client),
        page_code=_normalize_identifier(page_code, field_name="page_code", max_length=40),
    )
    normalized_codes = [
        _normalize_identifier(item, field_name="element_code")
        for item in _unique_non_empty(element_codes)
    ]
    if not normalized_codes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="element_codes cannot be empty")
    rows = list(
        db.execute(
            select(PageElement).where(
                PageElement.page_object_id == page_object.id,
                PageElement.element_code.in_(normalized_codes),
            )
        ).scalars().all()
    )
    element_ids = [int(item.id) for item in rows]
    deleted_codes = [str(item.element_code or "") for item in rows]
    if element_ids:
        db.execute(delete(PageElementVersion).where(PageElementVersion.page_element_id.in_(element_ids)))
        db.execute(delete(PageElementLocator).where(PageElementLocator.page_element_id.in_(element_ids)))
        db.execute(delete(PageObjectRef).where(PageObjectRef.page_element_id.in_(element_ids)))
        db.execute(delete(PageElementHealthCheck).where(PageElementHealthCheck.page_element_id.in_(element_ids)))
        db.execute(delete(PageElement).where(PageElement.id.in_(element_ids)))
        db.commit()
        _sync_page_object_metrics(db, page_object_id=page_object.id)
        db.commit()
    missing_codes = [item for item in normalized_codes if item not in set(deleted_codes)]
    return {
        "page_object_id": page_object.id,
        "deleted_count": len(deleted_codes),
        "deleted_element_codes": deleted_codes,
        "missing_count": len(missing_codes),
        "missing_element_codes": missing_codes,
    }


def _refresh_or_delete_candidate_group_after_physical_delete(
    db: Session,
    *,
    project_code: str,
    client: str,
    page_code: str,
    group_key: str,
) -> bool:
    group = db.execute(
        select(PageObjectCandidateGroup).where(
            PageObjectCandidateGroup.project_code == project_code,
            PageObjectCandidateGroup.client == client,
            PageObjectCandidateGroup.page_code == page_code,
            PageObjectCandidateGroup.group_key == group_key,
        )
    ).scalar_one_or_none()
    if group is None:
        return False
    rows = _candidate_rows_for_group(
        db,
        project_code=project_code,
        client=client,
        page_code=page_code,
        group_key=group_key,
    )
    if not rows:
        db.delete(group)
        return True
    _refresh_group_status_from_candidates(group, rows)
    scores = [int(row.quality_score or 0) for row in rows]
    group.max_score = max(scores) if scores else 0
    group.avg_score = round(sum(scores) / len(scores)) if scores else 0
    group.latest_session_id = str(rows[0].session_id or "") if rows else ""
    db.add(group)
    return False


def batch_delete_candidate_groups(
    db: Session,
    *,
    page_code: str,
    group_keys: list[str],
    project_code: str,
    client: str,
) -> dict[str, Any]:
    page_object = _page_object_or_404(
        db,
        project_code=_normalize_project_code(project_code),
        client=normalize_client_code(client),
        page_code=_normalize_identifier(page_code, field_name="page_code", max_length=40),
    )
    normalized_keys = _unique_non_empty(group_keys)
    if not normalized_keys:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="group_keys cannot be empty")
    existing_keys = {
        str(item or "")
        for item in db.execute(
            select(PageObjectCandidateGroup.group_key).where(
                PageObjectCandidateGroup.project_code == page_object.project_code,
                PageObjectCandidateGroup.client == page_object.client,
                PageObjectCandidateGroup.page_code == page_object.page_code,
                PageObjectCandidateGroup.group_key.in_(normalized_keys),
            )
        ).scalars().all()
    }
    candidate_count = int(
        db.execute(
            select(func.count()).select_from(PageObjectCandidateElement).where(
                PageObjectCandidateElement.project_code == page_object.project_code,
                PageObjectCandidateElement.client == page_object.client,
                PageObjectCandidateElement.page_code == page_object.page_code,
                PageObjectCandidateElement.group_key.in_(list(existing_keys)),
            )
        ).scalar_one()
        or 0
    ) if existing_keys else 0
    if existing_keys:
        db.execute(
            delete(PageObjectCandidateElement).where(
                PageObjectCandidateElement.project_code == page_object.project_code,
                PageObjectCandidateElement.client == page_object.client,
                PageObjectCandidateElement.page_code == page_object.page_code,
                PageObjectCandidateElement.group_key.in_(list(existing_keys)),
            )
        )
        db.execute(
            delete(PageObjectCandidateGroup).where(
                PageObjectCandidateGroup.project_code == page_object.project_code,
                PageObjectCandidateGroup.client == page_object.client,
                PageObjectCandidateGroup.page_code == page_object.page_code,
                PageObjectCandidateGroup.group_key.in_(list(existing_keys)),
            )
        )
        db.commit()
        _sync_page_object_metrics(db, page_object_id=page_object.id)
        db.commit()
    missing_keys = [item for item in normalized_keys if item not in existing_keys]
    return {
        "page_object_id": page_object.id,
        "deleted_group_count": len(existing_keys),
        "deleted_candidate_count": candidate_count,
        "deleted_group_keys": sorted(existing_keys),
        "missing_count": len(missing_keys),
        "missing_group_keys": missing_keys,
    }


def batch_delete_candidate_elements(
    db: Session,
    *,
    page_code: str,
    candidate_keys: list[str],
    project_code: str,
    client: str,
) -> dict[str, Any]:
    page_object = _page_object_or_404(
        db,
        project_code=_normalize_project_code(project_code),
        client=normalize_client_code(client),
        page_code=_normalize_identifier(page_code, field_name="page_code", max_length=40),
    )
    normalized_keys = _unique_non_empty(candidate_keys)
    if not normalized_keys:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="candidate_keys cannot be empty")
    rows = list(
        db.execute(
            select(PageObjectCandidateElement).where(
                PageObjectCandidateElement.project_code == page_object.project_code,
                PageObjectCandidateElement.client == page_object.client,
                PageObjectCandidateElement.page_code == page_object.page_code,
                PageObjectCandidateElement.candidate_key.in_(normalized_keys),
            )
        ).scalars().all()
    )
    row_ids = [int(item.id) for item in rows]
    deleted_keys = [str(item.candidate_key or "") for item in rows]
    affected_group_keys = sorted({str(item.group_key or "") for item in rows if str(item.group_key or "").strip()})
    empty_group_count = 0
    if row_ids:
        db.execute(delete(PageObjectCandidateElement).where(PageObjectCandidateElement.id.in_(row_ids)))
        db.flush()
        for group_key in affected_group_keys:
            if _refresh_or_delete_candidate_group_after_physical_delete(
                db,
                project_code=page_object.project_code,
                client=page_object.client,
                page_code=page_object.page_code,
                group_key=group_key,
            ):
                empty_group_count += 1
        db.commit()
        _sync_page_object_metrics(db, page_object_id=page_object.id)
        db.commit()
    missing_keys = [item for item in normalized_keys if item not in set(deleted_keys)]
    return {
        "page_object_id": page_object.id,
        "deleted_candidate_count": len(deleted_keys),
        "deleted_candidate_keys": deleted_keys,
        "empty_group_deleted_count": empty_group_count,
        "affected_group_keys": affected_group_keys,
        "missing_count": len(missing_keys),
        "missing_candidate_keys": missing_keys,
    }


def create_page_element_version(
    db: Session,
    *,
    page_code: str,
    element_code: str,
    project_code: str,
    client: str,
    payload: PageElementVersionCreate,
) -> dict[str, Any]:
    normalized_project_code = _normalize_project_code(project_code)
    test_project_service.ensure_project_active_for_write(db, normalized_project_code)
    page_object = _page_object_or_404(
        db,
        project_code=normalized_project_code,
        client=normalize_client_code(client),
        page_code=_normalize_identifier(page_code, field_name="page_code", max_length=40),
    )
    element = _page_element_or_404(
        db,
        page_object_id=page_object.id,
        element_code=_normalize_identifier(element_code, field_name="element_code"),
    )
    version_no = _snapshot_element(
        db,
        element=element,
        changed_by=payload.changed_by,
        change_summary=payload.change_summary,
    )
    version = db.execute(
        select(PageElementVersion).where(
            PageElementVersion.page_element_id == element.id,
            PageElementVersion.version_no == version_no,
        )
    ).scalar_one()
    db.commit()
    return _serialize_element_version(version)


def list_page_element_versions(
    db: Session,
    *,
    page_code: str,
    element_code: str,
    project_code: str,
    client: str,
) -> list[dict[str, Any]]:
    page_object = _page_object_or_404(
        db,
        project_code=_normalize_project_code(project_code),
        client=normalize_client_code(client),
        page_code=_normalize_identifier(page_code, field_name="page_code", max_length=40),
    )
    element = _page_element_or_404(
        db,
        page_object_id=page_object.id,
        element_code=_normalize_identifier(element_code, field_name="element_code"),
    )
    rows = list(
        db.execute(
            select(PageElementVersion)
            .where(PageElementVersion.page_element_id == element.id)
            .order_by(PageElementVersion.version_no.desc(), PageElementVersion.id.desc())
        ).scalars().all()
    )
    return [_serialize_element_version(item) for item in rows]


def create_page_object_ref(
    db: Session,
    *,
    page_code: str,
    element_code: str,
    project_code: str,
    client: str,
    payload: PageObjectRefCreate,
) -> dict[str, Any]:
    normalized_project_code = _normalize_project_code(project_code)
    test_project_service.ensure_project_active_for_write(db, normalized_project_code)
    page_object = _page_object_or_404(
        db,
        project_code=normalized_project_code,
        client=normalize_client_code(client),
        page_code=_normalize_identifier(page_code, field_name="page_code", max_length=40),
    )
    element = _page_element_or_404(
        db,
        page_object_id=page_object.id,
        element_code=_normalize_identifier(element_code, field_name="element_code"),
    )
    normalized_reference_type = _normalize_reference_type(payload.reference_type)
    normalized_reference_key = str(payload.reference_key or "").strip()
    existing = db.execute(
        select(PageObjectRef).where(
            PageObjectRef.page_element_id == element.id,
            PageObjectRef.reference_type == normalized_reference_type,
            PageObjectRef.reference_key == normalized_reference_key,
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"page object reference already exists: {normalized_reference_type}/{normalized_reference_key}",
        )
    item = PageObjectRef(
        page_element_id=element.id,
        reference_type=normalized_reference_type,
        reference_key=normalized_reference_key,
        source=str(payload.source or "").strip().lower() or "manual",
        created_by=str(payload.created_by or "").strip() or "system",
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return _serialize_ref(item)


def list_page_object_refs(
    db: Session,
    *,
    page_code: str,
    element_code: str,
    project_code: str,
    client: str,
) -> list[dict[str, Any]]:
    page_object = _page_object_or_404(
        db,
        project_code=_normalize_project_code(project_code),
        client=normalize_client_code(client),
        page_code=_normalize_identifier(page_code, field_name="page_code", max_length=40),
    )
    element = _page_element_or_404(
        db,
        page_object_id=page_object.id,
        element_code=_normalize_identifier(element_code, field_name="element_code"),
    )
    rows = list(
        db.execute(
            select(PageObjectRef)
            .where(PageObjectRef.page_element_id == element.id)
            .order_by(PageObjectRef.created_at.desc(), PageObjectRef.id.desc())
        ).scalars().all()
    )
    return [_serialize_ref(item) for item in rows]


def list_candidate_groups(
    db: Session,
    *,
    page_code: str,
    project_code: str = "mall",
    client: str = "web",
    promotion_status: str = "",
    quality_tier: str = "",
    session_id: str = "",
) -> list[dict[str, Any]]:
    normalized_project_code = _normalize_project_code(project_code)
    normalized_client = normalize_client_code(client)
    normalized_page_code = _normalize_identifier(page_code, field_name="page_code", max_length=40)
    _page_object_or_404(
        db,
        project_code=normalized_project_code,
        client=normalized_client,
        page_code=normalized_page_code,
    )
    stmt = select(PageObjectCandidateGroup).where(
        PageObjectCandidateGroup.project_code == normalized_project_code,
        PageObjectCandidateGroup.client == normalized_client,
        PageObjectCandidateGroup.page_code == normalized_page_code,
    )
    normalized_status = str(promotion_status or "").strip().lower()
    if normalized_status:
        if normalized_status not in CANDIDATE_PROMOTION_STATUS_VALUES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"promotion_status must be one of: {', '.join(sorted(CANDIDATE_PROMOTION_STATUS_VALUES))}",
            )
        stmt = stmt.where(PageObjectCandidateGroup.promotion_status == normalized_status)
    normalized_quality = str(quality_tier or "").strip()
    if normalized_quality:
        stmt = stmt.where(PageObjectCandidateGroup.quality_tier == normalized_quality)
    normalized_session_id = str(session_id or "").strip()
    if normalized_session_id:
        group_keys = select(PageObjectCandidateElement.group_key).where(
            PageObjectCandidateElement.project_code == normalized_project_code,
            PageObjectCandidateElement.client == normalized_client,
            PageObjectCandidateElement.page_code == normalized_page_code,
            PageObjectCandidateElement.session_id == normalized_session_id,
        )
        stmt = stmt.where(PageObjectCandidateGroup.group_key.in_(group_keys))
    rows = list(
        db.execute(
            stmt.order_by(PageObjectCandidateGroup.updated_at.desc(), PageObjectCandidateGroup.id.desc())
        ).scalars().all()
    )
    return [_serialize_candidate_group(item) for item in rows]


def list_candidate_elements(
    db: Session,
    *,
    page_code: str,
    project_code: str = "mall",
    client: str = "web",
    group_key: str = "",
    session_id: str = "",
    candidate_status: str = "",
) -> list[dict[str, Any]]:
    normalized_project_code = _normalize_project_code(project_code)
    normalized_client = normalize_client_code(client)
    normalized_page_code = _normalize_identifier(page_code, field_name="page_code", max_length=40)
    _page_object_or_404(
        db,
        project_code=normalized_project_code,
        client=normalized_client,
        page_code=normalized_page_code,
    )
    stmt = select(PageObjectCandidateElement).where(
        PageObjectCandidateElement.project_code == normalized_project_code,
        PageObjectCandidateElement.client == normalized_client,
        PageObjectCandidateElement.page_code == normalized_page_code,
    )
    normalized_group_key = str(group_key or "").strip()
    if normalized_group_key:
        stmt = stmt.where(PageObjectCandidateElement.group_key == normalized_group_key)
    normalized_session_id = str(session_id or "").strip()
    if normalized_session_id:
        stmt = stmt.where(PageObjectCandidateElement.session_id == normalized_session_id)
    normalized_status = str(candidate_status or "").strip().lower()
    if normalized_status:
        if normalized_status not in CANDIDATE_STATUS_VALUES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"candidate_status must be one of: {', '.join(sorted(CANDIDATE_STATUS_VALUES))}",
            )
        stmt = stmt.where(PageObjectCandidateElement.candidate_status == normalized_status)
    rows = list(
        db.execute(
            stmt.order_by(PageObjectCandidateElement.quality_score.desc(), PageObjectCandidateElement.id.desc())
        ).scalars().all()
    )
    return [_serialize_candidate_element(item) for item in rows]


def get_candidate_group(
    db: Session,
    *,
    page_code: str,
    group_key: str,
    project_code: str = "mall",
    client: str = "web",
) -> dict[str, Any]:
    normalized_project_code = _normalize_project_code(project_code)
    normalized_client = normalize_client_code(client)
    normalized_page_code = _normalize_identifier(page_code, field_name="page_code", max_length=40)
    _page_object_or_404(
        db,
        project_code=normalized_project_code,
        client=normalized_client,
        page_code=normalized_page_code,
    )
    group = _candidate_group_or_404(
        db,
        project_code=normalized_project_code,
        client=normalized_client,
        page_code=normalized_page_code,
        group_key=str(group_key or "").strip(),
    )
    payload = _serialize_candidate_group(group)
    payload["candidates"] = list_candidate_elements(
        db,
        page_code=normalized_page_code,
        project_code=normalized_project_code,
        client=normalized_client,
        group_key=group.group_key,
    )
    return payload


def _candidate_rows_for_group(
    db: Session,
    *,
    project_code: str,
    client: str,
    page_code: str,
    group_key: str,
) -> list[PageObjectCandidateElement]:
    return list(
        db.execute(
            select(PageObjectCandidateElement)
            .where(
                PageObjectCandidateElement.project_code == project_code,
                PageObjectCandidateElement.client == client,
                PageObjectCandidateElement.page_code == page_code,
                PageObjectCandidateElement.group_key == group_key,
            )
            .order_by(PageObjectCandidateElement.quality_score.desc(), PageObjectCandidateElement.id.desc())
        ).scalars().all()
    )


def _refresh_group_status_from_candidates(
    group: PageObjectCandidateGroup,
    candidate_rows: list[PageObjectCandidateElement],
) -> None:
    statuses = [str(row.candidate_status or "").strip().lower() for row in candidate_rows]
    handled_statuses = {"promoted", "merged"}
    if statuses and all(item == "rejected" for item in statuses):
        group.promotion_status = "rejected"
    elif statuses and all(item in handled_statuses for item in statuses):
        group.promotion_status = "promoted"
    elif any(item in handled_statuses for item in statuses):
        group.promotion_status = "partially_promoted"
    else:
        group.promotion_status = "pending"
    group.candidate_count = len(candidate_rows)
    group.session_count = len({str(row.session_id or "") for row in candidate_rows if str(row.session_id or "").strip()})


def _primary_candidate_locator(
    group: PageObjectCandidateGroup,
    candidate_rows: list[PageObjectCandidateElement],
) -> tuple[str, str, str, PageObjectCandidateElement | None]:
    top_candidate = candidate_rows[0] if candidate_rows else None
    locator_type = str(group.top_locator_type or "").strip()
    locator_value = str(group.top_locator_value or "").strip()
    role = str(group.top_role or "").strip()
    if (not locator_type or not locator_value) and top_candidate is not None:
        locator_type = str(top_candidate.raw_locator_type or "").strip()
        locator_value = str(top_candidate.raw_locator_value or "").strip()
        role = str(top_candidate.raw_role or "").strip()
    return locator_type, locator_value, role, top_candidate


def promote_candidate_group(
    db: Session,
    *,
    page_code: str,
    group_key: str,
    project_code: str,
    client: str,
    payload: CandidateGroupPromotePayload,
) -> dict[str, Any]:
    normalized_project_code = _normalize_project_code(project_code)
    test_project_service.ensure_project_active_for_write(db, normalized_project_code)
    normalized_client = normalize_client_code(client)
    normalized_page_code = _normalize_identifier(page_code, field_name="page_code", max_length=40)
    page_object = _page_object_or_404(
        db,
        project_code=normalized_project_code,
        client=normalized_client,
        page_code=normalized_page_code,
    )
    group = _candidate_group_or_404(
        db,
        project_code=normalized_project_code,
        client=normalized_client,
        page_code=normalized_page_code,
        group_key=str(group_key or "").strip(),
    )
    candidate_rows = _candidate_rows_for_group(
        db,
        project_code=normalized_project_code,
        client=normalized_client,
        page_code=normalized_page_code,
        group_key=group.group_key,
    )
    if not candidate_rows:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="candidate group has no candidate elements")

    business_type = _normalize_business_type(payload.business_type, group.business_type_guess)
    business_domain = _normalize_business_domain(payload.business_domain, group.business_domain_guess)
    fallback_locator_type, fallback_locator_value, fallback_role, top_candidate = _primary_candidate_locator(group, candidate_rows)
    locator_type = _normalize_locator_type(str(payload.locator_type or fallback_locator_type))
    locator_value = str(payload.locator_value or fallback_locator_value or "").strip()
    if not locator_value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="locator_value cannot be empty")
    role = str(payload.role or fallback_role or "").strip()
    locator_source = _normalize_locator_source(payload.locator_source or group.top_locator_source or _locator_source_from_type(locator_type))
    testid_value = str(payload.testid_value or "").strip()
    qa_value = str(payload.qa_value or "").strip()
    if locator_type == "data-testid" and not testid_value:
        testid_value = locator_value
    if locator_type == "data-qa" and not qa_value:
        qa_value = locator_value
    element_code = _normalize_formal_element_code(
        payload.element_code,
        page_code=normalized_page_code,
        business_type=business_type,
        locator_source=locator_source,
        locator_type=locator_type,
        testid_value=testid_value,
    )
    existing = db.execute(
        select(PageElement).where(PageElement.page_object_id == page_object.id, PageElement.element_code == element_code)
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"page element already exists: {element_code}")
    if bool(payload.is_key_element) and not testid_value and not qa_value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="key element promotion requires testid_value or qa_value",
        )

    stability_level = _stability_from_locator_source(locator_source, review_status="approved")
    operator = str(payload.operator or "").strip() or "admin"
    item = PageElement(
        page_object_id=page_object.id,
        element_code=element_code,
        element_name=str(payload.element_name or "").strip(),
        locator_type=locator_type,
        locator_value=locator_value,
        backup_locator="",
        business_type=business_type,
        business_domain=business_domain,
        aliases_json=_json_list(group.sample_texts_json),
        semantic_tags_json=[],
        locator_source=locator_source,
        match_strategy="exact",
        stability_level=stability_level,
        review_status="approved",
        origin_candidate_key=str(top_candidate.candidate_key or "") if top_candidate is not None else "",
        route_scope=str(payload.route_scope or group.route_scope or "").strip(),
        anchor_required=False,
        is_key_element=bool(payload.is_key_element),
        testid_value=testid_value,
        qa_value=qa_value,
        governance_note=str(payload.governance_note or "").strip(),
        health_status=1,
        version=1,
        role=role,
        status="active",
        is_primary=True,
        owner=operator,
    )
    db.add(item)
    db.flush()
    db.add(
        PageElementVersion(
            page_element_id=item.id,
            version_no=1,
            locator_type=item.locator_type,
            locator_value=item.locator_value,
            role=item.role,
            status=item.status,
            is_primary=True,
            changed_by=operator,
            change_summary=f"promoted from candidate group {group.group_key}",
        )
    )
    db.add(
        PageElementLocator(
            page_element_id=item.id,
            locator_type=item.locator_type,
            locator_value=item.locator_value[:512],
            role=item.role,
            locator_source=item.locator_source,
            priority=1,
            is_primary=True,
            health_status="unknown",
            verification_status="unknown",
            created_by=operator,
        )
    )
    now = datetime.now(timezone.utc)
    before_group = _serialize_candidate_group(group)
    for row in candidate_rows:
        if str(row.candidate_status or "") in {"rejected", "merged"}:
            continue
        row.candidate_status = "promoted"
        row.promoted_element_code = element_code
        row.reviewed_by = operator
        row.reviewed_at = now
        row.review_note = str(payload.governance_note or "").strip() or "promoted to formal element"
        db.add(row)
    group.proposed_element_code = element_code
    group.proposed_element_name = item.element_name
    group.business_type_guess = business_type
    group.business_domain_guess = business_domain
    group.matched_existing_element_code = element_code
    group.reviewed_by = operator
    group.reviewed_at = now
    group.review_note = str(payload.governance_note or "").strip()
    _refresh_group_status_from_candidates(group, candidate_rows)
    db.add(group)
    _write_governance_log(
        db,
        page_object=page_object,
        entity_type="candidate_group",
        entity_key=group.group_key,
        action="promote",
        before_payload=before_group,
        after_payload={"element_code": element_code, "group": _serialize_candidate_group(group)},
        operator=operator,
    )
    db.flush()
    _sync_page_object_metrics(db, page_object_id=page_object.id)
    db.commit()
    db.refresh(item)
    db.refresh(group)
    return {
        "element": _serialize_page_element(item, latest_version_no=1, reference_count=0),
        "group": _serialize_candidate_group(group),
    }


def merge_candidate_group(
    db: Session,
    *,
    page_code: str,
    group_key: str,
    project_code: str,
    client: str,
    payload: CandidateGroupMergePayload,
) -> dict[str, Any]:
    normalized_project_code = _normalize_project_code(project_code)
    test_project_service.ensure_project_active_for_write(db, normalized_project_code)
    normalized_client = normalize_client_code(client)
    normalized_page_code = _normalize_identifier(page_code, field_name="page_code", max_length=40)
    page_object = _page_object_or_404(
        db,
        project_code=normalized_project_code,
        client=normalized_client,
        page_code=normalized_page_code,
    )
    group = _candidate_group_or_404(
        db,
        project_code=normalized_project_code,
        client=normalized_client,
        page_code=normalized_page_code,
        group_key=str(group_key or "").strip(),
    )
    target = _page_element_or_404(
        db,
        page_object_id=page_object.id,
        element_code=_normalize_identifier(payload.target_element_code, field_name="target_element_code"),
    )
    candidate_rows = _candidate_rows_for_group(
        db,
        project_code=normalized_project_code,
        client=normalized_client,
        page_code=normalized_page_code,
        group_key=group.group_key,
    )
    if not candidate_rows:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="candidate group has no candidate elements")
    operator = str(payload.operator or "").strip() or "admin"
    review_note = str(payload.review_note or "").strip()
    before_group = _serialize_candidate_group(group)
    before_target_governance = _element_governance_payload(target)
    now = datetime.now(timezone.utc)
    locator_count = 0
    if bool(payload.write_locator):
        seen_locator_keys = {
            (
                int(locator.page_element_id),
                str(locator.locator_type or "").strip(),
                str(locator.locator_value or "").strip(),
                str(locator.role or "").strip(),
            )
            for locator in _element_locators_for_serialization(db, page_element_id=target.id)
        }
        primary_locator_type = str(target.locator_type or "").strip()
        primary_locator_value = str(target.locator_value or "").strip()
        primary_role = str(target.role or "").strip()
        if primary_locator_type and primary_locator_value:
            primary_key = (int(target.id), primary_locator_type, primary_locator_value[:512], primary_role)
            existing_primary = db.execute(
                select(PageElementLocator).where(
                    PageElementLocator.page_element_id == target.id,
                    PageElementLocator.locator_type == primary_locator_type,
                    PageElementLocator.locator_value == primary_locator_value[:512],
                    PageElementLocator.role == primary_role,
                )
            ).scalar_one_or_none()
            if existing_primary is None:
                db.add(
                    PageElementLocator(
                        page_element_id=target.id,
                        locator_type=primary_locator_type,
                        locator_value=primary_locator_value[:512],
                        role=primary_role,
                        locator_source=target.locator_source or _locator_source_from_type(primary_locator_type),
                        priority=1,
                        is_primary=True,
                        health_status="unknown",
                        verification_status="unknown",
                        created_by=operator,
                    )
                )
                seen_locator_keys.add(primary_key)
        for row in candidate_rows:
            locator_type = str(row.raw_locator_type or "").strip()
            locator_value = str(row.raw_locator_value or "").strip()
            role = str(row.raw_role or "").strip()
            if not locator_type or not locator_value:
                continue
            locator_key = (int(target.id), locator_type, locator_value[:512], role)
            if locator_key in seen_locator_keys:
                continue
            existing_locator = db.execute(
                select(PageElementLocator).where(
                    PageElementLocator.page_element_id == target.id,
                    PageElementLocator.locator_type == locator_type,
                    PageElementLocator.locator_value == locator_value[:512],
                    PageElementLocator.role == role,
                )
            ).scalar_one_or_none()
            if existing_locator is None:
                db.add(
                    PageElementLocator(
                        page_element_id=target.id,
                        locator_type=locator_type,
                        locator_value=locator_value[:512],
                        role=role,
                        locator_source=_locator_source_from_type(locator_type),
                        priority=100 + locator_count,
                        is_primary=False,
                        health_status="unknown",
                        verification_status="unknown",
                        created_by=operator,
                    )
                )
                locator_count += 1
                seen_locator_keys.add(locator_key)
    merge_note = review_note or f"已合并候选分组 {group.group_key}"
    if locator_count:
        merge_note = f"{merge_note}，新增备选定位器 {locator_count} 个"
    target.governance_note = _append_governance_note(target.governance_note, merge_note)
    db.add(target)
    for row in candidate_rows:
        if str(row.candidate_status or "") == "rejected":
            continue
        row.candidate_status = "merged"
        row.merged_to_element_code = target.element_code
        row.reviewed_by = operator
        row.reviewed_at = now
        row.review_note = review_note or f"merged to {target.element_code}"
        db.add(row)
    group.matched_existing_element_code = target.element_code
    group.reviewed_by = operator
    group.reviewed_at = now
    group.review_note = review_note
    _refresh_group_status_from_candidates(group, candidate_rows)
    db.add(group)
    _write_governance_log(
        db,
        page_object=page_object,
        entity_type="candidate_group",
        entity_key=group.group_key,
        action="merge",
        before_payload=before_group,
        after_payload={"target_element_code": target.element_code, "locator_added_count": locator_count, "group": _serialize_candidate_group(group)},
        operator=operator,
    )
    _write_governance_log(
        db,
        page_object=page_object,
        entity_type="page_element",
        entity_key=target.element_code,
        action="merge",
        before_payload=before_target_governance,
        after_payload={
            **_element_governance_payload(target),
            "merged_group_key": group.group_key,
            "locator_added_count": locator_count,
        },
        operator=operator,
    )
    db.flush()
    _sync_page_object_metrics(db, page_object_id=page_object.id)
    db.commit()
    db.refresh(group)
    db.refresh(target)
    locators = _element_locators_for_serialization(db, page_element_id=target.id)
    return {
        "target_element": _serialize_page_element(target, locators=locators),
        "group": _serialize_candidate_group(group),
        "locator_added_count": locator_count,
        "locator_count": len(locators),
    }


def reject_candidate_group(
    db: Session,
    *,
    page_code: str,
    group_key: str,
    project_code: str,
    client: str,
    payload: CandidateRejectPayload,
) -> dict[str, Any]:
    normalized_project_code = _normalize_project_code(project_code)
    test_project_service.ensure_project_active_for_write(db, normalized_project_code)
    normalized_client = normalize_client_code(client)
    normalized_page_code = _normalize_identifier(page_code, field_name="page_code", max_length=40)
    page_object = _page_object_or_404(
        db,
        project_code=normalized_project_code,
        client=normalized_client,
        page_code=normalized_page_code,
    )
    group = _candidate_group_or_404(
        db,
        project_code=normalized_project_code,
        client=normalized_client,
        page_code=normalized_page_code,
        group_key=str(group_key or "").strip(),
    )
    candidate_rows = _candidate_rows_for_group(
        db,
        project_code=normalized_project_code,
        client=normalized_client,
        page_code=normalized_page_code,
        group_key=group.group_key,
    )
    operator = str(payload.operator or "").strip() or "admin"
    review_note = str(payload.review_note or "").strip()
    before_group = _serialize_candidate_group(group)
    now = datetime.now(timezone.utc)
    rejected_count = 0
    for row in candidate_rows:
        if str(row.candidate_status or "") in {"promoted", "merged"}:
            continue
        row.candidate_status = "rejected"
        row.reviewed_by = operator
        row.reviewed_at = now
        row.review_note = review_note
        db.add(row)
        rejected_count += 1
    group.reviewed_by = operator
    group.reviewed_at = now
    group.review_note = review_note
    _refresh_group_status_from_candidates(group, candidate_rows)
    db.add(group)
    _write_governance_log(
        db,
        page_object=page_object,
        entity_type="candidate_group",
        entity_key=group.group_key,
        action="reject",
        before_payload=before_group,
        after_payload={"rejected_count": rejected_count, "group": _serialize_candidate_group(group)},
        operator=operator,
    )
    db.flush()
    _sync_page_object_metrics(db, page_object_id=page_object.id)
    db.commit()
    db.refresh(group)
    return {"group": _serialize_candidate_group(group), "rejected_count": rejected_count}


def reject_candidate_element(
    db: Session,
    *,
    page_code: str,
    candidate_key: str,
    project_code: str,
    client: str,
    payload: CandidateRejectPayload,
) -> dict[str, Any]:
    normalized_project_code = _normalize_project_code(project_code)
    test_project_service.ensure_project_active_for_write(db, normalized_project_code)
    normalized_client = normalize_client_code(client)
    normalized_page_code = _normalize_identifier(page_code, field_name="page_code", max_length=40)
    page_object = _page_object_or_404(
        db,
        project_code=normalized_project_code,
        client=normalized_client,
        page_code=normalized_page_code,
    )
    item = _candidate_element_or_404(
        db,
        project_code=normalized_project_code,
        client=normalized_client,
        page_code=normalized_page_code,
        candidate_key=str(candidate_key or "").strip(),
    )
    if str(item.candidate_status or "") in {"promoted", "merged"}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="promoted or merged candidate cannot be rejected")
    before_payload = _serialize_candidate_element(item)
    operator = str(payload.operator or "").strip() or "admin"
    item.candidate_status = "rejected"
    item.reviewed_by = operator
    item.reviewed_at = datetime.now(timezone.utc)
    item.review_note = str(payload.review_note or "").strip()
    db.add(item)
    group = _candidate_group_or_404(
        db,
        project_code=normalized_project_code,
        client=normalized_client,
        page_code=normalized_page_code,
        group_key=item.group_key,
    )
    candidate_rows = _candidate_rows_for_group(
        db,
        project_code=normalized_project_code,
        client=normalized_client,
        page_code=normalized_page_code,
        group_key=item.group_key,
    )
    _refresh_group_status_from_candidates(group, candidate_rows)
    db.add(group)
    _write_governance_log(
        db,
        page_object=page_object,
        entity_type="candidate_element",
        entity_key=item.candidate_key,
        action="reject",
        before_payload=before_payload,
        after_payload=_serialize_candidate_element(item),
        operator=operator,
    )
    db.flush()
    _sync_page_object_metrics(db, page_object_id=page_object.id)
    db.commit()
    db.refresh(item)
    db.refresh(group)
    return {"candidate": _serialize_candidate_element(item), "group": _serialize_candidate_group(group)}
