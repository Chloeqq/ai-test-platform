"""页面对象元素与别名映射，解析 involved_elements 为 element_code。"""
from __future__ import annotations

from typing import Any


def _normalized_text(value: Any) -> str:
    return str(value or "").strip()


def _normalized_key(value: Any) -> str:
    text = _normalized_text(value).lower()
    return "".join(ch for ch in text if ch.isalnum())


def _register_aliases(aliases: dict[str, str], code: str, value: Any) -> None:
    if isinstance(value, list):
        for item in value:
            key = _normalized_key(item)
            if key and key not in aliases:
                aliases[key] = code
        return
    key = _normalized_key(value)
    if key and key not in aliases:
        aliases[key] = code


def _derived_role_aliases(locator_type: str, locator_value: str, role: str) -> list[str]:
    normalized_type = _normalized_text(locator_type).lower()
    normalized_value = _normalized_text(locator_value)
    normalized_role = _normalized_text(role).lower()
    if not normalized_value or normalized_type != "role":
        return []
    # 按 ARIA role 生成中文别名，便于自然语言步骤命中 element_code
    suffix = ""
    if normalized_role == "button":
        suffix = "按钮"
    elif normalized_role in {"textbox", "searchbox", "combobox", "spinbutton"}:
        suffix = "输入框"
    elif normalized_role == "link":
        suffix = "链接"
    elif normalized_role == "menuitem":
        suffix = "菜单项"
    elif normalized_role == "checkbox":
        suffix = "复选框"
    elif normalized_role == "radio":
        suffix = "单选框"
    elif normalized_role == "switch":
        suffix = "开关"
    if not suffix:
        return []
    return [f"{normalized_value}{suffix}", f"{suffix}{normalized_value}"]


def build_element_alias_map(page_object: dict[str, Any]) -> dict[str, str]:
    """从页面对象 elements 构建规范化别名 → element_code 映射。"""
    elements = page_object.get("elements") if isinstance(page_object, dict) else {}
    if not isinstance(elements, dict):
        return {}

    aliases: dict[str, str] = {}
    for raw_code, raw_meta in elements.items():
        code = _normalized_text(raw_code)
        if not code:
            continue
        meta = raw_meta if isinstance(raw_meta, dict) else {}
        selector = _normalized_text(meta.get("selector") or meta.get("locator_value"))
        element_name = _normalized_text(meta.get("name") or meta.get("element_name"))
        locator_type = _normalized_text(meta.get("type") or meta.get("locator_type"))
        role = _normalized_text(meta.get("role"))
        business_type = _normalized_text(meta.get("business_type")).lower()
        explicit_aliases = meta.get("aliases") if isinstance(meta.get("aliases"), list) else meta.get("aliases")
        for alias in (code, selector, element_name, explicit_aliases):
            _register_aliases(aliases, code, alias)
        for alias in _derived_role_aliases(locator_type, selector, role):
            _register_aliases(aliases, code, alias)
        if business_type == "password_toggle":
            for alias in ("密码显隐", "密码隐藏", "密码明文显示", "密码可见性切换", "password_visibility_toggle"):
                _register_aliases(aliases, code, alias)
        elif business_type == "metric_label":
            if element_name:
                _register_aliases(aliases, code, f"{element_name}指标")
        elif business_type == "metric_value":
            if element_name:
                _register_aliases(aliases, code, f"{element_name}指标值")

    return aliases


def resolve_element_code(element_text: Any, alias_map: dict[str, str]) -> str:
    """将展示名/别名解析为 element_code，未命中返回空串。"""
    candidate = _normalized_key(element_text)
    if not candidate or not alias_map:
        return ""
    return alias_map.get(candidate, "")


def resolve_involved_element_codes(
    involved_elements: Any,
    page_object: dict[str, Any],
) -> tuple[list[str], list[str]]:
    """解析 involved_elements 列表，返回 (已识别 codes, 未识别原文)。"""
    if not isinstance(involved_elements, list):
        return [], []
    alias_map = build_element_alias_map(page_object)
    codes: list[str] = []
    unknown: list[str] = []
    for item in involved_elements:
        element_text = _normalized_text(item)
        if not element_text:
            continue
        code = resolve_element_code(element_text, alias_map)
        if code:
            if code not in codes:
                codes.append(code)
        else:
            unknown.append(element_text)
    return codes, unknown


def enrich_candidate_with_element_codes(
    candidate: dict[str, Any],
    page_object: dict[str, Any],
) -> dict[str, Any]:
    """为候选测试点写入 involved_element_codes（若能解析）。"""
    enriched = dict(candidate) if isinstance(candidate, dict) else {}
    codes, _unknown = resolve_involved_element_codes(enriched.get("involved_elements"), page_object)
    if codes:
        enriched["involved_element_codes"] = codes
    return enriched
