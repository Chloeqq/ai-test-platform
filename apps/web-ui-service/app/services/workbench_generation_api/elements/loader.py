"""从数据库或资产文件加载页面对象，构建元素别名映射和页面级配置。

加载优先级：DB(page_objects + page_elements) → YAML 资产 → 默认值
"""

from __future__ import annotations

import logging
from typing import Any, NamedTuple

from sqlalchemy.orm import Session

from shared_backend.element_binding import build_element_alias_map
from shared_backend.element_naming import element_display_name

LOGGER = logging.getLogger(__name__)


class PageConfig(NamedTuple):
    """页面级配置，从 DB/YAML 加载，包含别名映射、路由、首页元素等。"""
    alias_map: dict[str, str]
    home_element_code: str
    home_element_name: str
    default_route: str
    login_url: str
    fallback_element_code: str

    @staticmethod
    def defaults() -> PageConfig:
        """当 DB 和 YAML 都无数据时的最小回退配置。"""
        return PageConfig(
            alias_map=dict(_FALLBACK_LOGIN_PAGE_MAP),
            home_element_code="home_menu",
            home_element_name="首页菜单",
            default_route="#/home",
            login_url="#/login",
            fallback_element_code="login-submit-btn",
        )

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


def load_page_config(
    db: Session,
    *,
    project: str,
    client: str = "web",
    page: str,
) -> PageConfig:
    """从数据源加载页面完整配置。

    三层回退策略：
    1. DB: page_objects + page_elements 表 → 提取路由、首页元素等
    2. 文件: assets/page-objects/{client}/{page}.page-object.yaml
    3. 默认: PageConfig.defaults()

    返回 PageConfig 包含 alias_map, 路由, 首页元素等全部页面级配置。
    """
    # 1. 尝试从 DB 加载
    db_result = _load_from_db(db, project=project, client=client, page=page)
    if db_result:
        return _page_config_from_db_result(db_result)

    # 2. 回退到 YAML 资产文件
    yaml_po = _load_from_yaml(page)
    if yaml_po:
        alias_map = build_element_alias_map(yaml_po)
        defaults = PageConfig.defaults()
        return defaults._replace(alias_map=alias_map)

    # 3. 最终回退：默认 login 页面配置
    LOGGER.warning(
        "No page_object found for project=%s client=%s page=%s, using defaults",
        project, client, page,
    )
    return PageConfig.defaults()


def load_alias_map(
    db: Session,
    *,
    project: str,
    client: str = "web",
    page: str,
) -> dict[str, str]:
    """从数据源加载页面对象，构建元素别名 → element_code 映射。

    后向兼容包装，新代码请使用 load_page_config()。
    """
    return load_page_config(db, project=project, client=client, page=page).alias_map


def _load_from_db(
    db: Session,
    *,
    project: str,
    client: str,
    page: str,
) -> dict[str, Any] | None:
    """从 page_objects + page_elements 表加载页面对象。

    返回 dict 包含:
      - page, route_pattern, login_url
      - elements: {element_code: {name, type, selector, role, aliases, is_key_element}}
    失败返回 None。
    """
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
            "route_pattern": po.route_pattern or "",
            "elements": {
                elem.element_code: {
                    "name": elem.element_name or "",
                    "type": elem.locator_type or "",
                    "selector": elem.locator_value or "",
                    "role": elem.role or "",
                    "aliases": elem.aliases_json or [],
                    "is_key_element": bool(elem.is_key_element),
                }
                for elem in elements
            },
        }
    except Exception:
        LOGGER.warning(
            "failed to load page_object from DB for page=%s", page, exc_info=True,
        )
        return None


def _page_config_from_db_result(db_result: dict[str, Any]) -> PageConfig:
    """从 DB 查询结果构建 PageConfig。"""
    alias_map = build_element_alias_map(db_result)
    defaults = PageConfig.defaults()

    # 首页元素：取 is_key_element=True 的第一个元素
    home_elem_code = defaults.home_element_code
    home_elem_name = defaults.home_element_name
    for code, meta in db_result.get("elements", {}).items():
        if meta.get("is_key_element"):
            home_elem_code = code
            home_elem_name = element_display_name(code) or meta.get("name", code)
            break

    # 路由
    route_pattern = db_result.get("route_pattern", "") or defaults.default_route

    # 回退元素 code：取元素列表最后一个
    elem_codes = list(db_result.get("elements", {}).keys())
    fallback_code = elem_codes[-1] if elem_codes else defaults.fallback_element_code

    return PageConfig(
        alias_map=alias_map,
        home_element_code=home_elem_code,
        home_element_name=home_elem_name,
        default_route=route_pattern,
        login_url=route_pattern or defaults.login_url,
        fallback_element_code=fallback_code,
    )


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
