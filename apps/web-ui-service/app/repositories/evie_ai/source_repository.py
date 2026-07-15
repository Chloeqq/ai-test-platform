"""EvieAi TestAsset 来源主表和类型化子表的数据访问。"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select

from app.constants.evie_ai import TestAssetSourceType
from app.models.evie_ai import (
    Requirement,
    RequirementVersion,
    TestAsset,
    TestAssetRequirementSource,
    TestAssetSource,
)
from app.repositories.base import BaseRepository
from app.repositories.evie_ai.errors import (
    RepositoryDataIntegrityError,
    SourceOwnershipError,
)


@dataclass(frozen=True, slots=True)
class TestAssetSourceRecord:
    """已完成主/子类型一致性校验的来源记录。"""

    source: TestAssetSource
    requirement_source: TestAssetRequirementSource | None
    requirement: Requirement | None
    requirement_version: RequirementVersion | None


class TestAssetSourceRepository(BaseRepository):
    """持久化并校验 Manual/Requirement 来源。"""

    def add_manual_source(
        self,
        source: TestAssetSource,
        *,
        trace_id: str | None = None,
    ) -> TestAssetSource:
        self._assert_source_asset(source, trace_id=trace_id)
        if source.source_type != TestAssetSourceType.MANUAL.value:
            raise SourceOwnershipError(
                source_id=source.test_asset_source_id,
                trace_id=trace_id,
            )
        self.db.add(source)
        self.db.flush()
        return source

    def add_requirement_source(
        self,
        source: TestAssetSource,
        *,
        requirement_pk: int,
        requirement_version_pk: int,
        trace_id: str | None = None,
    ) -> TestAssetSource:
        asset = self._assert_source_asset(source, trace_id=trace_id)
        requirement_row = self.db.execute(
            select(Requirement, RequirementVersion)
            .join(
                RequirementVersion,
                RequirementVersion.requirement_pk == Requirement.id,
            )
            .where(
                Requirement.id == requirement_pk,
                RequirementVersion.id == requirement_version_pk,
            )
        ).one_or_none()
        if (
            source.source_type != TestAssetSourceType.REQUIREMENT.value
            or requirement_row is None
        ):
            raise SourceOwnershipError(
                source_id=source.test_asset_source_id,
                trace_id=trace_id,
            )

        requirement, requirement_version = requirement_row
        if (
            requirement_version.requirement_pk != requirement.id
            or requirement.project_code != asset.project_code
        ):
            raise SourceOwnershipError(
                source_id=source.test_asset_source_id,
                trace_id=trace_id,
            )

        self.db.add(source)
        self.db.flush()
        self.db.add(
            TestAssetRequirementSource(
                test_asset_source_pk=source.id,
                requirement_pk=requirement.id,
                requirement_version_pk=requirement_version.id,
            )
        )
        self.db.flush()
        return source

    def get_by_identity(
        self,
        *,
        test_asset_pk: int,
        source_identity_hash: str,
        include_deleted: bool = False,
    ) -> TestAssetSource | None:
        statement = (
            select(TestAssetSource)
            .join(TestAsset, TestAsset.id == TestAssetSource.test_asset_pk)
            .where(
                TestAssetSource.test_asset_pk == test_asset_pk,
                TestAssetSource.source_identity_hash == source_identity_hash,
            )
        )
        if not include_deleted:
            statement = statement.where(TestAsset.deleted_at.is_(None))
        return self.db.execute(statement).scalar_one_or_none()

    def exists_identity(
        self,
        *,
        test_asset_pk: int,
        source_identity_hash: str,
        include_deleted: bool = False,
    ) -> bool:
        statement = (
            select(TestAssetSource.id)
            .join(TestAsset, TestAsset.id == TestAssetSource.test_asset_pk)
            .where(
                TestAssetSource.test_asset_pk == test_asset_pk,
                TestAssetSource.source_identity_hash == source_identity_hash,
            )
        )
        if not include_deleted:
            statement = statement.where(TestAsset.deleted_at.is_(None))
        return self.db.execute(statement).scalar_one_or_none() is not None

    def list_by_asset(
        self,
        test_asset_pk: int,
        *,
        include_deleted: bool = False,
        trace_id: str | None = None,
    ) -> list[TestAssetSourceRecord]:
        return self.list_by_asset_pks(
            [test_asset_pk],
            include_deleted=include_deleted,
            trace_id=trace_id,
        ).get(test_asset_pk, [])

    def list_by_asset_pks(
        self,
        test_asset_pks: list[int],
        *,
        include_deleted: bool = False,
        trace_id: str | None = None,
    ) -> dict[int, list[TestAssetSourceRecord]]:
        if not test_asset_pks:
            return {}

        statement = (
            select(
                TestAssetSource,
                TestAssetRequirementSource,
                Requirement,
                RequirementVersion,
                TestAsset,
            )
            .join(TestAsset, TestAsset.id == TestAssetSource.test_asset_pk)
            .outerjoin(
                TestAssetRequirementSource,
                TestAssetRequirementSource.test_asset_source_pk == TestAssetSource.id,
            )
            .outerjoin(
                Requirement,
                Requirement.id == TestAssetRequirementSource.requirement_pk,
            )
            .outerjoin(
                RequirementVersion,
                RequirementVersion.id
                == TestAssetRequirementSource.requirement_version_pk,
            )
            .where(TestAssetSource.test_asset_pk.in_(test_asset_pks))
            .order_by(TestAssetSource.test_asset_pk, TestAssetSource.id)
        )
        if not include_deleted:
            statement = statement.where(TestAsset.deleted_at.is_(None))

        records: dict[int, list[TestAssetSourceRecord]] = {
            test_asset_pk: [] for test_asset_pk in test_asset_pks
        }
        for source, subtype, requirement, version, asset in self.db.execute(statement):
            self._validate_record(
                source=source,
                subtype=subtype,
                requirement=requirement,
                version=version,
                asset=asset,
                trace_id=trace_id,
            )
            records[source.test_asset_pk].append(
                TestAssetSourceRecord(
                    source=source,
                    requirement_source=subtype,
                    requirement=requirement,
                    requirement_version=version,
                )
            )
        return records

    def _assert_source_asset(
        self,
        source: TestAssetSource,
        *,
        trace_id: str | None,
    ) -> TestAsset:
        asset = self.db.execute(
            select(TestAsset).where(
                TestAsset.id == source.test_asset_pk,
                TestAsset.deleted_at.is_(None),
            )
        ).scalar_one_or_none()
        if asset is None:
            raise SourceOwnershipError(
                source_id=source.test_asset_source_id,
                trace_id=trace_id,
            )
        return asset

    @staticmethod
    def _validate_record(
        *,
        source: TestAssetSource,
        subtype: TestAssetRequirementSource | None,
        requirement: Requirement | None,
        version: RequirementVersion | None,
        asset: TestAsset,
        trace_id: str | None,
    ) -> None:
        is_requirement = source.source_type == TestAssetSourceType.REQUIREMENT.value
        is_manual = source.source_type == TestAssetSourceType.MANUAL.value
        requirement_valid = (
            subtype is not None
            and requirement is not None
            and version is not None
            and subtype.requirement_pk == requirement.id
            and subtype.requirement_version_pk == version.id
            and version.requirement_pk == requirement.id
            and requirement.project_code == asset.project_code
        )
        if (is_requirement and requirement_valid) or (is_manual and subtype is None):
            return
        raise RepositoryDataIntegrityError(
            message="test asset source subtype is inconsistent",
            entity_id=source.test_asset_source_id,
            trace_id=trace_id,
        )
