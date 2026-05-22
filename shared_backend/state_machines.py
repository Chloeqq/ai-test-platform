"""用例、运行与 AI 状态码的规范化及字典显示名查询。"""
from __future__ import annotations

from typing import Any

from .case_dictionary import get_enabled_codes, resolve_dictionary_name


CASE_STATUS_CODES = get_enabled_codes("case_status")
RUN_STATUS_CODES = get_enabled_codes("run_status")
AI_STATUS_CODES = get_enabled_codes("ai_status")
MIGRATION_STATUS_CODES = get_enabled_codes("migration_status")

CASE_STATE_TRANSITIONS = {
    "draft": {"review", "ready", "deprecated"},
    "review": {"ready", "draft", "deprecated"},
    "ready": {"deprecated", "review"},
    "deprecated": set(),
    "automated": set(),
}

RUN_STATE_TRANSITIONS = {
    "queued": {"running", "blocked", "skipped"},
    "running": {"passed", "failed", "blocked", "skipped"},
    "generated": {"queued", "running", "passed", "failed", "blocked", "skipped"},
    "passed": set(),
    "failed": set(),
    "blocked": set(),
    "skipped": set(),
}

AI_STATE_TRANSITIONS = {
    "generated": {"reviewed", "accepted", "rejected"},
    "reviewed": {"accepted", "rejected"},
    "accepted": set(),
    "rejected": set(),
}


def normalize_case_status(value: Any, *, fallback: str = "ready") -> str:
    """将任意状态值规范为字典内的 case_status code。"""
    normalized = str(value or "").strip().lower()
    return normalized if normalized in CASE_STATUS_CODES else fallback


def normalize_run_status(value: Any, *, fallback: str = "generated") -> str:
    """将任意状态值规范为字典内的 run_status code。"""
    normalized = str(value or "").strip().lower()
    return normalized if normalized in RUN_STATUS_CODES else fallback



def get_case_status_name(code: str) -> str:
    """case_status code 的显示名。"""
    return resolve_dictionary_name("case_status", code, fallback=str(code or "").strip())


def get_run_status_name(code: str) -> str:
    """run_status code 的显示名。"""
    return resolve_dictionary_name("run_status", code, fallback=str(code or "").strip())


def get_ai_status_name(code: str) -> str:
    """ai_status code 的显示名。"""
    return resolve_dictionary_name("ai_status", code, fallback=str(code or "").strip())

