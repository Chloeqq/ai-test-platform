"""Behavior Registry Repository — Phase 0."""
from __future__ import annotations

from typing import Any

from sqlalchemy import select

from app.models.behavior_registry import (
    AssertionTemplate,
    BehaviorRegistry,
)
from .base import BaseRepository


class BehaviorRegistryRepository(BaseRepository):
    """行为注册表 + 断言模板的数据访问。"""

    # ---- Behavior Registry ----

    def find_by_code(self, behavior_code: str) -> BehaviorRegistry | None:
        return self.db.execute(
            select(BehaviorRegistry).where(
                BehaviorRegistry.behavior_code == behavior_code,
                BehaviorRegistry.status == "active",
            ).order_by(BehaviorRegistry.priority.asc())
        ).scalars().first()

    def find_by_intent(
        self,
        intent_type: str,
        scenario: str,
        page_code: str = "",
        context_filter: dict[str, Any] | None = None,
    ) -> BehaviorRegistry | None:
        """三步查找: page → domain → none。"""
        ctx = context_filter or {}

        # Level 1: Page-level, context 匹配优先
        stmt = (
            select(BehaviorRegistry)
            .where(
                BehaviorRegistry.intent_type == intent_type,
                BehaviorRegistry.scenario == scenario,
                BehaviorRegistry.status == "active",
            )
            .order_by(BehaviorRegistry.priority.asc())
        )
        rows = list(self.db.execute(stmt).scalars().all())

        # Try page-level first
        for row in rows:
            if row.scope == "page" and row.page_code == page_code:
                if _context_matches(row.context_filter, ctx):
                    return row

        # Try page-level without context
        for row in rows:
            if row.scope == "page" and row.page_code == page_code:
                if not row.context_filter:
                    return row

        # Try domain-level
        for row in rows:
            if row.scope == "domain":
                if _context_matches(row.context_filter, ctx):
                    return row

        # Try domain-level without context
        for row in rows:
            if row.scope == "domain" and not row.context_filter:
                return row

        return None

    def upsert_behavior(self, **kwargs: Any) -> BehaviorRegistry:
        """创建或更新 behavior 记录。"""
        existing = self.find_by_code(kwargs.get("behavior_code", ""))
        if existing:
            for key, value in kwargs.items():
                setattr(existing, key, value)
            self.db.commit()
            return existing
        record = BehaviorRegistry(**kwargs)
        self.db.add(record)
        self.db.commit()
        return record

    # ---- Assertion Template ----

    def list_templates_by_behavior(self, behavior_id: int) -> list[AssertionTemplate]:
        return list(
            self.db.execute(
                select(AssertionTemplate).where(
                    AssertionTemplate.behavior_id == behavior_id,
                )
            ).scalars().all()
        )

    def add_template(self, **kwargs: Any) -> AssertionTemplate:
        record = AssertionTemplate(**kwargs)
        self.db.add(record)
        self.db.commit()
        return record

    # ---- List all active behaviors ----

    def list_active(self, page_code: str = "") -> list[BehaviorRegistry]:
        stmt = select(BehaviorRegistry).where(BehaviorRegistry.status == "active")
        if page_code:
            stmt = stmt.where(BehaviorRegistry.page_code == page_code)
        return list(self.db.execute(stmt).scalars().all())


def _context_matches(registered: dict[str, Any] | None, query: dict[str, Any]) -> bool:
    """检查 registered context 是否匹配 query context。"""
    if not registered:
        return True
    if not query:
        return True
    for key, value in query.items():
        if registered.get(key) != value:
            return False
    return True
