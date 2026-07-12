"""Repository for PromptTemplate（唯一可写 db.execute(select(...)) 的地方）。"""
from __future__ import annotations

from sqlalchemy import select

from app.models.prompt_template import PromptTemplate

from .base import BaseRepository


class PromptTemplateRepository(BaseRepository):
    """Prompt 模板的 DB 读写。"""

    def get_by_code(self, code: str) -> PromptTemplate | None:
        return self.db.execute(
            select(PromptTemplate).where(PromptTemplate.code == code)
        ).scalar_one_or_none()

    def get_by_id(self, template_id: int) -> PromptTemplate | None:
        return self.db.execute(
            select(PromptTemplate).where(PromptTemplate.id == template_id)
        ).scalar_one_or_none()

    def get_enabled_custom(self, code: str) -> PromptTemplate | None:
        """获取用户自定义的、启用的模板（is_default=False, is_enabled=True）。"""
        return self.db.execute(
            select(PromptTemplate).where(
                PromptTemplate.code == code,
                PromptTemplate.is_default.is_(False),
                PromptTemplate.is_enabled.is_(True),
            )
        ).scalar_one_or_none()

    def list_all(self) -> list[PromptTemplate]:
        return list(
            self.db.execute(
                select(PromptTemplate).order_by(PromptTemplate.code)
            ).scalars().all()
        )

    def create_or_update_builtin(self, *, code: str, **kwargs: object) -> PromptTemplate:
        """创建或更新内置模板（is_default=True）。如已存在且 version 不同则升级。"""
        # 过滤掉只存在于内置元数据但不在 DB 列上的 key（如 description）
        model_cols = {c.name for c in PromptTemplate.__table__.columns}
        clean_kwargs = {k: v for k, v in kwargs.items() if k in model_cols}
        existing = self.get_by_code(code)
        new_version = int(clean_kwargs.get("version", 1) or 1)
        if existing is not None:
            if existing.is_default and existing.version < new_version:
                for key, value in clean_kwargs.items():
                    if hasattr(existing, key):
                        setattr(existing, key, value)
                self.db.flush()
            return existing
        tmpl = PromptTemplate(code=code, is_default=True, **clean_kwargs)
        self.db.add(tmpl)
        self.db.flush()
        return tmpl

    def update(self, template_id: int, **kwargs: object) -> PromptTemplate | None:
        """更新自定义模板。内置模板更新后 is_default 变为 False(用户覆盖)。"""
        tmpl = self.get_by_id(template_id)
        if tmpl is None:
            return None
        for key, value in kwargs.items():
            if hasattr(tmpl, key):
                setattr(tmpl, key, value)
        if tmpl.is_default:
            tmpl.is_default = False  # 用户覆盖内置模板
        self.db.flush()
        return tmpl

    def reset_to_default(self, template_id: int) -> PromptTemplate | None:
        """将用户自定义模板标记为待删除（软重置）。实际种子在下次 initialize_builtins 时重新写入。"""
        tmpl = self.get_by_id(template_id)
        if tmpl is None or tmpl.is_default:
            return tmpl
        self.db.delete(tmpl)
        self.db.flush()
        return None
