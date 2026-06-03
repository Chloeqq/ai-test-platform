"""Repository for TestPoint model."""
from __future__ import annotations

from sqlalchemy import select

from app.models.test_point import TestPoint
from .base import BaseRepository


class TestPointRepository(BaseRepository):
    """Repository for TestPoint CRUD operations."""

    def get_by_point_id(
        self, project_code: str, page_code: str, point_id: str
    ) -> TestPoint | None:
        return self.db.execute(
            select(TestPoint).where(
                TestPoint.project_code == project_code,
                TestPoint.page_code == page_code,
                TestPoint.point_id == point_id,
            )
        ).scalar_one_or_none()
