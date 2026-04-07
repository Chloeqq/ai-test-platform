from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.page_object import (
    PageElementCreate,
    PageElementUpdate,
    PageElementVersionCreate,
    PageObjectCreate,
    PageObjectRefCreate,
    PageObjectUpdate,
)
from app.services import page_object_service

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


@router.get("/{page_code}")
def get_page_object(
    page_code: str,
    project_code: str = Query(default="atp"),
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


@router.put("/{page_code}")
def update_page_object(
    page_code: str,
    payload: PageObjectUpdate,
    project_code: str = Query(default="atp"),
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
    project_code: str = Query(default="atp"),
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
    project_code: str = Query(default="atp"),
    client: str = Query(default="web"),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    items = page_object_service.list_page_elements(
        db,
        page_code=page_code,
        project_code=project_code,
        client=client,
    )
    return {"items": items}


@router.post("/{page_code}/elements", status_code=status.HTTP_201_CREATED)
def create_page_element(
    page_code: str,
    payload: PageElementCreate,
    project_code: str = Query(default="atp"),
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


@router.get("/{page_code}/elements/{element_code}")
def get_page_element(
    page_code: str,
    element_code: str,
    project_code: str = Query(default="atp"),
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
    project_code: str = Query(default="atp"),
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
    project_code: str = Query(default="atp"),
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
    project_code: str = Query(default="atp"),
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
    project_code: str = Query(default="atp"),
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
    project_code: str = Query(default="atp"),
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
    project_code: str = Query(default="atp"),
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
