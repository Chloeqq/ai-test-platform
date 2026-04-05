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
NormalizeReportUrl: TypeAlias = Callable[[str, int], str]
NormalizeDataConfig: TypeAlias = Callable[[TestCaseDataConfig | None], DataConfigPayload]


def to_list_item(case: TestCase, *, latest_version_no: int | None = None) -> dict[str, object]:
    data_config = case.data_config if isinstance(case.data_config, dict) else {}
    return {
        "id": case.id,
        "name": case.name,
        "product_line": case.product_line,
        "module": case.module,
        "priority": case.priority,
        "test_type": case.test_type,
        "tags": list(case.tags or []),
        "markers": list(case.markers or []),
        "creator": case.creator,
        "pytest_path": case.pytest_path,
        "status": case.status,
        "last_execution_result": case.last_execution_result,
        "updated_at": case.updated_at,
        "data_config_enabled": bool(data_config.get("enabled")),
        "latest_version_no": latest_version_no,
    }


def build_list_payload(
    cases: list[TestCase],
    pagination: PaginationPayload,
    filters: FilterOptionsPayload,
    latest_versions: dict[int, int] | None = None,
    search_context: SearchContextPayload | None = None,
) -> dict[str, object]:
    version_map = latest_versions or {}
    return {
        "items": [to_list_item(case, latest_version_no=version_map.get(case.id)) for case in cases],
        "pagination": pagination,
        "filters": filters,
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
    return {
        "basic": {
            **to_list_item(case),
            "created_at": case.created_at,
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
            "id",
            "name",
            "product_line",
            "module",
            "priority",
            "test_type",
            "tags",
            "markers",
            "creator",
            "pytest_path",
            "status",
            "last_execution_result",
            "data_config_enabled",
        ]
    )
    for case in cases:
        data_config = case.data_config if isinstance(case.data_config, dict) else {}
        writer.writerow(
            [
                case.id,
                case.name,
                case.product_line,
                case.module,
                case.priority,
                case.test_type,
                ",".join(case.tags or []),
                ",".join(case.markers or []),
                case.creator,
                case.pytest_path,
                case.status,
                case.last_execution_result,
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
