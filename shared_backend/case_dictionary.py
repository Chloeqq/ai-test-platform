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
    raw = json.loads(_DATA_PATH.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        return {}
    return {str(kind).strip().lower(): _normalize_items(items) for kind, items in raw.items()}


def get_dictionary_items(kind: str) -> list[dict[str, Any]]:
    return list(load_case_dictionaries().get(str(kind).strip().lower(), []))


def get_code_name_map(kind: str) -> dict[str, str]:
    return {item["code"]: item["name"] for item in get_dictionary_items(kind) if item.get("enabled", True)}


def get_alias_code_map(kind: str) -> dict[str, str]:
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
    return {item["code"] for item in get_dictionary_items(kind) if item.get("enabled", True)}


def resolve_dictionary_code(kind: str, value: str, *, fallback: str = "") -> str:
    normalized = str(value or "").strip().lower()
    if not normalized:
        return str(fallback or "").strip().lower()
    return get_alias_code_map(kind).get(normalized, str(fallback or "").strip().lower())


def resolve_dictionary_name(kind: str, code: str, *, fallback: str = "") -> str:
    normalized = str(code or "").strip().lower()
    if not normalized:
        return fallback
    return get_code_name_map(kind).get(normalized, fallback or normalized)
