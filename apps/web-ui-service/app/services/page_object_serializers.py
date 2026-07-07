from typing import Any

from shared_backend.type_utils import json_dict as _json_dict

from sqlalchemy.orm import Session

from app.models.page_object import (
    PageElement,
    PageElementLocator,
    PageElementVersion,
    PageObject,
    PageObjectCandidateElement,
    PageObjectCandidateGroup,
    PageObjectRef,
)
from app.repositories.page_object_governance_repository import PageObjectGovernanceRepository
from app.services.page_element_code_policy import suggest_business_element_code


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


from shared_backend.type_utils import json_list as _json_list


from shared_backend.type_utils import bounded_score as _bounded_score


# ---------------------------------------------------------------------------
# Serializers
# ---------------------------------------------------------------------------


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
    return PageObjectGovernanceRepository(db).list_locators_by_element_id(page_element_id)


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
