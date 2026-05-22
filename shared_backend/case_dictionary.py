"""用例字典加载与编码/别名解析（page、module、case_type 等）。"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


_DATA_PATH = Path(__file__).resolve().parent / "data" / "case_dictionaries.json"


def _normalize_items(items: Any) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    if not isinstance(items, list):
        return normalized
    for item in items:
        if not isinstance(item, dict):
            continue
        code = str(item.get("code", "")).strip().lower()
        if not code:
            continue
        aliases_value = item.get("aliases")
        aliases_raw: list[Any] = aliases_value if isinstance(aliases_value, list) else []
        normalized.append(
            {
                "code": code,
                "name": str(item.get("name", code)).strip() or code,
                "enabled": bool(item.get("enabled", True)),
                "aliases": [
                    str(alias).strip().lower()
                    for alias in aliases_raw
                    if str(alias).strip()
                ],
            }
        )
    return normalized


@lru_cache(maxsize=1)
def load_case_dictionaries() -> dict[str, list[dict[str, Any]]]:
    """加载并缓存 case_dictionaries.json，按 kind 分组。"""
    raw = json.loads(_DATA_PATH.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        return {}
    return {str(kind).strip().lower(): _normalize_items(items) for kind, items in raw.items()}


def get_dictionary_items(kind: str) -> list[dict[str, Any]]:
    """返回某类字典项列表（如 page、module）。"""
    return list(load_case_dictionaries().get(str(kind).strip().lower(), []))


def get_code_name_map(kind: str) -> dict[str, str]:
    """code → 显示名，仅含 enabled 项。"""
    return {item["code"]: item["name"] for item in get_dictionary_items(kind) if item.get("enabled", True)}


def get_alias_code_map(kind: str) -> dict[str, str]:
    """别名（小写）→ 标准 code。"""
    alias_map: dict[str, str] = {}
    for item in get_dictionary_items(kind):
        if not item.get("enabled", True):
            continue
        code = item["code"]
        alias_map[code] = code
        for alias in item.get("aliases", []):
            alias_map[str(alias).strip().lower()] = code
    return alias_map


def get_enabled_codes(kind: str) -> set[str]:
    """某类字典下所有 enabled 的 code 集合。"""
    return {item["code"] for item in get_dictionary_items(kind) if item.get("enabled", True)}


def resolve_dictionary_code(kind: str, value: str, *, fallback: str = "") -> str:
    """将 value（含别名）解析为标准 code，未命中则 fallback。"""
    normalized = str(value or "").strip().lower()
    if not normalized:
        return str(fallback or "").strip().lower()
    return get_alias_code_map(kind).get(normalized, str(fallback or "").strip().lower())


def resolve_dictionary_name(kind: str, code: str, *, fallback: str = "") -> str:
    """由 code 查显示名，未命中则 fallback 或 code 本身。"""
    normalized = str(code or "").strip().lower()
    if not normalized:
        return fallback
    return get_code_name_map(kind).get(normalized, fallback or normalized)
