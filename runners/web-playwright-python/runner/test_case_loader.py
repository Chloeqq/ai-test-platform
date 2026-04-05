# mypy: ignore-errors

import os
from pathlib import Path

from runner.data_expander import expand_test_case
from runner.paths import AI_GENERATED_CASES_ROOT, SMOKE_TEST_CASES_ROOT
from runner.yaml_loader import load_yaml_file, load_yaml_files


def load_ai_generated_test_cases(
    case_id: str | None = None,
    case_path: str | None = None,
) -> list[dict]:
    return load_expanded_test_cases("ai", case_id=case_id, case_path=case_path)


def _ensure_case_path_allowed(selected_mode: str, selected_case_path: str) -> None:
    if not selected_case_path:
        return

    resolved_path = Path(selected_case_path).resolve()
    allowed_root = None

    if selected_mode == "ai":
        allowed_root = AI_GENERATED_CASES_ROOT.resolve()
    elif selected_mode == "smoke":
        allowed_root = SMOKE_TEST_CASES_ROOT.resolve()

    if allowed_root is None:
        return

    try:
        resolved_path.relative_to(allowed_root)
    except ValueError as exc:
        raise ValueError(
            f"TEST_CASE_PATH must stay under {allowed_root} when RUN_MODE={selected_mode}: {resolved_path}"
        ) from exc


def load_expanded_test_cases(
    run_mode: str | None = None,
    case_id: str | None = None,
    case_path: str | None = None,
) -> list[dict]:
    selected_mode = (run_mode or os.getenv("RUN_MODE", "ai")).strip().lower()
    selected_case_id = (case_id or os.getenv("TEST_CASE_ID", "")).strip()
    selected_case_path = (case_path or os.getenv("TEST_CASE_PATH", "")).strip()
    raw_cases = []

    _ensure_case_path_allowed(selected_mode, selected_case_path)

    if selected_case_path:
        raw_case = load_yaml_file(selected_case_path)
        if raw_case is None:
            raise ValueError(f"Test case file is empty: {selected_case_path}")
        raw_cases.append(raw_case)
    elif selected_mode == "smoke":
        raw_cases.extend(load_yaml_files(SMOKE_TEST_CASES_ROOT))
    elif selected_mode == "ai":
        raw_cases.extend(load_yaml_files(AI_GENERATED_CASES_ROOT))
    elif selected_mode == "all":
        raw_cases.extend(load_yaml_files(SMOKE_TEST_CASES_ROOT))
        raw_cases.extend(load_yaml_files(AI_GENERATED_CASES_ROOT))
    else:
        raise ValueError(f"Unsupported RUN_MODE: {selected_mode}")

    test_cases = []

    for case in raw_cases:
        test_cases.extend(expand_test_case(case))

    if selected_case_id:
        test_cases = [case for case in test_cases if case.get("id") == selected_case_id]

    return test_cases
