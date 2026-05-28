from __future__ import annotations

"""线程安全包装层。

对 app.services.workbench_state_store 的 FILE_LOCK 包装，
供 facade 层使用。业务代码应 import 本模块而非直接 import state_store。

关系：store.py（本文件）= state_store 的线程安全外观。
"""

import os
import threading
import time
from pathlib import Path
from typing import Any

from app.services import workbench_state_store as state_store

REPO_ROOT = state_store.REPO_ROOT
WEB_UI_STATE_ROOT = state_store.WEB_UI_STATE_ROOT
WEB_UI_DEFAULT_STATE_DIR = state_store.WEB_UI_DEFAULT_STATE_DIR
WEB_UI_RUNS_DIR = state_store.WEB_UI_RUNS_DIR
WEB_UI_REPORTING_DIR = state_store.WEB_UI_REPORTING_DIR
TEST_POINTS_ROOT = state_store.TEST_POINTS_ROOT
ASSETS_CASES_ROOT = state_store.ASSETS_CASES_ROOT
AI_CASES_ROOT = state_store.AI_CASES_ROOT
ALLURE_SNAPSHOTS_ROOT = state_store.ALLURE_SNAPSHOTS_ROOT
HISTORY_FILE = state_store.HISTORY_FILE
RUNTIME_RUNS_FILE = state_store.RUNTIME_RUNS_FILE
DEFECT_LINKS_FILE = state_store.DEFECT_LINKS_FILE
REVIEW_DECISIONS_FILE = state_store.REVIEW_DECISIONS_FILE
EXECUTION_GATE_DECISIONS_FILE = state_store.EXECUTION_GATE_DECISIONS_FILE
FAILURE_SOURCE_CALIBRATIONS_FILE = state_store.FAILURE_SOURCE_CALIBRATIONS_FILE
FILE_LOCK = state_store.FILE_LOCK
RUN_JOB_TTL_SECONDS = int(str(os.getenv("WORKBENCH_RUN_JOB_CACHE_TTL_SECONDS", "300")).strip() or "300")

_RUN_LOCK = threading.Lock()
_RUN_JOBS: dict[str, dict[str, Any]] = {}


from shared_backend.type_utils import now_iso  # noqa: F401 — 重新导出为模块级函数
now_iso = state_store.now_iso  # 保持兼容


def ensure_dirs() -> None:
    state_store.ensure_dirs()


def read_json_list(path: Path, db: Any = None) -> list[dict[str, Any]]:
    return state_store.read_json_list(path, db=db)


def write_json_list(path: Path, items: list[dict[str, Any]], db: Any = None) -> None:
    state_store.write_json_list(path, items, db=db)


def append_history(entry: dict[str, Any], db: Any = None) -> None:
    state_store.append_history(entry, db=db)


def append_runtime_run(entry: dict[str, Any], db: Any = None) -> None:
    state_store.append_runtime_run(entry, db=db)


def update_runtime_run(run_id: str, updates: dict[str, Any], db: Any = None) -> None:
    state_store.update_runtime_run(run_id, updates, db=db)


def list_defect_items(case_id: str = "") -> list[dict[str, Any]]:
    ensure_dirs()
    items = read_json_list(DEFECT_LINKS_FILE)
    normalized_case_id = str(case_id or "").strip()
    if normalized_case_id:
        items = [item for item in items if str(item.get("case_id", "")).strip() == normalized_case_id]
    items.sort(key=lambda item: str(item.get("linked_at", "")), reverse=True)
    return items


def read_defect_items(case_id: str = "") -> list[dict[str, Any]]:
    return list_defect_items(case_id)


def read_history_items() -> list[dict[str, Any]]:
    ensure_dirs()
    return read_json_list(HISTORY_FILE)


def read_runtime_run_items() -> list[dict[str, Any]]:
    ensure_dirs()
    return read_json_list(RUNTIME_RUNS_FILE)


def read_review_items() -> list[dict[str, Any]]:
    ensure_dirs()
    return read_json_list(REVIEW_DECISIONS_FILE)


def read_gate_decision_items() -> list[dict[str, Any]]:
    ensure_dirs()
    return read_json_list(EXECUTION_GATE_DECISIONS_FILE)


def read_failure_source_calibration_items() -> list[dict[str, Any]]:
    ensure_dirs()
    return read_json_list(FAILURE_SOURCE_CALIBRATIONS_FILE)


def write_history_items(items: list[dict[str, Any]], db: Any = None) -> None:
    write_json_list(HISTORY_FILE, items, db=db)


def write_runtime_run_items(items: list[dict[str, Any]], db: Any = None) -> None:
    write_json_list(RUNTIME_RUNS_FILE, items, db=db)


def write_defect_items(items: list[dict[str, Any]], db: Any = None) -> None:
    write_json_list(DEFECT_LINKS_FILE, items, db=db)


def write_review_items(items: list[dict[str, Any]], db: Any = None) -> None:
    write_json_list(REVIEW_DECISIONS_FILE, items, db=db)


def write_gate_decision_items(items: list[dict[str, Any]], db: Any = None) -> None:
    write_json_list(EXECUTION_GATE_DECISIONS_FILE, items, db=db)


def write_failure_source_calibration_items(items: list[dict[str, Any]], db: Any = None) -> None:
    write_json_list(FAILURE_SOURCE_CALIBRATIONS_FILE, items, db=db)


def clear_state_files() -> None:
    write_history_items([])
    write_runtime_run_items([])
    write_defect_items([])
    write_review_items([])
    write_gate_decision_items([])
    write_failure_source_calibration_items([])


def store_run_job(run_id: str, job: dict[str, Any]) -> None:
    normalized_run_id = str(run_id or "").strip()
    if not normalized_run_id:
        return
    with _RUN_LOCK:
        _RUN_JOBS[normalized_run_id] = dict(job)


def update_run_job(run_id: str, updates: dict[str, Any]) -> None:
    normalized_run_id = str(run_id or "").strip()
    if not normalized_run_id:
        return
    with _RUN_LOCK:
        job = _RUN_JOBS.get(normalized_run_id)
        if not job:
            return
        merged = dict(job)
        merged.update(updates if isinstance(updates, dict) else {})
        merged["_cache_updated_at"] = time.time()
        _RUN_JOBS[normalized_run_id] = merged


def get_run_job(run_id: str) -> dict[str, Any] | None:
    normalized_run_id = str(run_id or "").strip()
    if not normalized_run_id:
        return None
    with _RUN_LOCK:
        job = _RUN_JOBS.get(normalized_run_id)
        if not job:
            return None
        cache_updated_at = float(job.get("_cache_updated_at", 0.0) or 0.0)
        if RUN_JOB_TTL_SECONDS > 0 and cache_updated_at > 0 and (time.time() - cache_updated_at) > RUN_JOB_TTL_SECONDS:
            _RUN_JOBS.pop(normalized_run_id, None)
            return None
        return dict(job)


def list_run_jobs() -> list[dict[str, Any]]:
    with _RUN_LOCK:
        return [dict(item) for item in _RUN_JOBS.values()]
