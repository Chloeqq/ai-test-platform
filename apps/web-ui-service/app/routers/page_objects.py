from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.page_object import (
    CandidateElementBatchDeletePayload,
    CandidateGroupBatchDeletePayload,
    CandidateGroupMergePayload,
    CandidateGroupPromotePayload,
    CandidateRejectPayload,
    PageElementBatchDeletePayload,
    PageElementCreate,
    PageElementUpdate,
    PageElementVersionCreate,
    PageObjectCreate,
    PageObjectRefCreate,
    PageObjectUpdate,
)
from app.services import page_object_import_service, page_object_service

router = APIRouter(prefix="/api/page-objects", tags=["page-objects"])


@router.get("")
def list_page_objects(
    project_code: str = Query(default=""),
    client: str = Query(default=""),
    status_value: str = Query(default="", alias="status"),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    items = page_object_service.list_page_objects(
        db,
        project_code=project_code,
        client=client,
        status_value=status_value,
    )
    return {"items": items}


@router.post("", status_code=status.HTTP_201_CREATED)
def create_page_object(payload: PageObjectCreate, db: Session = Depends(get_db)) -> dict[str, object]:
    item = page_object_service.create_page_object(db, payload)
    return {"item": item}


@router.post("/deduplicate")
def deduplicate_page_elements(
    project_code: str = Query(default=""),
    client: str = Query(default=""),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    item = page_object_service.deduplicate_page_elements(
        db,
        project_code=project_code,
        client=client,
    )
    return {"item": item}


@router.post("/imports/preview")
async def preview_page_object_import(
    project_code: str = Form(default="mall"),
    client: str = Form(default="web"),
    source_type: str = Form(default="data_testid_guidelines"),
    page_code: str = Form(default=""),
    data_testid_guidelines: UploadFile = File(...),
    runtime_dom_selectors: UploadFile | None = File(default=None),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    data_testid_content = await data_testid_guidelines.read()
    runtime_dom_content = await runtime_dom_selectors.read() if runtime_dom_selectors is not None else None
    item = page_object_import_service.create_import_preview(
        db,
        project_code=project_code,
        client=client,
        source_type=source_type,
        data_testid_filename=data_testid_guidelines.filename or "data-testid-guidelines.md",
        data_testid_content=data_testid_content,
        runtime_dom_filename=runtime_dom_selectors.filename if runtime_dom_selectors is not None else "",
        runtime_dom_content=runtime_dom_content,
        page_code_filter=page_code,
    )
    return {"item": item}


@router.get("/imports/{import_id}")
def get_page_object_import(import_id: str) -> dict[str, object]:
    return {"item": page_object_import_service.get_import(import_id)}


@router.post("/imports/{import_id}/apply")
def apply_page_object_import(
    import_id: str,
    auto_approve: bool = Query(default=True),
    upsert_policy: str = Query(default="upgrade_existing"),
    operator: str = Query(default="admin"),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    item = page_object_import_service.apply_import(
        db,
        import_id=import_id,
        operator=operator,
        auto_approve=auto_approve,
        upsert_policy=upsert_policy,
    )
    return {"item": item}


@router.get("/{page_code}")
def get_page_object(
    page_code: str,
    project_code: str = Query(default="mall"),
    client: str = Query(default="web"),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    item = page_object_service.get_page_object(
        db,
        page_code=page_code,
        project_code=project_code,
        client=client,
    )
    return {"item": item}


@router.get("/{page_code}/governance/summary")
def get_page_object_governance_summary(
    page_code: str,
    project_code: str = Query(default="mall"),
    client: str = Query(default="web"),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    item = page_object_service.get_page_object_governance_summary(
        db,
        page_code=page_code,
        project_code=project_code,
        client=client,
    )
    return {"item": item}


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
    items = page_object_service.list_candidate_groups(
        db,
        page_code=page_code,
        project_code=project_code,
        client=client,
        promotion_status=promotion_status,
        quality_tier=quality_tier,
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
    items = page_object_service.list_candidate_elements(
        db,
        page_code=page_code,
        project_code=project_code,
        client=client,
        group_key=group_key,
        session_id=session_id,
        candidate_status=candidate_status,
    )
    return {"items": items}


@router.get("/{page_code}/candidate-groups/{group_key}")
def get_candidate_group(
    page_code: str,
    group_key: str,
    project_code: str = Query(default="mall"),
    client: str = Query(default="web"),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    item = page_object_service.get_candidate_group(
        db,
        page_code=page_code,
        group_key=group_key,
        project_code=project_code,
        client=client,
    )
    return {"item": item}


@router.post("/{page_code}/candidate-groups/batch/delete")
def batch_delete_candidate_groups(
    page_code: str,
    payload: CandidateGroupBatchDeletePayload,
    project_code: str = Query(default="mall"),
    client: str = Query(default="web"),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    item = page_object_service.batch_delete_candidate_groups(
        db,
        page_code=page_code,
        project_code=project_code,
        client=client,
        group_keys=payload.group_keys,
    )
    return {"item": item}


@router.post("/{page_code}/candidate-elements/batch/delete")
def batch_delete_candidate_elements(
    page_code: str,
    payload: CandidateElementBatchDeletePayload,
    project_code: str = Query(default="mall"),
    client: str = Query(default="web"),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    item = page_object_service.batch_delete_candidate_elements(
        db,
        page_code=page_code,
        project_code=project_code,
        client=client,
        candidate_keys=payload.candidate_keys,
    )
    return {"item": item}


@router.post("/{page_code}/candidate-groups/{group_key}/promote")
def promote_candidate_group(
    page_code: str,
    group_key: str,
    payload: CandidateGroupPromotePayload,
    project_code: str = Query(default="mall"),
    client: str = Query(default="web"),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    item = page_object_service.promote_candidate_group(
        db,
        page_code=page_code,
        group_key=group_key,
        project_code=project_code,
        client=client,
        payload=payload,
    )
    return {"item": item}


@router.post("/{page_code}/candidate-groups/{group_key}/merge")
def merge_candidate_group(
    page_code: str,
    group_key: str,
    payload: CandidateGroupMergePayload,
    project_code: str = Query(default="mall"),
    client: str = Query(default="web"),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    item = page_object_service.merge_candidate_group(
        db,
        page_code=page_code,
        group_key=group_key,
        project_code=project_code,
        client=client,
        payload=payload,
    )
    return {"item": item}


@router.post("/{page_code}/candidate-groups/{group_key}/reject")
def reject_candidate_group(
    page_code: str,
    group_key: str,
    payload: CandidateRejectPayload,
    project_code: str = Query(default="mall"),
    client: str = Query(default="web"),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    item = page_object_service.reject_candidate_group(
        db,
        page_code=page_code,
        group_key=group_key,
        project_code=project_code,
        client=client,
        payload=payload,
    )
    return {"item": item}


@router.post("/{page_code}/candidate-elements/{candidate_key}/reject")
def reject_candidate_element(
    page_code: str,
    candidate_key: str,
    payload: CandidateRejectPayload,
    project_code: str = Query(default="mall"),
    client: str = Query(default="web"),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    item = page_object_service.reject_candidate_element(
        db,
        page_code=page_code,
        candidate_key=candidate_key,
        project_code=project_code,
        client=client,
        payload=payload,
    )
    return {"item": item}


@router.put("/{page_code}")
def update_page_object(
    page_code: str,
    payload: PageObjectUpdate,
    project_code: str = Query(default="mall"),
    client: str = Query(default="web"),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    item = page_object_service.update_page_object(
        db,
        page_code=page_code,
        project_code=project_code,
        client=client,
        payload=payload,
    )
    return {"item": item}


@router.delete("/{page_code}")
def delete_page_object(
    page_code: str,
    project_code: str = Query(default="mall"),
    client: str = Query(default="web"),
    cascade_elements: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    item = page_object_service.delete_page_object(
        db,
        page_code=page_code,
        project_code=project_code,
        client=client,
        cascade_elements=cascade_elements,
    )
    return {"item": item}


@router.get("/{page_code}/elements")
def list_page_elements(
    page_code: str,
    project_code: str = Query(default="mall"),
    client: str = Query(default="web"),
    purge_duplicates: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    items = page_object_service.list_page_elements(
        db,
        page_code=page_code,
        project_code=project_code,
        client=client,
        purge_duplicates=purge_duplicates,
    )
    return {"items": items}


@router.post("/{page_code}/elements", status_code=status.HTTP_201_CREATED)
def create_page_element(
    page_code: str,
    payload: PageElementCreate,
    project_code: str = Query(default="mall"),
    client: str = Query(default="web"),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    item = page_object_service.create_page_element(
        db,
        page_code=page_code,
        project_code=project_code,
        client=client,
        payload=payload,
    )
    return {"item": item}


@router.post("/{page_code}/elements/batch/delete")
def batch_delete_page_elements(
    page_code: str,
    payload: PageElementBatchDeletePayload,
    project_code: str = Query(default="mall"),
    client: str = Query(default="web"),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    item = page_object_service.batch_delete_page_elements(
        db,
        page_code=page_code,
        project_code=project_code,
        client=client,
        element_codes=payload.element_codes,
    )
    return {"item": item}


@router.get("/{page_code}/elements/{element_code}")
def get_page_element(
    page_code: str,
    element_code: str,
    project_code: str = Query(default="mall"),
    client: str = Query(default="web"),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    item = page_object_service.get_page_element(
        db,
        page_code=page_code,
        element_code=element_code,
        project_code=project_code,
        client=client,
    )
    return {"item": item}


@router.put("/{page_code}/elements/{element_code}")
def update_page_element(
    page_code: str,
    element_code: str,
    payload: PageElementUpdate,
    project_code: str = Query(default="mall"),
    client: str = Query(default="web"),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    item = page_object_service.update_page_element(
        db,
        page_code=page_code,
        element_code=element_code,
        project_code=project_code,
        client=client,
        payload=payload,
    )
    return {"item": item}


@router.delete("/{page_code}/elements/{element_code}")
def delete_page_element(
    page_code: str,
    element_code: str,
    project_code: str = Query(default="mall"),
    client: str = Query(default="web"),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    item = page_object_service.delete_page_element(
        db,
        page_code=page_code,
        element_code=element_code,
        project_code=project_code,
        client=client,
    )
    return {"item": item}


@router.get("/{page_code}/elements/{element_code}/versions")
def list_page_element_versions(
    page_code: str,
    element_code: str,
    project_code: str = Query(default="mall"),
    client: str = Query(default="web"),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    items = page_object_service.list_page_element_versions(
        db,
        page_code=page_code,
        element_code=element_code,
        project_code=project_code,
        client=client,
    )
    return {"items": items}


@router.post("/{page_code}/elements/{element_code}/versions", status_code=status.HTTP_201_CREATED)
def create_page_element_version(
    page_code: str,
    element_code: str,
    payload: PageElementVersionCreate,
    project_code: str = Query(default="mall"),
    client: str = Query(default="web"),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    item = page_object_service.create_page_element_version(
        db,
        page_code=page_code,
        element_code=element_code,
        project_code=project_code,
        client=client,
        payload=payload,
    )
    return {"item": item}


@router.get("/{page_code}/elements/{element_code}/refs")
def list_page_object_refs(
    page_code: str,
    element_code: str,
    project_code: str = Query(default="mall"),
    client: str = Query(default="web"),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    items = page_object_service.list_page_object_refs(
        db,
        page_code=page_code,
        element_code=element_code,
        project_code=project_code,
        client=client,
    )
    return {"items": items}


@router.post("/{page_code}/elements/{element_code}/refs", status_code=status.HTTP_201_CREATED)
def create_page_object_ref(
    page_code: str,
    element_code: str,
    payload: PageObjectRefCreate,
    project_code: str = Query(default="mall"),
    client: str = Query(default="web"),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    item = page_object_service.create_page_object_ref(
        db,
        page_code=page_code,
        element_code=element_code,
        project_code=project_code,
        client=client,
        payload=payload,
    )
    return {"item": item}
