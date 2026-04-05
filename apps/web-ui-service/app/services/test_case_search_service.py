from __future__ import annotations

import shlex
from dataclasses import dataclass

from app.services.test_case_data_service import normalize_status, normalize_test_case_type


@dataclass(frozen=True)
class ParsedTestCaseSearch:
    keyword: str
    test_type: str
    status: str
    creator: str
    last_result: str


_FIELD_ALIASES = {
    "type": "test_type",
    "test_type": "test_type",
    "类型": "test_type",
    "测试类型": "test_type",
    "status": "status",
    "状态": "status",
    "creator": "creator",
    "owner": "creator",
    "创建人": "creator",
    "结果": "last_result",
    "执行结果": "last_result",
    "result": "last_result",
    "last_result": "last_result",
}

_TEST_TYPE_ALIASES = {
    "ui": "ui",
    "web": "ui",
    "界面": "ui",
    "页面": "ui",
    "api": "api",
    "接口": "api",
    "mobile": "mobile",
    "app": "mobile",
    "移动端": "mobile",
    "database": "database",
    "db": "database",
    "数据库": "database",
}

_STATUS_ALIASES = {
    "active": "active",
    "enabled": "active",
    "启用": "active",
    "inactive": "inactive",
    "disabled": "inactive",
    "停用": "inactive",
    "禁用": "inactive",
    "deprecated": "deprecated",
    "archive": "deprecated",
    "archived": "deprecated",
    "废弃": "deprecated",
    "已废弃": "deprecated",
}

_RESULT_ALIASES = {
    "通过": "passed",
    "passed": "passed",
    "pass": "passed",
    "失败": "failed",
    "failed": "failed",
    "fail": "failed",
    "跳过": "skipped",
    "skipped": "skipped",
    "skip": "skipped",
    "未知": "unknown",
    "unknown": "unknown",
}


def _normalize_field_name(key: str) -> str:
    text = str(key or "").strip().lower()
    return _FIELD_ALIASES.get(text, "")


def _normalize_field_value(field: str, value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if field == "test_type":
        normalized = _TEST_TYPE_ALIASES.get(text.lower(), text)
        return normalize_test_case_type(normalized)
    if field == "status":
        normalized = _STATUS_ALIASES.get(text.lower(), "")
        return normalize_status(normalized) if normalized else ""
    if field == "last_result":
        return _RESULT_ALIASES.get(text.strip().lower(), "")
    return text


def parse_test_case_search_query(raw_query: str) -> ParsedTestCaseSearch:
    normalized_query = str(raw_query or "").replace("：", ":").strip()
    if not normalized_query:
        return ParsedTestCaseSearch(keyword="", test_type="", status="", creator="", last_result="")

    try:
        tokens = shlex.split(normalized_query)
    except ValueError:
        tokens = normalized_query.split()

    keyword_parts: list[str] = []
    parsed_values = {
        "test_type": "",
        "status": "",
        "creator": "",
        "last_result": "",
    }

    for token in tokens:
        if ":" not in token:
            keyword_parts.append(token)
            continue
        key, value = token.split(":", 1)
        field = _normalize_field_name(key)
        if not field or not value.strip():
            keyword_parts.append(token)
            continue
        normalized_value = _normalize_field_value(field, value)
        if not normalized_value:
            keyword_parts.append(token)
            continue
        parsed_values[field] = normalized_value

    return ParsedTestCaseSearch(
        keyword=" ".join(keyword_parts).strip(),
        test_type=parsed_values["test_type"],
        status=parsed_values["status"],
        creator=parsed_values["creator"],
        last_result=parsed_values["last_result"],
    )


def build_test_case_search_context(
    *,
    keyword: str,
    product_line: str,
    module: str,
    test_type: str,
    status: str,
    creator: str,
    last_result: str,
) -> dict[str, str]:
    return {
        "keyword": str(keyword or "").strip(),
        "product_line": str(product_line or "").strip(),
        "module": str(module or "").strip(),
        "test_type": str(test_type or "").strip(),
        "status": str(status or "").strip(),
        "creator": str(creator or "").strip(),
        "last_result": str(last_result or "").strip(),
    }
