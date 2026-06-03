from __future__ import annotations

import json
import logging
from typing import Any
import yaml

from fastapi import HTTPException, status
from sqlalchemy import inspect, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.test_case import TestCase
from app.models.test_data_pool import TestDataPool, TestDataPoolAuditLog, TestDataPoolItem
from app.repositories.test_case_repository import TestCaseRepository
from app.repositories.test_data_pool_repository import TestDataPoolRepository
from app.services.test_case_data_service import normalize_optional_text

_VALID_POOL_STATUS = {"active", "inactive"}
LOGGER = logging.getLogger(__name__)


def _normalized_pool_name(value: Any) -> str:
    return normalize_optional_text(value)


def _normalized_item_key(value: Any) -> str:
    return normalize_optional_text(value)


def _normalized_pool_status(value: Any) -> str:
    normalized = normalize_optional_text(value).lower() or "active"
    if normalized not in _VALID_POOL_STATUS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "code": "data_pool_invalid_status",
                "message": f"unsupported pool status `{normalized}`",
            },
        )
    return normalized


def _json_text(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except Exception:
        return str(value or "")


def _append_audit_log(
    db: Session,
    *,
    pool_name: str,
    item_key: str,
    operation: str,
    changed_by: str,
    note: str,
    before_value: Any,
    after_value: Any,
) -> None:
    db.add(
        TestDataPoolAuditLog(
            pool_name=pool_name,
            item_key=item_key,
            operation=operation,
            changed_by=normalize_optional_text(changed_by) or "admin",
            note=normalize_optional_text(note),
            before_value=_json_text(before_value),
            after_value=_json_text(after_value),
        )
    )


def _pool_or_404(db: Session, pool_name: str) -> TestDataPool:
    normalized = _normalized_pool_name(pool_name)
    pool = TestDataPoolRepository(db).get_by_name(normalized)
    if pool is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"pool not found: {normalized}")
    return pool


def _to_pool_item_payload(pool: TestDataPool) -> dict[str, Any]:
    return {
        "pool_name": pool.pool_name,
        "description": pool.description,
        "status": pool.status,
        "created_by": pool.created_by,
        "updated_by": pool.updated_by,
        "created_at": pool.created_at.isoformat() if pool.created_at else "",
        "updated_at": pool.updated_at.isoformat() if pool.updated_at else "",
    }


def _masked_item_value(value: Any) -> str:
    raw = str(value or "")
    if not raw:
        return ""
    if len(raw) <= 4:
        return "*" * len(raw)
    return f"{raw[:2]}***{raw[-2:]}"


def _to_item_payload(item: TestDataPoolItem, *, reveal_secret: bool = False) -> dict[str, Any]:
    item_value = str(item.item_value or "")
    return {
        "item_key": item.item_key,
        "item_value": item_value if reveal_secret else "",
        "item_value_preview": item_value[:2] + "***" if reveal_secret and item_value else _masked_item_value(item_value),
        "has_value": bool(item_value),
        "status": item.status,
        "created_by": item.created_by,
        "updated_by": item.updated_by,
        "created_at": item.created_at.isoformat() if item.created_at else "",
        "updated_at": item.updated_at.isoformat() if item.updated_at else "",
    }


def list_data_pools(db: Session) -> list[dict[str, Any]]:
    rows = TestDataPoolRepository(db).list_all()
    return [_to_pool_item_payload(row) for row in rows]


def create_data_pool(
    db: Session,
    *,
    pool_name: str,
    description: str,
    status_value: str,
    created_by: str,
) -> dict[str, Any]:
    normalized_pool_name = _normalized_pool_name(pool_name)
    if not normalized_pool_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="pool_name must not be empty")
    existing = TestDataPoolRepository(db).get_by_name(normalized_pool_name)
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"pool already exists: {normalized_pool_name}")
    pool = TestDataPool(
        pool_name=normalized_pool_name,
        description=normalize_optional_text(description),
        status=_normalized_pool_status(status_value),
        created_by=normalize_optional_text(created_by) or "admin",
        updated_by=normalize_optional_text(created_by) or "admin",
    )
    db.add(pool)
    _append_audit_log(
        db,
        pool_name=normalized_pool_name,
        item_key="",
        operation="pool_create",
        changed_by=created_by,
        note="",
        before_value="",
        after_value=description,
    )
    db.commit()
    db.refresh(pool)
    return _to_pool_item_payload(pool)


def update_data_pool(
    db: Session,
    *,
    pool_name: str,
    description: str | None,
    status_value: str | None,
    updated_by: str,
) -> dict[str, Any]:
    pool = _pool_or_404(db, pool_name)
    before_payload = _to_pool_item_payload(pool)
    if description is not None:
        pool.description = normalize_optional_text(description)
    if status_value is not None:
        pool.status = _normalized_pool_status(status_value)
    pool.updated_by = normalize_optional_text(updated_by) or "admin"
    db.add(pool)
    _append_audit_log(
        db,
        pool_name=pool.pool_name,
        item_key="",
        operation="pool_update",
        changed_by=updated_by,
        note="",
        before_value=before_payload,
        after_value=_to_pool_item_payload(pool),
    )
    db.commit()
    db.refresh(pool)
    return _to_pool_item_payload(pool)


def list_data_pool_items(db: Session, *, pool_name: str, reveal_secret: bool = False) -> list[dict[str, Any]]:
    pool = _pool_or_404(db, pool_name)
    rows = TestDataPoolRepository(db).list_items_by_pool(pool.id)
    return [_to_item_payload(row, reveal_secret=reveal_secret) for row in rows]


def upsert_data_pool_item(
    db: Session,
    *,
    pool_name: str,
    item_key: str,
    item_value: Any,
    status_value: str,
    changed_by: str,
    note: str,
) -> dict[str, Any]:
    pool = _pool_or_404(db, pool_name)
    normalized_item_key = _normalized_item_key(item_key)
    if not normalized_item_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="item_key must not be empty")
    row = TestDataPoolRepository(db).get_item_by_key(pool.id, normalized_item_key)
    before_value = ""
    if row is None:
        row = TestDataPoolItem(
            pool_id=pool.id,
            item_key=normalized_item_key,
            item_value=str(item_value or ""),
            status=_normalized_pool_status(status_value),
            created_by=normalize_optional_text(changed_by) or "admin",
            updated_by=normalize_optional_text(changed_by) or "admin",
        )
        operation = "item_create"
    else:
        before_value = row.item_value
        row.item_value = str(item_value or "")
        row.status = _normalized_pool_status(status_value)
        row.updated_by = normalize_optional_text(changed_by) or "admin"
        operation = "item_update"
    db.add(row)
    _append_audit_log(
        db,
        pool_name=pool.pool_name,
        item_key=normalized_item_key,
        operation=operation,
        changed_by=changed_by,
        note=note,
        before_value=before_value,
        after_value=row.item_value,
    )
    db.commit()
    db.refresh(row)
    return _to_item_payload(row, reveal_secret=True)


def _extract_pool_refs_from_case_yaml(case_yaml: dict[str, Any]) -> list[tuple[str, str]]:
    data = case_yaml.get("data")
    if not isinstance(data, dict):
        return []
    refs: list[tuple[str, str]] = []
    for raw_value in data.values():
        if not isinstance(raw_value, dict):
            continue
        source_type = normalize_optional_text(raw_value.get("source_type")).lower()
        if source_type != "pool":
            continue
        pool_name = _normalized_pool_name(raw_value.get("pool_name"))
        item_key = _normalized_item_key(raw_value.get("key"))
        if pool_name and item_key:
            refs.append((pool_name, item_key))
    return refs


def _load_case_yaml(script_code: Any) -> dict[str, Any]:
    try:
        payload = yaml.safe_load(str(script_code or "")) or {}
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def find_pool_item_references(
    db: Session,
    *,
    pool_name: str,
    item_key: str,
) -> list[dict[str, Any]]:
    normalized_pool_name = _normalized_pool_name(pool_name)
    normalized_item_key = _normalized_item_key(item_key)
    if not normalized_pool_name or not normalized_item_key:
        return []
    refs: list[dict[str, Any]] = []
    all_cases = TestCaseRepository(db).list_all()
    rows = [(c.id, c.case_id, c.project_code, c.name, c.script_code) for c in all_cases]
    for case_id, case_business_id, project_code, case_name, script_code in rows:
        case_yaml = _load_case_yaml(script_code)
        pool_refs = _extract_pool_refs_from_case_yaml(case_yaml)
        if (normalized_pool_name, normalized_item_key) in pool_refs:
            refs.append(
                {
                    "id": case_id,
                    "case_id": case_business_id,
                    "project_code": project_code,
                    "name": case_name,
                }
            )
    return refs


def delete_data_pool_item(
    db: Session,
    *,
    pool_name: str,
    item_key: str,
    changed_by: str,
    note: str,
) -> dict[str, Any]:
    pool = _pool_or_404(db, pool_name)
    normalized_item_key = _normalized_item_key(item_key)
    row = TestDataPoolRepository(db).get_item_by_key(pool.id, normalized_item_key)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"pool item not found: {pool.pool_name}.{normalized_item_key}")
    refs = find_pool_item_references(db, pool_name=pool.pool_name, item_key=normalized_item_key)
    if refs:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "data_pool_key_in_use",
                "message": f"pool item is referenced by test cases: {pool.pool_name}.{normalized_item_key}",
                "references": refs,
            },
        )
    before_value = row.item_value
    db.delete(row)
    _append_audit_log(
        db,
        pool_name=pool.pool_name,
        item_key=normalized_item_key,
        operation="item_delete",
        changed_by=changed_by,
        note=note,
        before_value=before_value,
        after_value="",
    )
    db.commit()
    return {"pool_name": pool.pool_name, "item_key": normalized_item_key, "deleted": True}


def serialize_runner_data_pool_snapshot(db: Session) -> str:
    try:
        conn = db.get_bind()
        db_inspector = inspect(conn)
        if not db_inspector.has_table("test_data_pools") or not db_inspector.has_table("test_data_pool_items"):
            return "{}"
        rows = TestDataPoolRepository(db).list_active_items_with_pool_name()
    except SQLAlchemyError as exc:
        LOGGER.warning("serialize_runner_data_pool_snapshot skipped due to database error: %s", exc)
        return "{}"
    payload: dict[str, dict[str, Any]] = {}
    for pool_name, item_key, item_value in rows:
        normalized_pool_name = _normalized_pool_name(pool_name)
        normalized_item_key = _normalized_item_key(item_key)
        if not normalized_pool_name or not normalized_item_key:
            continue
        payload.setdefault(normalized_pool_name, {})[normalized_item_key] = item_value
    return json.dumps(payload, ensure_ascii=False)
