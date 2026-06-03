"""TestDataPool Repository。"""
from __future__ import annotations

from typing import Any

from sqlalchemy import func, select

from app.models.test_data_pool import TestDataPool, TestDataPoolItem

from .base import BaseRepository


class TestDataPoolRepository(BaseRepository):
    __test__ = False

    def get_by_name(self, pool_name: str) -> TestDataPool | None:
        return self.db.execute(
            select(TestDataPool).where(TestDataPool.pool_name == pool_name)
        ).scalar_one_or_none()

    def list_all(self) -> list[TestDataPool]:
        return list(
            self.db.execute(
                select(TestDataPool).order_by(TestDataPool.pool_name)
            ).scalars().all()
        )

    # ---- Items ----

    def list_items_by_pool(self, pool_id: int) -> list[TestDataPoolItem]:
        return list(
            self.db.execute(
                select(TestDataPoolItem)
                .where(TestDataPoolItem.pool_id == pool_id)
                .order_by(TestDataPoolItem.item_key)
            ).scalars().all()
        )

    def get_item_by_key(self, pool_id: int, item_key: str) -> TestDataPoolItem | None:
        return self.db.execute(
            select(TestDataPoolItem).where(
                TestDataPoolItem.pool_id == pool_id,
                TestDataPoolItem.item_key == item_key,
            )
        ).scalar_one_or_none()

    def count_items_by_pool(self, pool_id: int) -> int:
        return self.db.execute(
            select(func.count()).select_from(TestDataPoolItem).where(
                TestDataPoolItem.pool_id == pool_id
            )
        ).scalar_one()

    # ---- Extended queries ----

    def list_active_items_with_pool_name(
        self,
    ) -> list[tuple[str, str, Any]]:
        """返回 [(pool_name, item_key, item_value), ...]"""
        return list(
            self.db.execute(
                select(
                    TestDataPool.pool_name,
                    TestDataPoolItem.item_key,
                    TestDataPoolItem.item_value,
                )
                .join(TestDataPoolItem, TestDataPoolItem.pool_id == TestDataPool.id)
                .where(
                    TestDataPool.status == "active",
                    TestDataPoolItem.status == "active",
                )
            ).all()
        )
