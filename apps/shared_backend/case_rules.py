from __future__ import annotations

import re
from typing import Any

from .case_dictionary import get_code_name_map, resolve_dictionary_name
from .case_ids import (
    build_case_metadata,
    match_case_id,
    normalize_case_id,
)
from .state_machines import (
    AI_STATUS_CODES,
    CASE_STATUS_CODES,
    MIGRATION_STATUS_CODES,
    get_case_status_name,
    get_ai_status_name,
    normalize_case_status,
    normalize_run_status,
)


PAGE_CODE_DICT = get_code_name_map("page")
MODULE_CODE_DICT = get_code_name_map("module")
CASE_TYPE_DICT = get_code_name_map("case_type")
SOURCE_DICT = get_code_name_map("source")
CASE_STATUS_DICT = {code: get_case_status_name(code) for code in CASE_STATUS_CODES}
MIGRATION_STATUS_DICT = {code: resolve_dictionary_name("migration_status", code, fallback=code) for code in MIGRATION_STATUS_CODES}

_ASCII_WORD_RE = re.compile(r"[A-Za-z]{3,}")
_CJK_RE = re.compile(r"[\u4e00-\u9fff]")
_TITLE_CODELIKE_RE = re.compile(r"^[A-Za-z0-9_-]+(?:-[A-Za-z0-9_-]+){2,}$")


class CaseRuleViolation(ValueError):
    pass


def _text(value: Any) -> str:
    return str(value or "").strip()


def _contains_cjk(text: str) -> bool:
    return bool(_CJK_RE.search(text))


def _contains_ascii_word(text: str) -> bool:
    return bool(_ASCII_WORD_RE.search(text))


def validate_case_title(title: str) -> list[str]:
    value = _text(title)
    errors: list[str] = []
    if not value:
        return ["case_title 不能为空"]
    if len(value) > 100:
        errors.append("case_title 长度不能超过 100 个字符")
    if _TITLE_CODELIKE_RE.match(value):
        errors.append("case_title 不能只是编码或英文短横线拼接")
    if not _contains_cjk(value):
        errors.append("case_title 应使用中文描述")
    if _contains_ascii_word(value):
        errors.append("case_title 不应混入明显英文单词")
    segments = [segment.strip() for segment in value.split("-") if segment.strip()]
    if len(segments) < 4:
        errors.append("case_title 至少应包含页面、模块、条件、操作、预期中的 4 段语义")
    return errors


def validate_case_description(description: str) -> list[str]:
    value = _text(description)
    if not value:
        return []
    errors: list[str] = []
    if not _contains_cjk(value):
        errors.append("description 应使用中文描述")
    return errors


def validate_case_payload(payload: dict[str, Any]) -> list[str]:
    raw = payload if isinstance(payload, dict) else {}
    errors: list[str] = []

    case_id = _text(raw.get("id") or raw.get("case_id"))
    if not case_id:
        errors.append("case_id 不能为空")
        return errors

    normalized_case_id = normalize_case_id(case_id)
    if case_id != normalized_case_id:
        errors.append("case_id 必须使用平台标准规范")
    match = match_case_id(normalized_case_id)
    if not match:
        errors.append("case_id 不符合命名规则")
        return errors

    page_code = _text(raw.get("page_code")) or match.group("page").lower()
    module_code = _text(raw.get("module_code")) or match.group("module").lower()
    case_type = _text(raw.get("case_type")) or match.group("case_type").lower()
    source = _text(raw.get("source")) or match.group("source").lower()
    status = _text(raw.get("status")).lower()
    ai_status = _text(raw.get("ai_status")).lower()
    migration_status = _text(raw.get("migration_status")).lower()

    if page_code.lower() not in PAGE_CODE_DICT:
        errors.append(f"page_code 不在平台字典中: {page_code}")
    if module_code.lower() not in MODULE_CODE_DICT:
        errors.append(f"module_code 不在平台字典中: {module_code}")
    if case_type.lower() not in CASE_TYPE_DICT:
        errors.append(f"case_type 不在平台字典中: {case_type}")
    if source.lower() not in SOURCE_DICT:
        errors.append(f"source 不在平台字典中: {source}")
    if status and status not in CASE_STATUS_DICT:
        errors.append(f"status 不在平台字典中: {status}")
    if ai_status and ai_status not in AI_STATUS_CODES:
        errors.append(f"ai_status 不在平台字典中: {ai_status}")
    if migration_status and migration_status not in MIGRATION_STATUS_DICT:
        errors.append(f"migration_status 不在平台字典中: {migration_status}")

    errors.extend(validate_case_title(_text(raw.get("title") or raw.get("case_title"))))
    errors.extend(validate_case_description(_text(raw.get("description"))))
    return errors


def enrich_case_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    raw = dict(payload if isinstance(payload, dict) else {})
    raw.pop("case_id", None)
    case_id = normalize_case_id(_text(raw.get("id") or raw.get("case_id")))
    match = match_case_id(case_id)
    if not match:
        return raw

    raw_page = _text(((raw.get("execution") or {}) if isinstance(raw.get("execution"), dict) else {}).get("page")) or _text(raw.get("page"))
    raw_module = _text(raw.get("module"))
    title = _text(raw.get("title") or raw.get("case_title"))
    description = _text(raw.get("description"))
    tags = raw.get("tags")
    source_hint = _text(raw.get("source_hint") or raw.get("created_by") or raw.get("source"))
    metadata = build_case_metadata(
        page=raw_page or match.group("page").lower(),
        module=raw_module or match.group("module").lower(),
        title=title,
        description=description,
        tags=tags,
        project=match.group("project").lower(),
        client=match.group("client").lower(),
        source_hint=source_hint,
        legacy=match.group("source").lower() == "imp",
    )
    page_code = _text(raw.get("page_code")) or metadata["page_code"]
    module_code = _text(raw.get("module_code")) or metadata["module_code"]
    case_type = _text(raw.get("case_type")) or metadata["case_type"]
    source = _text(raw.get("source")) or metadata["source"]

    raw["id"] = case_id
    raw["project"] = match.group("project").lower()
    raw["client"] = match.group("client").lower()
    raw["page_code"] = page_code.lower()
    raw["page_name"] = PAGE_CODE_DICT.get(page_code.lower(), raw.get("page_name") or metadata["page_name"])
    raw["module_code"] = module_code.lower()
    raw["module_name"] = MODULE_CODE_DICT.get(module_code.lower(), raw.get("module_name") or metadata["module_name"])
    raw["case_type"] = case_type.lower()
    raw["case_type_name"] = CASE_TYPE_DICT.get(case_type.lower(), raw.get("case_type_name") or metadata["case_type_name"])
    raw["source"] = source.lower()
    raw["source_name"] = SOURCE_DICT.get(source.lower(), raw.get("source_name") or metadata["source_name"])
    raw["status"] = normalize_case_status(raw.get("status"), fallback="automated" if str(raw.get("status", "")).strip().lower() == "automated" else "ready")
    raw["status_name"] = get_case_status_name(raw["status"])
    raw["created_by"] = _text(raw.get("created_by")) or ("AI" if raw["source"] in {"ai", "cv", "fb"} else "HUMAN")
    raw["change_source"] = _text(raw.get("change_source")) or ("AI" if raw["source"] in {"ai", "cv", "fb"} else "HUMAN")
    ai_status = _text(raw.get("ai_status")).lower() or "generated"
    raw["ai_status"] = ai_status
    raw["ai_status_name"] = get_ai_status_name(ai_status)
    if raw.get("run_status") is not None:
        raw["run_status"] = normalize_run_status(raw.get("run_status"))
    return raw
