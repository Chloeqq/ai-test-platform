from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.schemas.test_data_pool import (
    TestDataPoolCreate,
    TestDataPoolItemDelete,
    TestDataPoolItemUpsert,
    TestDataPoolUpdate,
)
from app.services import test_data_pool_service

router = APIRouter(prefix="/api/test-data-pools", tags=["test-data-pools"])


def _require_data_pool_admin(current_user: Any) -> None:
    role = str(getattr(current_user, "role", "") or "").strip().lower()
    if role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "data_pool_access_forbidden", "message": "only admin can manage test data pools"},
        )


@router.get("")
def list_data_pools(
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> dict[str, object]:
    _require_data_pool_admin(current_user)
    return {"items": test_data_pool_service.list_data_pools(db)}


@router.post("")
def create_data_pool(
    payload: TestDataPoolCreate,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> dict[str, object]:
    _require_data_pool_admin(current_user)
    item = test_data_pool_service.create_data_pool(
        db,
        pool_name=payload.pool_name,
        description=payload.description,
        status_value=payload.status,
        created_by=payload.created_by,
    )
    return {"item": item}


@router.put("/{pool_name}")
def update_data_pool(
    pool_name: str,
    payload: TestDataPoolUpdate,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> dict[str, object]:
    _require_data_pool_admin(current_user)
    item = test_data_pool_service.update_data_pool(
        db,
        pool_name=pool_name,
        description=payload.description,
        status_value=payload.status,
        updated_by=payload.updated_by,
    )
    return {"item": item}


@router.get("/{pool_name}/items")
def list_pool_items(
    pool_name: str,
    reveal_secret: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> dict[str, object]:
    _require_data_pool_admin(current_user)
    return {"items": test_data_pool_service.list_data_pool_items(db, pool_name=pool_name, reveal_secret=reveal_secret)}


@router.put("/{pool_name}/items/{item_key}")
def upsert_pool_item(
    pool_name: str,
    item_key: str,
    payload: TestDataPoolItemUpsert,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> dict[str, object]:
    _require_data_pool_admin(current_user)
    item = test_data_pool_service.upsert_data_pool_item(
        db,
        pool_name=pool_name,
        item_key=item_key,
        item_value=payload.item_value,
        status_value=payload.status,
        changed_by=payload.changed_by,
        note=payload.note,
    )
    return {"item": item}


@router.get("/{pool_name}/items/{item_key}/references")
def list_pool_item_references(
    pool_name: str,
    item_key: str,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> dict[str, object]:
    _require_data_pool_admin(current_user)
    items = test_data_pool_service.find_pool_item_references(
        db,
        pool_name=pool_name,
        item_key=item_key,
    )
    return {"items": items, "total": len(items)}


@router.delete("/{pool_name}/items/{item_key}")
def delete_pool_item(
    pool_name: str,
    item_key: str,
    payload: TestDataPoolItemDelete,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> dict[str, object]:
    _require_data_pool_admin(current_user)
    item = test_data_pool_service.delete_data_pool_item(
        db,
        pool_name=pool_name,
        item_key=item_key,
        changed_by=payload.changed_by,
        note=payload.note,
    )
    return {"item": item}
