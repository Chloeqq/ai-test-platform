"""Recorder Repository——录制器相关的数据访问。

覆盖模型：PageObjectRecorderSession, PageObjectCandidateElement, PageObjectCandidateGroup。
"""
from __future__ import annotations

from sqlalchemy import delete, func, select

from app.models.page_object import (
    PageObjectCandidateElement,
    PageObjectCandidateGroup,
    PageObjectRecorderSession,
)

from .base import BaseRepository


class RecorderRepository(BaseRepository):
    __test__ = False

    # ---- Sessions ----

    def get_session_by_id(self, session_id: str) -> PageObjectRecorderSession | None:
        return self.db.execute(
            select(PageObjectRecorderSession).where(
                PageObjectRecorderSession.session_id == session_id
            )
        ).scalar_one_or_none()

    def list_sessions(
        self,
        *,
        project_code: str | None = None,
        client: str | None = None,
        page_code: str | None = None,
        status: str | None = None,
    ) -> list[PageObjectRecorderSession]:
        stmt = select(PageObjectRecorderSession)
        if project_code:
            stmt = stmt.where(PageObjectRecorderSession.project_code == project_code)
        if client:
            stmt = stmt.where(PageObjectRecorderSession.client == client)
        if page_code:
            stmt = stmt.where(PageObjectRecorderSession.page_code == page_code)
        if status:
            stmt = stmt.where(PageObjectRecorderSession.status == status)
        stmt = stmt.order_by(PageObjectRecorderSession.started_at.desc())
        return list(self.db.execute(stmt).scalars().all())

    def count_sessions(
        self,
        *,
        project_code: str | None = None,
        client: str | None = None,
        page_code: str | None = None,
        status: str | None = None,
    ) -> int:
        stmt = select(func.count()).select_from(PageObjectRecorderSession)
        if project_code:
            stmt = stmt.where(PageObjectRecorderSession.project_code == project_code)
        if client:
            stmt = stmt.where(PageObjectRecorderSession.client == client)
        if page_code:
            stmt = stmt.where(PageObjectRecorderSession.page_code == page_code)
        if status:
            stmt = stmt.where(PageObjectRecorderSession.status == status)
        return self.db.execute(stmt).scalar_one()

    def delete_sessions(self, project_code: str, client: str, session_ids: list[str]) -> None:
        if not session_ids:
            return
        self.db.execute(
            delete(PageObjectRecorderSession).where(
                PageObjectRecorderSession.project_code == project_code,
                PageObjectRecorderSession.client == client,
                PageObjectRecorderSession.session_id.in_(session_ids),
            )
        )

    def list_all_session_ids(self) -> list[str]:
        rows = self.db.execute(
            select(PageObjectRecorderSession.session_id)
        ).scalars().all()
        return [str(row) for row in rows if row]

    # ---- Candidate Elements ----

    def list_candidates_by_session(self, session_id: str) -> list[PageObjectCandidateElement]:
        return list(
            self.db.execute(
                select(PageObjectCandidateElement).where(
                    PageObjectCandidateElement.session_id == session_id
                )
            ).scalars().all()
        )

    def list_candidates_by_sessions(
        self, session_ids: list[str]
    ) -> list[PageObjectCandidateElement]:
        if not session_ids:
            return []
        return list(
            self.db.execute(
                select(PageObjectCandidateElement).where(
                    PageObjectCandidateElement.session_id.in_(session_ids)
                )
            ).scalars().all()
        )

    def delete_candidates_by_sessions(
        self, project_code: str, client: str, session_ids: list[str]
    ) -> None:
        if not session_ids:
            return
        self.db.execute(
            delete(PageObjectCandidateElement).where(
                PageObjectCandidateElement.project_code == project_code,
                PageObjectCandidateElement.client == client,
                PageObjectCandidateElement.session_id.in_(session_ids),
            )
        )

    def count_candidates_remaining(self, project_code: str, client: str) -> int:
        return self.db.execute(
            select(func.count()).select_from(PageObjectCandidateElement).where(
                PageObjectCandidateElement.project_code == project_code,
                PageObjectCandidateElement.client == client,
            )
        ).scalar_one()

    # ---- Candidate Groups ----

    def get_group(
        self, project_code: str, client: str, page_code: str, group_key: str
    ) -> PageObjectCandidateGroup | None:
        return self.db.execute(
            select(PageObjectCandidateGroup).where(
                PageObjectCandidateGroup.project_code == project_code,
                PageObjectCandidateGroup.client == client,
                PageObjectCandidateGroup.page_code == page_code,
                PageObjectCandidateGroup.group_key == group_key,
            )
        ).scalar_one_or_none()

    def delete_empty_groups(
        self, project_code: str, client: str, page_code: str, group_key: str
    ) -> None:
        self.db.execute(
            delete(PageObjectCandidateGroup).where(
                PageObjectCandidateGroup.project_code == project_code,
                PageObjectCandidateGroup.client == client,
                PageObjectCandidateGroup.page_code == page_code,
                PageObjectCandidateGroup.group_key == group_key,
                PageObjectCandidateGroup.candidate_count == 0,
            )
        )
