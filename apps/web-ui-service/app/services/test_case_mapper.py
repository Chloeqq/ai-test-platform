from __future__ import annotations

import csv
import io
import json
from typing import Callable, TypeAlias

from app.models.test_case import TestCase, TestCaseDefect, TestCaseExecution, TestCaseVersion
from app.schemas.test_case import TestCaseDataConfig

DataConfigValue: TypeAlias = bool | list[str] | list[list[str]]
DataConfigPayload: TypeAlias = dict[str, DataConfigValue]
PaginationPayload: TypeAlias = dict[str, int | bool | None]
FilterOptionsPayload: TypeAlias = dict[str, list[str]]
SearchContextPayload: TypeAlias = dict[str, str]
StatsPayload: TypeAlias = dict[str, int | float]
NormalizeReportUrl: TypeAlias = Callable[[str, int], str]
NormalizeDataConfig: TypeAlias = Callable[[TestCaseDataConfig | None], DataConfigPayload]


def _list_value(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def to_list_item(case: TestCase, *, latest_version_no: int | None = None) -> dict[str, object]:
    data_config = case.data_config if isinstance(case.data_config, dict) else {}
    return {
        "id": case.id,
        "internal_id": case.id,
        "case_id": case.case_id,
        "case_title": case.name,
        "project_code": case.project_code,
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
) -> dict[str, object]:
    version_map = latest_versions or {}
    return {
        "items": [to_list_item(case, latest_version_no=version_map.get(case.id)) for case in cases],
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
    normalize_report_url: NormalizeReportUrl,
) -> dict[str, object]:
    asset_references = _list_value(case.artifact_links)
    source_ref = str(case.source_ref or "").strip()
    if source_ref:
        asset_references = [source_ref, *asset_references]
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
            **to_list_item(case),
            "created_at": case.created_at,
        },
        "governance": {
            "internal_id": case.id,
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
