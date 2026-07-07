"""从数据库或资产文件加载页面对象，构建元素别名映射。

加载优先级：DB(page_objects + page_elements) → YAML 资产 → 空字典
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from shared_backend.element_binding import build_element_alias_map

LOGGER = logging.getLogger(__name__)

# 回退映射 — 当 DB 和 YAML 都无数据时使用（过渡期安全网）
_FALLBACK_LOGIN_PAGE_MAP: dict[str, str] = {
    "用户名输入框": "login-username-input",
    "账号输入框": "login-username-input",
    "用户名": "login-username-input",
    "账号": "login-username-input",
    "密码可见性切换": "login-password-toggle-btn",
    "密码显隐": "login-password-toggle-btn",
    "显示密码": "login-password-toggle-btn",
    "隐藏密码": "login-password-toggle-btn",
    "密码可见": "login-password-toggle-btn",
    "明文": "login-password-toggle-btn",
    "密文": "login-password-toggle-btn",
    "眼睛图标": "login-password-toggle-btn",
    "眼睛": "login-password-toggle-btn",
    "密码输入框": "login-password-input",
    "密码": "login-password-input",
    "登录按钮": "login-submit-btn",
    "登录": "login-submit-btn",
    "首页菜单": "home-page",
    "首页": "home-page",
    "工作台首页": "home-page",
}


def load_alias_map(
    db: Session,
    *,
    project: str,
    client: str = "web",
    page: str,
) -> dict[str, str]:
    """从数据源加载页面对象，构建元素别名 → element_code 映射。

    三层回退策略：
    1. DB: page_objects + page_elements 表
    2. 文件: assets/page-objects/{client}/{page}.page-object.yaml
    3. 硬编码: login 页面最小映射（过渡期安全网，生产不应触发）

    返回的 dict 可直接传入 ElementResolver.resolve()。
    """
    # 1. 尝试从 DB 加载
    page_object = _load_from_db(db, project=project, client=client, page=page)
    if page_object:
        return build_element_alias_map(page_object)

    # 2. 回退到 YAML 资产文件
    page_object = _load_from_yaml(page)
    if page_object:
        return build_element_alias_map(page_object)

    # 3. 最终回退：login 页面硬编码映射
    LOGGER.warning(
        "No page_object found for project=%s client=%s page=%s, falling back to login page map",
        project, client, page,
    )
    return dict(_FALLBACK_LOGIN_PAGE_MAP)


def _load_from_db(
    db: Session,
    *,
    project: str,
    client: str,
    page: str,
) -> dict[str, Any] | None:
    """从 page_objects + page_elements 表加载页面对象。"""
    try:
        from app.repositories.page_object_repository import PageObjectRepository
        repo = PageObjectRepository(db)
        po = repo.get_by_identity(project_code=project, client=client, page_code=page)
        if po is None:
            return None
        elements = repo.list_elements_by_page_object_id(po.id)
        if not elements:
            return None
        return {
            "page": page,
            "elements": {
                elem.element_code: {
                    "name": elem.element_name or "",
                    "type": elem.locator_type or "",
                    "selector": elem.locator_value or "",
                    "role": elem.role or "",
                    "aliases": elem.aliases_json or [],
                }
                for elem in elements
            },
        }
    except Exception:
        LOGGER.warning(
            "failed to load page_object from DB for page=%s", page, exc_info=True,
        )
        return None


def _load_from_yaml(page: str) -> dict[str, Any] | None:
    """从 YAML 资产文件加载页面对象。"""
    try:
        from shared_backend.page_object_assets import load_page_object_yaml
        yaml_po = load_page_object_yaml(page)
        if yaml_po:
            return yaml_po
    except Exception:
        LOGGER.warning(
            "failed to load page_object from YAML for page=%s", page, exc_info=True,
        )
    return None
