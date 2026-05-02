from __future__ import annotations

import re
from pathlib import Path

from sqlalchemy.orm import Session

import app.schemas.test_project as test_project_schema
from app.services import test_project_service

DEFAULT_PROJECT_CODE = "mall"


def _normalize_project_code(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "", str(value or "").strip()).lower()
    if len(normalized) < 2 or len(normalized) > 10:
        raise ValueError("invalid project_code")
    return normalized


def list_project_items(db: Session, *, state_root: Path | None = None) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    seen: set[str] = set()

    def add(code: str, *, project_name: str = "", status: str = "active", source: str = "master") -> None:
        try:
            normalized = _normalize_project_code(code)
        except ValueError:
            return
        if normalized in seen:
            return
        seen.add(normalized)
        items.append(
            {
                "project_code": normalized,
                "project_name": str(project_name or normalized.upper()).strip() or normalized.upper(),
                "status": str(status or "active").strip().lower() or "active",
                "source": source,
            }
        )

    add(DEFAULT_PROJECT_CODE, project_name="Mall", status="active", source="default")
    for project in test_project_service.list_projects(db):
        add(
            project.project_code,
            project_name=project.project_name,
            status=project.status,
            source="master",
        )

    if state_root and state_root.exists():
        for entry in sorted(state_root.iterdir()):
            if entry.is_dir():
                add(entry.name, project_name=entry.name.upper(), status="active", source="legacy_state")

    if not items:
        add(DEFAULT_PROJECT_CODE, project_name="Mall", status="active", source="default")
    return items


def list_project_codes(db: Session, *, state_root: Path | None = None) -> list[str]:
    return [str(item["project_code"]) for item in list_project_items(db, state_root=state_root)]


def ensure_project_writable(db: Session, project_code: str) -> str:
    normalized_project_code = _normalize_project_code(project_code)
    existing_codes = {
        str(item["project_code"]).strip().lower()
        for item in list_project_items(db)
    }
    if normalized_project_code not in existing_codes:
        test_project_service.create_project(
            db,
            test_project_schema.TestProjectCreate(
                project_code=normalized_project_code,
                project_name=normalized_project_code.upper(),
                description="Auto-created from workbench save path",
                created_by="system",
            ),
        )
    test_project_service.ensure_project_active_for_write(db, normalized_project_code)
    return normalized_project_code
