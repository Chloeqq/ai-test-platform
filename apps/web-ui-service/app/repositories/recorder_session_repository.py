"""Recorder Session 扩展 Repository——分页、最新录制时间等。"""
from __future__ import annotations

from sqlalchemy import func, select

from app.models.page_object_recorder_models import (
    PageObjectRecorderSession,
)

from .base import BaseRepository


class RecorderSessionRepository(BaseRepository):
    """录制器 Session 的扩展查询（分页、聚合）。"""

    __test__ = False

    def list_sessions_paginated(
        self,
        *,
        project_code: str,
        client: str,
        session_ids: list[str] | None = None,
        page_code: str | None = None,
        status: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> list[PageObjectRecorderSession]:
        stmt = select(PageObjectRecorderSession)
        conditions = [
            PageObjectRecorderSession.project_code == project_code,
            PageObjectRecorderSession.client == client,
        ]
        if session_ids:
            conditions.append(
                PageObjectRecorderSession.session_id.in_(session_ids)
            )
        if page_code:
            conditions.append(
                PageObjectRecorderSession.page_code == page_code
            )
        if status:
            conditions.append(
                PageObjectRecorderSession.status == status
            )
        stmt = stmt.where(*conditions)
        stmt = stmt.order_by(
            PageObjectRecorderSession.started_at.desc(),
            PageObjectRecorderSession.id.desc(),
        ).offset(offset).limit(limit)
        return list(self.db.execute(stmt).scalars().all())

    def get_latest_recorded_at_by_page(
        self,
        *,
        project_code: str | None = None,
        client: str | None = None,
        page_codes: list[str] | None = None,
    ) -> dict[tuple[str, str, str], object]:
        stmt = select(
            PageObjectRecorderSession.project_code,
            PageObjectRecorderSession.client,
            PageObjectRecorderSession.page_code,
            func.max(PageObjectRecorderSession.stopped_at),
        )
        if page_codes:
            stmt = stmt.where(
                PageObjectRecorderSession.page_code.in_(page_codes)
            )
        if project_code:
            stmt = stmt.where(
                PageObjectRecorderSession.project_code == project_code
            )
        if client:
            stmt = stmt.where(
                PageObjectRecorderSession.client == client
            )
        stmt = stmt.group_by(
            PageObjectRecorderSession.project_code,
            PageObjectRecorderSession.client,
            PageObjectRecorderSession.page_code,
        )
        return {
            (str(p), str(c), str(pc)): latest
            for p, c, pc, latest in self.db.execute(stmt).all()
        }

    def list_sessions_by_page_identity(
        self, project_code: str, client: str, page_code: str
    ) -> list[PageObjectRecorderSession]:
        return list(
            self.db.execute(
                select(PageObjectRecorderSession).where(
                    PageObjectRecorderSession.project_code == project_code,
                    PageObjectRecorderSession.client == client,
                    PageObjectRecorderSession.page_code == page_code,
                )
            ).scalars().all()
        )
