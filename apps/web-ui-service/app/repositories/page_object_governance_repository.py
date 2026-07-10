"""PageObject 治理与列表查询 Repository。

覆盖模型：PageObject, PageElement, PageElementLocator, PageObjectGovernanceLog。
"""
from __future__ import annotations

from sqlalchemy import delete, func, select

from app.models.page_object import (
    PageElement,
    # PageElementLocator,  # TODO: model missing — need migration
    PageObject,
    PageObjectGovernanceLog,
)

from .base import BaseRepository


class PageObjectGovernanceRepository(BaseRepository):
    """PageObject 治理指标、筛选列表、跨页查询。"""

    __test__ = False

    # ---- Governance counts ----

    def count_approved_elements(self, page_object_id: int) -> int:
        return self.db.execute(
            select(func.count()).select_from(PageElement).where(
                PageElement.page_object_id == page_object_id,
                PageElement.status == "active",
                PageElement.review_status == "approved",
            )
        ).scalar_one() or 0

    def count_key_elements(self, page_object_id: int) -> int:
        return self.db.execute(
            select(func.count()).select_from(PageElement).where(
                PageElement.page_object_id == page_object_id,
                PageElement.is_key_element.is_(True),
            )
        ).scalar_one() or 0

    def count_unhealthy_elements(self, page_object_id: int) -> int:
        return self.db.execute(
            select(func.count()).select_from(PageElement).where(
                PageElement.page_object_id == page_object_id,
                PageElement.health_status == 0,
            )
        ).scalar_one() or 0

    def count_elements_grouped_by_page_object_ids(
        self, page_object_ids: list[int]
    ) -> dict[int, int]:
        if not page_object_ids:
            return {}
        rows = self.db.execute(
            select(PageElement.page_object_id, func.count())
            .where(PageElement.page_object_id.in_(page_object_ids))
            .group_by(PageElement.page_object_id)
        ).all()
        return {int(pid): int(cnt) for pid, cnt in rows}

    # ---- Filtered PageObject listing ----

    def list_page_objects_filtered(
        self,
        *,
        project_code: str = "",
        client: str = "",
        status_value: str = "",
    ) -> list[PageObject]:
        stmt = select(PageObject).order_by(
            PageObject.updated_at.desc(), PageObject.id.desc()
        )
        if project_code:
            stmt = stmt.where(PageObject.project_code == project_code)
        if client:
            stmt = stmt.where(PageObject.client == client)
        if status_value:
            stmt = stmt.where(PageObject.status == status_value)
        return list(self.db.execute(stmt).scalars().all())

    # ---- Join queries ----

    def list_elements_join_pageobject(
        self,
        *,
        project_code: str,
        client: str,
        page_codes: list[str] | None = None,
        locator_type: str | None = None,
        element_code: str | None = None,
    ) -> list[PageElement]:
        """跨页查找元素，用于 login repair 等场景。"""
        stmt = (
            select(PageElement)
            .join(PageObject, PageElement.page_object_id == PageObject.id)
            .where(
                PageObject.project_code == project_code,
                PageObject.client == client,
            )
        )
        if page_codes:
            stmt = stmt.where(PageObject.page_code.in_(page_codes))
        if locator_type:
            stmt = stmt.where(PageElement.locator_type == locator_type)
        if element_code:
            stmt = stmt.where(PageElement.element_code == element_code)
        stmt = stmt.order_by(PageElement.id.asc())
        return list(self.db.execute(stmt).scalars().all())

    # ---- Locator listing (disabled — PageElementLocator model missing) ----
    # def list_locators_by_element_id(self, element_id: int):
    #     ...

    # ---- GovernanceLog delete ----

    def delete_governance_logs_by_page_identity(
        self, project_code: str, client: str, page_code: str
    ) -> None:
        self.db.execute(
            delete(PageObjectGovernanceLog).where(
                PageObjectGovernanceLog.project_code == project_code,
                PageObjectGovernanceLog.client == client,
                PageObjectGovernanceLog.page_code == page_code,
            )
        )
