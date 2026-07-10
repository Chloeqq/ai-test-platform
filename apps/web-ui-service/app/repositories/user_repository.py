"""User 数据访问层。"""
from __future__ import annotations

from sqlalchemy import select

from app.models.user import User

from .base import BaseRepository


class UserRepository(BaseRepository):
    """User 的 Repository。"""

    def get_by_id(self, user_id: int) -> User | None:
        return self.db.execute(
            select(User).where(User.id == user_id)
        ).scalar_one_or_none()

    def get_by_username(self, username: str) -> User | None:
        return self.db.execute(
            select(User).where(User.username == username)
        ).scalar_one_or_none()
