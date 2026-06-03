"""Workbench 报表视图函数 —— 性能报表 & Allure 报表构建。

提取自 workbench_reporting_service.py 以控制单文件大小在 1000 行以内。
"""
from __future__ import annotations

import json
import re
import shutil
from datetime import datetime
from datetime_compat import UTC
from pathlib import Path
from typing import Any, Callable

from shared_backend.type_utils import dict_value as _dict_value

from app.services.workbench_reporting_service import (
    ReadAllureSummary,
    ReadAllureEnvironment,
    ReadAllureExecutors,
    EnsureAllureSnapshot,
    GetAllureIndexVersion,
    RunCommand,
    CollectExecutionRecords,
    NormalizeExecutionMeta,
    _safe_report_slug,
)


def build_report_allure_pending(*, reason: str, message: str, legacy_available: bool = False) -> dict[str, Any]:
    """构建"暂无 Allure 报告"的占位视图。"""
    return {
        "allure_index": "", "available": False, "version": "", "display_version": "",
        "cache_version": 0, "report_name": "暂无本次 Allure 执行报告", "snapshot_slug": "",
        "summary": {"statistic": {"failed": 0, "broken": 0, "skipped": 0, "passed": 0, "unknown": 0, "total": 0}},
        "environment": [], "executors": [], "report_source": "none",
        "reason": reason, "message": message, "legacy_available": legacy_available,
    }


def build_report_performance(
    *,
    collect_execution_records_with_meta: CollectExecutionRecords,
    normalize_execution_meta: NormalizeExecutionMeta,
) -> dict[str, Any]:
    """构建性能报表（平均耗时、最慢用例等）。"""
    run_entries, execution_meta_raw = collect_execution_records_with_meta(limit=1000)
    execution_meta = normalize_execution_meta(execution_meta_raw)
    duration_rows: list[dict[str, Any]] = []
    for item in run_entries:
        execution_record = _dict_value(item.get("execution_record"))
        started = str(execution_record.get("started_at", "")).strip()
        finished = str(execution_record.get("finished_at", "")).strip()
        if not started or not finished:
            continue
        try:
            started_dt = datetime.fromisoformat(started)
            finished_dt = datetime.fromisoformat(finished)
            duration = max(0.0, (finished_dt - started_dt).total_seconds())
        except Exception:
            duration = 0.0
        duration_rows.append({
            "run_id": execution_record.get("run_id", ""),
            "case_id": execution_record.get("case_id", ""),
            "status": execution_record.get("status", ""),
            "duration_seconds": duration,
            "finished_at": finished,
            "source": item.get("source", ""),
        })
    duration_rows.sort(key=lambda item: item["finished_at"], reverse=True)
    avg_duration = round(sum(item["duration_seconds"] for item in duration_rows) / len(duration_rows), 2) if duration_rows else 0.0
    max_duration = round(max((item["duration_seconds"] for item in duration_rows), default=0.0), 2)
    latest = duration_rows[0]["duration_seconds"] if len(duration_rows) >= 1 else 0.0
    previous = duration_rows[1]["duration_seconds"] if len(duration_rows) >= 2 else 0.0
    delta = round(latest - previous, 2) if previous else 0.0
    slowest = sorted(duration_rows, key=lambda item: item["duration_seconds"], reverse=True)[:10]
    return {
        "summary": {
            "average_duration_seconds": avg_duration,
            "max_duration_seconds": max_duration,
            "latest_delta_seconds": delta,
            "sample_count": len(duration_rows),
        },
        "slow_cases": slowest,
        "execution_meta": execution_meta,
    }


# ---- Allure 报表 -----------------------------------------------------------


def build_report_allure(
    *,
    available: bool,
    read_allure_summary: ReadAllureSummary,
    ensure_allure_snapshot: EnsureAllureSnapshot,
    get_allure_index_version: GetAllureIndexVersion,
    read_allure_environment: ReadAllureEnvironment | None = None,
    read_allure_executors: ReadAllureExecutors | None = None,
    current_results_dir: Path | None = None,
) -> dict[str, Any]:
    """构建本次 run 的 Allure 报表视图。"""
    if current_results_dir is None:
        return build_report_allure_pending(
            reason="no_run_scoped_allure_results",
            message="暂无本次执行报告，请先在用例中心执行用例后再查看 Allure 报告。",
            legacy_available=available,
        )
    cache_version = get_allure_index_version() if available else 0
    summary = read_allure_summary() if available else {}
    environment = read_allure_environment() if available and read_allure_environment is not None else []
    executors = read_allure_executors() if available and read_allure_executors is not None else []
    identity = build_allure_report_identity(summary=summary, cache_version=cache_version)
    allure_index = (
        ensure_allure_snapshot(version=cache_version, snapshot_slug=identity["snapshot_slug"])
        if available else "/allure/index.html"
    )
    return {
        "allure_index": allure_index, "available": available,
        "version": identity["display_version"], "display_version": identity["display_version"],
        "cache_version": cache_version, "report_name": identity["report_name"],
        "snapshot_slug": identity["snapshot_slug"], "summary": summary,
        "environment": environment, "executors": executors,
        "report_source": "run_scoped", "results_dir": str(current_results_dir),
    }


def build_report_allure_refresh(
    *,
    command_result: Any,
    available: bool,
    read_allure_summary: ReadAllureSummary,
    ensure_allure_snapshot: EnsureAllureSnapshot,
    get_allure_index_version: GetAllureIndexVersion,
    read_allure_environment: ReadAllureEnvironment | None = None,
    read_allure_executors: ReadAllureExecutors | None = None,
    current_results_dir: Path | None = None,
) -> dict[str, Any]:
    """Allure generate 后刷新报表视图。"""
    if current_results_dir is None:
        return build_report_allure_pending(
            reason="no_run_scoped_allure_results",
            message="暂无可刷新的本次执行报告，请先执行用例生成 run 级 Allure results。",
            legacy_available=available,
        )
    summary = read_allure_summary() if available else {}
    environment = read_allure_environment() if available and read_allure_environment is not None else []
    executors = read_allure_executors() if available and read_allure_executors is not None else []
    return_code = int(getattr(command_result, "returncode", 1))
    if return_code != 0:
        return {
            "error": {
                "message": "allure generate failed", "return_code": return_code,
                "stdout": str(getattr(command_result, "stdout", "") or "").strip()[-4000:],
                "stderr": str(getattr(command_result, "stderr", "") or "").strip()[-4000:],
            }
        }
    cache_version = get_allure_index_version() if available else 0
    identity = build_allure_report_identity(summary=summary, cache_version=cache_version)
    allure_index = (
        ensure_allure_snapshot(version=cache_version, snapshot_slug=identity["snapshot_slug"])
        if available else "/allure/index.html"
    )
    return {
        "available": available, "version": identity["display_version"],
        "display_version": identity["display_version"], "cache_version": cache_version,
        "report_name": identity["report_name"], "snapshot_slug": identity["snapshot_slug"],
        "allure_index": allure_index, "return_code": return_code,
        "stdout": str(getattr(command_result, "stdout", "") or "").strip()[-4000:],
        "stderr": str(getattr(command_result, "stderr", "") or "").strip()[-4000:],
        "summary": summary, "environment": environment, "executors": executors,
        "report_source": "run_scoped", "results_dir": str(current_results_dir),
    }


def refresh_allure_report(
    *,
    python_bin: str, runner_root: Path, repo_root: Path,
    allure_report_root: Path, run_command: RunCommand,
    read_allure_summary: ReadAllureSummary,
    ensure_allure_snapshot: EnsureAllureSnapshot,
    get_allure_index_version: GetAllureIndexVersion,
    read_allure_environment: ReadAllureEnvironment | None = None,
    read_allure_executors: ReadAllureExecutors | None = None,
) -> dict[str, Any]:
    """运行 allure generate 并返回刷新后的报表视图。"""
    results_dir = find_latest_run_allure_results(repo_root=repo_root)
    if results_dir is None:
        return build_report_allure_refresh(
            command_result=None,
            available=(allure_report_root / "index.html").exists(),
            read_allure_summary=read_allure_summary,
            read_allure_environment=read_allure_environment,
            read_allure_executors=read_allure_executors,
            ensure_allure_snapshot=ensure_allure_snapshot,
            get_allure_index_version=get_allure_index_version,
            current_results_dir=None,
        )
    command = [
        python_bin, str(runner_root / "tools" / "manage_allure.py"),
        "--results-dir", str(results_dir), "--report-dir", str(allure_report_root), "generate",
    ]
    command_result = run_command(command, cwd=str(repo_root), text=True, capture_output=True, check=False)
    available = (allure_report_root / "index.html").exists()
    return build_report_allure_refresh(
        command_result=command_result, available=available,
        read_allure_summary=read_allure_summary,
        read_allure_environment=read_allure_environment,
        read_allure_executors=read_allure_executors,
        ensure_allure_snapshot=ensure_allure_snapshot,
        get_allure_index_version=get_allure_index_version,
        current_results_dir=results_dir,
    )


def find_latest_run_allure_results(*, repo_root: Path) -> Path | None:
    """查找最新的 run 级 allure-results 目录。"""
    runs_root = repo_root / "web-ui" / "state" / "runs"
    if not runs_root.exists():
        return None
    candidates = []
    for path in runs_root.glob("*-artifacts/allure-results"):
        if not path.is_dir():
            continue
        result_files = list(path.glob("*-result.json"))
        if not result_files:
            continue
        newest_mtime = max(item.stat().st_mtime for item in result_files)
        candidates.append((newest_mtime, path))
    if not candidates:
        return None
    return max(candidates, key=lambda item: item[0])[1]


def get_allure_index_version(*, allure_report_root: Path) -> int:
    """计算 Allure 报表的版本号（基于文件修改时间）。"""
    candidates = [
        allure_report_root / "index.html",
        allure_report_root / "widgets" / "summary.json",
        allure_report_root / "history" / "history-trend.json",
    ]
    versions: list[int] = []
    for path in candidates:
        if not path.exists():
            continue
        try:
            versions.append(int(path.stat().st_mtime_ns))
        except Exception:
            continue
    return max(versions) if versions else 0


def build_allure_report_identity(*, summary: dict[str, Any], cache_version: int) -> dict[str, str]:
    """根据 summary 和版本号生成 Allure 报表的展示标识。"""
    statistic = _dict_value(summary.get("statistic"))
    total_runs = int(statistic.get("total", 0) or 0)
    raw_report_name = str(summary.get("reportName", "")).strip()
    time_info = _dict_value(summary.get("time"))
    stop_ms = int(time_info.get("stop", 0) or 0)
    report_date = ""
    if stop_ms > 0:
        try:
            report_date = datetime.fromtimestamp(stop_ms / 1000, tz=UTC).date().isoformat()
        except Exception:
            report_date = ""
    if not report_date and cache_version > 0:
        try:
            report_date = datetime.fromtimestamp(cache_version / 1_000_000_000, tz=UTC).date().isoformat()
        except Exception:
            report_date = datetime.now(UTC).date().isoformat()
    report_date = report_date or datetime.now(UTC).date().isoformat()
    run_suffix = f"Run{max(total_runs, 1):02d}"
    display_version = f"Allure-{report_date}-{run_suffix}"
    if raw_report_name:
        version_match = re.search(r"\(([^()]+)\)\s*$", raw_report_name)
        if version_match and version_match.group(1).strip():
            display_version = version_match.group(1).strip()
    report_name = raw_report_name if (raw_report_name and raw_report_name != "Allure Report") else f"AI 自动化测试执行报告 ({display_version})"
    return {
        "display_version": display_version, "report_name": report_name,
        "snapshot_slug": _safe_report_slug(display_version),
    }


def read_allure_summary(*, allure_report_root: Path) -> dict[str, Any]:
    """读取 Allure widgets/summary.json。"""
    summary_path = allure_report_root / "widgets" / "summary.json"
    if not summary_path.exists():
        return {}
    try:
        payload = json.loads(summary_path.read_text(encoding="utf-8")) or {}
    except (json.JSONDecodeError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def read_allure_environment(*, allure_report_root: Path) -> list[dict[str, Any]]:
    return _read_allure_widget_list(allure_report_root / "widgets" / "environment.json")


def read_allure_executors(*, allure_report_root: Path) -> list[dict[str, Any]]:
    return _read_allure_widget_list(allure_report_root / "widgets" / "executors.json")


def _read_allure_widget_list(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8")) or []
    except (json.JSONDecodeError, ValueError):
        return []
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict)]


def ensure_allure_snapshot(
    *,
    version: int, allure_report_root: Path,
    allure_snapshots_root: Path, snapshot_slug: str = "",
) -> str:
    """确保 Allure 快照存在，返回快照 URL 路径。"""
    if version <= 0:
        return "/allure/index.html"
    normalized_slug = _safe_report_slug(snapshot_slug or str(version))
    target = allure_snapshots_root / normalized_slug
    version_marker = target / ".snapshot-version"
    existing_version = ""
    if version_marker.exists():
        try:
            existing_version = version_marker.read_text(encoding="utf-8").strip()
        except (OSError, UnicodeDecodeError):
            existing_version = ""
    if target.exists() and existing_version != str(version):
        shutil.rmtree(target, ignore_errors=True)
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(allure_report_root, target)
        version_marker.write_text(str(version), encoding="utf-8")
        snapshot_dirs = sorted(
            [item for item in allure_snapshots_root.iterdir() if item.is_dir()],
            key=lambda p: p.name, reverse=True,
        )
        for stale in snapshot_dirs[10:]:
            shutil.rmtree(stale, ignore_errors=True)
    return f"/allure-snapshots/{normalized_slug}/index.html"
