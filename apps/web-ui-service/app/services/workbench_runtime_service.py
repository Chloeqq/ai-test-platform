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
import yaml
from datetime import datetime
from shared_backend.datetime_compat import UTC
from pathlib import Path
from typing import Any, Callable

from shared_backend.case_ids import normalize_case_id
from shared_backend.type_utils import dict_value as _dict_value
from sqlalchemy import select, text as _text
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


def _apply_sut_base_url(env: dict[str, str], case_path: Path) -> None:
    """从用例 YAML 中提取被测系统的 page_url 作为 runner 的 BASE_URL。

    平台自身的 BASE_URL（web 服务地址）和 runner 需要的 BASE_URL（被测系统地址）
    是两个不同的概念。多项目场景下不存在合理的默认值——page_url 必须在生成用例时
    由平台写入 YAML，此处仅负责提取和校验。
    """
    try:
        import yaml

        raw = case_path.read_text(encoding="utf-8")
        payload = yaml.safe_load(raw) or {}
    except Exception as exc:
        raise RuntimeError(
            f"无法读取用例 YAML 以提取被测系统地址: {case_path}"
        ) from exc
    if not isinstance(payload, dict):
        raise RuntimeError(
            f"用例 YAML 格式无效，无法提取被测系统地址: {case_path}"
        )
    execution = payload.get("execution")
    if not isinstance(execution, dict):
        raise RuntimeError(
            f"用例 YAML 缺少 execution 段，无法提取 page_url: {case_path}"
        )
    page_url = str(execution.get("page_url") or "").strip()
    if not page_url:
        raise RuntimeError(
            f"用例 YAML 的 execution.page_url 为空，无法确定被测系统地址: {case_path}"
        )
    env["BASE_URL"] = page_url


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
    # 从 YAML 中提取被测系统的 page_url 作为 runner 的 BASE_URL，
    # 而不是复用平台自身的 BASE_URL（web 服务和 runner 的 BASE_URL 含义完全不同）。
    _apply_sut_base_url(env, case_path)
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


# load_runtime_execution_record_from_artifacts → 移至 workbench_runtime_views.py


# runtime_view_from_entry → 移至 workbench_runtime_views.py


# runtime_view_with_execution_record_preferred → 移至 workbench_runtime_views.py
# 以下 import 保持向后兼容：所有外部调用者通过 workbench_runtime_service 访问这些函数。
from app.services.workbench_runtime_views import (  # noqa: E402
    load_runtime_execution_record_from_artifacts,
    runtime_view_from_entry,
    runtime_view_with_execution_record_preferred,
)


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
        runtime_case_script = _resolve_pool_data(runtime_case_script)
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


def _execute_setup_sql(
    *,
    case_path: Path,
    log_fp: Any,
    run_id: str,
) -> bool:
    """V3.0: 执行用例的 setup_sql。返回 True 表示执行失败。"""
    try:
        with open(case_path, encoding="utf-8") as fh:
            case = yaml.safe_load(fh)
    except (yaml.YAMLError, OSError) as exc:
        log_fp.write(f"[setup_sql] failed to read case YAML: {exc}\n")
        return True  # 无法读取 → 失败

    setup_sql = str(case.get("setup_sql", "")).strip() if isinstance(case, dict) else ""
    if not setup_sql:
        return False  # 无 setup_sql → 跳过

    log_fp.write(f"[setup_sql] executing: {setup_sql[:200]}\n")
    log_fp.flush()

    try:
        from shared_backend.db import get_db_session as SessionLocal

        with SessionLocal() as session:
            for statement in setup_sql.split(";"):
                stmt = statement.strip()
                if not stmt:
                    continue
                session.execute(_text(stmt))
            session.commit()
        log_fp.write(f"[setup_sql] executed successfully\n")
        return False
    except Exception as exc:
        log_fp.write(f"[setup_sql] execution failed: {exc}\n")
        return True


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

        # V3.0: 在启动 Runner 前执行 setup_sql
        if _execute_setup_sql(case_path=case_path, log_fp=log_fp, run_id=run_id):
            update_job(run_id, {"status": "setup_failed", "finished_at": now_iso_fn()})
            return

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
        existing = TestCaseRepository(db).get_execution_by_report_url_like(
            int(case.id), f"%run_id={run_id}%"
        )
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



def _resolve_pool_data(yaml_text: str) -> str:
    """解析 YAML 中的 source_type: pool 字段，用数据池的实际值替换。

    与运行时侧（Runner `data_expander`）共用 `resolve_pool_reference`，
    确保「按 (pool_name, key) 精确解析为标量值」的契约只有一处实现。
    单条引用解析失败（池/key 缺失）时跳过该字段，把 pool 引用原样留给
    Runner 处理，而非中断整批替换。
    """
    data = yaml.safe_load(yaml_text) or {}
    if not isinstance(data, dict):
        return yaml_text

    case_data = data.get("data") if isinstance(data.get("data"), dict) else {}
    pool_refs = [
        (key, entry)
        for key, entry in case_data.items()
        if isinstance(entry, dict) and entry.get("source_type") == "pool"
    ]
    if not pool_refs:
        return yaml_text

    from shared_backend.data_pool_resolver import PoolResolutionError, resolve_pool_reference
    from app.services.test_data_pool_service import load_runner_data_pool_snapshot

    pool_snapshot = load_runner_data_pool_snapshot(None)
    resolved = False
    for key, entry in pool_refs:
        pool_name = str(entry.get("pool_name", "")).strip()
        item_key = str(entry.get("key", "")).strip()
        if not pool_name or not item_key:
            continue
        try:
            value = resolve_pool_reference(
                field=key,
                pool_name=pool_name,
                item_key=item_key,
                pool_snapshot=pool_snapshot,
            )
        except PoolResolutionError:
            continue
        entry["source_type"] = "inline"
        entry.pop("pool_name", None)
        entry.pop("key", None)
        entry["value"] = value
        resolved = True

    if resolved:
        return yaml.safe_dump(data, allow_unicode=True, sort_keys=False)
    return yaml_text