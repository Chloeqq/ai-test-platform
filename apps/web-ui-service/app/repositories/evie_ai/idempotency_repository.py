"""EvieAi 幂等 scope、generation CAS 和结果摘要持久化。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, cast

from sqlalchemy import delete, select, tuple_, update
from sqlalchemy.engine import CursorResult

from app.models.evie_ai import TestAssetIdempotencyRecord
from app.repositories.base import BaseRepository


@dataclass(frozen=True, slots=True)
class IdempotencyScope:
    project_code: str
    operation_type: str
    actor_or_client_id: str
    idempotency_key: str


@dataclass(frozen=True, slots=True)
class IdempotencyResultSummary:
    result_http_status: int
    result_type: str
    test_asset_id: str | None = None
    test_asset_version_id: str | None = None
    test_asset_review_record_id: str | None = None
    created: bool | None = None
    reused_existing: bool | None = None
    changed: bool | None = None
    row_version: int | None = None
    deleted: bool | None = None


class TestAssetIdempotencyRepository(BaseRepository):
    """不控制事务的数据库幂等协调访问。"""

    def add(
        self,
        record: TestAssetIdempotencyRecord,
    ) -> TestAssetIdempotencyRecord:
        self.db.add(record)
        self.db.flush()
        return record

    def get_by_scope(
        self,
        scope: IdempotencyScope,
        *,
        for_update: bool = False,
    ) -> TestAssetIdempotencyRecord | None:
        statement = select(TestAssetIdempotencyRecord).where(
            TestAssetIdempotencyRecord.project_code == scope.project_code,
            TestAssetIdempotencyRecord.operation_type == scope.operation_type,
            TestAssetIdempotencyRecord.actor_or_client_id == scope.actor_or_client_id,
            TestAssetIdempotencyRecord.idempotency_key == scope.idempotency_key,
        )
        if for_update:
            statement = statement.with_for_update()
        return self.db.execute(statement).scalar_one_or_none()

    def try_reoccupy_expired(
        self,
        *,
        record_id: int,
        expected_generation: int,
        expired_at_or_before: datetime,
        request_fingerprint: str,
        expires_at: datetime,
    ) -> bool:
        result = cast(
            CursorResult[Any],
            self.db.execute(
                update(TestAssetIdempotencyRecord)
                .where(
                    TestAssetIdempotencyRecord.id == record_id,
                    TestAssetIdempotencyRecord.generation == expected_generation,
                    TestAssetIdempotencyRecord.expires_at <= expired_at_or_before,
                )
                .values(
                    request_fingerprint=request_fingerprint,
                    expires_at=expires_at,
                    generation=TestAssetIdempotencyRecord.generation + 1,
                    result_http_status=None,
                    result_type=None,
                    test_asset_id=None,
                    test_asset_version_id=None,
                    test_asset_review_record_id=None,
                    created=None,
                    reused_existing=None,
                    changed=None,
                    row_version=None,
                    deleted=None,
                    completed_at=None,
                )
                .execution_options(synchronize_session=False)
            ),
        )
        return result.rowcount == 1

    def complete(
        self,
        *,
        record_id: int,
        expected_generation: int,
        completed_at: datetime,
        summary: IdempotencyResultSummary,
    ) -> bool:
        result = cast(
            CursorResult[Any],
            self.db.execute(
                update(TestAssetIdempotencyRecord)
                .where(
                    TestAssetIdempotencyRecord.id == record_id,
                    TestAssetIdempotencyRecord.generation == expected_generation,
                    TestAssetIdempotencyRecord.completed_at.is_(None),
                )
                .values(
                    result_http_status=summary.result_http_status,
                    result_type=summary.result_type,
                    test_asset_id=summary.test_asset_id,
                    test_asset_version_id=summary.test_asset_version_id,
                    test_asset_review_record_id=summary.test_asset_review_record_id,
                    created=summary.created,
                    reused_existing=summary.reused_existing,
                    changed=summary.changed,
                    row_version=summary.row_version,
                    deleted=summary.deleted,
                    completed_at=completed_at,
                )
                .execution_options(synchronize_session=False)
            ),
        )
        return result.rowcount == 1

    def delete_expired(
        self,
        *,
        expired_at_or_before: datetime,
        limit: int,
    ) -> int:
        if limit < 1:
            raise ValueError("limit must be positive")

        candidates = list(
            self.db.execute(
                select(
                    TestAssetIdempotencyRecord.id,
                    TestAssetIdempotencyRecord.generation,
                )
                .where(TestAssetIdempotencyRecord.expires_at <= expired_at_or_before)
                .order_by(
                    TestAssetIdempotencyRecord.expires_at,
                    TestAssetIdempotencyRecord.id,
                )
                .limit(limit)
            ).all()
        )
        if not candidates:
            return 0

        result = cast(
            CursorResult[Any],
            self.db.execute(
                delete(TestAssetIdempotencyRecord).where(
                    tuple_(
                        TestAssetIdempotencyRecord.id,
                        TestAssetIdempotencyRecord.generation,
                    ).in_(candidates),
                    TestAssetIdempotencyRecord.expires_at <= expired_at_or_before,
                )
            ),
        )
        return int(result.rowcount or 0)
