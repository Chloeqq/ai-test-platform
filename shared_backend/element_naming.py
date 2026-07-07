"""元素编码命名中心 —— element_code ↔ 展示名/数据键/变量名 的唯一映射。

规范：element_code 从页面对象取材，格式为 {page_prefix}-{semantic}-{type_suffix}。
本模块从 element_code 本身推导语义，不依赖硬编码映射表，适配任何页面的任何元素。

用法：
    from shared_backend.element_naming import element_data_key, element_variable_name, element_display_name
    key = element_data_key("login-username-input")   # → "username"
    var = element_variable_name("login-username-input", page="login")  # → "login_username"
    name = element_display_name("login-submit-btn")   # → "登录按钮" (有 page_object 时优先查 name)
"""

from __future__ import annotations

import re
from typing import Any

from shared_backend.type_utils import str_value as _normalized_text

# 规范后缀 → 中文展示名映射（不依赖具体页面）
_TYPE_SUFFIX_DISPLAY: dict[str, str] = {
    "input": "输入框",
    "textarea": "文本域",
    "select": "下拉框",
    "button": "按钮",
    "btn": "按钮",
    "checkbox": "复选框",
    "radio": "单选框",
    "switch": "开关",
    "tab": "标签页",
    "menu": "菜单",
    "link": "链接",
    "table": "表格",
    "dialog": "弹窗",
    "drawer": "抽屉",
    "section": "区块",
    "card": "卡片",
    "toggle": "切换开关",
    "column": "列",
    "filter": "筛选器",
    "picker": "选择器",
    "label": "标签",
    "value": "值",
    "icon": "图标",
    "avatar": "头像",
    "dropdown": "下拉菜单",
    "breadcrumb": "面包屑",
    "navbar": "导航栏",
    "sidebar": "侧边栏",
    "hamburger": "折叠按钮",
    "item": "项",
}

# 常用语义词 → 中文
_SEMANTIC_DISPLAY: dict[str, str] = {
    "username": "用户名",
    "password": "密码",
    "login": "登录",
    "logout": "退出",
    "submit": "提交",
    "search": "搜索",
    "keyword": "关键词",
    "save": "保存",
    "cancel": "取消",
    "delete": "删除",
    "edit": "编辑",
    "view": "查看",
    "home": "首页",
    "user": "用户",
    "order": "订单",
    "product": "商品",
    "brand": "品牌",
    "coupon": "优惠券",
    "remark": "备注",
    "remember": "记住",
    "trial": "体验",
    "account": "账号",
    "confirm": "确认",
    "statistics": "统计",
    "overview": "概览",
    "pending": "待处理",
    "total": "总计",
    "qrcode": "二维码",
    "chart": "图表",
    "date": "日期",
    "time": "时间",
}


def _parse_element_code(element_code: str) -> tuple[str, str, str]:
    """解析 element_code 为 (prefix, semantic, type_suffix)。

    login-username-input → ("login", "username", "input")
    login-submit-btn → ("login", "submit", "btn")
    home-page → ("", "home", "page")
    layout-navbar → ("layout", "navbar", "")
    """
    parts = [p for p in element_code.split("-") if p]
    if len(parts) == 1:
        return ("", parts[0], "")
    if len(parts) == 2:
        return ("", parts[0], parts[1])
    # 3+ parts: 最后一段是 type_suffix
    return ("-".join(parts[:-2]), parts[-2], parts[-1])


def element_semantic_part(element_code: str) -> str:
    """提取 element_code 的语义部分。login-username-input → "username" """
    _prefix, semantic, _suffix = _parse_element_code(element_code)
    return semantic or element_code


def element_data_key(element_code: str) -> str:
    """element_code → data 段 key。login-username-input → "username", login-submit-btn → "submit" """
    return element_semantic_part(element_code)


def element_variable_name(element_code: str, *, page: str = "") -> str:
    """element_code → execution.variables 中的变量名。

    login-username-input, page="login" → "login_username"
    product-search-input, page="product" → "product_search"
    """
    semantic = element_semantic_part(element_code)
    normalized_page = re.sub(r"[^a-z0-9_]+", "_", _normalized_text(page).lower()).strip("_")
    if normalized_page:
        return f"{normalized_page}_{semantic}"
    return semantic


def element_display_name(element_code: str, elements_meta: dict[str, dict[str, Any]] | None = None) -> str:
    """element_code → 中文展示名。

    优先从页面对象 elements 的 name 字段取；
    其次从语义词+类型后缀推导。
    login-username-input → "用户名输入框"
    login-submit-btn → "登录按钮"
    """
    code = _normalized_text(element_code)
    if not code:
        return ""

    # 优先从页面对象元数据获取
    if isinstance(elements_meta, dict) and code in elements_meta:
        meta = elements_meta[code]
        name = _normalized_text(meta.get("name") or meta.get("element_name"))
        if name:
            return name

    # 从 element_code 推导
    _prefix, semantic, suffix = _parse_element_code(code)

    # 已知语义词
    semantic_cn = _SEMANTIC_DISPLAY.get(semantic, "")
    # 已知类型后缀
    suffix_cn = _TYPE_SUFFIX_DISPLAY.get(suffix, "")

    if semantic_cn and suffix_cn:
        return f"{semantic_cn}{suffix_cn}"
    if semantic_cn:
        return semantic_cn
    if suffix_cn:
        return f"{semantic}{suffix_cn}"
    return code


# ── 向后兼容的旧码映射（供存量数据过渡，逐步移除） ──

_LEGACY_TO_CANONICAL: dict[str, str] = {
    "username_input": "login-username-input",
    "password_input": "login-password-input",
    "login_button": "login-submit-btn",
    "home_menu": "home-page",
    "username": "login-username-input",
    "password": "login-password-input",
    "loginButton": "login-submit-btn",
    "eyeIcon": "login-password-toggle-btn",
    "rememberCheckbox": "",
    "userInfo": "",
    "logoutButton": "",
}


def resolve_legacy_code(value: str) -> str:
    """旧语义码 → 规范码（向后兼容）。不在映射中则返回空串。"""
    return _LEGACY_TO_CANONICAL.get(_normalized_text(value), "")
