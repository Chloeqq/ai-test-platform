"""PageObject candidate group/element routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.page_object import (
    CandidateElementBatchDeletePayload,
    CandidateGroupBatchDeletePayload,
    CandidateGroupMergePayload,
    CandidateGroupPromotePayload,
    CandidateRejectPayload,
)
from app.services import page_object_candidates

router = APIRouter(prefix="/api/page-objects", tags=["page-objects"])


@router.get("/{page_code}/candidate-groups")
def list_candidate_groups(
    page_code: str,
    project_code: str = Query(default="mall"),
    client: str = Query(default="web"),
    promotion_status: str = Query(default=""),
    quality_tier: str = Query(default=""),
    session_id: str = Query(default=""),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    items = page_object_candidates.list_candidate_groups(
        db, page_code=page_code, project_code=project_code, client=client,
        promotion_status=promotion_status, quality_tier=quality_tier,
        session_id=session_id,
    )
    return {"items": items}


@router.get("/{page_code}/candidate-elements")
def list_candidate_elements(
    page_code: str,
    project_code: str = Query(default="mall"),
    client: str = Query(default="web"),
    group_key: str = Query(default=""),
    session_id: str = Query(default=""),
    candidate_status: str = Query(default=""),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    items = page_object_candidates.list_candidate_elements(
        db, page_code=page_code, project_code=project_code, client=client,
        group_key=group_key, session_id=session_id, candidate_status=candidate_status,
    )
    return {"items": items}


@router.get("/{page_code}/candidate-groups/{group_key}")
def get_candidate_group(
    page_code: str, group_key: str,
    project_code: str = Query(default="mall"), client: str = Query(default="web"),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    item = page_object_candidates.get_candidate_group(
        db, page_code=page_code, group_key=group_key,
        project_code=project_code, client=client,
    )
    return {"item": item}


@router.post("/{page_code}/candidate-groups/batch/delete")
def batch_delete_candidate_groups(
    page_code: str, payload: CandidateGroupBatchDeletePayload,
    project_code: str = Query(default="mall"), client: str = Query(default="web"),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    item = page_object_candidates.batch_delete_candidate_groups(
        db, page_code=page_code, project_code=project_code, client=client,
        group_keys=payload.group_keys,
    )
    return {"item": item}


@router.post("/{page_code}/candidate-elements/batch/delete")
def batch_delete_candidate_elements(
    page_code: str, payload: CandidateElementBatchDeletePayload,
    project_code: str = Query(default="mall"), client: str = Query(default="web"),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    item = page_object_candidates.batch_delete_candidate_elements(
        db, page_code=page_code, project_code=project_code, client=client,
        candidate_keys=payload.candidate_keys,
    )
    return {"item": item}


@router.post("/{page_code}/candidate-groups/{group_key}/promote")
def promote_candidate_group(
    page_code: str, group_key: str, payload: CandidateGroupPromotePayload,
    project_code: str = Query(default="mall"), client: str = Query(default="web"),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    item = page_object_candidates.promote_candidate_group(
        db, page_code=page_code, group_key=group_key,
        project_code=project_code, client=client, payload=payload,
    )
    return {"item": item}


@router.post("/{page_code}/candidate-groups/{group_key}/merge")
def merge_candidate_group(
    page_code: str, group_key: str, payload: CandidateGroupMergePayload,
    project_code: str = Query(default="mall"), client: str = Query(default="web"),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    item = page_object_candidates.merge_candidate_group(
        db, page_code=page_code, group_key=group_key,
        project_code=project_code, client=client, payload=payload,
    )
    return {"item": item}


@router.post("/{page_code}/candidate-groups/{group_key}/reject")
def reject_candidate_group(
    page_code: str, group_key: str, payload: CandidateRejectPayload,
    project_code: str = Query(default="mall"), client: str = Query(default="web"),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    item = page_object_candidates.reject_candidate_group(
        db, page_code=page_code, group_key=group_key,
        project_code=project_code, client=client, payload=payload,
    )
    return {"item": item}


@router.post("/{page_code}/candidate-elements/{candidate_key}/reject")
def reject_candidate_element(
    page_code: str, candidate_key: str, payload: CandidateRejectPayload,
    project_code: str = Query(default="mall"), client: str = Query(default="web"),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    item = page_object_candidates.reject_candidate_element(
        db, page_code=page_code, candidate_key=candidate_key,
        project_code=project_code, client=client, payload=payload,
    )
    return {"item": item}
