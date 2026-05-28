"""从 assets 加载 YAML 页面对象并与运行时 elements 合并。"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from shared_backend.type_utils import str_value as _normalized_text

_PAGE_OBJECT_ROOT = Path(__file__).resolve().parents[1] / "assets" / "page-objects" / "web"



def _normalized_page_slug(page: str) -> str:
    return _normalized_text(page).lower()


def _dedupe_keep_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        text = _normalized_text(value)
        if not text or text in seen:
            continue
        seen.add(text)
        ordered.append(text)
    return ordered


def _normalize_aliases(value: Any) -> list[str]:
    if isinstance(value, list):
        return _dedupe_keep_order([_normalized_text(item) for item in value])
    if isinstance(value, str):
        text = _normalized_text(value)
        return [text] if text else []
    return []


def load_page_object_yaml(page: str, *, root: Path | None = None) -> dict[str, Any] | None:
    """读取 assets/page-objects/web/{page}.page-object.yaml，失败返回 None。"""
    page_slug = _normalized_page_slug(page)
    if not page_slug:
        return None
    base_root = root if isinstance(root, Path) else _PAGE_OBJECT_ROOT
    asset_path = base_root / f"{page_slug}.page-object.yaml"
    if not asset_path.exists():
        return None
    try:
        raw = yaml.safe_load(asset_path.read_text(encoding="utf-8")) or {}
    except Exception:
        return None
    return raw if isinstance(raw, dict) else None


def merge_page_object_elements(
    elements: dict[str, Any] | None,
    yaml_page_object: dict[str, Any] | None,
) -> dict[str, dict[str, Any]]:
    """合并内存 elements 与 YAML；YAML 仅填充空缺字段（不覆盖已有 selector）。"""
    normalized: dict[str, dict[str, Any]] = {}
    if isinstance(elements, dict):
        for raw_code, raw_meta in elements.items():
            code = _normalized_text(raw_code)
            if not code:
                continue
            meta = raw_meta if isinstance(raw_meta, dict) else {}
            normalized[code] = {
                "selector": _normalized_text(meta.get("selector") or meta.get("locator_value")),
                "type": _normalized_text(meta.get("type") or meta.get("locator_type")) or "css",
                "role": _normalized_text(meta.get("role")),
                "name": _normalized_text(meta.get("name") or meta.get("element_name")),
                "aliases": _normalize_aliases(meta.get("aliases")),
                "business_type": _normalized_text(meta.get("business_type")),
                "business_domain": _normalized_text(meta.get("business_domain")),
                "semantic_tags": _normalize_aliases(meta.get("semantic_tags")),
                "review_status": _normalized_text(meta.get("review_status")),
                "stability_level": _normalized_text(meta.get("stability_level")),
                "status": _normalized_text(meta.get("status")),
            }

    yaml_elements = yaml_page_object.get("elements") if isinstance(yaml_page_object, dict) else {}
    if not isinstance(yaml_elements, dict):
        return normalized

    for raw_code, raw_meta in yaml_elements.items():
        code = _normalized_text(raw_code)
        if not code:
            continue
        meta = raw_meta if isinstance(raw_meta, dict) else {}
        current = normalized.setdefault(
            code,
            {
                "selector": "",
                "type": "css",
                "role": "",
                "name": "",
                "aliases": [],
                "business_type": "",
                "business_domain": "",
                "semantic_tags": [],
                "review_status": "",
                "stability_level": "",
                "status": "",
            },
        )
        selector = _normalized_text(meta.get("locator_value") or meta.get("selector"))
        locator_type = _normalized_text(meta.get("locator_type") or meta.get("type"))
        role = _normalized_text(meta.get("role"))
        name = _normalized_text(meta.get("element_name") or meta.get("name"))
        aliases = _normalize_aliases(meta.get("aliases"))
        business_type = _normalized_text(meta.get("business_type"))
        business_domain = _normalized_text(meta.get("business_domain"))
        semantic_tags = _normalize_aliases(meta.get("semantic_tags"))
        review_status = _normalized_text(meta.get("review_status"))
        stability_level = _normalized_text(meta.get("stability_level"))
        status = _normalized_text(meta.get("status"))
        if selector and not current.get("selector"):
            current["selector"] = selector
        if locator_type and not current.get("type"):
            current["type"] = locator_type
        if role and not current.get("role"):
            current["role"] = role
        if name:
            current["name"] = name
        current["aliases"] = _dedupe_keep_order([*current.get("aliases", []), *aliases])
        if business_type and not current.get("business_type"):
            current["business_type"] = business_type
        if business_domain and not current.get("business_domain"):
            current["business_domain"] = business_domain
        if semantic_tags:
            current["semantic_tags"] = _dedupe_keep_order([*current.get("semantic_tags", []), *semantic_tags])
        if review_status and not current.get("review_status"):
            current["review_status"] = review_status
        if stability_level and not current.get("stability_level"):
            current["stability_level"] = stability_level
        if status and not current.get("status"):
            current["status"] = status
    return normalized


def merge_page_object_with_yaml(page: str, page_object: dict[str, Any] | None) -> dict[str, Any]:
    """加载 YAML 并与传入 page_object 合并 elements。"""
    normalized_page_object = page_object if isinstance(page_object, dict) else {}
    yaml_page_object = load_page_object_yaml(page)
    merged = dict(normalized_page_object)
    merged["page"] = _normalized_text(merged.get("page")) or _normalized_page_slug(page)
    merged["elements"] = merge_page_object_elements(merged.get("elements"), yaml_page_object)
    return merged
