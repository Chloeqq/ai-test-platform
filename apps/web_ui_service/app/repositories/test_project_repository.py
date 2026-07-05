"""TestProject Repository。"""
from __future__ import annotations

from typing import Any

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

    def list_by_codes(
        self, project_codes: list[str]
    ) -> list[tuple[str, str]]:
        """返回 [(project_code, status), ...]"""
        if not project_codes:
            return []
        return list(
            self.db.execute(
                select(TestProject.project_code, TestProject.status).where(
                    TestProject.project_code.in_(project_codes)
                )
            ).all()
        )

    def count_test_cases_by_project(self, project_code: str) -> int:
        # 延迟导入避免循环依赖
        from app.models.test_case import TestCase  # noqa: E402

        return self.db.execute(
            select(func.count()).select_from(TestCase).where(
                TestCase.project_code == project_code
            )
        ).scalar_one() or 0
