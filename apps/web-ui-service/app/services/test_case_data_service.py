from __future__ import annotations

import os
from collections.abc import Sequence
from typing import Any, TypeAlias

from app.schemas.test_case import TestCaseDataConfig
from shared_backend.step_fields import STEP_FIELD_NAMES

DataConfigValue: TypeAlias = bool | list[str] | list[list[str]]
DataConfigPayload: TypeAlias = dict[str, DataConfigValue]


def _env_flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def normalize_tags(tags: list[str]) -> list[str]:
    normalized: list[str] = []
    for item in tags:
        value = str(item).strip()
        if value and value not in normalized:
            normalized.append(value)
    return normalized


def normalize_markers(markers: list[str]) -> list[str]:
    return normalize_tags(markers)


def normalize_text_list(values: Sequence[Any] | None) -> list[str]:
    normalized: list[str] = []
    for item in values or []:
        value = str(item).strip()
        if value and value not in normalized:
            normalized.append(value)
    return normalized


def normalize_case_ids(values: Sequence[Any] | None) -> list[str]:
    normalized: list[str] = []
    for item in values or []:
        value = str(item).strip()
        if value and value not in normalized:
            normalized.append(value)
    return normalized


def normalize_optional_text(value: Any) -> str:
    return str(value or "").strip()


def normalize_test_steps(steps: Sequence[Any] | None) -> list[dict[str, Any]]:
    if not _env_flag("NORMALIZE_TEST_STEPS_ENABLED", True):
        passthrough: list[dict[str, Any]] = []
        for step in steps or []:
            if isinstance(step, dict):
                row = dict(step)
                if row:
                    passthrough.append(row)
                continue
            text = str(step or "").strip()
            if text:
                passthrough.append({"description": text})
        return passthrough

    normalized: list[dict[str, Any]] = []
    # 字段列表来自 shared_backend/step_fields.py（唯一事实源），需要和
    # `yaml_testcase.schema.json` 的步骤字段保持一致。`test_steps` 只是
    # `script_code` 的派生投影，但详情页、步骤表和失败分析都会读取它；
    # 如果这里过滤掉 DSL 字段，下游展示就会和唯一事实源不一致。
    for step in steps or []:
        if not isinstance(step, dict):
            continue
        row = {key: step.get(key) for key in STEP_FIELD_NAMES if str(step.get(key, "")).strip()}
        if "expected" not in row and str(row.get("expected_result", "")).strip():
            row["expected"] = str(row.get("expected_result", "")).strip()
        if row:
            normalized.append(row)
    return normalized


def render_test_steps_text(steps: Sequence[dict[str, Any]] | None) -> str:
    lines: list[str] = []
    for index, step in enumerate(steps or [], start=1):
        if not isinstance(step, dict):
            continue
        parts = [
            str(step.get("description", "")).strip(),
            str(step.get("action", "")).strip(),
            str(step.get("target", "")).strip(),
            str(step.get("value", "")).strip(),
            str(step.get("expected", "")).strip() or str(step.get("expected_result", "")).strip(),
        ]
        content = " | ".join(part for part in parts if part)
        if content:
            lines.append(f"Step{index} {content}")
    return "\n".join(lines)


def normalize_report_url(report_url: str, execution_id: int) -> str:
    value = str(report_url or "").strip()
    if value.startswith("http://") or value.startswith("https://"):
        return value
    if value.startswith("/react/execution/results/"):
        return value
    if value.startswith("/execution/results/"):
        return f"/react{value}"
    return f"/react/execution/results/{execution_id}"


def positive_ids(values: Sequence[Any]) -> list[int]:
    ids: list[int] = []
    for raw in values:
        try:
            value = int(raw)
        except (TypeError, ValueError):
            continue
        if value > 0 and value not in ids:
            ids.append(value)
    return ids


def normalize_data_config(data_config: TestCaseDataConfig | None) -> DataConfigPayload:
    payload = data_config or TestCaseDataConfig()
    parameters = normalize_tags(payload.parameters)

    normalized_rows: list[list[str]] = []
    expected_width = len(parameters)
    for row in payload.rows:
        values = [str(item).strip() for item in (row or [])]
        if not any(values):
            continue
        if expected_width and len(values) < expected_width:
            values.extend([""] * (expected_width - len(values)))
        if expected_width:
            values = values[:expected_width]
        normalized_rows.append(values)

    enabled = bool(payload.enabled and parameters and normalized_rows)
    return {
        "enabled": enabled,
        "parameters": parameters,
        "rows": normalized_rows if enabled else [],
    }


def normalize_test_case_type(test_type: str | None) -> str:
    normalized = str(test_type or "").strip().lower()
    return normalized or "ui"


def normalize_status(status_value: str | None) -> str:
    normalized = str(status_value or "").strip().lower() or "active"
    if normalized not in {"active", "inactive", "deprecated"}:
        return "active"
    return normalized


def _data_config_literal(data_config: DataConfigPayload) -> str:
    import json

    return json.dumps(data_config, ensure_ascii=False, indent=2)


def _sanitize_py_identifier(value: str) -> str:
    raw = str(value or "").strip().lower()
    if not raw:
        return "field"
    chars: list[str] = []
    for index, ch in enumerate(raw):
        if ch.isalnum() or ch == "_":
            if index == 0 and ch.isdigit():
                chars.append("_")
            chars.append(ch)
        else:
            chars.append("_")
    normalized = "".join(chars).strip("_") or "field"
    if normalized[0].isdigit():
        normalized = f"_{normalized}"
    return normalized


def compose_data_driven_script(original_script: str, data_config: DataConfigPayload) -> str:
    if not bool(data_config.get("enabled")):
        return original_script

    parameters = data_config.get("parameters", [])
    rows = data_config.get("rows", [])
    if not isinstance(parameters, list) or not isinstance(rows, list) or not parameters or not rows:
        return original_script

    if original_script.strip():
        header = (
            "# Data-driven configuration injected by platform.\n"
            "# You can consume DATA_CONFIG in your custom script.\n"
            f"DATA_CONFIG = {_data_config_literal(data_config)}\n\n"
        )
        return f"{header}{original_script.strip()}\n"

    safe_parameters: list[str] = []
    for item in parameters:
        candidate = _sanitize_py_identifier(str(item))
        if candidate in safe_parameters:
            suffix = 2
            while f"{candidate}_{suffix}" in safe_parameters:
                suffix += 1
            candidate = f"{candidate}_{suffix}"
        safe_parameters.append(candidate)

    parameter_names = ", ".join(safe_parameters)
    case_rows = ",\n".join(
        f"    {repr(tuple(str(column) for column in row))}"
        for row in rows
        if isinstance(row, list)
    )
    return (
        "import pytest\n\n"
        f"@pytest.mark.parametrize(\"{parameter_names}\", [\n{case_rows}\n])\n"
        f"def test_data_driven_case({parameter_names}):\n"
        "    assert True  # placeholder — add real assertions\n"
    )


def refresh_existing_data_driven_script(original_script: str, data_config: DataConfigPayload) -> str:
    script = (original_script or "").lstrip()
    if not bool(data_config.get("enabled")):
        return original_script

    if script.startswith("# Data-driven configuration injected by platform."):
        lines = script.splitlines()
        index = 0
        while index < len(lines):
            current = lines[index].strip()
            if current.startswith("# Data-driven configuration injected by platform."):
                index += 1
                continue
            if current.startswith("# You can consume DATA_CONFIG"):
                index += 1
                continue
            if current.startswith("DATA_CONFIG ="):
                index += 1
                continue
            if not current:
                index += 1
                continue
            break
        remainder = "\n".join(lines[index:])
        if remainder.strip():
            return compose_data_driven_script(remainder, data_config)
        return compose_data_driven_script("", data_config)

    if script.startswith("import pytest\n\n@pytest.mark.parametrize("):
        return compose_data_driven_script("", data_config)

    return original_script


def generate_ai_script(requirement: str, module: str) -> str:
    normalized_requirement = requirement.strip() or "请补充需求"
    return (
        f"def test_ai_generated_{module.lower().replace(' ', '_')}(page):\n"
        f"    # AI根据需求生成：{normalized_requirement}\n"
        "    page.goto('/')\n"
        "    assert page.title() is not None  # placeholder — add steps per requirement\n"
    )
