from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import HTTPException, status
from shared_backend.case_ids import normalize_client_code
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models.page_object import (
    PageElement,
    PageElementHealthCheck,
    PageElementVersion,
    PageObject,
    PageObjectRecorderSession,
    PageObjectRef,
)
from app.schemas.page_object import (
    PageElementCreate,
    PageElementUpdate,
    PageElementVersionCreate,
    PageObjectCreate,
    PageObjectRefCreate,
    PageObjectUpdate,
)
from app.services import test_project_service

PAGE_OBJECT_STATUS_VALUES = {"draft", "review", "published", "retired"}
PAGE_ELEMENT_STATUS_VALUES = {"active", "inactive", "deprecated"}
LOCATOR_TYPE_VALUES = {"id", "name", "css", "xpath", "text", "placeholder", "role", "data-testid"}
REFERENCE_TYPE_VALUES = {"test_case", "script", "test_point", "plan", "suite"}
_RECORDER_ROOT = (Path(__file__).resolve().parents[4] / "artifacts" / "page-recorder").resolve()
_RECORDER_CLEANABLE_STATUSES = {"stopped", "failed"}


@dataclass(frozen=True)
class PageElementMutationResult:
    element: PageElement
    latest_version_no: int


def _normalize_project_code(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "", str(value or "").strip()).lower()
    if len(normalized) < 2 or len(normalized) > 20:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="project_code must be 2-20 letters or digits",
        )
    return normalized


def _normalize_identifier(value: str, *, field_name: str, min_length: int = 2, max_length: int = 80) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9_-]+", "-", str(value or "").strip()).strip("-").lower()
    if len(normalized) < min_length or len(normalized) > max_length:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{field_name} must be {min_length}-{max_length} chars and use letters/digits/_/-",
        )
    return normalized


def _normalize_page_object_status(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized not in PAGE_OBJECT_STATUS_VALUES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"page object status must be one of: {', '.join(sorted(PAGE_OBJECT_STATUS_VALUES))}",
        )
    return normalized


def _normalize_page_element_status(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized not in PAGE_ELEMENT_STATUS_VALUES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"page element status must be one of: {', '.join(sorted(PAGE_ELEMENT_STATUS_VALUES))}",
        )
    return normalized


def _normalize_locator_type(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized not in LOCATOR_TYPE_VALUES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"locator_type must be one of: {', '.join(sorted(LOCATOR_TYPE_VALUES))}",
        )
    return normalized


def _normalize_reference_type(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized not in REFERENCE_TYPE_VALUES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"reference_type must be one of: {', '.join(sorted(REFERENCE_TYPE_VALUES))}",
        )
    return normalized


def _normalize_binary_health_status(value: int) -> int:
    normalized = int(value)
    if normalized not in {0, 1}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="health_status must be 0 or 1",
        )
    return normalized


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
    sessions = list(
        db.execute(
            select(PageObjectRecorderSession).where(
                PageObjectRecorderSession.project_code == project_code,
                PageObjectRecorderSession.client == client,
                PageObjectRecorderSession.page_code == page_code,
            )
        ).scalars().all()
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
) -> dict[str, Any]:
    return {
        "id": item.id,
        "element_id": item.id,
        "page_object_id": item.page_object_id,
        "page_id": item.page_object_id,
        "element_code": item.element_code,
        "element_name": item.element_name,
        "locator_type": item.locator_type,
        "locator_value": item.locator_value,
        "backup_locator": item.backup_locator,
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


def _page_object_or_404(
    db: Session,
    *,
    project_code: str,
    client: str,
    page_code: str,
) -> PageObject:
    item = db.execute(
        select(PageObject).where(
            PageObject.project_code == project_code,
            PageObject.client == client,
            PageObject.page_code == page_code,
        )
    ).scalar_one_or_none()
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"page object not found: {project_code}/{client}/{page_code}",
        )
    return item


def _page_element_or_404(db: Session, *, page_object_id: int, element_code: str) -> PageElement:
    item = db.execute(
        select(PageElement).where(
            PageElement.page_object_id == page_object_id,
            PageElement.element_code == element_code,
        )
    ).scalar_one_or_none()
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"page element not found: {element_code}",
        )
    return item


def _next_element_version_no(db: Session, *, page_element_id: int) -> int:
    latest = db.execute(
        select(func.max(PageElementVersion.version_no)).where(PageElementVersion.page_element_id == page_element_id)
    ).scalar_one()
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
    db.commit()
    return next_version_no


def _sync_page_object_metrics(db: Session, *, page_object_id: int) -> None:
    page_object = db.get(PageObject, page_object_id)
    if page_object is None:
        return
    next_element_count = int(
        db.execute(
            select(func.count()).select_from(PageElement).where(PageElement.page_object_id == page_object_id)
        ).scalar_one()
        or 0
    )
    unhealthy_count = int(
        db.execute(
            select(func.count()).select_from(PageElement).where(
                PageElement.page_object_id == page_object_id,
                PageElement.health_status == 0,
            )
        ).scalar_one()
        or 0
    )
    next_health_status = 0 if unhealthy_count > 0 else 1
    changed = False
    if int(page_object.element_count or 0) != next_element_count:
        page_object.element_count = next_element_count
        changed = True
    if int(page_object.health_status if page_object.health_status is not None else 1) != next_health_status:
        page_object.health_status = next_health_status
        changed = True
    if changed:
        db.add(page_object)
        db.commit()


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
    rows = list(db.execute(stmt).scalars().all())
    if not rows:
        return []
    object_ids = [item.id for item in rows]
    element_counts = {
        int(page_object_id): int(count or 0)
        for page_object_id, count in db.execute(
            select(PageElement.page_object_id, func.count())
            .where(PageElement.page_object_id.in_(object_ids))
            .group_by(PageElement.page_object_id)
        ).all()
    }
    return [_serialize_page_object(item, element_count=element_counts.get(item.id, 0)) for item in rows]


def create_page_object(db: Session, payload: PageObjectCreate) -> dict[str, Any]:
    normalized_project_code = _normalize_project_code(payload.project_code)
    test_project_service.ensure_project_active_for_write(db, normalized_project_code)
    normalized_client = normalize_client_code(payload.client)
    normalized_page_code = _normalize_identifier(payload.page_code, field_name="page_code", max_length=40)
    existing = db.execute(
        select(PageObject).where(
            PageObject.project_code == normalized_project_code,
            PageObject.client == normalized_client,
            PageObject.page_code == normalized_page_code,
        )
    ).scalar_one_or_none()
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
    project_code: str = "atp",
    client: str = "web",
) -> dict[str, Any]:
    item = _page_object_or_404(
        db,
        project_code=_normalize_project_code(project_code),
        client=normalize_client_code(client),
        page_code=_normalize_identifier(page_code, field_name="page_code", max_length=40),
    )
    element_count = int(
        db.execute(select(func.count()).select_from(PageElement).where(PageElement.page_object_id == item.id)).scalar_one()
        or 0
    )
    return _serialize_page_object(item, element_count=element_count)


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
    element_count = int(
        db.execute(select(func.count()).select_from(PageElement).where(PageElement.page_object_id == item.id)).scalar_one()
        or 0
    )
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
    element_ids = [int(value) for value in db.execute(
        select(PageElement.id).where(PageElement.page_object_id == item.id)
    ).scalars().all()]
    if element_ids and not cascade_elements:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"page object still has {len(element_ids)} element(s); set cascade_elements=true to delete",
        )
    deleted_element_count = len(element_ids)
    if element_ids:
        db.execute(delete(PageElementVersion).where(PageElementVersion.page_element_id.in_(element_ids)))
        db.execute(delete(PageObjectRef).where(PageObjectRef.page_element_id.in_(element_ids)))
        db.execute(delete(PageElementHealthCheck).where(PageElementHealthCheck.page_element_id.in_(element_ids)))
        db.execute(delete(PageElement).where(PageElement.id.in_(element_ids)))
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
    project_code: str = "atp",
    client: str = "web",
) -> list[dict[str, Any]]:
    page_object = _page_object_or_404(
        db,
        project_code=_normalize_project_code(project_code),
        client=normalize_client_code(client),
        page_code=_normalize_identifier(page_code, field_name="page_code", max_length=40),
    )
    rows = list(
        db.execute(
            select(PageElement)
            .where(PageElement.page_object_id == page_object.id)
            .order_by(PageElement.updated_at.desc(), PageElement.id.desc())
        ).scalars().all()
    )
    if not rows:
        return []
    element_ids = [item.id for item in rows]
    version_map = {
        int(element_id): int(version_no or 0)
        for element_id, version_no in db.execute(
            select(PageElementVersion.page_element_id, func.max(PageElementVersion.version_no))
            .where(PageElementVersion.page_element_id.in_(element_ids))
            .group_by(PageElementVersion.page_element_id)
        ).all()
    }
    ref_count_map = {
        int(element_id): int(count or 0)
        for element_id, count in db.execute(
            select(PageObjectRef.page_element_id, func.count())
            .where(PageObjectRef.page_element_id.in_(element_ids))
            .group_by(PageObjectRef.page_element_id)
        ).all()
    }
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
    project_code: str = "atp",
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
        db.execute(
            select(func.max(PageElementVersion.version_no)).where(PageElementVersion.page_element_id == element.id)
        ).scalar_one()
        or 0
    )
    latest_version_no = max(latest_version_no, int(element.version if element.version is not None else 1))
    reference_count = int(
        db.execute(select(func.count()).select_from(PageObjectRef).where(PageObjectRef.page_element_id == element.id)).scalar_one()
        or 0
    )
    return _serialize_page_element(
        element,
        latest_version_no=latest_version_no,
        reference_count=reference_count,
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
    normalized_element_code = _normalize_identifier(payload.element_code, field_name="element_code")
    existing = db.execute(
        select(PageElement).where(
            PageElement.page_object_id == page_object.id,
            PageElement.element_code == normalized_element_code,
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"page element already exists: {normalized_element_code}",
        )
    item = PageElement(
        page_object_id=page_object.id,
        element_code=normalized_element_code,
        element_name=str(payload.element_name).strip(),
        locator_type=_normalize_locator_type(payload.locator_type),
        locator_value=str(payload.locator_value).strip(),
        backup_locator=str(payload.backup_locator or "").strip(),
        health_status=_normalize_binary_health_status(payload.health_status),
        version=1,
        role=str(payload.role or "").strip(),
        status=_normalize_page_element_status(payload.status),
        is_primary=bool(payload.is_primary),
        owner=str(payload.owner or "").strip(),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    version_no = _snapshot_element(
        db,
        element=item,
        changed_by=payload.changed_by,
        change_summary=payload.change_summary,
    )
    _sync_page_object_metrics(db, page_object_id=page_object.id)
    db.refresh(item)
    return _serialize_page_element(item, latest_version_no=version_no, reference_count=0)


def update_page_element(
    db: Session,
    *,
    page_code: str,
    element_code: str,
    project_code: str,
    client: str,
    payload: PageElementUpdate,
) -> dict[str, Any]:
    normalized_project_code = _normalize_project_code(project_code)
    test_project_service.ensure_project_active_for_write(db, normalized_project_code)
    page_object = _page_object_or_404(
        db,
        project_code=normalized_project_code,
        client=normalize_client_code(client),
        page_code=_normalize_identifier(page_code, field_name="page_code", max_length=40),
    )
    element = _page_element_or_404(
        db,
        page_object_id=page_object.id,
        element_code=_normalize_identifier(element_code, field_name="element_code"),
    )
    changed = False
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
        db.add(element)
        db.commit()
        db.refresh(element)
        version_no = _snapshot_element(
            db,
            element=element,
            changed_by=payload.changed_by,
            change_summary=payload.change_summary,
        )
        db.refresh(element)
        _sync_page_object_metrics(db, page_object_id=page_object.id)
    else:
        version_no = max(
            int(element.version if element.version is not None else 1),
            db.execute(
                select(func.max(PageElementVersion.version_no)).where(PageElementVersion.page_element_id == element.id)
            ).scalar_one()
            or 0,
        )

    reference_count = int(
        db.execute(select(func.count()).select_from(PageObjectRef).where(PageObjectRef.page_element_id == element.id)).scalar_one()
        or 0
    )
    return _serialize_page_element(element, latest_version_no=version_no, reference_count=reference_count)


def delete_page_element(
    db: Session,
    *,
    page_code: str,
    element_code: str,
    project_code: str,
    client: str,
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
    db.execute(delete(PageElementVersion).where(PageElementVersion.page_element_id == element.id))
    db.execute(delete(PageObjectRef).where(PageObjectRef.page_element_id == element.id))
    db.execute(delete(PageElementHealthCheck).where(PageElementHealthCheck.page_element_id == element.id))
    db.delete(element)
    db.commit()
    _sync_page_object_metrics(db, page_object_id=page_object.id)
    remaining_element_count = int(
        db.execute(
            select(func.count()).select_from(PageElement).where(PageElement.page_object_id == page_object.id)
        ).scalar_one()
        or 0
    )
    cleanup_result = (
        _cleanup_page_recorder_assets(
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


def create_page_element_version(
    db: Session,
    *,
    page_code: str,
    element_code: str,
    project_code: str,
    client: str,
    payload: PageElementVersionCreate,
) -> dict[str, Any]:
    normalized_project_code = _normalize_project_code(project_code)
    test_project_service.ensure_project_active_for_write(db, normalized_project_code)
    page_object = _page_object_or_404(
        db,
        project_code=normalized_project_code,
        client=normalize_client_code(client),
        page_code=_normalize_identifier(page_code, field_name="page_code", max_length=40),
    )
    element = _page_element_or_404(
        db,
        page_object_id=page_object.id,
        element_code=_normalize_identifier(element_code, field_name="element_code"),
    )
    version_no = _snapshot_element(
        db,
        element=element,
        changed_by=payload.changed_by,
        change_summary=payload.change_summary,
    )
    version = db.execute(
        select(PageElementVersion).where(
            PageElementVersion.page_element_id == element.id,
            PageElementVersion.version_no == version_no,
        )
    ).scalar_one()
    return _serialize_element_version(version)


def list_page_element_versions(
    db: Session,
    *,
    page_code: str,
    element_code: str,
    project_code: str,
    client: str,
) -> list[dict[str, Any]]:
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
    rows = list(
        db.execute(
            select(PageElementVersion)
            .where(PageElementVersion.page_element_id == element.id)
            .order_by(PageElementVersion.version_no.desc(), PageElementVersion.id.desc())
        ).scalars().all()
    )
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
    normalized_project_code = _normalize_project_code(project_code)
    test_project_service.ensure_project_active_for_write(db, normalized_project_code)
    page_object = _page_object_or_404(
        db,
        project_code=normalized_project_code,
        client=normalize_client_code(client),
        page_code=_normalize_identifier(page_code, field_name="page_code", max_length=40),
    )
    element = _page_element_or_404(
        db,
        page_object_id=page_object.id,
        element_code=_normalize_identifier(element_code, field_name="element_code"),
    )
    normalized_reference_type = _normalize_reference_type(payload.reference_type)
    normalized_reference_key = str(payload.reference_key or "").strip()
    existing = db.execute(
        select(PageObjectRef).where(
            PageObjectRef.page_element_id == element.id,
            PageObjectRef.reference_type == normalized_reference_type,
            PageObjectRef.reference_key == normalized_reference_key,
        )
    ).scalar_one_or_none()
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
    rows = list(
        db.execute(
            select(PageObjectRef)
            .where(PageObjectRef.page_element_id == element.id)
            .order_by(PageObjectRef.created_at.desc(), PageObjectRef.id.desc())
        ).scalars().all()
    )
    return [_serialize_ref(item) for item in rows]
