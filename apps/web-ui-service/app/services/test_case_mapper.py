from __future__ import annotations

import csv
import io
import json
import re
from pathlib import Path
from typing import Any, Callable, TypeAlias

import yaml

from app.models.test_case import TestCase, TestCaseDefect, TestCaseExecution, TestCaseVersion
from app.schemas.test_case import TestCaseDataConfig
from shared_backend.type_utils import str_value as _text

DataConfigValue: TypeAlias = bool | list[str] | list[list[str]]
DataConfigPayload: TypeAlias = dict[str, DataConfigValue]
PaginationPayload: TypeAlias = dict[str, int | bool | None]
FilterOptionsPayload: TypeAlias = dict[str, list[str]]
SearchContextPayload: TypeAlias = dict[str, str]
StatsPayload: TypeAlias = dict[str, int | float]
NormalizeReportUrl: TypeAlias = Callable[[str, int], str]
NormalizeDataConfig: TypeAlias = Callable[[TestCaseDataConfig | None], DataConfigPayload]
REPO_ROOT = Path(__file__).resolve().parents[4]
GENERIC_EXPECTED_TEXT = "系统应给出符合业务规则的反馈。"
SECTION_LABELS = {
    "测试意图": "test_intent",
    "测试类型": "test_type",
    "前置条件": "precondition",
    "操作步骤": "operation_steps",
    "涉及元素": "involved_elements",
    "断言点": "assertion_points",
    "整体预期结果": "overall_expected",
    "预期结果": "overall_expected",
}


def _list_value(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _string_list_value(value: object) -> list[str]:
    """将 DSL 中可能是字符串或数组的字段统一成可展示文本列表。"""
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value or "").strip()
    return [text] if text else []



def _clean_inline_item(value: str) -> str:
    cleaned = re.sub(r"^\s*[-*•·]+\s*", "", str(value or "").strip())
    cleaned = re.sub(r"^\s*\d+\s*[\.\)、]\s*", "", cleaned)
    return cleaned.strip()


def _split_inline_items(value: str, *, separators: str = r"[，,；;]") -> list[str]:
    text = _text(value)
    if not text:
        return []
    items = [
        item.strip(" \t\r\n。；;，,、")
        for item in re.split(separators, text)
        if item.strip(" \t\r\n。；;，,、")
    ]
    return items or [text]


def _looks_generic_expected(value: str) -> bool:
    text = _text(value)
    if not text:
        return True
    if any(token in text for token in ("测试意图：", "测试类型：", "前置条件：", "操作步骤：", "涉及元素：")):
        return True
    generic_tokens = {
        GENERIC_EXPECTED_TEXT,
        "系统应给出符合业务规则的反馈",
        "符合预期",
        "系统提示正确",
        "登录功能：",
    }
    return text in generic_tokens


def _load_case_yaml(case: TestCase) -> tuple[dict[str, Any], str]:
    source_ref = _text(case.source_ref)
    script_code = _text(case.script_code)
    if script_code:
        try:
            payload = yaml.safe_load(script_code) or {}
            if isinstance(payload, dict):
                return payload, source_ref
        except yaml.YAMLError:
            pass

    candidates: list[Path] = []
    if source_ref:
        source_path = Path(source_ref).expanduser()
        if not source_path.is_absolute():
            source_path = (REPO_ROOT / source_path).resolve()
        candidates.append(source_path)
    for candidate in candidates:
        try:
            if candidate.exists():
                payload = yaml.safe_load(candidate.read_text(encoding="utf-8")) or {}
                if isinstance(payload, dict):
                    return payload, str(candidate)
        except (OSError, yaml.YAMLError):
            continue
    return {}, source_ref


def _parse_requirement_block(raw_block: str) -> dict[str, Any]:
    sections: dict[str, Any] = {
        "raw_requirement_block": _text(raw_block),
        "requirement_scope": [],
        "test_intent": "",
        "test_type": "",
        "precondition": [],
        "operation_steps": [],
        "involved_elements": [],
        "assertion_points": [],
        "overall_expected": [],
    }
    current_section = "requirement_scope"
    for raw_line in _text(raw_block).replace("\r\n", "\n").split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        matched_key = None
        matched_value = ""
        for label, key in SECTION_LABELS.items():
            prefix_cn = f"{label}："
            prefix_en = f"{label}:"
            if line.startswith(prefix_cn):
                matched_key = key
                matched_value = line[len(prefix_cn):].strip()
                break
            if line.startswith(prefix_en):
                matched_key = key
                matched_value = line[len(prefix_en):].strip()
                break
        if matched_key:
            current_section = matched_key
            if matched_key in {"test_intent", "test_type"}:
                sections[matched_key] = matched_value
            elif matched_value:
                sections[matched_key].append(matched_value)
            continue

        if current_section in {"test_intent", "test_type"}:
            if not sections[current_section]:
                sections[current_section] = line
            else:
                sections[current_section] = f"{sections[current_section]} {line}".strip()
            continue
        sections[current_section].append(line)

    sections["requirement_scope"] = [_clean_inline_item(item) for item in sections["requirement_scope"] if _clean_inline_item(item)]
    sections["precondition"] = [_clean_inline_item(item) for item in sections["precondition"] if _clean_inline_item(item)]
    sections["operation_steps"] = [_clean_inline_item(item) for item in sections["operation_steps"] if _clean_inline_item(item)]
    sections["assertion_points"] = [_clean_inline_item(item) for item in sections["assertion_points"] if _clean_inline_item(item)]
    if sections["overall_expected"]:
        sections["overall_expected"] = [_clean_inline_item(item) for item in sections["overall_expected"] if _clean_inline_item(item)]
    involved: list[str] = []
    for item in sections["involved_elements"]:
        involved.extend(_split_inline_items(item, separators=r"[、，,/／]"))
    sections["involved_elements"] = [item for item in involved if item]
    if len(sections["precondition"]) == 1:
        sections["precondition"] = _split_inline_items(sections["precondition"][0])
    return sections


def _dedupe_keep_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for raw in items:
        item = _text(raw)
        if not item or item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered


def _requirement_rows_from_yaml(case_yaml: dict[str, Any]) -> tuple[list[str], dict[str, str]]:
    """同时兼容旧版文本 requirement 和结构化 requirement。

    详情页当前仍通过既有文本块解析器渲染需求信息。DSL V1.1 可能把
    `requirement` 存成对象，因此这里先把结构化字段转换成同样的中文标签
    行，避免退回使用可能过时的 `test_steps_text`。
    """
    raw_requirement = case_yaml.get("requirement")
    if not isinstance(raw_requirement, dict):
        return _list_value(raw_requirement), {}

    title = (
        _text(raw_requirement.get("title"))
        or _text(raw_requirement.get("summary"))
        or _text(case_yaml.get("title"))
    )
    intent_type = _text(raw_requirement.get("type") or raw_requirement.get("intent_type"))
    preconditions = _string_list_value(raw_requirement.get("precondition"))
    expected_results = _string_list_value(raw_requirement.get("expected_result"))
    involved_elements = _string_list_value(raw_requirement.get("involved_elements"))

    lines: list[str] = []
    if title:
        lines.append(f"测试意图：{title}")
    if intent_type:
        lines.append(f"测试类型：{intent_type}")
    if preconditions:
        lines.append(f"前置条件：{'，'.join(preconditions)}")
    if involved_elements:
        lines.append(f"涉及元素：{'、'.join(involved_elements)}")
    if expected_results:
        lines.append(f"整体预期结果：{'；'.join(expected_results)}")

    # 追踪元数据和展示文本分开返回，调用方无需再从自然语言中反解析
    # source asset 或 intent ID。
    metadata = {
        "intent_id": _text(raw_requirement.get("intent_id")),
        "source_asset_id": _text(raw_requirement.get("source_asset_id")),
        "source_asset_title": _text(raw_requirement.get("source_asset_title")),
    }
    rows = ["\n".join(lines)] if lines else []
    return rows, {key: value for key, value in metadata.items() if value}


def _steps_from_case_payload(case: TestCase) -> list[str]:
    raw_steps = case.test_steps if isinstance(case.test_steps, list) else []
    normalized: list[str] = []
    for index, raw in enumerate(raw_steps, start=1):
        if isinstance(raw, dict):
            action = _text(raw.get("action"))
            target = _text(raw.get("target")) or _text(raw.get("target_name")) or _text(raw.get("element"))
            value = _text(raw.get("value")) or _text(raw.get("step_data"))
            parts = [part for part in [action, target, value] if part]
            if parts:
                normalized.append(f"{index}. {' / '.join(parts)}")
            continue
        cleaned = _clean_inline_item(_text(raw))
        if cleaned:
            normalized.append(cleaned)
    if normalized:
        return normalized
    return [_clean_inline_item(item) for item in _text(case.test_steps_text).splitlines() if _clean_inline_item(item)]


def _build_detail_content(case: TestCase) -> dict[str, Any]:
    case_yaml, source_path = _load_case_yaml(case)
    requirement_rows, requirement_metadata = _requirement_rows_from_yaml(case_yaml)
    if not requirement_rows and _text(case.test_steps_text):
        requirement_rows = [_text(case.test_steps_text)]
    primary_requirement = requirement_rows[0] if requirement_rows else ""
    parsed = _parse_requirement_block(primary_requirement)

    description = _text(case_yaml.get("description")) or ""
    if "前置条件：" in description and not parsed["precondition"]:
        _, _, possible_precondition = description.partition("前置条件：")
        parsed["precondition"] = _split_inline_items(possible_precondition)
        description = description.split("前置条件：", 1)[0].strip(" 。；;，,")

    overall_expected = _dedupe_keep_order(
        list(parsed.get("overall_expected") or [])
        or ([] if _looks_generic_expected(case.expected_result) else _split_inline_items(case.expected_result))
    )
    assertion_points = _dedupe_keep_order(
        list(parsed.get("assertion_points") or [])
    )
    operation_steps = _dedupe_keep_order(list(parsed.get("operation_steps") or []))
    involved_elements = _dedupe_keep_order(list(parsed.get("involved_elements") or []))
    precondition = _dedupe_keep_order(list(parsed.get("precondition") or []))
    split_suggestions = _dedupe_keep_order(
        [item for item in requirement_rows[1:] if re.match(r"^\[P\d\]", _text(item))]
    )

    if not operation_steps:
        operation_steps = _steps_from_case_payload(case)

    return {
        "source_path": source_path,
        "description": description,
        "requirement_scope": _dedupe_keep_order(list(parsed.get("requirement_scope") or [])),
        "raw_requirement_block": _text(primary_requirement),
        "test_intent": _text(parsed.get("test_intent")) or _text(case.name),
        "test_type": _text(parsed.get("test_type")) or _text(case.case_type),
        "intent_id": requirement_metadata.get("intent_id", ""),
        "source_asset_id": requirement_metadata.get("source_asset_id", ""),
        "source_asset_title": requirement_metadata.get("source_asset_title", ""),
        "precondition": precondition,
        "operation_steps": operation_steps,
        "involved_elements": involved_elements,
        "overall_expected": overall_expected,
        "assertion_points": assertion_points,
        "split_suggestions": split_suggestions,
        "missing_sections": [
            key
            for key, value in {
                "overall_expected": overall_expected,
                "assertion_points": assertion_points,
                "precondition": precondition,
                "operation_steps": operation_steps,
                "involved_elements": involved_elements,
            }.items()
            if not value
        ],
    }


def to_list_item(
    case: TestCase,
    *,
    latest_version_no: int | None = None,
    project_status: str = "active",
) -> dict[str, object]:
    data_config = case.data_config if isinstance(case.data_config, dict) else {}
    return {
        "id": case.id,
        "internal_id": case.id,
        "case_id": case.case_id,
        "case_title": case.name,
        "project_code": case.project_code,
        "project_status": project_status or "active",
        "client": case.client,
        "page_code": case.page_code,
        "page_name": case.page_name,
        "module_code": case.module_code,
        "module_name": case.module_name,
        "case_type": case.case_type,
        "source": case.source,
        "name": case.name,
        "product_line": case.product_line,
        "business_module": case.module,
        "module": case.module,
        "chain_stage": case.chain_stage,
        "sut_service": case.sut_service,
        "related_services": _list_value(case.related_services),
        "priority": case.priority,
        "execution_surface_type": case.test_type,
        "test_type": case.test_type,
        "scenario_types": _list_value(case.scenario_types),
        "trigger_entry": case.trigger_entry,
        "fault_injection_type": case.fault_injection_type,
        "fault_injection_target": case.fault_injection_target,
        "fault_injection_params": case.fault_injection_params,
        "setup_sql": case.setup_sql,
        "precondition_state": case.precondition_state,
        "test_steps": case.test_steps if isinstance(case.test_steps, list) else [],
        "test_steps_text": case.test_steps_text,
        "concurrency_model": case.concurrency_model,
        "retry_policy": case.retry_policy,
        "expected_result": case.expected_result,
        "assert_sql": case.assert_sql,
        "event_assertion": case.event_assertion,
        "metric_assertion": case.metric_assertion,
        "cleanup_script": case.cleanup_script,
        "artifact_links": _list_value(case.artifact_links),
        "notes": case.notes,
        "tags": list(case.tags or []),
        "markers": list(case.markers or []),
        "created_by": case.creator,
        "creator": case.creator,
        "assignee": case.assignee,
        "script_path": case.pytest_path,
        "pytest_path": case.pytest_path,
        "lifecycle_status": case.status,
        "status": case.status,
        "automation_status": case.automation_status,
        "created_source": case.created_source,
        "source_ref": case.source_ref,
        "last_execution_result": case.last_execution_result,
        "last_report_url": case.last_report_url,
        "updated_at": case.updated_at,
        "data_config_enabled": bool(data_config.get("enabled")),
        "latest_version_no": latest_version_no,
    }


def build_list_payload(
    cases: list[TestCase],
    pagination: PaginationPayload,
    filters: FilterOptionsPayload,
    stats: StatsPayload | None = None,
    latest_versions: dict[int, int] | None = None,
    search_context: SearchContextPayload | None = None,
    project_statuses: dict[str, str] | None = None,
) -> dict[str, object]:
    version_map = latest_versions or {}
    project_status_map = {
        str(project_code or "").strip().lower(): str(status or "").strip().lower() or "active"
        for project_code, status in (project_statuses or {}).items()
    }
    return {
        "items": [
            to_list_item(
                case,
                latest_version_no=version_map.get(case.id),
                project_status=project_status_map.get(str(case.project_code or "").strip().lower(), "active"),
            )
            for case in cases
        ],
        "pagination": pagination,
        "filters": filters,
        "stats": stats or {},
        "search_context": search_context or {},
    }


def build_case_detail_payload(
    case: TestCase,
    defects: list[TestCaseDefect],
    executions: list[TestCaseExecution],
    versions: list[TestCaseVersion],
    data_config: DataConfigPayload,
    *,
    project_status: str = "active",
    normalize_report_url: NormalizeReportUrl,
) -> dict[str, object]:
    asset_references = _list_value(case.artifact_links)
    source_ref = str(case.source_ref or "").strip()
    if source_ref:
        asset_references = [source_ref, *asset_references]
    detail_content = _build_detail_content(case)
    version_history = [
        {
            "version_no": item.version_no,
            "changed_by": item.changed_by,
            "change_summary": item.change_summary,
            "created_at": item.created_at,
        }
        for item in versions
    ]
    execution_history = [
        {
            "status": item.status,
            "duration_ms": item.duration_ms,
            "report_url": normalize_report_url(item.report_url, item.id),
            "executed_at": item.executed_at,
        }
        for item in executions
    ]
    linked_defects = [
        {
            "defect_key": item.defect_key,
            "defect_url": item.defect_url,
            "created_at": item.created_at,
        }
        for item in defects
    ]
    test_point_summary = (
        f"tags={len(case.tags or [])}, markers={len(case.markers or [])}, "
        f"data_config={'enabled' if bool(data_config.get('enabled')) else 'disabled'}"
    )
    return {
        "basic": {
            **to_list_item(case, project_status=project_status),
            "created_at": case.created_at,
        },
        "governance": {
            "internal_id":   case.id,
            "project_code": case.project_code,
            "product_line": case.product_line,
            "business_module": case.module,
            "page_code": case.page_code,
            "execution_surface_type": case.test_type,
            "tags": list(case.tags or []),
            "markers": list(case.markers or []),
            "created_by": case.creator,
            "lifecycle_status": case.status,
            "script_path": case.pytest_path,
            "automation_script": case.script_code,
            "data_config": data_config,
            "latest_run_result": case.last_execution_result,
            "version_history": version_history,
            "execution_history": execution_history,
            "linked_defects": linked_defects,
            "asset_references": asset_references,
            "test_point_summary": test_point_summary,
        },
        "script_code": case.script_code,
        "detail_content": detail_content,
        "data_config": data_config,
        "defects": [build_defect_item(item) for item in defects],
        "executions": [
            {
                "id": item.id,
                "status": item.status,
                "duration_ms": item.duration_ms,
                "report_url": normalize_report_url(item.report_url, item.id),
                "executed_at": item.executed_at,
            }
            for item in executions
        ],
        "versions": [
            {
                "id": item.id,
                "version_no": item.version_no,
                "changed_by": item.changed_by,
                "change_summary": item.change_summary,
                "created_at": item.created_at,
            }
            for item in versions
        ],
    }


def build_version_compare_payload(
    *,
    from_version: int,
    to_version: int,
    added_lines: int,
    removed_lines: int,
    diff_lines: list[str],
) -> dict[str, object]:
    return {
        "from_version": from_version,
        "to_version": to_version,
        "added_lines": added_lines,
        "removed_lines": removed_lines,
        "diff_lines": diff_lines,
    }


def build_export_csv(cases: list[TestCase]) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "case_id",
            "project_code",
            "name",
            "product_line",
            "module",
            "chain_stage",
            "sut_service",
            "priority",
            "test_type",
            "scenario_types",
            "tags",
            "markers",
            "creator",
            "assignee",
            "pytest_path",
            "status",
            "automation_status",
            "last_execution_result",
            "last_report_url",
            "data_config_enabled",
        ]
    )
    for case in cases:
        data_config = case.data_config if isinstance(case.data_config, dict) else {}
        writer.writerow(
            [
                case.case_id,
                case.project_code,
                case.name,
                case.product_line,
                case.module,
                case.chain_stage,
                case.sut_service,
                case.priority,
                case.test_type,
                ",".join(_list_value(case.scenario_types)),
                ",".join(case.tags or []),
                ",".join(case.markers or []),
                case.creator,
                case.assignee,
                case.pytest_path,
                case.status,
                case.automation_status,
                case.last_execution_result,
                case.last_report_url,
                bool(data_config.get("enabled")),
            ]
        )
    return output.getvalue()


def build_export_json(cases: list[TestCase], *, normalize_data_config: NormalizeDataConfig) -> str:
    body_items: list[dict[str, object]] = []
    for case in cases:
        raw_data_config = case.data_config if isinstance(case.data_config, dict) else {}
        body_items.append(
            {
                **to_list_item(case),
                "data_config": normalize_data_config(TestCaseDataConfig.model_validate(raw_data_config or {})),
            }
        )
    return json.dumps(body_items, ensure_ascii=False, default=str, indent=2)


def build_defect_item(defect: TestCaseDefect) -> dict[str, object]:
    return {
        "id": defect.id,
        "defect_key": defect.defect_key,
        "defect_url": defect.defect_url,
        "created_at": defect.created_at,
    }
