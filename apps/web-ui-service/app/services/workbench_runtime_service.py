from __future__ import annotations

import json
import logging
import os
import selectors
import threading
import time
import uuid
import subprocess
import sys
from datetime import datetime
from shared_backend.datetime_compat import UTC
from pathlib import Path
from typing import Any, Callable

from shared_backend.case_ids import normalize_case_id
from shared_backend.type_utils import dict_value as _dict_value
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.workbench._helpers import (
    parse_iso_datetime as _parse_iso_datetime,
    text as _text,
)
from app.models.test_case import TestCase, TestCaseExecution
from app.repositories.test_case_repository import TestCaseRepository

NormalizeExecutionRecordPayload = Callable[[dict[str, Any]], dict[str, Any]]
NormalizePageSlug = Callable[[str], str]
BuildPageAnalysisContext = Callable[..., dict[str, Any]]
BuildItemReviewState = Callable[..., dict[str, Any]]
BuildRunReviewStateFromDecisions = Callable[..., dict[str, Any]]
BuildTestPointAssetGateContext = Callable[..., dict[str, Any]]
BuildExecutionGate = Callable[..., dict[str, Any]]
BuildReviewAuditSummary = Callable[[dict[str, Any]], dict[str, Any]]
BuildReviewAuditTimeline = Callable[..., list[dict[str, Any]]]
BuildRiskReportSummary = Callable[[dict[str, Any] | None], dict[str, Any]]
BuildSelfHealingSummary = Callable[..., dict[str, Any]]
ExecutionGateDecisionForRun = Callable[..., dict[str, Any]]
LoadRuntimeExecutionRecordFromArtifacts = Callable[[Path], dict[str, Any]]
GetJob = Callable[[str], dict[str, Any] | None]
ReadRuntimeRuns = Callable[[], list[dict[str, Any]]]
StoreRunJob = Callable[[str, dict[str, Any]], None]
AppendRuntimeRun = Callable[[dict[str, Any]], None]
AppendHistory = Callable[[dict[str, Any]], None]
ExecuteRunFn = Callable[[dict[str, Any]], None]
NowIsoFn = Callable[[], str]
ThreadFactory = Callable[..., threading.Thread]
SleepFn = Callable[[float], None]
TimeFn = Callable[[], float]
BuildRuntimeExecutionRecord = Callable[..., dict[str, Any]]
RuntimeViewFromEntryFn = Callable[[dict[str, Any]], dict[str, Any]]
BuildRunCommand = Callable[[Path], tuple[list[str], dict[str, str]]]
CollectFailureEntries = Callable[[], list[dict[str, Any]]]
IsWithin = Callable[[Path, Path], bool]
UpdateRun = Callable[[str, dict[str, Any]], None]
GetPythonBin = Callable[[], str]
NormalizeEvidenceManifestPayload = Callable[[dict[str, Any]], dict[str, Any]]

LOGGER = logging.getLogger(__name__)


def _runtime_cases_root_for_path(case_path: Path) -> Path | None:
    """返回运行态 YAML 所属的受治理 runtime-cases 根目录。

    `TEST_CASE_ALLOWED_ROOTS` 不能被扩展成任意 `case_path.parent`。只有形如
    `.../runtime-cases/{run_id}/{case_id}.yaml` 的路径，才允许贡献稳定的
    `runtime-cases` 根目录。
    """
    resolved_path = case_path.resolve()
    parents = list(resolved_path.parents)
    if len(parents) < 2:
        return None
    runtime_cases_root = parents[1]
    if runtime_cases_root.name != "runtime-cases":
        return None
    return runtime_cases_root


def runtime_run_id(item: dict[str, Any]) -> str:
    run_id = str(item.get("run_id", "")).strip()
    if run_id:
        return run_id
    execution_record = item.get("execution_record")
    if isinstance(execution_record, dict):
        return str(execution_record.get("run_id", "")).strip()
    return ""


def build_runtime_execution_record(
    *,
    run_id: str,
    case_id: str,
    project: str,
    source: str,
    mode: str,
    status: str,
    started_at: str,
    finished_at: str,
    return_code: int | None,
    created_at: str = "",
    normalize_execution_record_payload: NormalizeExecutionRecordPayload,
) -> dict[str, Any]:
    return normalize_execution_record_payload(
        {
            "version": "ExecutionRecordV1",
            "schema_version": "execution-record.v1",
            "run_id": run_id,
            "case_id": case_id,
            "project": project,
            "source": source,
            "mode": mode or "generate_and_run",
            "status": status,
            "started_at": started_at or created_at,
            "finished_at": finished_at,
            "step_summary": {
                "page": "",
                "requirement_count": 0,
                "total_steps": 0,
                "action_types": [],
            },
            "evidence_index": {
                "total_files": 0,
                "artifact_categories": {
                    "screenshots": 0,
                    "html_pages": 0,
                    "meta_files": 0,
                    "analysis_files": 0,
                    "suggestion_files": 0,
                    "execution_record_files": 0,
                    "self_healing_result_files": 0,
                    "videos": 0,
                    "other_files": 0,
                },
                "runner_exit_code": return_code,
                "execution_requested": True,
            },
        }
    )


def build_run_command(
    case_path: Path,
    *,
    get_python_bin_fn: GetPythonBin,
    repo_root: Path,
    allure_results_root: Path,
    environ: dict[str, str],
) -> tuple[list[str], dict[str, str]]:
    command = [
        get_python_bin_fn(),
        "-m",
        "pytest",
        "-s",
        str(repo_root / "runners" / "web-playwright-python" / "tests" / "test_yaml_ai_generated.py"),
        "--alluredir",
        str(allure_results_root),
    ]
    env = dict(environ)
    batch_run_enabled = str(env.get("WORKBENCH_BATCH_RUN", "")).strip().lower() in {"1", "true", "yes", "on"}
    visible_run_enabled = str(
        env.get("WORKBENCH_VISIBLE_RUN") or env.get("RECORDER_DESKTOP_ENABLED") or ""
    ).strip().lower() in {"1", "true", "yes", "on"} and not batch_run_enabled
    if batch_run_enabled:
        env.setdefault("WORKBENCH_VISIBLE_STEP_DELAY_MS", "0")
        env.setdefault("WORKBENCH_VISIBLE_HOLD_MS", "0")
        env.setdefault("WORKBENCH_RECORD_VIDEO", "0")
        env.setdefault("WORKBENCH_RUN_TIMEOUT_SECONDS", "180")
    elif visible_run_enabled and str(env.get("DISPLAY", "")).strip():
        command.append("--headed")
        slowmo_ms = str(env.get("WORKBENCH_VISIBLE_SLOWMO_MS") or "80").strip()
        if slowmo_ms and slowmo_ms not in {"0", "0.0"}:
            command.extend(["--slowmo", slowmo_ms])
        env.setdefault("WORKBENCH_VISIBLE_STEP_DELAY_MS", "100")
        env.setdefault("WORKBENCH_VISIBLE_HOLD_MS", "800")
        env.setdefault("WORKBENCH_RUN_TIMEOUT_SECONDS", "120")
        env.setdefault("WORKBENCH_RECORD_VIDEO", "1")
    current_pythonpath = env.get("PYTHONPATH", "").strip()
    runner_path = str(repo_root / "runners" / "web-playwright-python")
    env["PYTHONPATH"] = f"{runner_path}:{current_pythonpath}" if current_pythonpath else runner_path
    env["RUN_MODE"] = "ai"
    env["RUN_SOURCE"] = "web-ui"
    env["TEST_CASE_PATH"] = str(case_path.resolve())
    # 只允许长期存在的 AI 生成用例根目录，以及运行态物化脚本所在的稳定
    # `runtime-cases` 根目录。不要盲目加入 `case_path.parent`，否则未来
    # 任意调用方都可能把任意目录扩大成 runner 允许读取的输入根。
    allowed_roots = [
        (repo_root / "assets" / "test-cases" / "ai-generated").resolve(),
    ]
    runtime_cases_root = _runtime_cases_root_for_path(case_path)
    if runtime_cases_root is not None:
        allowed_roots.append(runtime_cases_root)
    env["TEST_CASE_ALLOWED_ROOTS"] = os.pathsep.join(
        str(root) for root in dict.fromkeys(allowed_roots)
    )
    env["SELF_HEALING_ENABLED"] = "0"
    env.setdefault("BASE_URL", "http://localhost:5174/#/login")
    return command, env


def is_runner_termination(return_code: int | None, *, timed_out: bool = False) -> bool:
    return bool(timed_out or return_code in {-9, 124})


def build_runner_termination_failure(
    *,
    run_id: str,
    case_id: str,
    project: str,
    case_path: str,
    return_code: int | None,
    timeout_seconds: int,
    timed_out: bool,
) -> dict[str, Any]:
    reason = "runner_timeout" if timed_out else "runner_terminated"
    title = "执行超时" if timed_out else "执行进程被终止"
    summary = (
        f"执行超过 {timeout_seconds}s 后被平台终止，未生成完整执行产物。"
        if timed_out
        else f"执行进程异常退出，return_code={return_code}，未生成完整执行产物。"
    )
    return {
        "version": "FailureArtifactV1",
        "run_id": run_id,
        "case_id": case_id,
        "project": project,
        "case_path": case_path,
        "summary": summary,
        "failure_type": reason,
        "analysis": {
            "summary": summary,
            "failure_category": "runner",
            "failure_source": "runner",
            "failure_source_reason": "Runner did not complete, so no assertion-level failure artifact was produced.",
            "failure_source_confidence": 1.0,
            "likely_cause": title,
            "risk_level": "high",
            "recommended_action": "先查看执行日志确认卡住阶段；若是可视化演示执行，建议降低 slowmo/等待时间或改用批量快速执行。",
            "confidence": 1.0,
            "requires_manual_review": False,
            "evidence_used": ["runtime_log"],
        },
    }


def build_fallback_execution_record(
    job: dict[str, Any],
    *,
    status_value: str,
    return_code: int | None,
    started_at: str,
    finished_at: str,
    artifacts_dir: Path,
    videos_dir: Path,
    timeout_seconds: int,
    timed_out: bool,
) -> dict[str, Any]:
    record = dict(_dict_value(job.get("execution_record")))
    run_id = str(job.get("run_id", record.get("run_id", ""))).strip()
    case_id = str(job.get("case_id", record.get("case_id", ""))).strip()
    project = str(job.get("project", record.get("project", "mall"))).strip() or "mall"
    source = str(job.get("source", record.get("source", "manual"))).strip() or "manual"
    mode = str(job.get("mode", record.get("mode", "generate_and_run"))).strip() or "generate_and_run"
    evidence_index = dict(_dict_value(record.get("evidence_index")))
    artifact_categories = dict(_dict_value(evidence_index.get("artifact_categories")))
    evidence_index.update(
        {
            "runner_exit_code": return_code,
            "execution_requested": True,
            "artifacts_dir": str(artifacts_dir),
            "videos_dir": str(videos_dir),
            "runner_timed_out": bool(timed_out),
            "runner_timeout_seconds": timeout_seconds if timed_out else 0,
        }
    )
    evidence_index["artifact_categories"] = artifact_categories
    metadata = dict(_dict_value(record.get("metadata")))
    if is_runner_termination(return_code, timed_out=timed_out):
        metadata.update(
            {
                "failure_type": "runner_timeout" if timed_out else "runner_terminated",
                "failure_summary": (
                    f"执行超过 {timeout_seconds}s 后被平台终止。"
                    if timed_out
                    else f"执行进程异常退出，return_code={return_code}。"
                ),
            }
        )
    record.update(
        {
            "version": record.get("version") or "ExecutionRecordV1",
            "schema_version": record.get("schema_version") or "execution-record.v1",
            "run_id": run_id,
            "case_id": case_id,
            "project": project,
            "source": source,
            "mode": mode,
            "status": status_value,
            "started_at": started_at or str(job.get("started_at", "")).strip(),
            "finished_at": finished_at,
            "return_code": return_code,
            "evidence_index": evidence_index,
            "metadata": metadata,
        }
    )
    record.setdefault(
        "step_summary",
        {
            "page": "",
            "requirement_count": 0,
            "total_steps": 0,
            "action_types": [],
        },
    )
    return record


def update_runtime_run_with_retry(
    run_id: str,
    updates: dict[str, Any],
    *,
    update_runtime_run: UpdateRun,
    attempts: int = 3,
    retry_delay_seconds: float = 1.0,
) -> None:
    for attempt in range(1, max(1, attempts) + 1):
        try:
            update_runtime_run(run_id, updates)
            return
        except Exception:
            if attempt >= max(1, attempts):
                LOGGER.exception("runtime run update failed run_id=%s", run_id)
                return
            time.sleep(max(0.0, retry_delay_seconds) * attempt)


def replace_allure_results_dir(command: list[str], allure_results_dir: Path) -> list[str]:
    updated = list(command)
    for index, item in enumerate(updated):
        if item == "--alluredir" and index + 1 < len(updated):
            updated[index + 1] = str(allure_results_dir)
            return updated
        if item.startswith("--alluredir="):
            updated[index] = f"--alluredir={allure_results_dir}"
            return updated
    updated.extend(["--alluredir", str(allure_results_dir)])
    return updated


def extract_json_from_text(text: str) -> dict[str, Any]:
    text = str(text or "").strip()
    if not text:
        return {}
    try:
        payload = json.loads(text)
        return payload if isinstance(payload, dict) else {}
    except (json.JSONDecodeError, ValueError):
        pass
    start = text.rfind("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        candidate = text[start : end + 1]
        try:
            payload = json.loads(candidate)
            return payload if isinstance(payload, dict) else {}
        except (json.JSONDecodeError, ValueError):
            return {}
    return {}


def get_python_bin(*, repo_root: Path) -> str:
    venv_python = repo_root / ".venv" / "bin" / "python"
    if venv_python.exists():
        return str(venv_python)
    return "python3"


def _positive_int_from_env(env: dict[str, str], name: str, *, default: int, min_value: int = 1, max_value: int = 3600) -> int:
    raw_value = str(env.get(name, "") or "").strip()
    if not raw_value:
        return default
    try:
        value = int(float(raw_value))
    except ValueError:
        return default
    return max(min_value, min(value, max_value))


def resolve_manifest_entries(entries: Any, *, root: Path) -> list[Path]:
    if not isinstance(entries, list):
        return []
    resolved: list[Path] = []
    for item in entries:
        raw_text = str(item).strip()
        if not raw_text:
            continue
        candidate = Path(raw_text)
        if not candidate.is_absolute():
            candidate = root / candidate
        if candidate.exists() and candidate.is_file():
            resolved.append(candidate.resolve())
    return resolved


def load_execution_record_payload(
    path: Path,
    *,
    normalize_execution_record_payload: NormalizeExecutionRecordPayload,
) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8")) or {}
    except (json.JSONDecodeError, ValueError):
        return {}
    return normalize_execution_record_payload(payload)


def load_runtime_execution_record_from_artifacts(
    artifacts_dir: Path,
    *,
    normalize_evidence_manifest_payload: NormalizeEvidenceManifestPayload,
    resolve_manifest_entries_fn: Callable[[Any, Path], list[Path]],
    load_execution_record_payload_fn: Callable[[Path], dict[str, Any]],
) -> dict[str, Any]:
    if not artifacts_dir.exists():
        return {}
    manifest_candidates = sorted(
        artifacts_dir.rglob("evidence_manifest.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for manifest_path in manifest_candidates:
        try:
            raw_manifest = json.loads(manifest_path.read_text(encoding="utf-8")) or {}
        except (json.JSONDecodeError, ValueError):
            continue
        manifest = normalize_evidence_manifest_payload(raw_manifest)
        record_paths = resolve_manifest_entries_fn(manifest.get("execution_record_files"), manifest_path.parent)
        for record_path in record_paths:
            execution_record = load_execution_record_payload_fn(record_path)
            if execution_record:
                return execution_record

    candidates = sorted(
        artifacts_dir.rglob("execution_record.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        return {}
    return load_execution_record_payload_fn(candidates[0])


def runtime_view_from_entry(
    entry: dict[str, Any],
    *,
    normalize_execution_record_payload: NormalizeExecutionRecordPayload,
    normalize_page_slug: NormalizePageSlug,
    build_page_analysis_context: BuildPageAnalysisContext,
    build_item_review_state: BuildItemReviewState,
    build_run_review_state_from_decisions: BuildRunReviewStateFromDecisions,
    build_test_point_asset_gate_context: BuildTestPointAssetGateContext,
    build_execution_gate: BuildExecutionGate,
    build_review_audit_summary: BuildReviewAuditSummary,
    build_review_audit_timeline: BuildReviewAuditTimeline,
    build_risk_report_summary: BuildRiskReportSummary,
    build_self_healing_summary: BuildSelfHealingSummary,
    execution_gate_decision_for_run: ExecutionGateDecisionForRun,
) -> dict[str, Any]:
    source = entry if isinstance(entry, dict) else {}
    run_id = runtime_run_id(source)
    execution_record_raw = source.get("execution_record") if isinstance(source.get("execution_record"), dict) else {}
    if execution_record_raw:
        execution_record = normalize_execution_record_payload(execution_record_raw)
    else:
        execution_record = build_runtime_execution_record(
            run_id=run_id,
            case_id=str(source.get("case_id", "")).strip(),
            project=str(source.get("project", "mall")).strip() or "mall",
            source=str(source.get("source", "manual")).strip() or "manual",
            mode=str(source.get("mode", "generate_and_run")).strip() or "generate_and_run",
            status=str(source.get("status", "queued")).strip() or "queued",
            started_at=str(source.get("started_at", "")).strip(),
            finished_at=str(source.get("finished_at", "")).strip(),
            return_code=source.get("return_code"),
            created_at=str(source.get("created_at", "")).strip(),
            normalize_execution_record_payload=normalize_execution_record_payload,
        )

    status_value = str(source.get("status", "")).strip() or str(execution_record.get("status", "queued")).strip() or "queued"
    started_at = str(source.get("started_at", "")).strip() or str(execution_record.get("started_at", "")).strip()
    finished_at = str(source.get("finished_at", "")).strip() or str(execution_record.get("finished_at", "")).strip()
    mode_value = str(source.get("mode", "")).strip() or str(execution_record.get("mode", "generate_and_run")).strip() or "generate_and_run"
    project_value = str(source.get("project", execution_record.get("project", "mall"))).strip() or "mall"
    case_id_value = normalize_case_id(str(source.get("case_id", execution_record.get("case_id", ""))).strip()) if str(source.get("case_id", execution_record.get("case_id", ""))).strip() else ""
    inferred_page = [
        str(source.get("page", "")).strip(),
        str((source.get("page_surface", {}) or {}).get("page", "")).strip() if isinstance(source.get("page_surface"), dict) else "",
        str((source.get("page_object", {}) or {}).get("page", "")).strip() if isinstance(source.get("page_object"), dict) else "",
        str((source.get("test_points", {}) or {}).get("page", "")).strip() if isinstance(source.get("test_points"), dict) else "",
        str((execution_record.get("step_summary", {}) or {}).get("page", "")).strip() if isinstance(execution_record.get("step_summary"), dict) else "",
    ]
    page_value = ""
    for candidate in inferred_page:
        if candidate:
            page_value = normalize_page_slug(candidate)
            break

    has_model_payload = any(
        isinstance(source.get(key), dict)
        for key in ("page_surface", "page_surface_summary", "page_object", "page_object_summary", "test_points")
    )
    page_surface_payload = _dict_value(source.get("page_surface"))
    page_surface_summary = _dict_value(source.get("page_surface_summary"))
    if not page_surface_payload and page_surface_summary:
        page_surface_payload = {"confidence_summary": page_surface_summary}
    page_object_payload = _dict_value(source.get("page_object"))
    page_object_summary = _dict_value(source.get("page_object_summary"))
    if not page_object_payload and page_object_summary:
        page_object_payload = {"summary": page_object_summary}
    test_points_payload = _dict_value(source.get("test_points"))

    analysis_context: dict[str, Any] = {}
    if has_model_payload and page_value:
        analysis_context = build_page_analysis_context(
            page=page_value,
            project=project_value,
            case_id=case_id_value,
            page_url=str(source.get("page_url", "")).strip(),
            page_surface=page_surface_payload,
            page_object=page_object_payload,
            test_points=test_points_payload,
        )

    consumed_page_semantic_summary = _dict_value(analysis_context.get("page_semantic_summary")) or _dict_value(source.get("page_semantic_summary"))
    consumed_page_object_summary = _dict_value(analysis_context.get("page_object_summary")) or page_object_summary
    consumed_surface_summary = _dict_value(analysis_context.get("page_surface_summary")) or page_surface_summary
    consumed_test_points = _dict_value(analysis_context.get("test_points")) or test_points_payload
    consumed_model_versions = _dict_value(analysis_context.get("model_versions"))

    risk_report = _dict_value(source.get("risk_report"))
    if risk_report and any(consumed_model_versions.values()):
        risk_metadata = _dict_value(risk_report.get("metadata"))
        if not isinstance(risk_metadata.get("consumed_models"), dict):
            risk_metadata["consumed_models"] = consumed_model_versions
            risk_report = {**risk_report, "metadata": risk_metadata}

    stored_review_state = _dict_value(source.get("review_state"))
    review_state: dict[str, Any] = {}
    if has_model_payload and page_value:
        review_state = build_item_review_state(
            project=project_value,
            run_id=run_id,
            page=page_value,
            page_surface_summary=consumed_surface_summary,
            test_points=consumed_test_points,
            page_surface=_dict_value(analysis_context.get("page_surface")) or page_surface_payload,
            page_object=_dict_value(analysis_context.get("page_object")) or page_object_payload,
            risk_report=risk_report,
        )
    if not review_state:
        latest_review_state = build_run_review_state_from_decisions(project=project_value, run_id=run_id, page=page_value)
        review_state = latest_review_state or stored_review_state

    test_point_asset_context: dict[str, Any] = {}
    if page_value and case_id_value:
        test_point_asset_context = build_test_point_asset_gate_context(
            project=project_value,
            case_id=case_id_value,
            page=page_value,
            coverage=source.get("coverage", {}) if isinstance(source.get("coverage"), dict) else {},
            review_state=review_state if isinstance(review_state, dict) else {},
            risk_report=risk_report if isinstance(risk_report, dict) else {},
        )

    stored_execution_gate = _dict_value(source.get("execution_gate"))
    execution_gate = stored_execution_gate
    if (not isinstance(execution_gate, dict) or not execution_gate) and page_value and (has_model_payload or test_point_asset_context):
        execution_gate = build_execution_gate(
            page=page_value,
            final_status=status_value,
            coverage=source.get("coverage", {}) if isinstance(source.get("coverage"), dict) else {},
            page_surface_summary=consumed_surface_summary,
            page_semantic_summary=consumed_page_semantic_summary,
            page_object_summary=consumed_page_object_summary,
            test_points=consumed_test_points,
            review_state=review_state if isinstance(review_state, dict) else {},
            risk_report=risk_report if isinstance(risk_report, dict) else {},
            test_point_asset_context=test_point_asset_context,
        )
    latest_gate_decision = execution_gate_decision_for_run(
        run_id=run_id,
        project=project_value,
        page=page_value,
    )
    if latest_gate_decision:
        approval_status = str(latest_gate_decision.get("approval_status", "approved")).strip() or "approved"
        record_status = str(latest_gate_decision.get("record_status", "active")).strip() or "active"
        gate_manual = {
            "decision": str(latest_gate_decision.get("decision", "")).strip(),
            "note": str(latest_gate_decision.get("note", "")).strip(),
            "decided_by": str(latest_gate_decision.get("decided_by", "")).strip() or "anonymous",
            "decided_by_role": str(latest_gate_decision.get("decided_by_role", "")).strip() or "unknown",
            "updated_at": str(latest_gate_decision.get("updated_at", "")).strip(),
            "approval_status": approval_status,
            "record_status": record_status,
            "second_approver": str(latest_gate_decision.get("second_approver", "")).strip(),
            "second_approver_role": str(latest_gate_decision.get("second_approver_role", "")).strip(),
            "second_approved_at": str(latest_gate_decision.get("second_approved_at", "")).strip(),
            "revoked_at": str(latest_gate_decision.get("revoked_at", "")).strip(),
            "revoked_by": str(latest_gate_decision.get("revoked_by", "")).strip(),
            "revoked_by_role": str(latest_gate_decision.get("revoked_by_role", "")).strip(),
        }
        if not isinstance(execution_gate, dict) or not execution_gate:
            execution_gate = {
                "version": "ExecutionGateV1",
                "page": page_value,
                "decision": gate_manual["decision"],
                "requires_review": gate_manual["decision"] != "allow",
                "blockers": [],
                "warnings": [],
                "metrics": {},
            }
        execution_gate["manual_decision"] = gate_manual
        execution_gate["approval_status"] = approval_status
        execution_gate["record_status"] = record_status
        execution_gate["second_approver"] = gate_manual["second_approver"]
        execution_gate["second_approver_role"] = gate_manual["second_approver_role"]
        execution_gate["second_approved_at"] = gate_manual["second_approved_at"]
        execution_gate["revoked_at"] = gate_manual["revoked_at"]
        execution_gate["revoked_by"] = gate_manual["revoked_by"]
        execution_gate["revoked_by_role"] = gate_manual["revoked_by_role"]
        if record_status == "revoked":
            execution_gate["effective_decision"] = str(execution_gate.get("decision", "")).strip() or "allow"
            execution_gate["decision_source"] = "manual_revoked"
            execution_gate["requires_review"] = bool(execution_gate.get("requires_review", False))
        elif approval_status == "pending_second_approval":
            execution_gate["effective_decision"] = str(execution_gate.get("decision", "")).strip() or "allow"
            execution_gate["decision_source"] = "manual_pending_second_approval"
            execution_gate["requires_review"] = True
        else:
            execution_gate["effective_decision"] = gate_manual["decision"]
            execution_gate["decision_source"] = "manual_override"
    elif isinstance(execution_gate, dict) and execution_gate:
        execution_gate["effective_decision"] = str(execution_gate.get("decision", "")).strip() or "allow"
        execution_gate["decision_source"] = "system"

    review_audit_summary = build_review_audit_summary(review_state)
    review_audit_timeline = build_review_audit_timeline(run_id=run_id, page=page_value)
    risk_summary = build_risk_report_summary(risk_report)
    self_healing_summary = build_self_healing_summary(
        execution_record=execution_record,
        artifacts_dir=str(source.get("artifacts_dir", "")).strip(),
    )

    return {
        "run_id": run_id,
        "project": project_value,
        "case_id": case_id_value,
        "case_path": str(source.get("case_path", "")).strip(),
        "page": page_value,
        "source": str(source.get("source", execution_record.get("source", "manual"))).strip() or "manual",
        "mode": mode_value,
        "status": status_value,
        "created_at": str(source.get("created_at", "")).strip(),
        "started_at": started_at,
        "finished_at": finished_at,
        "return_code": source.get("return_code"),
        "log_path": str(source.get("log_path", "")).strip(),
        "artifacts_dir": str(source.get("artifacts_dir", "")).strip(),
        "videos_dir": str(source.get("videos_dir", "")).strip(),
        "latest_failure": source.get("latest_failure", {}) if isinstance(source.get("latest_failure"), dict) else {},
        "coverage": source.get("coverage", {}) if isinstance(source.get("coverage"), dict) else {},
        "page_semantic": analysis_context.get("page_semantic", {}) if isinstance(analysis_context.get("page_semantic"), dict) else (source.get("page_semantic") if isinstance(source.get("page_semantic"), dict) else {}),
        "page_semantic_summary": consumed_page_semantic_summary,
        "page_object_summary": consumed_page_object_summary,
        "risk_report": risk_report,
        "risk_summary": risk_summary,
        "self_healing_summary": self_healing_summary,
        "execution_gate": execution_gate,
        "review_state": review_state,
        "review_audit_summary": review_audit_summary,
        "review_audit_timeline": review_audit_timeline,
        "execution_record": normalize_execution_record_payload(
            {
                **execution_record,
                "run_id": run_id,
                "case_id": case_id_value,
                "project": project_value,
                "source": str(source.get("source", execution_record.get("source", "manual"))).strip() or "manual",
                "mode": mode_value,
                "status": status_value,
                "started_at": started_at,
                "finished_at": finished_at,
                "evidence_index": execution_record.get("evidence_index", {}),
                "metadata": {
                    **(execution_record.get("metadata", {}) if isinstance(execution_record.get("metadata"), dict) else {}),
                    "runtime_state_source": "runtime-store",
                    "case_path": str(source.get("case_path", "")).strip(),
                    "log_path": str(source.get("log_path", "")).strip(),
                    "artifacts_dir": str(source.get("artifacts_dir", "")).strip(),
                    "videos_dir": str(source.get("videos_dir", "")).strip(),
                },
            }
        ),
    }


def runtime_view_with_execution_record_preferred(
    entry: dict[str, Any],
    *,
    runtime_view_from_entry_fn: Callable[[dict[str, Any]], dict[str, Any]],
    load_runtime_execution_record_from_artifacts: LoadRuntimeExecutionRecordFromArtifacts,
    normalize_execution_record_payload: NormalizeExecutionRecordPayload,
) -> dict[str, Any]:
    view = runtime_view_from_entry_fn(entry)
    artifacts_dir_value = str(view.get("artifacts_dir", "")).strip()
    if not artifacts_dir_value:
        return view
    artifact_execution_record = load_runtime_execution_record_from_artifacts(Path(artifacts_dir_value))
    if not artifact_execution_record:
        return view

    runtime_execution_record = _dict_value(view.get("execution_record"))
    normalized_execution_record = normalize_execution_record_payload(
        {
            **artifact_execution_record,
            "run_id": str(artifact_execution_record.get("run_id", "")).strip() or str(view.get("run_id", "")).strip(),
            "case_id": str(artifact_execution_record.get("case_id", "")).strip() or str(view.get("case_id", "")).strip(),
            "project": str(artifact_execution_record.get("project", "")).strip() or str(view.get("project", "mall")).strip(),
            "source": str(artifact_execution_record.get("source", "")).strip() or str(view.get("source", "manual")).strip(),
            "mode": str(artifact_execution_record.get("mode", "")).strip() or str(view.get("mode", "generate_and_run")).strip(),
            "metadata": {
                **(runtime_execution_record.get("metadata", {}) if isinstance(runtime_execution_record.get("metadata"), dict) else {}),
                **(artifact_execution_record.get("metadata", {}) if isinstance(artifact_execution_record.get("metadata"), dict) else {}),
                "runtime_realtime_supplement": True,
            },
        }
    )
    evidence_index = normalized_execution_record.get("evidence_index", {}) if isinstance(normalized_execution_record.get("evidence_index"), dict) else {}
    runner_exit_code = evidence_index.get("runner_exit_code")
    return {
        **view,
        "status": str(normalized_execution_record.get("status", "")).strip() or str(view.get("status", "")).strip(),
        "started_at": str(normalized_execution_record.get("started_at", "")).strip() or str(view.get("started_at", "")).strip(),
        "finished_at": str(normalized_execution_record.get("finished_at", "")).strip() or str(view.get("finished_at", "")).strip(),
        "return_code": runner_exit_code if isinstance(runner_exit_code, int) else view.get("return_code"),
        "execution_record": normalized_execution_record,
    }


def find_run_item(
    run_id: str,
    *,
    get_job: GetJob,
    read_runtime_runs: ReadRuntimeRuns,
    runtime_run_id_fn: Callable[[dict[str, Any]], str],
    runtime_view_with_execution_record_preferred_fn: Callable[[dict[str, Any]], dict[str, Any]],
) -> dict[str, Any] | None:
    for item in read_runtime_runs():
        if runtime_run_id_fn(item) == run_id:
            return runtime_view_with_execution_record_preferred_fn(item)
    job = get_job(run_id)
    if job:
        return job
    return None


def materialize_runtime_case_yaml(
    *,
    run_id: str,
    case_id: str,
    script_code: str,
    runs_dir: Path,
) -> Path:
    """Write the confirmed case script to an isolated runtime YAML file."""
    normalized_run_id = str(run_id or "").strip()
    normalized_case_id = normalize_case_id(str(case_id or "").strip()) or "UNKNOWN"
    normalized_script_code = str(script_code or "").strip()
    if not normalized_run_id:
        raise ValueError("run_id must not be empty")
    if not normalized_script_code:
        raise ValueError("script_code must not be empty")

    runtime_cases_dir = runs_dir / "runtime-cases" / normalized_run_id
    runtime_cases_dir.mkdir(parents=True, exist_ok=True)
    runtime_case_path = runtime_cases_dir / f"{normalized_case_id}.yaml"
    runtime_case_path.write_text(normalized_script_code + "\n", encoding="utf-8")
    return runtime_case_path.resolve()


def start_run(
    *,
    project: str,
    case_id: str,
    case_path: Path,
    source: str,
    runs_dir: Path,
    now_iso_fn: NowIsoFn,
    build_runtime_execution_record: BuildRuntimeExecutionRecord,
    runtime_view_from_entry_fn: RuntimeViewFromEntryFn,
    store_run_job: StoreRunJob,
    append_runtime_run: AppendRuntimeRun,
    append_history: AppendHistory,
    execute_run_fn: ExecuteRunFn,
    runtime_case_script: str = "",
    thread_factory: ThreadFactory = threading.Thread,
) -> dict[str, Any]:
    run_id = uuid.uuid4().hex
    if str(runtime_case_script or "").strip():
        case_path = materialize_runtime_case_yaml(
            run_id=run_id,
            case_id=case_id,
            script_code=runtime_case_script,
            runs_dir=runs_dir,
        )
    log_path = runs_dir / f"{run_id}.log"
    artifacts_dir = runs_dir / f"{run_id}-artifacts"
    videos_dir = runs_dir / f"{run_id}-videos"
    created_at = now_iso_fn()
    execution_record = build_runtime_execution_record(
        run_id=run_id,
        case_id=case_id,
        project=project,
        source=source,
        mode="generate_and_run",
        status="queued",
        started_at="",
        finished_at="",
        return_code=None,
        created_at=created_at,
    )
    job = {
        "run_id": run_id,
        "project": project,
        "case_id": case_id,
        "case_path": str(case_path.resolve()),
        "source": source,
        "mode": "generate_and_run",
        "status": "queued",
        "created_at": created_at,
        "started_at": "",
        "finished_at": "",
        "return_code": None,
        "log_path": str(log_path.resolve()),
        "artifacts_dir": str(artifacts_dir.resolve()),
        "videos_dir": str(videos_dir.resolve()),
        "latest_failure": {},
        "execution_record": execution_record,
    }
    normalized_job = runtime_view_from_entry_fn(job)
    store_run_job(run_id, dict(normalized_job))
    append_runtime_run(dict(normalized_job))
    append_history(
        {
            "timestamp": now_iso_fn(),
            "action": "run_case",
            "case_id": case_id,
            "path": str(case_path.resolve()),
            "run_id": run_id,
            "queue_status": "queued",
        }
    )
    worker = thread_factory(target=execute_run_fn, args=(job,), daemon=True)
    worker.start()
    return normalized_job


def wait_run_terminal(
    run_id: str,
    timeout_seconds: int,
    *,
    find_run_item: Callable[[str], dict[str, Any] | None],
    time_fn: TimeFn = time.time,
    sleep_fn: SleepFn = time.sleep,
) -> tuple[dict[str, Any] | None, bool]:
    deadline = time_fn() + max(timeout_seconds, 1)
    last_item: dict[str, Any] | None = None
    while time_fn() < deadline:
        current = find_run_item(run_id)
        if current:
            last_item = current
            status_value = str(current.get("status", "")).strip().lower()
            if status_value in {"passed", "failed", "cancelled"}:
                return current, False
        sleep_fn(0.5)
    return last_item, True


def execute_run(
    job: dict[str, Any],
    *,
    build_run_command_fn: BuildRunCommand,
    now_iso_fn: NowIsoFn,
    update_job: UpdateRun,
    update_runtime_run: UpdateRun,
    load_runtime_execution_record_from_artifacts: LoadRuntimeExecutionRecordFromArtifacts,
    collect_failure_entries: CollectFailureEntries,
    is_within: IsWithin,
    repo_root: Path,
    runner_root: Path,
    popen_fn: Callable[..., Any] = subprocess.Popen,
    run_fn: Callable[..., Any] = subprocess.run,
) -> None:
    run_id = str(job["run_id"])
    case_path = Path(job["case_path"]).resolve()
    log_path = Path(job["log_path"]).resolve()
    artifacts_dir = Path(job["artifacts_dir"]).resolve()
    videos_dir = Path(job["videos_dir"]).resolve()
    allure_results_dir = Path(os.getenv("ALLURE_RESULTS_DIR") or artifacts_dir / "allure-results")
    allure_report_dir = Path(os.getenv("ALLURE_REPORT_DIR") or runner_root / "allure-report")
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    videos_dir.mkdir(parents=True, exist_ok=True)
    allure_results_dir.mkdir(parents=True, exist_ok=True)

    command, env = build_run_command_fn(case_path)
    command = replace_allure_results_dir(command, allure_results_dir)
    env["PLAYWRIGHT_ARTIFACTS_DIR"] = str(artifacts_dir)
    env["PLAYWRIGHT_VIDEO_DIR"] = str(videos_dir)
    env["WORKBENCH_RUN_ID"] = run_id

    started_at_value = now_iso_fn()
    update_job(run_id, {"status": "running", "started_at": started_at_value, "command": " ".join(command)})
    update_runtime_run_with_retry(
        run_id,
        {"status": "running", "started_at": started_at_value},
        update_runtime_run=update_runtime_run,
    )

    with log_path.open("w", encoding="utf-8") as log_fp:
        log_fp.write(f"[run] id={run_id}\n")
        log_fp.write(f"[run] case={case_path}\n")
        log_fp.write(f"[run] command={' '.join(command)}\n")
        log_fp.write(f"[run] artifacts={artifacts_dir}\n")
        log_fp.write(f"[run] allure_results={allure_results_dir}\n")
        log_fp.flush()

        process = popen_fn(
            command,
            cwd=str(repo_root),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        timeout_seconds = _positive_int_from_env(env, "WORKBENCH_RUN_TIMEOUT_SECONDS", default=600)
        deadline = time.time() + timeout_seconds
        timed_out = False
        selector = selectors.DefaultSelector()
        if process.stdout is not None:
            selector.register(process.stdout, selectors.EVENT_READ)
        while True:
            if process.poll() is not None:
                break
            if time.time() >= deadline:
                timed_out = True
                log_fp.write(f"\n[run] timeout after {timeout_seconds}s; terminating runner\n")
                log_fp.flush()
                process.kill()
                break
            for key, _mask in selector.select(timeout=0.5):
                line = key.fileobj.readline()
                if line:
                    log_fp.write(line)
                    log_fp.flush()
        if process.stdout is not None:
            for line in process.stdout.readlines():
                log_fp.write(line)
            process.stdout.close()
        return_code = process.wait()
        if timed_out and return_code == 0:
            return_code = 124
        log_fp.write(f"\n[run] completed returncode={return_code}\n")
        log_fp.flush()

        allure_cmd = [
            sys.executable,
            str(runner_root / "tools" / "manage_allure.py"),
            "--results-dir",
            str(allure_results_dir),
            "--report-dir",
            str(allure_report_dir),
            "generate",
        ]
        log_fp.write(f"[allure] command={' '.join(allure_cmd)}\n")
        log_fp.flush()
        allure_result = run_fn(
            allure_cmd,
            cwd=str(repo_root),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        if allure_result.stdout:
            log_fp.write(allure_result.stdout.strip() + "\n")
        if allure_result.stderr:
            log_fp.write("[allure][stderr]\n")
            log_fp.write(allure_result.stderr.strip() + "\n")
        log_fp.write(f"[allure] completed returncode={allure_result.returncode}\n")
        log_fp.flush()

    status_value = "passed" if return_code == 0 else "timeout" if timed_out else "failed"
    finished_at_value = now_iso_fn()
    artifact_execution_record = load_runtime_execution_record_from_artifacts(artifacts_dir)
    if not artifact_execution_record:
        LOGGER.warning("run %s evidence degraded: no manifest found in %s", run_id, artifacts_dir)
        artifact_execution_record = build_fallback_execution_record(
            job,
            status_value=status_value,
            return_code=return_code,
            started_at=started_at_value,
            finished_at=finished_at_value,
            artifacts_dir=artifacts_dir,
            videos_dir=videos_dir,
            timeout_seconds=timeout_seconds,
            timed_out=timed_out,
        )
        if isinstance(artifact_execution_record, dict):
            artifact_execution_record["evidence_degraded"] = True
    case_failure: dict[str, Any] = {}
    if status_value == "failed":
        run_failure_entries: list[dict[str, Any]] = []
        for item in collect_failure_entries():
            artifact_dir_value = str(item.get("artifact_dir", "")).strip()
            if not artifact_dir_value:
                continue
            artifact_dir_path = Path(artifact_dir_value)
            if is_within(artifact_dir_path, artifacts_dir):
                run_failure_entries.append(item)
        if run_failure_entries:
            case_failure = run_failure_entries[0]
        elif is_runner_termination(return_code, timed_out=timed_out):
            case_failure = build_runner_termination_failure(
                run_id=run_id,
                case_id=str(job.get("case_id", "")).strip(),
                project=str(job.get("project", "mall")).strip() or "mall",
                case_path=str(job.get("case_path", "")).strip(),
                return_code=return_code,
                timeout_seconds=timeout_seconds,
                timed_out=timed_out,
            )
    update_job(
        run_id,
        {
            "status": status_value,
            "finished_at": finished_at_value,
            "return_code": return_code,
            "latest_failure": case_failure,
            "execution_record": artifact_execution_record,
        },
    )
    update_runtime_run_with_retry(
        run_id,
        {
            "status": status_value,
            "finished_at": finished_at_value,
            "return_code": return_code,
            "artifacts_dir": str(artifacts_dir),
            "videos_dir": str(videos_dir),
            "latest_failure": case_failure,
            "execution_record": artifact_execution_record,
        },
        update_runtime_run=update_runtime_run,
    )


def _duration_ms_from_run(run_item: dict[str, Any], execution_record: dict[str, Any]) -> int:
    """从运行快照或起止时间中计算执行耗时毫秒数。"""
    raw_duration = execution_record.get("duration_seconds")
    try:
        return max(0, int(float(raw_duration or 0) * 1000))
    except (TypeError, ValueError):
        pass
    started_at = _parse_iso_datetime(_text(execution_record.get("started_at")) or _text(run_item.get("started_at")))
    finished_at = _parse_iso_datetime(_text(execution_record.get("finished_at")) or _text(run_item.get("finished_at")))
    if started_at and finished_at:
        return max(0, int((finished_at - started_at).total_seconds() * 1000))
    return 0


def persist_runtime_run_to_case_center(db: Session, run_item: dict[str, Any]) -> TestCaseExecution | None:
    """将运行态执行结果同步写入用例中心执行记录。

    Args:
        db: SQLAlchemy database session.
        run_item: Runtime run dictionary containing run_id, case_id,
            project, status, and optional execution_record.

    Returns:
        The persisted TestCaseExecution record, or None if the run_item
        is invalid or the referenced case is not found.
    """
    if not isinstance(run_item, dict):
        return None
    run_id = _text(run_item.get("run_id"))
    case_id = _text(run_item.get("case_id"))
    project = _text(run_item.get("project")) or "mall"
    if not case_id:
        return None
    execution_record = run_item.get("execution_record") if isinstance(run_item.get("execution_record"), dict) else {}
    status_value = (_text(run_item.get("status")) or _text(execution_record.get("status")) or "unknown").lower()
    if status_value not in {"passed", "failed", "cancelled", "skipped", "error", "timeout"}:
        return None
    case = TestCaseRepository(db).get_by_case_id_and_project(case_id, project)
    if case is None:
        LOGGER.warning(
            "skip runtime persistence because case is not found in project: project=%s case_id=%s run_id=%s",
            project,
            case_id,
            run_id,
        )
        return None
    executed_at = (
        _parse_iso_datetime(_text(execution_record.get("finished_at")))
        or _parse_iso_datetime(_text(run_item.get("finished_at")))
        or _parse_iso_datetime(_text(execution_record.get("started_at")))
        or _parse_iso_datetime(_text(run_item.get("started_at")))
        or datetime.now(UTC)
    )
    duration_ms = _duration_ms_from_run(run_item, execution_record)
    existing: TestCaseExecution | None = None
    if run_id:
        existing = db.execute(
            select(TestCaseExecution).where(
                TestCaseExecution.case_id == int(case.id),
                TestCaseExecution.report_url.like(f"%run_id={run_id}%"),
            )
        ).scalar_one_or_none()
    if existing is None:
        existing = TestCaseExecution(
            case_id=int(case.id),
            status=status_value,
            duration_ms=duration_ms,
            report_url="",
            executed_at=executed_at,
        )
        db.add(existing)
        db.flush()
    else:
        existing.status = status_value
        existing.duration_ms = duration_ms
        existing.executed_at = executed_at
    report_url = f"/react/execution/results/{int(existing.id)}"
    if run_id:
        report_url = f"{report_url}?run_id={run_id}"
    existing.report_url = report_url
    case.last_execution_result = status_value
    case.last_report_url = report_url
    case.updated_at = datetime.now(UTC)
    db.add(case)
    db.add(existing)
    db.commit()
    db.refresh(existing)
    return existing
