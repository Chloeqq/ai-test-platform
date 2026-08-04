"""EvieAi TestAsset 聚合持久化访问。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, cast

from sqlalchemy import case, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.sql.dml import Update
from sqlalchemy.sql.elements import ColumnElement

from app.constants.evie_ai import (
    TestAssetConversionStatus,
    TestAssetReviewStatus,
)
from app.models.evie_ai import (
    TestAsset,
    TestAssetSource,
    TestAssetVersion,
)
from app.repositories.base import BaseRepository
from app.repositories.evie_ai.errors import (
    CurrentVersionOwnershipError,
    OptimisticConcurrencyError,
    RepositoryDataIntegrityError,
)
from app.repositories.evie_ai.source_repository import TestAssetSourceRepository

_VERSION_ADVANCEABLE_CONVERSION_STATUSES = (
    TestAssetConversionStatus.NOT_STARTED.value,
    TestAssetConversionStatus.BLOCKED.value,
    TestAssetConversionStatus.SUCCEEDED.value,
    TestAssetConversionStatus.STALE.value,
)
_VERSION_STALE_CONVERSION_STATUSES = (
    TestAssetConversionStatus.SUCCEEDED.value,
    TestAssetConversionStatus.STALE.value,
)


@dataclass(frozen=True)
class ReviewStatusCasInput:
    """审核状态条件更新的类型化输入。"""

    expected_review_status: TestAssetReviewStatus
    new_review_status: TestAssetReviewStatus
    updated_by: str


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

    def advance_current_version(
        self,
        *,
        project_code: str,
        test_asset_id: str,
        version: TestAssetVersion,
        expected_row_version: int,
        updated_by: str,
    ) -> bool:
        """原子推进 current Version，并按已批准规则重置资产状态。"""
        if version.id is None:
            return False
        statement = self._build_current_version_update(
            project_code=project_code,
            test_asset_id=test_asset_id,
            version_id=version.id,
            expected_row_version=expected_row_version,
            updated_by=updated_by,
        )
        return self._execute_conditional_update(statement)

    def compare_and_set_review_status(
        self,
        *,
        project_code: str,
        test_asset_id: str,
        expected_row_version: int,
        status_update: ReviewStatusCasInput,
    ) -> bool:
        """在 active 资产的指定审核状态上执行受限 CAS。"""
        statement = (
            update(TestAsset)
            .where(
                TestAsset.project_code == project_code,
                TestAsset.test_asset_id == test_asset_id,
                TestAsset.row_version == expected_row_version,
                TestAsset.deleted_at.is_(None),
                TestAsset.review_status == status_update.expected_review_status.value,
            )
            .values(
                review_status=status_update.new_review_status.value,
                row_version=TestAsset.row_version + 1,
                updated_by=status_update.updated_by,
            )
        )
        return self._execute_conditional_update(statement)

    def compare_and_set_deleted_at(
        self,
        *,
        project_code: str,
        test_asset_id: str,
        expected_row_version: int,
        deleted_at: datetime | None,
        updated_by: str,
    ) -> bool:
        """仅在当前删除状态匹配时执行软删除或恢复 CAS。"""
        statement = update(TestAsset).where(
            TestAsset.project_code == project_code,
            TestAsset.test_asset_id == test_asset_id,
            TestAsset.row_version == expected_row_version,
        )
        if deleted_at is None:
            statement = statement.where(TestAsset.deleted_at.is_not(None))
        else:
            statement = statement.where(TestAsset.deleted_at.is_(None))
        statement = statement.values(
            deleted_at=deleted_at,
            row_version=TestAsset.row_version + 1,
            updated_by=updated_by,
        )
        return self._execute_conditional_update(statement)

    def get_deleted_current_version_for_restore(
        self,
        *,
        project_code: str,
        test_asset_id: str,
    ) -> TestAssetVersion | None:
        """仅为恢复流程锁定并读取已删除资产的 current Version。"""
        statement = (
            select(TestAssetVersion)
            .join(TestAsset, TestAsset.current_version_pk == TestAssetVersion.id)
            .where(
                TestAsset.project_code == project_code,
                TestAsset.test_asset_id == test_asset_id,
                TestAsset.deleted_at.is_not(None),
                TestAssetVersion.test_asset_pk == TestAsset.id,
            )
            .with_for_update()
        )
        return self.db.execute(statement).scalar_one_or_none()

    def _build_current_version_update(
        self,
        *,
        project_code: str,
        test_asset_id: str,
        version_id: int,
        expected_row_version: int,
        updated_by: str,
    ) -> Update:
        return (
            update(TestAsset)
            .where(
                TestAsset.project_code == project_code,
                TestAsset.test_asset_id == test_asset_id,
                TestAsset.row_version == expected_row_version,
                TestAsset.deleted_at.is_(None),
                self._version_belongs_to_asset(version_id),
                TestAsset.conversion_status.in_(
                    _VERSION_ADVANCEABLE_CONVERSION_STATUSES
                ),
            )
            .values(
                current_version_pk=version_id,
                review_status=TestAssetReviewStatus.PENDING.value,
                conversion_status=case(
                    (
                        TestAsset.conversion_status.in_(
                            _VERSION_STALE_CONVERSION_STATUSES
                        ),
                        TestAssetConversionStatus.STALE.value,
                    ),
                    else_=TestAssetConversionStatus.NOT_STARTED.value,
                ),
                row_version=TestAsset.row_version + 1,
                updated_by=updated_by,
            )
        )

    def _execute_conditional_update(self, statement: Update) -> bool:
        result = cast(
            CursorResult[object],
            self.db.execute(statement.execution_options(synchronize_session="fetch")),
        )
        self.db.flush()
        return result.rowcount == 1

    @staticmethod
    def _version_belongs_to_asset(version_id: int) -> ColumnElement[bool]:
        return (
            select(TestAssetVersion.id)
            .where(
                TestAssetVersion.id == version_id,
                TestAssetVersion.test_asset_pk == TestAsset.id,
            )
            .exists()
        )

    def bind_initial_version(
        self,
        test_asset: TestAsset,
        version: TestAssetVersion,
        *,
        updated_by: str,
        trace_id: str | None = None,
    ) -> TestAsset:
        """绑定聚合创建期首版本，但不推进乐观锁版本。"""
        self._validate_initial_version(
            test_asset,
            version,
            trace_id=trace_id,
        )
        if not self._bind_initial_pointer(
            test_asset,
            version,
            updated_by=updated_by,
        ):
            raise RepositoryDataIntegrityError(
                message="initial test asset version is already bound or invalid",
                entity_id=test_asset.test_asset_id,
                trace_id=trace_id,
            )
        self.db.flush()
        self.db.refresh(test_asset)
        return test_asset

    @staticmethod
    def _validate_initial_version(
        test_asset: TestAsset,
        version: TestAssetVersion,
        *,
        trace_id: str | None,
    ) -> None:
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
        if version.version_no != 1:
            raise RepositoryDataIntegrityError(
                message="initial test asset version must have version number 1",
                entity_id=test_asset.test_asset_id,
                trace_id=trace_id,
            )

    def _bind_initial_pointer(
        self,
        test_asset: TestAsset,
        version: TestAssetVersion,
        *,
        updated_by: str,
    ) -> bool:
        result = cast(
            CursorResult[Any],
            self.db.execute(
                update(TestAsset)
                .where(
                    TestAsset.id == test_asset.id,
                    TestAsset.current_version_pk.is_(None),
                    TestAsset.row_version == 1,
                    TestAsset.deleted_at.is_(None),
                )
                .values(
                    current_version_pk=version.id,
                    updated_by=updated_by,
                )
                .execution_options(synchronize_session="fetch")
            ),
        )
        return result.rowcount == 1
