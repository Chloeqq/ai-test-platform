"""Repository 基类。"""
from __future__ import annotations

from sqlalchemy import inspect, select
from sqlalchemy.orm import Session


class BaseRepository:
    """所有 Repository 的基类，持有 DB session 引用。"""

    def __init__(self, db: Session) -> None:
        self.db = db

    def table_exists(self, table_name: str) -> bool:
        """检查数据库中是否存在指定表。"""
        return bool(inspect(self.db.get_bind()).has_table(table_name))

    def count_rows_if_table_exists(self, stmt) -> int:
        """执行 count 查询，若表不存在则返回 0。"""
        table = stmt.froms[0] if hasattr(stmt, "froms") and stmt.froms else None
        if table is not None:
            tablename = getattr(table, "__tablename__", None) or (
                table.name if hasattr(table, "name") else None
            )
            if tablename and not self.table_exists(tablename):
                return 0
        return self.db.execute(stmt).scalar_one() or 0
