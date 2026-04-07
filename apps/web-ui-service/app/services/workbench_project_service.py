from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from app.services import test_project_service

DEFAULT_PROJECT_CODE = "atp"


def list_project_codes(db: Session, *, state_root: Path | None = None) -> list[str]:
    items: list[str] = []
    seen: set[str] = set()

    def add(code: str) -> None:
        normalized = str(code or "").strip().lower()
        if not normalized or normalized in seen:
            return
        seen.add(normalized)
        items.append(normalized)

    add(DEFAULT_PROJECT_CODE)
    for project in test_project_service.list_projects(db):
        add(project.project_code)

    if state_root and state_root.exists():
        for entry in sorted(state_root.iterdir()):
            if entry.is_dir():
                add(entry.name)

    if not items:
        add(DEFAULT_PROJECT_CODE)
    return items
