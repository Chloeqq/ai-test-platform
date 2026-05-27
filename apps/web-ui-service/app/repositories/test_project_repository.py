"""TestProject Repository。"""
from __future__ import annotations

from sqlalchemy import func, select

from app.models.test_project import TestProject

from .base import BaseRepository


class TestProjectRepository(BaseRepository):
    __test__ = False

    def get_by_code(self, project_code: str) -> TestProject | None:
        return self.db.execute(
            select(TestProject).where(TestProject.project_code == project_code)
        ).scalar_one_or_none()

    def list_all(self) -> list[TestProject]:
        return list(
            self.db.execute(
                select(TestProject).order_by(TestProject.status, TestProject.project_code)
            ).scalars().all()
        )

    def count_all(self) -> int:
        return self.db.execute(
            select(func.count()).select_from(TestProject)
        ).scalar_one()
