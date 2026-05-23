# mypy: ignore-errors

import os
from pathlib import Path

from runner.data_expander import expand_test_case
from runner.paths import AI_GENERATED_CASES_ROOT, SMOKE_TEST_CASES_ROOT
from runner.yaml_loader import load_validated_yaml_file, load_yaml_files


def _extra_allowed_roots() -> list[Path]:
    roots: list[Path] = []
    for raw_root in os.getenv("TEST_CASE_ALLOWED_ROOTS", "").split(os.pathsep):
        value = raw_root.strip()
        if value:
            roots.append(Path(value).expanduser().resolve())
    return roots


def load_ai_generated_test_cases(
    case_id: str | None = None,
    case_path: str | None = None,
) -> list[dict]:
    return load_expanded_test_cases("ai", case_id=case_id, case_path=case_path)


def _ensure_case_path_allowed(selected_mode: str, selected_case_path: str) -> None:
    if not selected_case_path:
        return

    resolved_path = Path(selected_case_path).resolve()
    allowed_roots: list[Path] = []

    if selected_mode == "ai":
        allowed_roots.append(AI_GENERATED_CASES_ROOT.resolve())
    elif selected_mode == "smoke":
        allowed_roots.append(SMOKE_TEST_CASES_ROOT.resolve())
    allowed_roots.extend(_extra_allowed_roots())

    if not allowed_roots:
        return

    for allowed_root in allowed_roots:
        try:
            resolved_path.relative_to(allowed_root)
            return
        except ValueError:
            continue
    allowed_text = ", ".join(str(root) for root in allowed_roots)
    raise ValueError(
        f"TEST_CASE_PATH must stay under one of [{allowed_text}] when RUN_MODE={selected_mode}: {resolved_path}"
    )


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
        raw_cases.append(load_validated_yaml_file(Path(selected_case_path)))
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
