"""Recorder Repository——录制器相关的数据访问。

覆盖模型：PageObjectRecorderSession, PageObjectCandidateElement, PageObjectCandidateGroup。
"""
from __future__ import annotations

from sqlalchemy import delete, func, select

from app.models.page_object_recorder_models import (
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

    # ---- Candidate Elements (extended) ----

    def list_candidates_by_group(
        self, project_code: str, client: str, page_code: str, group_key: str
    ) -> list[PageObjectCandidateElement]:
        return list(
            self.db.execute(
                select(PageObjectCandidateElement)
                .where(
                    PageObjectCandidateElement.project_code == project_code,
                    PageObjectCandidateElement.client == client,
                    PageObjectCandidateElement.page_code == page_code,
                    PageObjectCandidateElement.group_key == group_key,
                )
                .order_by(
                    PageObjectCandidateElement.quality_score.desc(),
                    PageObjectCandidateElement.id.desc(),
                )
            ).scalars().all()
        )

    def count_candidates_by_group(
        self, project_code: str, client: str, page_code: str, group_key: str
    ) -> int:
        return self.db.execute(
            select(func.count()).select_from(PageObjectCandidateElement).where(
                PageObjectCandidateElement.project_code == project_code,
                PageObjectCandidateElement.client == client,
                PageObjectCandidateElement.page_code == page_code,
                PageObjectCandidateElement.group_key == group_key,
            )
        ).scalar_one() or 0

    def list_candidates_by_keys(
        self,
        project_code: str,
        client: str,
        page_code: str,
        candidate_keys: list[str],
    ) -> list[PageObjectCandidateElement]:
        if not candidate_keys:
            return []
        return list(
            self.db.execute(
                select(PageObjectCandidateElement).where(
                    PageObjectCandidateElement.project_code == project_code,
                    PageObjectCandidateElement.client == client,
                    PageObjectCandidateElement.page_code == page_code,
                    PageObjectCandidateElement.candidate_key.in_(candidate_keys),
                )
            ).scalars().all()
        )

    def get_candidate_by_key(
        self, project_code: str, client: str, page_code: str, candidate_key: str
    ) -> PageObjectCandidateElement | None:
        return self.db.execute(
            select(PageObjectCandidateElement).where(
                PageObjectCandidateElement.project_code == project_code,
                PageObjectCandidateElement.client == client,
                PageObjectCandidateElement.page_code == page_code,
                PageObjectCandidateElement.candidate_key == candidate_key,
            )
        ).scalar_one_or_none()

    def delete_candidates_by_ids(self, candidate_ids: list[int]) -> None:
        if not candidate_ids:
            return
        self.db.execute(
            delete(PageObjectCandidateElement).where(
                PageObjectCandidateElement.id.in_(candidate_ids)
            )
        )

    def delete_candidates_by_group_keys(
        self,
        project_code: str,
        client: str,
        page_code: str,
        group_keys: list[str],
    ) -> None:
        if not group_keys:
            return
        self.db.execute(
            delete(PageObjectCandidateElement).where(
                PageObjectCandidateElement.project_code == project_code,
                PageObjectCandidateElement.client == client,
                PageObjectCandidateElement.page_code == page_code,
                PageObjectCandidateElement.group_key.in_(group_keys),
            )
        )

    def delete_candidates_by_page_identity(
        self, project_code: str, client: str, page_code: str
    ) -> None:
        self.db.execute(
            delete(PageObjectCandidateElement).where(
                PageObjectCandidateElement.project_code == project_code,
                PageObjectCandidateElement.client == client,
                PageObjectCandidateElement.page_code == page_code,
            )
        )

    # ---- Candidate Groups (extended) ----

    def list_group_keys_by_page_identity(
        self,
        project_code: str,
        client: str,
        page_code: str,
        group_keys: list[str] | None = None,
    ) -> list[str]:
        stmt = select(PageObjectCandidateGroup.group_key).where(
            PageObjectCandidateGroup.project_code == project_code,
            PageObjectCandidateGroup.client == client,
            PageObjectCandidateGroup.page_code == page_code,
        )
        if group_keys:
            stmt = stmt.where(
                PageObjectCandidateGroup.group_key.in_(group_keys)
            )
        return [
            str(row) for row in self.db.execute(stmt).scalars().all() if row
        ]

    def delete_groups_by_keys(
        self,
        project_code: str,
        client: str,
        page_code: str,
        group_keys: list[str],
    ) -> None:
        if not group_keys:
            return
        self.db.execute(
            delete(PageObjectCandidateGroup).where(
                PageObjectCandidateGroup.project_code == project_code,
                PageObjectCandidateGroup.client == client,
                PageObjectCandidateGroup.page_code == page_code,
                PageObjectCandidateGroup.group_key.in_(group_keys),
            )
        )

    def delete_groups_by_page_identity(
        self, project_code: str, client: str, page_code: str
    ) -> None:
        self.db.execute(
            delete(PageObjectCandidateGroup).where(
                PageObjectCandidateGroup.project_code == project_code,
                PageObjectCandidateGroup.client == client,
                PageObjectCandidateGroup.page_code == page_code,
            )
        )

    def count_pending_candidate_groups(
        self, project_code: str, client: str, page_code: str
    ) -> int:
        return self.db.execute(
            select(func.count()).select_from(PageObjectCandidateGroup).where(
                PageObjectCandidateGroup.project_code == project_code,
                PageObjectCandidateGroup.client == client,
                PageObjectCandidateGroup.page_code == page_code,
                PageObjectCandidateGroup.promotion_status == "pending",
            )
        ).scalar_one() or 0

    def list_candidate_groups_filtered(
        self,
        *,
        project_code: str,
        client: str,
        page_code: str,
        promotion_status: str | None = None,
        quality_tier: str | None = None,
        session_id: str | None = None,
    ) -> list[PageObjectCandidateGroup]:
        stmt = select(PageObjectCandidateGroup).where(
            PageObjectCandidateGroup.project_code == project_code,
            PageObjectCandidateGroup.client == client,
            PageObjectCandidateGroup.page_code == page_code,
        )
        if promotion_status:
            stmt = stmt.where(
                PageObjectCandidateGroup.promotion_status == promotion_status
            )
        if quality_tier:
            stmt = stmt.where(
                PageObjectCandidateGroup.quality_tier == quality_tier
            )
        if session_id:
            stmt = stmt.where(
                PageObjectCandidateGroup.session_id == session_id
            )
        stmt = stmt.order_by(
            PageObjectCandidateGroup.updated_at.desc(),
            PageObjectCandidateGroup.id.desc(),
        )
        return list(self.db.execute(stmt).scalars().all())

    def list_candidates_filtered(
        self,
        *,
        project_code: str,
        client: str,
        page_code: str,
        group_key: str | None = None,
        session_id: str | None = None,
        status: str | None = None,
    ) -> list[PageObjectCandidateElement]:
        stmt = select(PageObjectCandidateElement).where(
            PageObjectCandidateElement.project_code == project_code,
            PageObjectCandidateElement.client == client,
            PageObjectCandidateElement.page_code == page_code,
        )
        if group_key:
            stmt = stmt.where(
                PageObjectCandidateElement.group_key == group_key
            )
        if session_id:
            stmt = stmt.where(
                PageObjectCandidateElement.session_id == session_id
            )
        if status:
            stmt = stmt.where(
                PageObjectCandidateElement.status == status
            )
        stmt = stmt.order_by(
            PageObjectCandidateElement.quality_score.desc(),
            PageObjectCandidateElement.id.desc(),
        )
        return list(self.db.execute(stmt).scalars().all())

