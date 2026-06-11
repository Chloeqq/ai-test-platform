"""PageObject 元素操作函数 —— 更新/删除元素、版本、引用。

提取自 page_object_service.py 以控制单文件大小在 1000 行以内。
"""
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
)

def _svc():
    """惰性导入以避免循环依赖。"""
    from app.services import page_object_service as _svc_mod
    return _svc_mod

def update_page_element(
    db: Session,
    *,
    page_code: str,
    element_code: str,
    project_code: str,
    client: str,
    payload: PageElementUpdate,
) -> dict[str, Any]:
    normalized_project_code = _svc()._normalize_project_code(project_code)
    test_project_service.ensure_project_active_for_write(db, normalized_project_code)
    page_object = _svc()._page_object_or_404(
        db,
        project_code=normalized_project_code,
        client=normalize_client_code(client),
        page_code=_svc()._normalize_identifier(page_code, field_name="page_code", max_length=40),
    )
    element = _svc()._page_element_or_404(
        db,
        page_object_id=page_object.id,
        element_code=_svc()._normalize_identifier(element_code, field_name="element_code"),
    )
    governance_before = _svc()._element_governance_payload(element)
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
            existing =  PageObjectRepository(db).get_element_by_code_excluding_id(
                page_object.id, next_value, element.id
            )
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
        version_no = _svc()._snapshot_element(
            db,
            element=element,
            changed_by=payload.changed_by,
            change_summary=payload.change_summary,
        )
        governance_after = _svc()._element_governance_payload(element)
        if governance_before != governance_after:
            _svc()._write_governance_log(
                db,
                page_object=page_object,
                entity_type="page_element",
                entity_key=element.element_code,
                action="edit",
                before_payload=governance_before,
                after_payload=governance_after,
                operator=payload.changed_by,
            )
        _svc()._sync_page_object_metrics(db, page_object_id=page_object.id)
        db.commit()
        db.refresh(element)
    else:
        version_no = max(
            int(element.version if element.version is not None else 1),
             PageObjectRepository(db).get_max_version_no(element.id) or 0,
        )

    reference_count =  PageObjectRepository(db).count_refs_by_element_id(element.id)
    return _serialize_page_element(element, latest_version_no=version_no, reference_count=reference_count)


def delete_page_element(
    db: Session,
    *,
    page_code: str,
    element_code: str,
    project_code: str,
    client: str,
) -> dict[str, Any]:
    page_object = _svc()._page_object_or_404(
        db,
        project_code=_svc()._normalize_project_code(project_code),
        client=normalize_client_code(client),
        page_code=_svc()._normalize_identifier(page_code, field_name="page_code", max_length=40),
    )
    element = _svc()._page_element_or_404(
        db,
        page_object_id=page_object.id,
        element_code=_svc()._normalize_identifier(element_code, field_name="element_code"),
    )
    repo =  PageObjectRepository(db)
    repo.cascade_delete_element(element.id)
    db.commit()
    _svc()._sync_page_object_metrics(db, page_object_id=page_object.id)
    db.commit()
    remaining_element_count = int(repo.count_elements_by_page_object_id(page_object.id) or 0)
    cleanup_result = (
        _svc()._cleanup_page_recorder_assets(
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
    page_object = _svc()._page_object_or_404(
        db,
        project_code=_svc()._normalize_project_code(project_code),
        client=normalize_client_code(client),
        page_code=_svc()._normalize_identifier(page_code, field_name="page_code", max_length=40),
    )
    normalized_codes = [
        _svc()._normalize_identifier(item, field_name="element_code")
        for item in _unique_non_empty(element_codes)
    ]
    if not normalized_codes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="element_codes cannot be empty")
    rows =  PageObjectRepository(db).list_elements_by_codes(page_object.id, normalized_codes)
    element_ids = [int(item.id) for item in rows]
    deleted_codes = [str(item.element_code or "") for item in rows]
    if element_ids:
        repo =  PageObjectRepository(db)
        repo.bulk_cascade_delete_elements(element_ids)
        db.commit()
        _svc()._sync_page_object_metrics(db, page_object_id=page_object.id)
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
    group =  RecorderRepository(db).get_group(
        project_code, client, page_code, group_key
    )
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
    page_object = _svc()._page_object_or_404(
        db,
        project_code=_svc()._normalize_project_code(project_code),
        client=normalize_client_code(client),
        page_code=_svc()._normalize_identifier(page_code, field_name="page_code", max_length=40),
    )
    normalized_keys = _unique_non_empty(group_keys)
    if not normalized_keys:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="group_keys cannot be empty")
    _rec_repo =  RecorderRepository(db)
    existing_keys_list = _rec_repo.list_group_keys_by_page_identity(
        page_object.project_code, page_object.client, page_object.page_code, normalized_keys
    )
    existing_keys = set(existing_keys_list)
    candidate_count = 0
    if existing_keys:
        for gk in existing_keys:
            candidate_count += _rec_repo.count_candidates_by_group(
                page_object.project_code, page_object.client, page_object.page_code, gk
            )
    if existing_keys:
        key_list = list(existing_keys)
        _rec_repo.delete_candidates_by_group_keys(
            page_object.project_code, page_object.client, page_object.page_code, key_list
        )
        _rec_repo.delete_groups_by_keys(
            page_object.project_code, page_object.client, page_object.page_code, key_list
        )
        db.commit()
        _svc()._sync_page_object_metrics(db, page_object_id=page_object.id)
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
    page_object = _svc()._page_object_or_404(
        db,
        project_code=_svc()._normalize_project_code(project_code),
        client=normalize_client_code(client),
        page_code=_svc()._normalize_identifier(page_code, field_name="page_code", max_length=40),
    )
    normalized_keys = _unique_non_empty(candidate_keys)
    if not normalized_keys:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="candidate_keys cannot be empty")
    _rec_repo =  RecorderRepository(db)
    rows = _rec_repo.list_candidates_by_keys(
        page_object.project_code, page_object.client, page_object.page_code, normalized_keys
    )
    row_ids = [int(item.id) for item in rows]
    deleted_keys = [str(item.candidate_key or "") for item in rows]
    affected_group_keys = sorted({str(item.group_key or "") for item in rows if str(item.group_key or "").strip()})
    empty_group_count = 0
    if row_ids:
        _rec_repo.delete_candidates_by_ids(row_ids)
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
        _svc()._sync_page_object_metrics(db, page_object_id=page_object.id)
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
    normalized_project_code = _svc()._normalize_project_code(project_code)
    test_project_service.ensure_project_active_for_write(db, normalized_project_code)
    page_object = _svc()._page_object_or_404(
        db,
        project_code=normalized_project_code,
        client=normalize_client_code(client),
        page_code=_svc()._normalize_identifier(page_code, field_name="page_code", max_length=40),
    )
    element = _svc()._page_element_or_404(
        db,
        page_object_id=page_object.id,
        element_code=_svc()._normalize_identifier(element_code, field_name="element_code"),
    )
    version_no = _svc()._snapshot_element(
        db,
        element=element,
        changed_by=payload.changed_by,
        change_summary=payload.change_summary,
    )
    version =  PageObjectRepository(db).get_version_by_element_id_and_no(
        element.id, version_no
    )
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
    page_object = _svc()._page_object_or_404(
        db,
        project_code=_svc()._normalize_project_code(project_code),
        client=normalize_client_code(client),
        page_code=_svc()._normalize_identifier(page_code, field_name="page_code", max_length=40),
    )
    element = _svc()._page_element_or_404(
        db,
        page_object_id=page_object.id,
        element_code=_svc()._normalize_identifier(element_code, field_name="element_code"),
    )
    rows =  PageObjectRepository(db).list_versions_by_element_id(element.id)
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
    normalized_project_code = _svc()._normalize_project_code(project_code)
    test_project_service.ensure_project_active_for_write(db, normalized_project_code)
    page_object = _svc()._page_object_or_404(
        db,
        project_code=normalized_project_code,
        client=normalize_client_code(client),
        page_code=_svc()._normalize_identifier(page_code, field_name="page_code", max_length=40),
    )
    element = _svc()._page_element_or_404(
        db,
        page_object_id=page_object.id,
        element_code=_svc()._normalize_identifier(element_code, field_name="element_code"),
    )
    normalized_reference_type = _normalize_reference_type(payload.reference_type)
    normalized_reference_key = str(payload.reference_key or "").strip()
    repo =  PageObjectRepository(db)
    existing = repo.get_ref(element.id, normalized_reference_type, normalized_reference_key)
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
    page_object = _svc()._page_object_or_404(
        db,
        project_code=_svc()._normalize_project_code(project_code),
        client=normalize_client_code(client),
        page_code=_svc()._normalize_identifier(page_code, field_name="page_code", max_length=40),
    )
    element = _svc()._page_element_or_404(
        db,
        page_object_id=page_object.id,
        element_code=_svc()._normalize_identifier(element_code, field_name="element_code"),
    )
    rows =  PageObjectRepository(db).list_refs_by_element_id(element.id)
    return [_serialize_ref(item) for item in rows]


