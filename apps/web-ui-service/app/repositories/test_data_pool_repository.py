"""TestDataPool Repository。"""
from __future__ import annotations

from typing import Any

from sqlalchemy import func, select

from app.models.test_data_pool import TestDataPool, TestDataPoolItem

from .base import BaseRepository


class TestDataPoolRepository(BaseRepository):
    __test__ = False

    def get_by_name(self, pool_name: str) -> TestDataPool | None:
        """按 pool_name 查询数据池，找不到返回 None。"""
        return self.db.execute(
            select(TestDataPool).where(TestDataPool.pool_name == pool_name)
        ).scalar_one_or_none()

    def list_all(self) -> list[TestDataPool]:
        """列出所有数据池，按名称排序。"""
        return list(
            self.db.execute(
                select(TestDataPool).order_by(TestDataPool.pool_name)
            ).scalars().all()
        )

    # ---- Items ----

    def list_items_by_pool(self, pool_id: int) -> list[TestDataPoolItem]:
        """列出指定数据池下的所有条目，按 item_key 排序。"""
        return list(
            self.db.execute(
                select(TestDataPoolItem)
                .where(TestDataPoolItem.pool_id == pool_id)
                .order_by(TestDataPoolItem.item_key)
            ).scalars().all()
        )

    def list_items_by_pool_and_tags(self, pool_id: int, tags_filter: dict[str, str]) -> list[TestDataPoolItem]:
        """
        按 pool_id + tags 过滤查询数据池条目。

        例: list_items_by_pool_and_tags(1, {"status": "locked", "env": "staging"})
          → WHERE pool_id=1 AND tags->>'status'='locked' AND tags->>'env'='staging'
        """
        query = select(TestDataPoolItem).where(
            TestDataPoolItem.pool_id == pool_id,
        )
        for key, value in tags_filter.items():
            query = query.where(
                TestDataPoolItem.tags[key].as_string() == value
            )
        query = query.order_by(TestDataPoolItem.item_key)
        return list(self.db.execute(query).scalars().all())

    def get_item_by_key(self, pool_id: int, item_key: str) -> TestDataPoolItem | None:
        """按 pool_id + item_key 精确查询某一条数据。"""
        return self.db.execute(
            select(TestDataPoolItem).where(
                TestDataPoolItem.pool_id == pool_id,
                TestDataPoolItem.item_key == item_key,
            )
        ).scalar_one_or_none()

    def count_items_by_pool(self, pool_id: int) -> int:
        """统计某个数据池有多少条数据。"""
        return self.db.execute(
            select(func.count()).select_from(TestDataPoolItem).where(
                TestDataPoolItem.pool_id == pool_id
            )
        ).scalar_one()

    # ---- Extended queries ----

    def list_active_items_with_pool_name(
        self,
    ) -> list[tuple[str, str, Any]]:
        """返回所有状态为 active 的 pool + item 关联数据 [(pool_name, item_key, item_value), ...]"""
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
