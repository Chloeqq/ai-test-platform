from __future__ import annotations

from typing import Any

from app.services import workbench_state_store as _state_store

_PROXY_NAMES = {
    "REPO_ROOT",
    "WEB_UI_STATE_ROOT",
    "WEB_UI_DEFAULT_STATE_DIR",
    "WEB_UI_RUNS_DIR",
    "WEB_UI_REPORTING_DIR",
    "TEST_POINTS_ROOT",
    "ASSETS_CASES_ROOT",
    "AI_CASES_ROOT",
    "PAGE_OBJECTS_ROOT",
    "RUNNER_ROOT",
    "ALLURE_RESULTS_ROOT",
    "ALLURE_REPORT_ROOT",
    "ALLURE_SNAPSHOTS_ROOT",
    "EXECUTION_REPORTS_ROOT",
    "HISTORY_FILE",
    "RUNTIME_RUNS_FILE",
    "DEFECT_LINKS_FILE",
    "REVIEW_DECISIONS_FILE",
    "EXECUTION_GATE_DECISIONS_FILE",
    "FAILURE_SOURCE_CALIBRATIONS_FILE",
    "PAGE_ALIAS_MAP",
    "PAGE_CANONICAL_HASH_ROUTE",
    "PAGE_FRIENDLY_NAME",
    "PAGE_OBJECT_DEFAULTS",
}
def __getattr__(name: str) -> Any:
    if hasattr(_state_store, name):
        return getattr(_state_store, name)
    raise AttributeError(name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | _PROXY_NAMES)


__all__ = sorted(_PROXY_NAMES)
