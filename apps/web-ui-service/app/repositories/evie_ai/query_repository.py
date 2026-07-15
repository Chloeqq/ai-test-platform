"""EvieAi TestAsset 列表、详情和历史查询。"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import Text, cast, exists, func, select
from sqlalchemy.sql.elements import ColumnElement

from app.models.evie_ai import (
    Requirement,
    TestAsset,
    TestAssetRequirementSource,
    TestAssetReviewRecord,
    TestAssetSource,
    TestAssetVersion,
)
from app.repositories.base import BaseRepository
from app.repositories.evie_ai.errors import RepositoryDataIntegrityError
from app.repositories.evie_ai.governance_repository import TestAssetReviewRepository
from app.repositories.evie_ai.source_repository import (
    TestAssetSourceRecord,
    TestAssetSourceRepository,
)
from app.repositories.evie_ai.types import RepositoryPage


@dataclass(frozen=True, slots=True)
class TestAssetListFilters:
    project_code: str
    review_status: str | None = None
    conversion_status: str | None = None
    priority: str | None = None
    tags: tuple[str, ...] = field(default_factory=tuple)
    requirement_id: str | None = None
    source_type: str | None = None
    created_by: str | None = None
    created_from: datetime | None = None
    created_to: datetime | None = None
    keyword: str | None = None
    include_deleted: bool = False


@dataclass(frozen=True, slots=True)
class TestAssetListRecord:
    asset: TestAsset
    current_version: TestAssetVersion
    source_types: tuple[str, ...]
    latest_review: TestAssetReviewRecord | None


@dataclass(frozen=True, slots=True)
class TestAssetDetailRecord:
    asset: TestAsset
    current_version: TestAssetVersion
    sources: tuple[TestAssetSourceRecord, ...]
    latest_review: TestAssetReviewRecord | None


class TestAssetQueryRepository(BaseRepository):
    """按项目和公共 ID 查询自然语言资产，不映射 API Schema。"""

    def list_assets(
        self,
        filters: TestAssetListFilters,
        *,
        page: int,
        page_size: int,
        trace_id: str | None = None,
    ) -> RepositoryPage[TestAssetListRecord]:
        _validate_page(page=page, page_size=page_size)
        predicates = self._list_predicates(filters)
        current_join = (TestAssetVersion.id == TestAsset.current_version_pk) & (
            TestAssetVersion.test_asset_pk == TestAsset.id
        )

        matching_assets = (
            select(TestAsset.id)
            .outerjoin(TestAssetVersion, current_join)
            .where(*predicates)
            .distinct()
            .subquery()
        )
        total = self.db.scalar(select(func.count()).select_from(matching_assets))

        latest_review_id = (
            select(TestAssetReviewRecord.id)
            .where(TestAssetReviewRecord.test_asset_pk == TestAsset.id)
            .order_by(
                TestAssetReviewRecord.reviewed_at.desc(),
                TestAssetReviewRecord.id.desc(),
            )
            .limit(1)
            .correlate(TestAsset)
            .scalar_subquery()
        )
        rows = list(
            self.db.execute(
                select(TestAsset, TestAssetVersion, TestAssetReviewRecord)
                .outerjoin(TestAssetVersion, current_join)
                .outerjoin(
                    TestAssetReviewRecord,
                    TestAssetReviewRecord.id == latest_review_id,
                )
                .where(*predicates)
                .order_by(TestAsset.created_at.desc(), TestAsset.test_asset_id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
        )
        asset_pks = [asset.id for asset, _version, _review in rows]
        sources_by_asset = TestAssetSourceRepository(self.db).list_by_asset_pks(
            asset_pks,
            include_deleted=True,
            trace_id=trace_id,
        )

        items: list[TestAssetListRecord] = []
        for asset, version, review in rows:
            if version is None:
                raise RepositoryDataIntegrityError(
                    message="test asset current version is missing or mis-scoped",
                    entity_id=asset.test_asset_id,
                    trace_id=trace_id,
                )
            source_types = tuple(
                sorted(
                    {
                        record.source.source_type
                        for record in sources_by_asset.get(asset.id, [])
                    }
                )
            )
            items.append(
                TestAssetListRecord(
                    asset=asset,
                    current_version=version,
                    source_types=source_types,
                    latest_review=review,
                )
            )
        return RepositoryPage(
            items=items,
            page=page,
            page_size=page_size,
            total=int(total or 0),
        )

    def get_detail(
        self,
        *,
        project_code: str,
        test_asset_id: str,
        include_deleted: bool = False,
        trace_id: str | None = None,
    ) -> TestAssetDetailRecord | None:
        latest_review_id = (
            select(TestAssetReviewRecord.id)
            .where(TestAssetReviewRecord.test_asset_pk == TestAsset.id)
            .order_by(
                TestAssetReviewRecord.reviewed_at.desc(),
                TestAssetReviewRecord.id.desc(),
            )
            .limit(1)
            .correlate(TestAsset)
            .scalar_subquery()
        )
        statement = (
            select(TestAsset, TestAssetVersion, TestAssetReviewRecord)
            .outerjoin(
                TestAssetVersion,
                (TestAssetVersion.id == TestAsset.current_version_pk)
                & (TestAssetVersion.test_asset_pk == TestAsset.id),
            )
            .outerjoin(
                TestAssetReviewRecord,
                TestAssetReviewRecord.id == latest_review_id,
            )
            .where(
                TestAsset.project_code == project_code,
                TestAsset.test_asset_id == test_asset_id,
            )
        )
        if not include_deleted:
            statement = statement.where(TestAsset.deleted_at.is_(None))
        row = self.db.execute(statement).one_or_none()
        if row is None:
            return None
        asset, version, review = row
        if version is None:
            raise RepositoryDataIntegrityError(
                message="test asset current version is missing or mis-scoped",
                entity_id=asset.test_asset_id,
                trace_id=trace_id,
            )
        sources = TestAssetSourceRepository(self.db).list_by_asset(
            asset.id,
            include_deleted=True,
            trace_id=trace_id,
        )
        return TestAssetDetailRecord(
            asset=asset,
            current_version=version,
            sources=tuple(sources),
            latest_review=review,
        )

    def list_version_history(
        self,
        *,
        project_code: str,
        test_asset_id: str,
        include_deleted: bool,
        page: int,
        page_size: int,
    ) -> RepositoryPage[TestAssetVersion] | None:
        _validate_page(page=page, page_size=page_size)
        asset = self._get_scoped_asset(
            project_code=project_code,
            test_asset_id=test_asset_id,
            include_deleted=include_deleted,
        )
        if asset is None:
            return None
        predicate = TestAssetVersion.test_asset_pk == asset.id
        total = self.db.scalar(
            select(func.count()).select_from(TestAssetVersion).where(predicate)
        )
        items = list(
            self.db.execute(
                select(TestAssetVersion)
                .where(predicate)
                .order_by(
                    TestAssetVersion.version_no.desc(),
                    TestAssetVersion.id.desc(),
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

    def list_review_history(
        self,
        *,
        project_code: str,
        test_asset_id: str,
        include_deleted: bool,
        page: int,
        page_size: int,
    ) -> RepositoryPage[TestAssetReviewRecord] | None:
        _validate_page(page=page, page_size=page_size)
        asset = self._get_scoped_asset(
            project_code=project_code,
            test_asset_id=test_asset_id,
            include_deleted=include_deleted,
        )
        if asset is None:
            return None
        return TestAssetReviewRepository(self.db).list_by_asset(
            asset.id,
            page=page,
            page_size=page_size,
        )

    def _get_scoped_asset(
        self,
        *,
        project_code: str,
        test_asset_id: str,
        include_deleted: bool,
    ) -> TestAsset | None:
        statement = select(TestAsset).where(
            TestAsset.project_code == project_code,
            TestAsset.test_asset_id == test_asset_id,
        )
        if not include_deleted:
            statement = statement.where(TestAsset.deleted_at.is_(None))
        return self.db.execute(statement).scalar_one_or_none()

    @staticmethod
    def _list_predicates(
        filters: TestAssetListFilters,
    ) -> list[ColumnElement[bool]]:
        predicates: list[ColumnElement[bool]] = [
            TestAsset.project_code == filters.project_code
        ]
        if not filters.include_deleted:
            predicates.append(TestAsset.deleted_at.is_(None))
        if filters.review_status is not None:
            predicates.append(TestAsset.review_status == filters.review_status)
        if filters.conversion_status is not None:
            predicates.append(TestAsset.conversion_status == filters.conversion_status)
        if filters.priority is not None:
            predicates.append(TestAssetVersion.priority == filters.priority)
        if filters.created_by is not None:
            predicates.append(TestAsset.created_by == filters.created_by)
        if filters.created_from is not None:
            predicates.append(TestAsset.created_at >= filters.created_from)
        if filters.created_to is not None:
            predicates.append(TestAsset.created_at <= filters.created_to)
        if filters.keyword:
            predicates.append(
                func.lower(TestAssetVersion.title).contains(
                    filters.keyword.lower(),
                    autoescape=True,
                )
            )
        for tag in filters.tags:
            encoded_tag = json.dumps(tag, ensure_ascii=False)
            predicates.append(
                cast(TestAssetVersion.tags, Text).contains(
                    encoded_tag,
                    autoescape=True,
                )
            )
        if filters.source_type is not None:
            predicates.append(
                exists(
                    select(TestAssetSource.id).where(
                        TestAssetSource.test_asset_pk == TestAsset.id,
                        TestAssetSource.source_type == filters.source_type,
                    )
                )
            )
        if filters.requirement_id is not None:
            predicates.append(
                exists(
                    select(TestAssetRequirementSource.id)
                    .join(
                        TestAssetSource,
                        TestAssetSource.id
                        == TestAssetRequirementSource.test_asset_source_pk,
                    )
                    .join(
                        Requirement,
                        Requirement.id == TestAssetRequirementSource.requirement_pk,
                    )
                    .where(
                        TestAssetSource.test_asset_pk == TestAsset.id,
                        Requirement.requirement_id == filters.requirement_id,
                    )
                )
            )
        return predicates


def _validate_page(*, page: int, page_size: int) -> None:
    if page < 1:
        raise ValueError("page must be at least 1")
    if page_size < 1 or page_size > 100:
        raise ValueError("page_size must be between 1 and 100")
