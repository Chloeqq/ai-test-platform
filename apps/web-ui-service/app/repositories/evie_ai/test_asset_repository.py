"""EvieAi TestAsset 聚合持久化访问。"""

from __future__ import annotations

from typing import Any, cast

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult

from app.models.evie_ai import (
    TestAsset,
    TestAssetSource,
    TestAssetVersion,
)
from app.repositories.base import BaseRepository
from app.repositories.evie_ai.errors import (
    CurrentVersionOwnershipError,
    OptimisticConcurrencyError,
)
from app.repositories.evie_ai.source_repository import TestAssetSourceRepository


class TestAssetRepository(BaseRepository):
    """TestAsset、不可变版本和 Requirement 来源的数据访问层。"""

    def add(self, test_asset: TestAsset) -> TestAsset:
        self.db.add(test_asset)
        self.db.flush()
        return test_asset

    def add_version(self, version: TestAssetVersion) -> TestAssetVersion:
        self.db.add(version)
        self.db.flush()
        return version

    def add_source(
        self,
        source: TestAssetSource,
        *,
        requirement_pk: int,
        requirement_version_pk: int,
        trace_id: str | None = None,
    ) -> TestAssetSource:
        return TestAssetSourceRepository(self.db).add_requirement_source(
            source,
            requirement_pk=requirement_pk,
            requirement_version_pk=requirement_version_pk,
            trace_id=trace_id,
        )

    def get_by_pk(
        self,
        test_asset_pk: int,
        *,
        include_deleted: bool = False,
        for_update: bool = False,
    ) -> TestAsset | None:
        statement = select(TestAsset).where(TestAsset.id == test_asset_pk)
        if not include_deleted:
            statement = statement.where(TestAsset.deleted_at.is_(None))
        if for_update:
            statement = statement.with_for_update()
        return self.db.execute(statement).scalar_one_or_none()

    def get_by_test_asset_id(
        self,
        test_asset_id: str,
        *,
        project_code: str | None = None,
        include_deleted: bool = False,
        for_update: bool = False,
    ) -> TestAsset | None:
        statement = select(TestAsset).where(TestAsset.test_asset_id == test_asset_id)
        if project_code is not None:
            statement = statement.where(TestAsset.project_code == project_code)
        if not include_deleted:
            statement = statement.where(TestAsset.deleted_at.is_(None))
        if for_update:
            statement = statement.with_for_update()
        return self.db.execute(statement).scalar_one_or_none()

    def get_version_by_test_asset_version_id(
        self,
        *,
        test_asset_pk: int,
        test_asset_version_id: str,
    ) -> TestAssetVersion | None:
        return self.db.execute(
            select(TestAssetVersion).where(
                TestAssetVersion.test_asset_pk == test_asset_pk,
                TestAssetVersion.test_asset_version_id == test_asset_version_id,
            )
        ).scalar_one_or_none()

    def get_current_version(
        self,
        test_asset_pk: int,
    ) -> TestAssetVersion | None:
        return self.db.execute(
            select(TestAssetVersion)
            .join(
                TestAsset,
                TestAsset.current_version_pk == TestAssetVersion.id,
            )
            .where(
                TestAsset.id == test_asset_pk,
                TestAsset.deleted_at.is_(None),
                TestAssetVersion.test_asset_pk == test_asset_pk,
            )
        ).scalar_one_or_none()

    def list_versions(self, test_asset_pk: int) -> list[TestAssetVersion]:
        return list(
            self.db.execute(
                select(TestAssetVersion)
                .join(TestAsset, TestAsset.id == TestAssetVersion.test_asset_pk)
                .where(
                    TestAssetVersion.test_asset_pk == test_asset_pk,
                    TestAsset.deleted_at.is_(None),
                )
                .order_by(TestAssetVersion.version_no.desc())
            )
            .scalars()
            .all()
        )

    def list_sources(self, test_asset_pk: int) -> list[TestAssetSource]:
        records = TestAssetSourceRepository(self.db).list_by_asset(test_asset_pk)
        return [record.source for record in records]

    def set_current_version(
        self,
        test_asset: TestAsset,
        version: TestAssetVersion,
        *,
        expected_row_version: int,
        updated_by: str,
        trace_id: str | None = None,
    ) -> TestAsset:
        if (
            test_asset.id is None
            or version.id is None
            or version.test_asset_pk != test_asset.id
        ):
            raise CurrentVersionOwnershipError(
                aggregate_type="test_asset",
                aggregate_id=test_asset.test_asset_id,
                trace_id=trace_id,
            )

        result = cast(
            CursorResult[Any],
            self.db.execute(
                update(TestAsset)
                .where(
                    TestAsset.id == test_asset.id,
                    TestAsset.row_version == expected_row_version,
                    TestAsset.deleted_at.is_(None),
                )
                .values(
                    current_version_pk=version.id,
                    row_version=TestAsset.row_version + 1,
                    updated_by=updated_by,
                )
                .execution_options(synchronize_session="fetch")
            ),
        )
        if result.rowcount != 1:
            raise OptimisticConcurrencyError(
                aggregate_type="test_asset",
                aggregate_id=test_asset.test_asset_id,
                trace_id=trace_id,
            )
        self.db.flush()
        self.db.refresh(test_asset)
        return test_asset
