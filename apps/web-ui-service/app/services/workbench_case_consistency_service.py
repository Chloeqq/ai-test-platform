from __future__ import annotations

import json
import shutil
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.repositories.test_case_repository import TestCaseRepository
from shared_backend.case_ids import match_case_id, normalize_case_id

RecordCaseIdResolver = Callable[[dict[str, Any]], Any]


def normalize_business_case_id(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    normalized = normalize_case_id(raw, fallback="").strip().lower()
    if not normalized or not match_case_id(normalized):
        return ""
    return normalized


def load_case_center_case_ids(db: Session) -> set[str] | None:
    try:
        rows = TestCaseRepository(db).list_case_ids()
    except SQLAlchemyError:
        return None
    case_ids: set[str] = set()
    for row in rows:
        case_id = normalize_business_case_id(row)
        if case_id:
            case_ids.add(case_id)
    return case_ids


def is_case_tracked(
    case_id: Any,
    *,
    case_center_case_ids: set[str] | None,
) -> bool:
    if case_center_case_ids is None:
        return True
    normalized_case_id = normalize_business_case_id(case_id)
    if not normalized_case_id:
        return False
    return normalized_case_id in case_center_case_ids


def filter_records_by_case_center(
    records: Sequence[dict[str, Any]],
    *,
    case_center_case_ids: set[str] | None,
    case_id_resolver: RecordCaseIdResolver | None = None,
    case_id_key: str = "case_id",
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if case_center_case_ids is None:
        passthrough = [dict(item) for item in records if isinstance(item, dict)]
        return passthrough, {
            "enforced": False,
            "total_records": len(passthrough),
            "removed_count": 0,
            "removed_case_ids": [],
        }

    resolver = case_id_resolver or (lambda row: row.get(case_id_key))
    filtered: list[dict[str, Any]] = []
    removed_count = 0
    removed_case_ids: set[str] = set()
    for record in records:
        if not isinstance(record, dict):
            continue
        normalized_case_id = normalize_business_case_id(resolver(record))
        if normalized_case_id and normalized_case_id in case_center_case_ids:
            row = dict(record)
            if case_id_key:
                row[case_id_key] = normalized_case_id
            filtered.append(row)
            continue
        removed_count += 1
        if normalized_case_id:
            removed_case_ids.add(normalized_case_id)

    return filtered, {
        "enforced": True,
        "total_records": len([item for item in records if isinstance(item, dict)]),
        "removed_count": removed_count,
        "removed_case_ids": sorted(removed_case_ids),
    }


def cleanup_execution_report_files(
    *,
    execution_reports_root: Path,
    case_center_case_ids: set[str] | None,
) -> dict[str, Any]:
    if case_center_case_ids is None:
        return {
            "enforced": False,
            "removed_files": [],
            "removed_case_ids": [],
            "removed_count": 0,
        }

    removed_files: list[str] = []
    removed_case_ids: set[str] = set()

    if not execution_reports_root.exists():
        return {
            "enforced": True,
            "removed_files": [],
            "removed_case_ids": [],
            "removed_count": 0,
        }

    report_json_paths = sorted(execution_reports_root.glob("*.report.json"))
    for report_json_path in report_json_paths:
        report_case_id = normalize_business_case_id(report_json_path.name.removesuffix(".report.json"))
        if not report_case_id:
            try:
                payload = json.loads(report_json_path.read_text(encoding="utf-8")) or {}
            except Exception:
                payload = {}
            if isinstance(payload, dict):
                report_case_id = normalize_business_case_id(payload.get("case_id"))
        if report_case_id and report_case_id in case_center_case_ids:
            continue

        report_md_path = report_json_path.with_suffix(".md")
        for candidate in (report_json_path, report_md_path):
            if candidate.exists():
                candidate.unlink()
                removed_files.append(str(candidate))
        if report_case_id:
            removed_case_ids.add(report_case_id)

    orphan_md_paths = sorted(execution_reports_root.glob("*.report.md"))
    for report_md_path in orphan_md_paths:
        report_json_path = report_md_path.with_suffix(".json")
        if report_json_path.exists():
            continue
        report_case_id = normalize_business_case_id(report_md_path.name.removesuffix(".report.md"))
        if report_case_id and report_case_id in case_center_case_ids:
            continue
        report_md_path.unlink()
        removed_files.append(str(report_md_path))
        if report_case_id:
            removed_case_ids.add(report_case_id)

    return {
        "enforced": True,
        "removed_files": removed_files,
        "removed_case_ids": sorted(removed_case_ids),
        "removed_count": len(removed_files),
    }


def _cleanup_directory_contents(path: Path) -> list[str]:
    removed: list[str] = []
    if not path.exists():
        return removed
    for child in sorted(path.iterdir()):
        if child.is_dir():
            shutil.rmtree(child, ignore_errors=True)
            removed.append(str(child))
            continue
        child.unlink(missing_ok=True)
        removed.append(str(child))
    return removed


def cleanup_allure_artifacts(
    *,
    allure_results_root: Path,
    allure_report_root: Path,
    allure_snapshots_root: Path,
    clear_report_root: bool = False,
) -> dict[str, Any]:
    removed_paths: list[str] = []
    removed_paths.extend(_cleanup_directory_contents(allure_results_root))
    if clear_report_root:
        removed_paths.extend(_cleanup_directory_contents(allure_report_root))
    removed_paths.extend(_cleanup_directory_contents(allure_snapshots_root))
    allure_results_root.mkdir(parents=True, exist_ok=True)
    if clear_report_root or not allure_report_root.exists():
        allure_report_root.mkdir(parents=True, exist_ok=True)
    allure_snapshots_root.mkdir(parents=True, exist_ok=True)
    return {
        "removed_paths": removed_paths,
        "removed_count": len(removed_paths),
        "allure_results_root": str(allure_results_root),
        "allure_report_root": str(allure_report_root),
        "allure_snapshots_root": str(allure_snapshots_root),
        "clear_report_root": clear_report_root,
    }


def cleanup_execution_task_artifacts(
    *,
    runner_artifacts_root: Path,
    web_ui_runs_root: Path,
) -> dict[str, Any]:
    removed_paths: list[str] = []
    removed_paths.extend(_cleanup_directory_contents(runner_artifacts_root))
    if web_ui_runs_root.exists():
        for artifact_dir in sorted(web_ui_runs_root.glob("*-artifacts")):
            shutil.rmtree(artifact_dir, ignore_errors=True)
            removed_paths.append(str(artifact_dir))
    runner_artifacts_root.mkdir(parents=True, exist_ok=True)
    web_ui_runs_root.mkdir(parents=True, exist_ok=True)
    return {
        "removed_paths": removed_paths,
        "removed_count": len(removed_paths),
        "runner_artifacts_root": str(runner_artifacts_root),
        "web_ui_runs_root": str(web_ui_runs_root),
    }
