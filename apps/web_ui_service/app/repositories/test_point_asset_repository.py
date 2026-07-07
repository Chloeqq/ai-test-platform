"""Repository for TestPointAsset (bundle 粒度的测试点资产)。"""
from __future__ import annotations

from typing import Any

from sqlalchemy import delete as sa_delete, select

from app.models.test_point_asset import TestPointAsset
from .base import BaseRepository


class TestPointAssetRepository(BaseRepository):
    """测试点资产的 DB 读写（唯一可写 db.execute(select(...)) 的地方）。"""

    def get(self, project_code: str, asset_id: str) -> TestPointAsset | None:
        return self.db.execute(
            select(TestPointAsset).where(
                TestPointAsset.project_code == project_code,
                TestPointAsset.asset_id == asset_id,
            )
        ).scalar_one_or_none()

    def list_by_project(
        self,
        project_code: str,
        *,
        page_code: str | None = None,
        source_type: str | None = None,
        status: str | None = None,
        keyword: str | None = None,
        offset: int = 0,
        limit: int = 500,
    ) -> tuple[list[TestPointAsset], int]:
        stmt = select(TestPointAsset).where(TestPointAsset.project_code == project_code)
        if page_code:
            stmt = stmt.where(TestPointAsset.page_code == page_code)
        if source_type:
            stmt = stmt.where(TestPointAsset.source_type == source_type)
        if status:
            stmt = stmt.where(TestPointAsset.status == status)
        if keyword:
            stmt = stmt.where(TestPointAsset.title.ilike(f"%{keyword}%"))
        # count
        from sqlalchemy import func
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = self.db.execute(count_stmt).scalar_one() or 0
        # paginated results
        stmt = stmt.order_by(TestPointAsset.updated_at.desc()).offset(offset).limit(limit)
        rows = list(self.db.execute(stmt).scalars().all())
        return rows, total

    def upsert(
        self,
        *,
        project_code: str,
        asset_id: str,
        page_code: str = "common",
        title: str = "",
        priority: str = "P1",
        source_type: str = "",
        status: str = "active",
        point_count: int = 0,
        intent_count: int = 0,
        requires_review: bool = False,
        version: int = 1,
        raw_payload: dict[str, Any] | None = None,
    ) -> TestPointAsset:
        existing = self.get(project_code, asset_id)
        if existing is not None:
            existing.page_code = page_code or existing.page_code
            existing.title = title
            existing.priority = priority or existing.priority
            existing.source_type = source_type
            existing.status = status or existing.status
            existing.point_count = point_count
            existing.intent_count = intent_count
            existing.requires_review = requires_review
            existing.version = version
            if raw_payload is not None:
                existing.raw_payload = raw_payload
            self.db.flush()
            return existing
        asset = TestPointAsset(
            project_code=project_code,
            asset_id=asset_id,
            page_code=page_code or "common",
            title=title,
            priority=priority or "P1",
            source_type=source_type,
            status=status or "active",
            point_count=point_count,
            intent_count=intent_count,
            requires_review=requires_review,
            version=version,
            raw_payload=raw_payload if raw_payload is not None else {},
        )
        self.db.add(asset)
        self.db.flush()
        return asset

    def delete(self, project_code: str, asset_id: str) -> bool:
        result = self.db.execute(
            sa_delete(TestPointAsset).where(
                TestPointAsset.project_code == project_code,
                TestPointAsset.asset_id == asset_id,
            )
        )
        return bool(result.rowcount)
