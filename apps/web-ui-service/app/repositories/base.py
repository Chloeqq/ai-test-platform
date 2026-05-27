"""Repository 基类。"""
from __future__ import annotations

from sqlalchemy.orm import Session


class BaseRepository:
    """所有 Repository 的基类，持有 DB session 引用。"""

    def __init__(self, db: Session) -> None:
        self.db = db
