"""页面对象查询辅助，供编排层和 web-ui 层共享使用。"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session


def fetch_page_object_id(
    db: Session, *, project: str, client: str, page: str
) -> int | None:
    """按 (project, client, page) 查询 page_objects 的 ID。未找到返回 None。"""
    row = db.execute(
        text(
            "select id from page_objects "
            "where project_code = :project and client = :client and page_code = :page"
        ),
        {"project": project, "client": client, "page": page},
    ).fetchone()
    return int(row[0]) if row is not None else None


def fetch_page_elements(
    db: Session, *, page_object_id: int
) -> list[dict[str, str]]:
    """按 page_object_id 查询 page_elements，返回元素字典列表。"""
    rows = db.execute(
        text(
            "select element_code, locator_type, locator_value, role, "
            "coalesce(element_name, '') as element_name "
            "from page_elements where page_object_id = :po_id order by id asc"
        ),
        {"po_id": page_object_id},
    ).fetchall()
    return [
        {
            "element_code": str(r[0] or "").strip(),
            "locator_type": str(r[1] or "").strip(),
            "locator_value": str(r[2] or "").strip(),
            "role": str(r[3] or "").strip(),
            "element_name": str(r[4] or "").strip(),
        }
        for r in rows
    ]
