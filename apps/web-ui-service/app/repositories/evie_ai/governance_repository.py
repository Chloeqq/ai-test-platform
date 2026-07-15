"""EvieAi 不可变审核和审计历史的追加与查询。"""

from __future__ import annotations

from sqlalchemy import func, select

from app.models.evie_ai import (
    TestAsset,
    TestAssetAuditEvent,
    TestAssetReviewRecord,
    TestAssetVersion,
)
from app.repositories.base import BaseRepository
from app.repositories.evie_ai.errors import RepositoryDataIntegrityError
from app.repositories.evie_ai.types import RepositoryPage


class TestAssetReviewRepository(BaseRepository):
    """只提供审核记录追加和只读访问，不提供更新或删除。"""

    def add(self, record: TestAssetReviewRecord) -> TestAssetReviewRecord:
        version_owner = self.db.execute(
            select(TestAssetVersion.test_asset_pk).where(
                TestAssetVersion.id == record.test_asset_version_pk
            )
        ).scalar_one_or_none()
        if version_owner != record.test_asset_pk:
            raise RepositoryDataIntegrityError(
                message="review version does not belong to test asset",
                entity_id=record.test_asset_review_record_id,
            )
        self.db.add(record)
        self.db.flush()
        return record

    def get_by_review_record_id(
        self,
        *,
        project_code: str,
        review_record_id: str,
        include_deleted: bool = False,
    ) -> TestAssetReviewRecord | None:
        statement = (
            select(TestAssetReviewRecord)
            .join(TestAsset, TestAsset.id == TestAssetReviewRecord.test_asset_pk)
            .where(
                TestAsset.project_code == project_code,
                TestAssetReviewRecord.test_asset_review_record_id == review_record_id,
            )
        )
        if not include_deleted:
            statement = statement.where(TestAsset.deleted_at.is_(None))
        return self.db.execute(statement).scalar_one_or_none()

    def get_latest(
        self,
        test_asset_pk: int,
    ) -> TestAssetReviewRecord | None:
        return self.db.execute(
            select(TestAssetReviewRecord)
            .where(TestAssetReviewRecord.test_asset_pk == test_asset_pk)
            .order_by(
                TestAssetReviewRecord.reviewed_at.desc(),
                TestAssetReviewRecord.id.desc(),
            )
            .limit(1)
        ).scalar_one_or_none()

    def list_by_asset(
        self,
        test_asset_pk: int,
        *,
        page: int,
        page_size: int,
    ) -> RepositoryPage[TestAssetReviewRecord]:
        _validate_page(page=page, page_size=page_size)
        predicate = TestAssetReviewRecord.test_asset_pk == test_asset_pk
        total = self.db.scalar(
            select(func.count()).select_from(TestAssetReviewRecord).where(predicate)
        )
        items = list(
            self.db.execute(
                select(TestAssetReviewRecord)
                .where(predicate)
                .order_by(
                    TestAssetReviewRecord.reviewed_at.desc(),
                    TestAssetReviewRecord.id.desc(),
                )
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
            .scalars()
            .all()
        )
        return RepositoryPage(
            items=items,
            page=page,
            page_size=page_size,
            total=int(total or 0),
        )


class TestAssetAuditRepository(BaseRepository):
    """只提供脱敏审计事件追加和只读访问。"""

    def add(self, event: TestAssetAuditEvent) -> TestAssetAuditEvent:
        self.db.add(event)
        self.db.flush()
        return event

    def list_by_asset(
        self,
        test_asset_pk: int,
        *,
        page: int,
        page_size: int,
    ) -> RepositoryPage[TestAssetAuditEvent]:
        _validate_page(page=page, page_size=page_size)
        predicate = TestAssetAuditEvent.test_asset_pk == test_asset_pk
        total = self.db.scalar(
            select(func.count()).select_from(TestAssetAuditEvent).where(predicate)
        )
        items = list(
            self.db.execute(
                select(TestAssetAuditEvent)
                .where(predicate)
                .order_by(
                    TestAssetAuditEvent.created_at.desc(),
                    TestAssetAuditEvent.id.desc(),
                )
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
            .scalars()
            .all()
        )
        return RepositoryPage(
            items=items,
            page=page,
            page_size=page_size,
            total=int(total or 0),
        )


def _validate_page(*, page: int, page_size: int) -> None:
    if page < 1:
        raise ValueError("page must be at least 1")
    if page_size < 1 or page_size > 100:
        raise ValueError("page_size must be between 1 and 100")
