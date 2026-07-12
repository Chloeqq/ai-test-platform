"""Prompt 模板管理器：DB 优先，内置默认兜底。

架构：DB → 用户自定义覆盖(is_default=False) → 内置默认(YAML 文件)
惰性初始化：首次访问时种子内置模板到 DB(ensure_builtins)
"""
from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

import jinja2
import yaml
from jinja2 import meta as jinja2_meta
from sqlalchemy.orm import Session

from app.repositories.prompt_template_repository import PromptTemplateRepository

_LOGGER = logging.getLogger(__name__)

_BUILTINS_PATH = Path(__file__).resolve().parent / "builtin_prompts.yaml"


@lru_cache(maxsize=1)
def _load_builtin_templates() -> dict[str, dict]:
    """从 YAML 文件加载内置模板定义（缓存，进程生命周期内只读一次）。"""
    if not _BUILTINS_PATH.exists():
        _LOGGER.warning("builtin prompts file not found: %s", _BUILTINS_PATH)
        return {}
    with open(_BUILTINS_PATH, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def to_template_dict(tmpl) -> dict[str, Any]:
    """将 PromptTemplate ORM 对象转为 dict（公共函数，供 router 使用）。"""
    return {
        "id": tmpl.id,
        "code": tmpl.code,
        "name": tmpl.name,
        "scene_type": tmpl.scene_type,
        "description": tmpl.description,
        "system_prompt": tmpl.system_prompt,
        "user_prompt_template": tmpl.user_prompt_template,
        "variables": tmpl.variables,
        "is_default": tmpl.is_default,
        "is_enabled": tmpl.is_enabled,
        "version": tmpl.version,
        "created_by": tmpl.created_by,
        "updated_by": tmpl.updated_by,
        "created_at": tmpl.created_at.isoformat() if tmpl.created_at else None,
        "updated_at": tmpl.updated_at.isoformat() if tmpl.updated_at else None,
    }


class PromptManager:
    """Prompt 模板管理器。DB 优先，内置默认兜底。所有 DB 操作通过 Repository。"""

    # --- read ---

    @classmethod
    def list_all(cls, db: Session) -> list[dict[str, Any]]:
        repo = PromptTemplateRepository(db)
        return [to_template_dict(t) for t in repo.list_all()]

    @classmethod
    def get_by_id(cls, db: Session, template_id: int) -> dict[str, Any] | None:
        repo = PromptTemplateRepository(db)
        tmpl = repo.get_by_id(template_id)
        if tmpl is None:
            return None
        return to_template_dict(tmpl)

    @classmethod
    def get_template(cls, db: Session, code: str) -> dict[str, Any] | None:
        """从 DB 获取模板（唯一事实源）。YAML 仅用于首次 bootstrap 种子，不在运行时回退。"""
        repo = PromptTemplateRepository(db)
        custom = repo.get_enabled_custom(code)
        if custom is not None:
            return to_template_dict(custom)
        # fallback: 查 is_default=True 的内置模板（由 seed_prompts/bootstrap 预先写入 DB）
        tmpl = repo.get_by_code(code)
        if tmpl is not None and tmpl.is_enabled:
            return to_template_dict(tmpl)
        return None

    # --- write ---

    @classmethod
    def update(cls, db: Session, template_id: int, **kwargs: Any) -> dict[str, Any] | None:
        repo = PromptTemplateRepository(db)
        tmpl = repo.update(template_id, **kwargs)
        if tmpl is None:
            return None
        db.commit()
        return to_template_dict(tmpl)

    @classmethod
    def reset_to_default(cls, db: Session, template_id: int) -> dict[str, Any] | None:
        """恢复默认：删除用户自定义模板，重新种子内置版本。在同一事务中完成。"""
        repo = PromptTemplateRepository(db)
        tmpl_before = repo.get_by_id(template_id)
        if tmpl_before is None:
            return None
        code = tmpl_before.code
        repo.reset_to_default(template_id)
        cls._seed_core(db)
        db.commit()
        return to_template_dict(repo.get_by_code(code) or tmpl_before)

    # --- render ---

    @classmethod
    def render(cls, template: dict, context: dict) -> tuple[str, str]:
        env = jinja2.Environment(undefined=jinja2.StrictUndefined)
        system = str(template.get("system_prompt", ""))
        user_tpl = env.from_string(str(template.get("user_prompt_template", "")))
        return system, user_tpl.render(**context)

    @classmethod
    def extract_variables(cls, template_text: str) -> list[str]:
        env = jinja2.Environment()
        ast = env.parse(template_text)
        return sorted(jinja2_meta.find_undeclared_variables(ast))

    # --- seed (dev only, not called at runtime) ---

    @classmethod
    def _seed_core(cls, db: Session) -> int:
        """将 YAML 内置模板写入 DB（不 commit,由调用方控制事务）。返回写入数量。"""
        builtins = _load_builtin_templates()
        if not builtins:
            return 0
        repo = PromptTemplateRepository(db)
        for code, data in builtins.items():
            repo.create_or_update_builtin(code=code, **data)
        return len(builtins)

    @classmethod
    def seed_from_yaml(cls, db: Session) -> int:
        """从 YAML 文件种子内置模板到 DB（仅开发/运维使用，上线不调用）。返回写入数量。"""
        count = cls._seed_core(db)
        if count > 0:
            db.commit()
        return count
