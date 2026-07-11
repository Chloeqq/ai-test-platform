"""Repository for RequirementDocument（唯一可写 db.execute(select(...)) 的地方）。"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from app.models.requirement_document import RequirementDocument

from .base import BaseRepository


class RequirementDocumentRepository(BaseRepository):
    """需求文档记录的 DB 读写。所有字段由调用方显式传入，不注入任何默认业务值。"""

    def create(
        self,
        *,
        project_code: str,
        filename: str,
        source_type: str,
        object_key: str,
        file_size: int,
        parse_status: str,
        created_by: str | None = None,
    ) -> RequirementDocument:
        doc = RequirementDocument(
            project_code=project_code,
            filename=filename,
            source_type=source_type,
            object_key=object_key,
            file_size=file_size,
            parse_status=parse_status,
            created_by=created_by,
        )
        self.db.add(doc)
        self.db.flush()
        return doc

    def get_by_id(self, doc_id: int) -> RequirementDocument | None:
        return self.db.execute(
            select(RequirementDocument).where(RequirementDocument.id == doc_id)
        ).scalar_one_or_none()

    def list_by_project(self, project_code: str) -> list[RequirementDocument]:
        return list(
            self.db.execute(
                select(RequirementDocument)
                .where(
                    RequirementDocument.project_code == project_code,
                    RequirementDocument.is_deleted.is_(False),
                )
                .order_by(RequirementDocument.created_at.desc())
            )
            .scalars()
            .all()
        )

    def update_parse_result(
        self,
        doc_id: int,
        parse_status: str,
        parse_error: str | None = None,
    ) -> RequirementDocument | None:
        doc = self.get_by_id(doc_id)
        if doc is None:
            return None
        doc.parse_status = parse_status
        doc.parse_error = parse_error
        self.db.flush()
        return doc