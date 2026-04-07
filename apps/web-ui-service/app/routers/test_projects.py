from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.test_project import TestProject
from app.schemas.test_project import TestProjectCreate, TestProjectUpdate
from app.services import test_project_service

router = APIRouter(prefix="/api/test-projects", tags=["test-projects"])


def _serialize_project(item: TestProject) -> dict[str, object]:
    return {
        "id": item.id,
        "project_code": item.project_code,
        "project_name": item.project_name,
        "description": item.description,
        "status": item.status,
        "created_by": item.created_by,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


@router.get("")
def list_test_projects(db: Session = Depends(get_db)) -> dict[str, object]:
    items = test_project_service.list_projects(db)
    return {"items": [_serialize_project(item) for item in items]}


@router.post("", status_code=status.HTTP_201_CREATED)
def create_test_project(payload: TestProjectCreate, db: Session = Depends(get_db)) -> dict[str, object]:
    item = test_project_service.create_project(db, payload)
    return {"item": _serialize_project(item)}


@router.put("/{project_code}")
def update_test_project(
    project_code: str,
    payload: TestProjectUpdate,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    item = test_project_service.update_project(db, project_code, payload)
    return {"item": _serialize_project(item)}


@router.delete("/{project_code}")
def delete_test_project(project_code: str, db: Session = Depends(get_db)) -> dict[str, object]:
    deleted_project_code = test_project_service.delete_project(db, project_code)
    return {"deleted": True, "project_code": deleted_project_code}
