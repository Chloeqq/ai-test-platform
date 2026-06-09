from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import HTTPException, status
from shared_backend.case_ids import normalize_client_code
from shared_backend.type_utils import json_dict as _json_dict
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models.page_object import (
    PageElement,
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
from app.repositories.page_object_repository import PageObjectRepository
from app.repositories.page_object_governance_repository import PageObjectGovernanceRepository
from app.repositories.recorder_repository import RecorderRepository
from app.repositories.recorder_session_repository import RecorderSessionRepository
from app.services import test_project_service

from app.services.page_object_normalizers import (
    CANDIDATE_PROMOTION_STATUS_VALUES,
    CANDIDATE_STATUS_VALUES,
    _normalize_page_object_status,
)

_RECORDER_ROOT = (Path(__file__).resolve().parents[4] / "artifacts" / "page-recorder").resolve()
_RECORDER_CLEANABLE_STATUSES = {"stopped", "failed"}


@dataclass(frozen=True)
class PageElementMutationResult:
    element: PageElement
    latest_version_no: int


from shared_backend.type_utils import json_list as _json_list


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


from shared_backend.type_utils import bounded_score as _bounded_score


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
    _po_repo = PageObjectRepository(db)
    _gov_repo = PageObjectGovernanceRepository(db)
    _rec_repo = RecorderRepository(db)
    formal_element_count = int(
        _po_repo.count_elements_by_page_object_id(page_object.id)
        or 0
    )
    approved_element_count = _gov_repo.count_approved_elements(page_object.id)
    key_element_count = _gov_repo.count_key_elements(page_object.id)
    pending_candidate_group_count = _rec_repo.count_pending_candidate_groups(
        page_object.project_code, page_object.client, page_object.page_code
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
    sessions = RecorderSessionRepository(db).list_sessions_by_page_identity(
        project_code, client, page_code
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


from .page_object_serializers import (
    _element_locators_for_serialization,
    _serialize_candidate_element,
    _serialize_candidate_group,
    _serialize_element_locator,
    _serialize_element_version,
    _serialize_page_element,
    _serialize_page_object,
    _serialize_ref,
)


def _candidate_group_or_404(
    db: Session,
    *,
    project_code: str,
    client: str,
    page_code: str,
    group_key: str,
) -> PageObjectCandidateGroup:
    item = RecorderRepository(db).get_group(
        project_code, client, page_code, group_key
    )
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
    item = RecorderRepository(db).get_candidate_by_key(
        project_code, client, page_code, candidate_key
    )
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
    repo = PageObjectRepository(db)
    item = repo.get_by_identity(project_code, client, page_code)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"page object not found: {project_code}/{client}/{page_code}",
        )
    return item


def _page_element_or_404(db: Session, *, page_object_id: int, element_code: str) -> PageElement:
    repo = PageObjectRepository(db)
    item = repo.get_element_by_code(page_object_id, element_code)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"page element not found: {element_code}",
        )
    return item


def _next_element_version_no(db: Session, *, page_element_id: int) -> int:
    latest = PageObjectRepository(db).get_max_version_no(page_element_id)
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
    unhealthy_count = PageObjectGovernanceRepository(db).count_unhealthy_elements(page_object_id)
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
    rows = PageObjectRepository(db).list_elements_by_page_object_id_ordered(page_object_id)
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
        repo = PageObjectRepository(db)
        repo.bulk_cascade_delete_elements(duplicate_ids)
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
    rows = PageObjectGovernanceRepository(db).list_page_objects_filtered(
        project_code=normalized_project_code,
        client=normalized_client,
        status_value=normalized_status,
    )
    if not rows:
        return []
    object_ids = [item.id for item in rows]
    element_counts = PageObjectGovernanceRepository(db).count_elements_grouped_by_page_object_ids(object_ids)
    latest_recorded_at_by_page = RecorderSessionRepository(db).get_latest_recorded_at_by_page(
        project_code=normalized_project_code or None,
        client=normalized_client or None,
        page_codes=[item.page_code for item in rows] if rows else None,
    )
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
    normalized_project_code = str(project_code or "").strip().lower()
    normalized_client = str(client or "").strip().lower()
    rows = PageObjectGovernanceRepository(db).list_page_objects_filtered(
        project_code=normalized_project_code if normalized_project_code else "",
        client=normalized_client if normalized_client else "",
    )
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
    repo = PageObjectRepository(db)
    normalized_project_code = _normalize_project_code(payload.project_code)
    test_project_service.ensure_project_active_for_write(db, normalized_project_code)
    normalized_client = normalize_client_code(payload.client)
    normalized_page_code = _normalize_identifier(payload.page_code, field_name="page_code", max_length=40)
    existing = repo.get_by_identity(normalized_project_code, normalized_client, normalized_page_code)
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
    repo = PageObjectRepository(db)
    element_count = int(repo.count_elements_by_page_object_id(item.id) or 0)
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
    repo = PageObjectRepository(db)
    element_count = int(repo.count_elements_by_page_object_id(item.id) or 0)
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
    _po_repo = PageObjectRepository(db)
    _rec_repo = RecorderRepository(db)
    element_ids = _po_repo.list_element_ids_by_page_object_id(item.id)
    if element_ids and not cascade_elements:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"page object still has {len(element_ids)} element(s); set cascade_elements=true to delete",
        )
    deleted_element_count = len(element_ids)
    if element_ids:
        _po_repo.bulk_cascade_delete_elements(element_ids)
    _rec_repo.delete_candidates_by_page_identity(
        item.project_code, item.client, item.page_code
    )
    _rec_repo.delete_groups_by_page_identity(
        item.project_code, item.client, item.page_code
    )
    PageObjectGovernanceRepository(db).delete_governance_logs_by_page_identity(
        item.project_code, item.client, item.page_code
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
    _po_repo = PageObjectRepository(db)
    if purge_duplicates:
        _purge_duplicate_page_elements(db, page_object_id=int(page_object.id))
    rows = _po_repo.list_elements_by_page_object_id_ordered(page_object.id)
    if not rows:
        return []
    element_ids = [item.id for item in rows]
    version_map = _po_repo.get_max_version_nos_by_element_ids(element_ids)
    ref_count_map = _po_repo.count_refs_grouped_by_element_ids(element_ids)
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
        PageObjectRepository(db).get_max_version_no(element.id) or 0
    )
    latest_version_no = max(latest_version_no, int(element.version if element.version is not None else 1))
    reference_count = PageObjectRepository(db).count_refs_by_element_id(element.id)
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
    repo = PageObjectRepository(db)
    existing = repo.get_element_by_code(page_object.id, normalized_element_code)
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



# ---- 以下函数体已移至 page_object_elements.py 和 page_object_candidates.py ----
# 导入放在文件末尾以避免循环依赖
from app.services.page_object_elements import (  # noqa: E402
    update_page_element, delete_page_element, _unique_non_empty,
    batch_delete_page_elements,
    _refresh_or_delete_candidate_group_after_physical_delete,
    batch_delete_candidate_groups, batch_delete_candidate_elements,
    create_page_element_version, list_page_element_versions,
    create_page_object_ref, list_page_object_refs,
)
from app.services.page_object_candidates import (  # noqa: E402
    list_candidate_groups, list_candidate_elements, get_candidate_group,
    _candidate_rows_for_group, _refresh_group_status_from_candidates,
    _primary_candidate_locator,
    promote_candidate_group, merge_candidate_group,
    reject_candidate_group, reject_candidate_element,
)
