"""EvieAi 有效资产内容占用的查询和原子变更。"""

from __future__ import annotations

from typing import Any, cast

from sqlalchemy import delete, select, update
from sqlalchemy.engine import CursorResult

from app.models.evie_ai import (
    TestAsset,
    TestAssetContentClaim,
    TestAssetVersion,
)
from app.repositories.base import BaseRepository
from app.repositories.evie_ai.errors import RepositoryDataIntegrityError


class TestAssetContentClaimRepository(BaseRepository):
    """依赖数据库唯一约束和条件更新保护 Content Claim。"""

    def add(self, claim: TestAssetContentClaim) -> TestAssetContentClaim:
        asset_row = self.db.execute(
            select(TestAsset.project_code, TestAsset.test_asset_id).where(
                TestAsset.id == claim.test_asset_pk,
                TestAsset.deleted_at.is_(None),
            )
        ).one_or_none()
        if asset_row is None or asset_row.project_code != claim.project_code:
            raise RepositoryDataIntegrityError(
                message="content claim project scope does not match active test asset",
                entity_id=None if asset_row is None else asset_row.test_asset_id,
            )
        self.db.add(claim)
        self.db.flush()
        return claim

    def acquire_for_deleted_asset_restore(
        self,
        *,
        project_code: str,
        test_asset_id: str,
        test_asset_version_id: str,
        content_fingerprint: str,
    ) -> TestAssetContentClaim | None:
        """仅为已删除资产恢复重新获取其 current content claim。"""
        asset = self._get_deleted_asset_for_restore(
            project_code=project_code,
            test_asset_id=test_asset_id,
            test_asset_version_id=test_asset_version_id,
            content_fingerprint=content_fingerprint,
        )
        if asset is None:
            return None

        if self.get_by_test_asset_pk(asset.id, for_update=True) is not None:
            raise RepositoryDataIntegrityError(
                message="deleted test asset must not retain a content claim",
                entity_id=test_asset_id,
            )

        claim = TestAssetContentClaim(
            test_asset_pk=asset.id,
            project_code=project_code,
            content_fingerprint=content_fingerprint,
        )
        self.db.add(claim)
        self.db.flush()
        return claim

    def _get_deleted_asset_for_restore(
        self,
        *,
        project_code: str,
        test_asset_id: str,
        test_asset_version_id: str,
        content_fingerprint: str,
    ) -> TestAsset | None:
        statement = (
            select(TestAsset)
            .join(
                TestAssetVersion,
                TestAsset.current_version_pk == TestAssetVersion.id,
            )
            .where(
                TestAsset.project_code == project_code,
                TestAsset.test_asset_id == test_asset_id,
                TestAsset.deleted_at.is_not(None),
                TestAssetVersion.test_asset_version_id == test_asset_version_id,
                TestAssetVersion.test_asset_pk == TestAsset.id,
                TestAssetVersion.content_checksum == content_fingerprint,
            )
            .with_for_update()
        )
        return self.db.execute(statement).scalar_one_or_none()

    def get_by_project_and_fingerprint(
        self,
        *,
        project_code: str,
        content_fingerprint: str,
        for_update: bool = False,
    ) -> TestAssetContentClaim | None:
        statement = select(TestAssetContentClaim).where(
            TestAssetContentClaim.project_code == project_code,
            TestAssetContentClaim.content_fingerprint == content_fingerprint,
        )
        if for_update:
            statement = statement.with_for_update()
        return self.db.execute(statement).scalar_one_or_none()

    def get_by_test_asset_pk(
        self,
        test_asset_pk: int,
        *,
        for_update: bool = False,
    ) -> TestAssetContentClaim | None:
        statement = select(TestAssetContentClaim).where(
            TestAssetContentClaim.test_asset_pk == test_asset_pk
        )
        if for_update:
            statement = statement.with_for_update()
        return self.db.execute(statement).scalar_one_or_none()

    def replace_fingerprint(
        self,
        *,
        test_asset_pk: int,
        project_code: str,
        expected_fingerprint: str,
        new_fingerprint: str,
    ) -> bool:
        result = cast(
            CursorResult[Any],
            self.db.execute(
                update(TestAssetContentClaim)
                .where(
                    TestAssetContentClaim.test_asset_pk == test_asset_pk,
                    TestAssetContentClaim.project_code == project_code,
                    TestAssetContentClaim.content_fingerprint == expected_fingerprint,
                )
                .values(content_fingerprint=new_fingerprint)
                .execution_options(synchronize_session=False)
            ),
        )
        return result.rowcount == 1

    def delete_by_test_asset_pk(
        self,
        test_asset_pk: int,
        *,
        expected_fingerprint: str | None = None,
    ) -> bool:
        statement = delete(TestAssetContentClaim).where(
            TestAssetContentClaim.test_asset_pk == test_asset_pk
        )
        if expected_fingerprint is not None:
            statement = statement.where(
                TestAssetContentClaim.content_fingerprint == expected_fingerprint
            )
        result = cast(CursorResult[Any], self.db.execute(statement))
        return result.rowcount == 1
