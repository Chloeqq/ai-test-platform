# mypy: ignore-errors

import os
import logging
from pathlib import Path

from runner.data_expander import expand_test_case
from runner.paths import AI_GENERATED_CASES_ROOT, SMOKE_TEST_CASES_ROOT
from runner.yaml_loader import load_validated_yaml_file, load_yaml_files

LOGGER = logging.getLogger(__name__)


def _text(value) -> str:
    return str(value or "").strip()


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


def _formal_ai_case_identity_error(case: dict) -> str:
    """正式 AI YAML 必须来自测试点资产，Runner 不接受临时来源进入执行。"""
    requirement = case.get("requirement") if isinstance(case.get("requirement"), dict) else {}
    execution = case.get("execution") if isinstance(case.get("execution"), dict) else {}
    source_asset_id = _text(requirement.get("source_asset_id") or case.get("source_asset_id"))
    intent_id = _text(requirement.get("intent_id"))
    selected_ids = execution.get("selected_intent_ids") if isinstance(execution.get("selected_intent_ids"), list) else []
    normalized_selected_ids = {_text(item) for item in selected_ids if _text(item)}
    if source_asset_id and intent_id and normalized_selected_ids == {intent_id}:
        return ""
    return (
        "Formal AI generated case requires requirement.source_asset_id, "
        "requirement.intent_id and exactly one execution.selected_intent_ids item"
    )


def _has_formal_ai_case_marker(case: dict) -> bool:
    """RUN_MODE=all 会混合 smoke 与 AI，用标识判断哪些用例需要执行正式门禁。"""
    tags = case.get("tags") if isinstance(case.get("tags"), list) else []
    normalized_tags = {_text(tag).lower() for tag in tags if _text(tag)}
    case_id = _text(case.get("id")).lower()
    return "ai-generated" in normalized_tags or "-ai-" in case_id


def _filter_formal_ai_cases_by_source_identity(
    raw_cases: list[dict],
    selected_mode: str,
    *,
    selected_case_id: str,
    selected_case_path: str,
) -> list[dict]:
    """只对正式 AI 执行入口加门禁，避免误伤 smoke 用例。

    规则：
    - 显式执行单用例（case_path/case_id）时，身份缺失直接失败，防止误跑临时脚本。
    - 批量目录扫描时，跳过坏用例并记录告警，避免全量被单条历史脏数据阻断。
    """
    if selected_mode not in {"ai", "all"}:
        return raw_cases
    valid_cases: list[dict] = []
    invalid_case_ids: list[str] = []
    for case in raw_cases:
        if not isinstance(case, dict):
            valid_cases.append(case)
            continue
        if selected_mode == "all" and not _has_formal_ai_case_marker(case):
            valid_cases.append(case)
            continue
        identity_error = _formal_ai_case_identity_error(case)
        if identity_error:
            case_id = _text(case.get("id")) or "<unknown>"
            if selected_case_path or selected_case_id:
                raise ValueError(f"{identity_error}: {case_id}")
            invalid_case_ids.append(case_id)
            continue
        valid_cases.append(case)
    if invalid_case_ids:
        LOGGER.warning(
            "skip %s formal AI case(s) due to missing source identity: %s",
            len(invalid_case_ids),
            ", ".join(invalid_case_ids),
        )
    return valid_cases


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

    raw_cases = _filter_formal_ai_cases_by_source_identity(
        raw_cases,
        selected_mode,
        selected_case_id=selected_case_id,
        selected_case_path=selected_case_path,
    )

    test_cases = []

    for case in raw_cases:
        test_cases.extend(expand_test_case(case))

    if selected_case_id:
        test_cases = [case for case in test_cases if case.get("id") == selected_case_id]

    return test_cases
