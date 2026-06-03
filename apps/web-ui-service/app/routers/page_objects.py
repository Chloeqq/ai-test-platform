from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.page_object import (
    PageObjectCreate,
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


