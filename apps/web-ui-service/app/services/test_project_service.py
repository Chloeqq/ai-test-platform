from __future__ import annotations

import re
from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy import Select, func, inspect, select
from sqlalchemy.orm import Session

from app.models.test_case import TestCase
from app.models.test_project import TestProject
from app.models.workbench_state import (
    WorkbenchExecutionGateDecision,
    WorkbenchReviewDecision,
    WorkbenchRuntimeRun,
)
from app.schemas.test_project import TestProjectCreate, TestProjectUpdate
from app.services.test_case_bootstrap_service import ensure_project_seed
from app.services.workbench_state_store import TEST_POINTS_ROOT

DEFAULT_PROJECT_CODE = "atp"
PROJECT_STATUS_VALUES = {"active", "inactive"}


def _normalize_non_empty_text(value: str, *, field_name: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{field_name} cannot be empty",
        )
    return normalized

def _normalize_project_code(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "", str(value or "").strip()).lower()
    if len(normalized) < 2 or len(normalized) > 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="project_code must be 2-10 letters or digits",
        )
    return normalized


def _normalize_project_status(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized not in PROJECT_STATUS_VALUES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"status must be one of: {', '.join(sorted(PROJECT_STATUS_VALUES))}",
        )
    return normalized


def _get_project_or_404(db: Session, project_code: str) -> TestProject:
    project = db.execute(
        select(TestProject).where(TestProject.project_code == project_code)
    ).scalar_one_or_none()
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"project not found: {project_code}",
        )
    return project


def _count_test_cases(db: Session, project_code: str) -> int:
    return int(
        db.execute(
            select(func.count()).select_from(TestCase).where(TestCase.project_code == project_code)
        ).scalar_one()
        or 0
    )


def _table_exists(db: Session, table_name: str) -> bool:
    return bool(inspect(db.get_bind()).has_table(table_name))


def _count_project_rows_if_table_exists(
    db: Session,
    *,
    table_name: str,
    stmt: Select[tuple[int]],
) -> int:
    if not _table_exists(db, table_name):
        return 0
    return int(db.execute(stmt).scalar_one() or 0)


def _count_workbench_state_refs(db: Session, project_code: str) -> int:
    runtime_count = _count_project_rows_if_table_exists(
        db,
        table_name=WorkbenchRuntimeRun.__tablename__,
        stmt=select(func.count()).select_from(WorkbenchRuntimeRun).where(WorkbenchRuntimeRun.project == project_code),
    )
    review_count = _count_project_rows_if_table_exists(
        db,
        table_name=WorkbenchReviewDecision.__tablename__,
        stmt=select(func.count()).select_from(WorkbenchReviewDecision).where(WorkbenchReviewDecision.project == project_code),
    )
    gate_count = _count_project_rows_if_table_exists(
        db,
        table_name=WorkbenchExecutionGateDecision.__tablename__,
        stmt=select(func.count()).select_from(WorkbenchExecutionGateDecision).where(
            WorkbenchExecutionGateDecision.project == project_code
        ),
    )
    return runtime_count + review_count + gate_count


def _has_workbench_state_dir(project_code: str, *, state_root: Path | None = None) -> bool:
    root = state_root or TEST_POINTS_ROOT
    project_dir = root / project_code
    if not project_dir.exists():
        return False
    return any(project_dir.iterdir())


def list_projects(db: Session) -> list[TestProject]:
    ensure_project_seed(db)
    return list(
        db.execute(
            select(TestProject).order_by(TestProject.status.asc(), TestProject.project_code.asc())
        ).scalars().all()
    )


def create_project(db: Session, payload: TestProjectCreate) -> TestProject:
    ensure_project_seed(db)
    project_code = _normalize_project_code(payload.project_code)
    existing = db.execute(
        select(TestProject).where(TestProject.project_code == project_code)
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"project already exists: {project_code}",
        )
    project = TestProject(
        project_code=project_code,
        project_name=payload.project_name.strip(),
        description=payload.description.strip(),
        created_by=payload.created_by.strip() or "admin",
        status="active",
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def update_project(db: Session, project_code: str, payload: TestProjectUpdate) -> TestProject:
    ensure_project_seed(db)
    normalized_project_code = _normalize_project_code(project_code)
    project = _get_project_or_404(db, normalized_project_code)

    changed = False
    if payload.project_name is not None:
        next_name = _normalize_non_empty_text(payload.project_name, field_name="project_name")
        if project.project_name != next_name:
            project.project_name = next_name
            changed = True

    if payload.description is not None:
        next_description = str(payload.description or "").strip()
        if project.description != next_description:
            project.description = next_description
            changed = True

    if payload.status is not None:
        next_status = _normalize_project_status(payload.status)
        if project.status != next_status:
            project.status = next_status
            changed = True

    if not changed:
        # Keep update idempotent for UI "save again" behavior.
        return project

    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def delete_project(db: Session, project_code: str, *, state_root: Path | None = None) -> str:
    ensure_project_seed(db)
    normalized_project_code = _normalize_project_code(project_code)
    if normalized_project_code == DEFAULT_PROJECT_CODE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"default project cannot be deleted: {DEFAULT_PROJECT_CODE}",
        )

    project = _get_project_or_404(db, normalized_project_code)

    case_count = _count_test_cases(db, normalized_project_code)
    if case_count > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"project is referenced by {case_count} test case(s): {normalized_project_code}",
        )

    workbench_ref_count = _count_workbench_state_refs(db, normalized_project_code)
    if workbench_ref_count > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"project is referenced by {workbench_ref_count} workbench record(s): {normalized_project_code}",
        )

    if _has_workbench_state_dir(normalized_project_code, state_root=state_root):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"project has workbench state files and cannot be deleted: {normalized_project_code}",
        )

    db.delete(project)
    db.commit()
    return normalized_project_code
