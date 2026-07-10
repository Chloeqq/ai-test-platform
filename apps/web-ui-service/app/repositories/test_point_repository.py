"""Repository for TestPoint model."""
from __future__ import annotations

from typing import Any

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

    def upsert_point(self, *, project_code: str, page_code: str, point_id: str,
                     point_name: str, scene_type: str = "", priority: str = "P1",
                     test_data_type: str = "", involved_elements: list[str] | None = None,
                     expect_result: str = "", source: str = "ai",
                     raw_payload: dict[str, Any] | None = None) -> TestPoint:
        existing = self.get_by_point_id(project_code, page_code, point_id)
        if existing is not None:
            existing.point_name = point_name or existing.point_name
            existing.scene_type = scene_type or existing.scene_type
            existing.priority = priority or existing.priority
            existing.test_data_type = test_data_type or existing.test_data_type
            existing.involved_elements = involved_elements or existing.involved_elements
            existing.expect_result = expect_result or existing.expect_result
            existing.source = source or existing.source
            if raw_payload is not None:
                existing.raw_payload = raw_payload
            self.db.flush()
            return existing
        point = TestPoint(
            project_code=project_code,
            page_code=page_code,
            point_id=point_id,
            point_name=point_name,
            scene_type=scene_type,
            priority=priority,
            test_data_type=test_data_type,
            involved_elements=involved_elements or [],
            expect_result=expect_result,
            source=source,
            raw_payload=raw_payload or {},
        )
        self.db.add(point)
        self.db.flush()
        return point
