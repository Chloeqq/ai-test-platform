"""PageObject 聚合根的 Repository。

覆盖模型：PageObject, PageElement, PageElementVersion,
          PageElementLocator, PageObjectRef, PageElementHealthCheck。
"""
from __future__ import annotations

from sqlalchemy import delete, func, select

from app.models.page_object import (
    PageElement,
    PageElementHealthCheck,
    PageElementVersion,
    PageObject,
)
from app.models.page_object_recorder_models import (
    PageElementLocator,
    PageObjectRef,
)

from .base import BaseRepository


class PageObjectRepository(BaseRepository):
    """PageObject 聚合根的数据访问层。"""

    __test__ = False

    # ---- PageObject ----

    def get_by_id(self, po_id: int) -> PageObject | None:
        return self.db.execute(
            select(PageObject).where(PageObject.id == po_id)
        ).scalar_one_or_none()

    def get_by_identity(
        self, project_code: str, client: str, page_code: str
    ) -> PageObject | None:
        return self.db.execute(
            select(PageObject).where(
                PageObject.project_code == project_code,
                PageObject.client == client,
                PageObject.page_code == page_code,
            )
        ).scalar_one_or_none()

    def list_by_project_and_page_codes(
        self, project_code: str, client: str, page_codes: list[str]
    ) -> list[PageObject]:
        if not page_codes:
            return []
        return list(
            self.db.execute(
                select(PageObject).where(
                    PageObject.project_code == project_code,
                    PageObject.client == client,
                    PageObject.page_code.in_(page_codes),
                )
            ).scalars().all()
        )

    def list_all(self) -> list[PageObject]:
        return list(
            self.db.execute(select(PageObject).order_by(PageObject.id.asc())).scalars().all()
        )

    def get_by_page_code_fallback(self, page_code: str) -> PageObject | None:
        """宽松匹配：仅按 page_code 查最新一条。"""
        return self.db.execute(
            select(PageObject)
            .where(PageObject.page_code == page_code)
            .order_by(PageObject.updated_at.desc())
        ).scalars().first()

    # ---- PageElement ----

    def list_elements_by_page_object_id(
        self, page_object_id: int, *, order_by_id: bool = False
    ) -> list[PageElement]:
        stmt = select(PageElement).where(PageElement.page_object_id == page_object_id)
        if order_by_id:
            stmt = stmt.order_by(PageElement.id.asc())
        return list(self.db.execute(stmt).scalars().all())

    def get_element_by_code(
        self, page_object_id: int, element_code: str
    ) -> PageElement | None:
        return self.db.execute(
            select(PageElement).where(
                PageElement.page_object_id == page_object_id,
                PageElement.element_code == element_code,
            )
        ).scalar_one_or_none()

    def list_elements_by_page_object_ids(
        self, page_object_ids: list[int]
    ) -> list[PageElement]:
        if not page_object_ids:
            return []
        return list(
            self.db.execute(
                select(PageElement).where(PageElement.page_object_id.in_(page_object_ids))
            ).scalars().all()
        )

    def count_elements_by_page_object_id(self, page_object_id: int) -> int:
        return self.db.execute(
            select(func.count()).select_from(PageElement).where(
                PageElement.page_object_id == page_object_id
            )
        ).scalar_one()

    def delete_elements_by_ids(self, element_ids: list[int]) -> None:
        if not element_ids:
            return
        self.db.execute(delete(PageElement).where(PageElement.id.in_(element_ids)))

    # ---- PageElement 跨页查找 ----

    def find_element_by_testid_across_pages(
        self, project_code: str, preferred_page_codes: list[str], element_code: str
    ) -> PageElement | None:
        """在指定页面的 data-testid 元素中查找匹配的 element_code。"""
        if not preferred_page_codes or not element_code:
            return None
        return self.db.execute(
            select(PageElement)
            .join(PageObject, PageElement.page_object_id == PageObject.id)
            .where(
                PageObject.project_code == project_code,
                PageObject.client == "web",
                PageObject.page_code.in_(preferred_page_codes),
                PageElement.element_code == element_code,
                PageElement.locator_type == "data-testid",
            )
            .order_by(PageElement.id.asc())
        ).scalars().first()

    # ---- PageElementLocator ----

    def get_locator(
        self, page_element_id: int, locator_type: str, locator_value: str, role: str = ""
    ) -> PageElementLocator | None:
        return self.db.execute(
            select(PageElementLocator).where(
                PageElementLocator.page_element_id == page_element_id,
                PageElementLocator.locator_type == locator_type,
                PageElementLocator.locator_value == locator_value,
                PageElementLocator.role == role,
            )
        ).scalar_one_or_none()

    def delete_locators_by_element_ids(self, element_ids: list[int]) -> None:
        if not element_ids:
            return
        self.db.execute(
            delete(PageElementLocator).where(
                PageElementLocator.page_element_id.in_(element_ids)
            )
        )

    # ---- PageElementVersion ----

    def delete_versions_by_element_ids(self, element_ids: list[int]) -> None:
        if not element_ids:
            return
        self.db.execute(
            delete(PageElementVersion).where(
                PageElementVersion.page_element_id.in_(element_ids)
            )
        )

    # ---- PageObjectRef ----

    def list_refs_by_element_id(self, page_element_id: int) -> list[PageObjectRef]:
        return list(
            self.db.execute(
                select(PageObjectRef).where(
                    PageObjectRef.page_element_id == page_element_id
                )
            ).scalars().all()
        )

    def get_ref(
        self, page_element_id: int, reference_type: str, reference_key: str
    ) -> PageObjectRef | None:
        return self.db.execute(
            select(PageObjectRef).where(
                PageObjectRef.page_element_id == page_element_id,
                PageObjectRef.reference_type == reference_type,
                PageObjectRef.reference_key == reference_key,
            )
        ).scalar_one_or_none()

    def count_refs_by_element_id(self, element_id: int) -> int:
        return self.db.execute(
            select(func.count()).select_from(PageObjectRef).where(
                PageObjectRef.page_element_id == element_id
            )
        ).scalar_one() or 0

    def delete_refs_by_element_ids(self, element_ids: list[int]) -> None:
        if not element_ids:
            return
        self.db.execute(
            delete(PageObjectRef).where(PageObjectRef.page_element_id.in_(element_ids))
        )

    # ---- PageElementHealthCheck ----

    def delete_health_checks_by_element_ids(self, element_ids: list[int]) -> None:
        if not element_ids:
            return
        self.db.execute(
            delete(PageElementHealthCheck).where(
                PageElementHealthCheck.page_element_id.in_(element_ids)
            )
        )

    # ---- PageElementVersion queries ----

    def get_max_version_no(self, element_id: int) -> int | None:
        return self.db.execute(
            select(func.max(PageElementVersion.version_no)).where(
                PageElementVersion.page_element_id == element_id
            )
        ).scalar_one()

    def get_max_version_nos_by_element_ids(
        self, element_ids: list[int]
    ) -> dict[int, int]:
        if not element_ids:
            return {}
        rows = self.db.execute(
            select(
                PageElementVersion.page_element_id,
                func.max(PageElementVersion.version_no),
            )
            .where(PageElementVersion.page_element_id.in_(element_ids))
            .group_by(PageElementVersion.page_element_id)
        ).all()
        return {int(eid): int(vn) for eid, vn in rows}

    def get_version_by_element_id_and_no(
        self, element_id: int, version_no: int
    ) -> PageElementVersion | None:
        return self.db.execute(
            select(PageElementVersion).where(
                PageElementVersion.page_element_id == element_id,
                PageElementVersion.version_no == version_no,
            )
        ).scalar_one_or_none()

    def list_versions_by_element_id(
        self, element_id: int
    ) -> list[PageElementVersion]:
        return list(
            self.db.execute(
                select(PageElementVersion)
                .where(PageElementVersion.page_element_id == element_id)
                .order_by(
                    PageElementVersion.version_no.desc(),
                    PageElementVersion.id.desc(),
                )
            ).scalars().all()
        )

    # ---- Element listing helpers ----

    def list_element_ids_by_page_object_id(self, page_object_id: int) -> list[int]:
        return list(
            self.db.execute(
                select(PageElement.id).where(
                    PageElement.page_object_id == page_object_id
                )
            ).scalars().all()
        )

    def get_element_by_code_excluding_id(
        self, page_object_id: int, element_code: str, exclude_id: int
    ) -> PageElement | None:
        return self.db.execute(
            select(PageElement).where(
                PageElement.page_object_id == page_object_id,
                PageElement.element_code == element_code,
                PageElement.id != exclude_id,
            )
        ).scalar_one_or_none()

    def list_elements_by_codes(
        self, page_object_id: int, element_codes: list[str]
    ) -> list[PageElement]:
        if not element_codes:
            return []
        return list(
            self.db.execute(
                select(PageElement).where(
                    PageElement.page_object_id == page_object_id,
                    PageElement.element_code.in_(element_codes),
                )
            ).scalars().all()
        )

    def list_elements_by_page_object_id_ordered(
        self, page_object_id: int
    ) -> list[PageElement]:
        return list(
            self.db.execute(
                select(PageElement)
                .where(PageElement.page_object_id == page_object_id)
                .order_by(PageElement.updated_at.desc(), PageElement.id.desc())
            ).scalars().all()
        )

    # ---- PageObjectRef grouped counts ----

    def count_refs_grouped_by_element_ids(
        self, element_ids: list[int]
    ) -> dict[int, int]:
        if not element_ids:
            return {}
        rows = self.db.execute(
            select(PageObjectRef.page_element_id, func.count())
            .where(PageObjectRef.page_element_id.in_(element_ids))
            .group_by(PageObjectRef.page_element_id)
        ).all()
        return {int(eid): int(cnt) for eid, cnt in rows}

    # ---- 级联删除 ----

    def cascade_delete_element(self, element_id: int) -> None:
        """删除一个元素及其所有子记录（定位器、版本、引用、健康检查）。"""
        self.delete_locators_by_element_ids([element_id])
        self.delete_versions_by_element_ids([element_id])
        self.delete_refs_by_element_ids([element_id])
        self.delete_health_checks_by_element_ids([element_id])
        self.delete_elements_by_ids([element_id])

    def bulk_cascade_delete_elements(self, element_ids: list[int]) -> None:
        """批量级联删除元素及其子记录。"""
        if not element_ids:
            return
        self.delete_locators_by_element_ids(element_ids)
        self.delete_versions_by_element_ids(element_ids)
        self.delete_refs_by_element_ids(element_ids)
        self.delete_health_checks_by_element_ids(element_ids)
        self.delete_elements_by_ids(element_ids)
