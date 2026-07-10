"""PageObject Candidate 操作函数 —— candidate group/element 的管理、晋升、合并。

提取自 page_object_service.py 以控制单文件大小在 1000 行以内。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.page_object import (
    PageElement,
    PageElementLocator,
    PageElementVersion,
)
from app.models.page_object_recorder_models import (
    PageObjectCandidateElement,
    PageObjectCandidateGroup,
)
from app.repositories.page_object_repository import PageObjectRepository
from app.repositories.recorder_repository import RecorderRepository
from app.schemas.page_object import (
    CandidateGroupMergePayload,
    CandidateGroupPromotePayload,
    CandidateRejectPayload,
)
from app.services.page_object_normalizers import (
    CANDIDATE_PROMOTION_STATUS_VALUES,
    CANDIDATE_STATUS_VALUES,
)
from shared_backend.case_ids import normalize_client_code
from shared_backend.type_utils import json_list as _json_list

_RECORDER_ROOT = (Path(__file__).resolve().parents[4] / "artifacts" / "page-recorder").resolve()
_RECORDER_CLEANABLE_STATUSES = {"stopped", "failed"}


@dataclass(frozen=True)
class PageElementMutationResult:
    element: PageElement
    latest_version_no: int


def _svc():
    """惰性导入以避免循环依赖。"""
    from app.services import page_object_service as _svc_mod
    return _svc_mod


from .page_object_serializers import (
    _element_locators_for_serialization,
    _serialize_candidate_element,
    _serialize_candidate_group,
    _serialize_page_element,
)


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
    normalized_project_code = _svc()._normalize_project_code(project_code)
    normalized_client = normalize_client_code(client)
    normalized_page_code = _svc()._normalize_identifier(page_code, field_name="page_code", max_length=40)
    _svc()._page_object_or_404(
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
    rows = RecorderRepository(db).list_candidate_groups_filtered(
        project_code=normalized_project_code,
        client=normalized_client,
        page_code=normalized_page_code,
        promotion_status=normalized_status or None,
        quality_tier=normalized_quality or None,
        session_id=normalized_session_id or None,
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
    normalized_project_code = _svc()._normalize_project_code(project_code)
    normalized_client = normalize_client_code(client)
    normalized_page_code = _svc()._normalize_identifier(page_code, field_name="page_code", max_length=40)
    _svc()._page_object_or_404(
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
    rows = RecorderRepository(db).list_candidates_filtered(
        project_code=normalized_project_code,
        client=normalized_client,
        page_code=normalized_page_code,
        group_key=normalized_group_key or None,
        session_id=normalized_session_id or None,
        status=normalized_status or None,
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
    normalized_project_code = _svc()._normalize_project_code(project_code)
    normalized_client = normalize_client_code(client)
    normalized_page_code = _svc()._normalize_identifier(page_code, field_name="page_code", max_length=40)
    _svc()._page_object_or_404(
        db,
        project_code=normalized_project_code,
        client=normalized_client,
        page_code=normalized_page_code,
    )
    group = _svc()._candidate_group_or_404(
        db,
        project_code=normalized_project_code,
        client=normalized_client,
        page_code=normalized_page_code,
        group_key=str(group_key or "").strip(),
    )
    payload = _serialize_candidate_group(group)
    payload["candidates"] = _svc().list_candidate_elements(
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
    return RecorderRepository(db).list_candidates_by_group(
        project_code, client, page_code, group_key
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
    normalized_project_code = _svc()._normalize_project_code(project_code)
    test_project_service.ensure_project_active_for_write(db, normalized_project_code)
    normalized_client = normalize_client_code(client)
    normalized_page_code = _svc()._normalize_identifier(page_code, field_name="page_code", max_length=40)
    page_object = _svc()._page_object_or_404(
        db,
        project_code=normalized_project_code,
        client=normalized_client,
        page_code=normalized_page_code,
    )
    group = _svc()._candidate_group_or_404(
        db,
        project_code=normalized_project_code,
        client=normalized_client,
        page_code=normalized_page_code,
        group_key=str(group_key or "").strip(),
    )
    candidate_rows = _svc()._candidate_rows_for_group(
        db,
        project_code=normalized_project_code,
        client=normalized_client,
        page_code=normalized_page_code,
        group_key=group.group_key,
    )
    if not candidate_rows:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="candidate group has no candidate elements")

    business_type = _svc()._normalize_business_type(payload.business_type, group.business_type_guess)
    business_domain = _svc()._normalize_business_domain(payload.business_domain, group.business_domain_guess)
    fallback_locator_type, fallback_locator_value, fallback_role, top_candidate = _svc()._primary_candidate_locator(group, candidate_rows)
    locator_type = _svc()._normalize_locator_type(str(payload.locator_type or fallback_locator_type))
    locator_value = str(payload.locator_value or fallback_locator_value or "").strip()
    if not locator_value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="locator_value cannot be empty")
    role = str(payload.role or fallback_role or "").strip()
    locator_source = _svc()._normalize_locator_source(payload.locator_source or group.top_locator_source or _svc()._locator_source_from_type(locator_type))
    testid_value = str(payload.testid_value or "").strip()
    qa_value = str(payload.qa_value or "").strip()
    if locator_type == "data-testid" and not testid_value:
        testid_value = locator_value
    if locator_type == "data-qa" and not qa_value:
        qa_value = locator_value
    element_code = _svc()._normalize_formal_element_code(
        payload.element_code,
        page_code=normalized_page_code,
        business_type=business_type,
        locator_source=locator_source,
        locator_type=locator_type,
        testid_value=testid_value,
    )
    repo = PageObjectRepository(db)
    existing = repo.get_element_by_code(page_object.id, element_code)
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"page element already exists: {element_code}")
    if bool(payload.is_key_element) and not testid_value and not qa_value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="key element promotion requires testid_value or qa_value",
        )

    stability_level = _svc()._stability_from_locator_source(locator_source, review_status="approved")
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
    now = datetime.now(UTC)
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
    _svc()._refresh_group_status_from_candidates(group, candidate_rows)
    db.add(group)
    _svc()._write_governance_log(
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
    _svc()._sync_page_object_metrics(db, page_object_id=page_object.id)
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
    normalized_project_code = _svc()._normalize_project_code(project_code)
    test_project_service.ensure_project_active_for_write(db, normalized_project_code)
    normalized_client = normalize_client_code(client)
    normalized_page_code = _svc()._normalize_identifier(page_code, field_name="page_code", max_length=40)
    page_object = _svc()._page_object_or_404(
        db,
        project_code=normalized_project_code,
        client=normalized_client,
        page_code=normalized_page_code,
    )
    group = _svc()._candidate_group_or_404(
        db,
        project_code=normalized_project_code,
        client=normalized_client,
        page_code=normalized_page_code,
        group_key=str(group_key or "").strip(),
    )
    target = _svc()._page_element_or_404(
        db,
        page_object_id=page_object.id,
        element_code=_svc()._normalize_identifier(payload.target_element_code, field_name="target_element_code"),
    )
    candidate_rows = _svc()._candidate_rows_for_group(
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
    before_target_governance = _svc()._element_governance_payload(target)
    now = datetime.now(UTC)
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
            repo = PageObjectRepository(db)
            existing_primary = repo.get_locator(target.id, primary_locator_type, primary_locator_value[:512], primary_role)
            if existing_primary is None:
                db.add(
                    PageElementLocator(
                        page_element_id=target.id,
                        locator_type=primary_locator_type,
                        locator_value=primary_locator_value[:512],
                        role=primary_role,
                        locator_source=target.locator_source or _svc()._locator_source_from_type(primary_locator_type),
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
            existing_locator = repo.get_locator(target.id, locator_type, locator_value[:512], role)
            if existing_locator is None:
                db.add(
                    PageElementLocator(
                        page_element_id=target.id,
                        locator_type=locator_type,
                        locator_value=locator_value[:512],
                        role=role,
                        locator_source=_svc()._locator_source_from_type(locator_type),
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
    target.governance_note = _svc()._append_governance_note(target.governance_note, merge_note)
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
    _svc()._refresh_group_status_from_candidates(group, candidate_rows)
    db.add(group)
    _svc()._write_governance_log(
        db,
        page_object=page_object,
        entity_type="candidate_group",
        entity_key=group.group_key,
        action="merge",
        before_payload=before_group,
        after_payload={"target_element_code": target.element_code, "locator_added_count": locator_count, "group": _serialize_candidate_group(group)},
        operator=operator,
    )
    _svc()._write_governance_log(
        db,
        page_object=page_object,
        entity_type="page_element",
        entity_key=target.element_code,
        action="merge",
        before_payload=before_target_governance,
        after_payload={
            **_svc()._element_governance_payload(target),
            "merged_group_key": group.group_key,
            "locator_added_count": locator_count,
        },
        operator=operator,
    )
    db.flush()
    _svc()._sync_page_object_metrics(db, page_object_id=page_object.id)
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
    normalized_project_code = _svc()._normalize_project_code(project_code)
    test_project_service.ensure_project_active_for_write(db, normalized_project_code)
    normalized_client = normalize_client_code(client)
    normalized_page_code = _svc()._normalize_identifier(page_code, field_name="page_code", max_length=40)
    page_object = _svc()._page_object_or_404(
        db,
        project_code=normalized_project_code,
        client=normalized_client,
        page_code=normalized_page_code,
    )
    group = _svc()._candidate_group_or_404(
        db,
        project_code=normalized_project_code,
        client=normalized_client,
        page_code=normalized_page_code,
        group_key=str(group_key or "").strip(),
    )
    candidate_rows = _svc()._candidate_rows_for_group(
        db,
        project_code=normalized_project_code,
        client=normalized_client,
        page_code=normalized_page_code,
        group_key=group.group_key,
    )
    operator = str(payload.operator or "").strip() or "admin"
    review_note = str(payload.review_note or "").strip()
    before_group = _serialize_candidate_group(group)
    now = datetime.now(UTC)
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
    _svc()._refresh_group_status_from_candidates(group, candidate_rows)
    db.add(group)
    _svc()._write_governance_log(
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
    _svc()._sync_page_object_metrics(db, page_object_id=page_object.id)
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
    normalized_project_code = _svc()._normalize_project_code(project_code)
    test_project_service.ensure_project_active_for_write(db, normalized_project_code)
    normalized_client = normalize_client_code(client)
    normalized_page_code = _svc()._normalize_identifier(page_code, field_name="page_code", max_length=40)
    page_object = _svc()._page_object_or_404(
        db,
        project_code=normalized_project_code,
        client=normalized_client,
        page_code=normalized_page_code,
    )
    item = _svc()._candidate_element_or_404(
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
    item.reviewed_at = datetime.now(UTC)
    item.review_note = str(payload.review_note or "").strip()
    db.add(item)
    group = _svc()._candidate_group_or_404(
        db,
        project_code=normalized_project_code,
        client=normalized_client,
        page_code=normalized_page_code,
        group_key=item.group_key,
    )
    candidate_rows = _svc()._candidate_rows_for_group(
        db,
        project_code=normalized_project_code,
        client=normalized_client,
        page_code=normalized_page_code,
        group_key=item.group_key,
    )
    _svc()._refresh_group_status_from_candidates(group, candidate_rows)
    db.add(group)
    _svc()._write_governance_log(
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
    _svc()._sync_page_object_metrics(db, page_object_id=page_object.id)
    db.commit()
    db.refresh(item)
    db.refresh(group)
    return {"candidate": _serialize_candidate_element(item), "group": _serialize_candidate_group(group)}
