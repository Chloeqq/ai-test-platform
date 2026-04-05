from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from . import legacy_workbench


router = APIRouter(tags=["workbench-runs"])


@router.post("/api/workbench/run")
def run_case(payload: legacy_workbench.RunCasePayload) -> dict[str, Any]:
    legacy_workbench._sync_stage_a_workbench_state()
    legacy_workbench._ensure_dirs()
    normalized_case_id = legacy_workbench._safe_case_id(payload.case_id)
    if payload.case_path.strip():
        case_path = Path(payload.case_path).expanduser()
        if not case_path.is_absolute():
            case_path = legacy_workbench.REPO_ROOT / case_path
        case_path = case_path.resolve()
    else:
        case_path = legacy_workbench._resolve_case_yaml_path(payload.project, normalized_case_id)
    if not case_path.exists():
        raise legacy_workbench.HTTPException(
            status_code=legacy_workbench.status.HTTP_404_NOT_FOUND,
            detail=f"case file not found: {case_path}",
        )
    if not legacy_workbench._is_within(case_path, legacy_workbench.ASSETS_CASES_ROOT):
        raise legacy_workbench.HTTPException(
            status_code=legacy_workbench.status.HTTP_400_BAD_REQUEST,
            detail="case_path must stay under assets/test-cases",
        )
    job = legacy_workbench._start_run(
        project=payload.project,
        case_id=normalized_case_id,
        case_path=case_path,
        source=payload.source,
    )
    return {"item": job}


@router.get("/api/workbench/runs")
def list_runs(limit: int = Query(default=30, ge=1, le=200)) -> dict[str, Any]:
    legacy_workbench._sync_stage_a_workbench_state()
    legacy_workbench._ensure_dirs()
    items = [
        legacy_workbench._attach_test_point_asset_summary(
            legacy_workbench._runtime_view_with_execution_record_preferred(item)
        )
        for item in legacy_workbench._read_json_list(legacy_workbench.RUNTIME_RUNS_FILE)
    ]
    return {"items": items[:limit]}


@router.get("/api/workbench/runs/{run_id}")
def get_run(run_id: str) -> dict[str, Any]:
    legacy_workbench._sync_stage_a_workbench_state()
    legacy_workbench._ensure_dirs()
    job = legacy_workbench._get_job(run_id)
    if job:
        return {"item": legacy_workbench._attach_test_point_asset_summary(job)}
    for item in legacy_workbench._read_json_list(legacy_workbench.RUNTIME_RUNS_FILE):
        if legacy_workbench._runtime_run_id(item) == run_id:
            return {
                "item": legacy_workbench._attach_test_point_asset_summary(
                    legacy_workbench._runtime_view_with_execution_record_preferred(item)
                )
            }
    raise legacy_workbench.HTTPException(
        status_code=legacy_workbench.status.HTTP_404_NOT_FOUND,
        detail="run not found",
    )


@router.post("/api/workbench/runs/{run_id}/rerun")
def rerun_case(run_id: str) -> dict[str, Any]:
    legacy_workbench._sync_stage_a_workbench_state()
    legacy_workbench._ensure_dirs()
    run_item = legacy_workbench._get_job(run_id)
    if not run_item:
        historical = next(
            (item for item in legacy_workbench._read_json_list(legacy_workbench.RUNTIME_RUNS_FILE) if legacy_workbench._runtime_run_id(item) == run_id),
            None,
        )
        run_item = legacy_workbench._runtime_view_with_execution_record_preferred(historical) if historical else None
    if not run_item:
        raise legacy_workbench.HTTPException(
            status_code=legacy_workbench.status.HTTP_404_NOT_FOUND,
            detail="run not found",
        )
    case_path = Path(str(run_item.get("case_path", "")))
    if not case_path.exists():
        raise legacy_workbench.HTTPException(
            status_code=legacy_workbench.status.HTTP_404_NOT_FOUND,
            detail="case file not found for rerun",
        )
    new_job = legacy_workbench._start_run(
        project=str(run_item.get("project", "default")),
        case_id=str(run_item.get("case_id", "")).strip() or "UNKNOWN",
        case_path=case_path,
        source="rerun",
    )
    legacy_workbench._append_history(
        {
            "timestamp": legacy_workbench._now_iso(),
            "action": "rerun_case",
            "case_id": run_item.get("case_id", ""),
            "from_run_id": run_id,
            "run_id": new_job["run_id"],
            "path": str(case_path.resolve()),
            "queue_status": "queued",
        }
    )
    return {"item": new_job}


@router.get("/api/workbench/runs/{run_id}/events")
def stream_run_events(run_id: str) -> StreamingResponse:
    legacy_workbench._sync_stage_a_workbench_state()
    legacy_workbench._ensure_dirs()
    run = legacy_workbench._get_job(run_id)
    if run:
        log_path = Path(run["log_path"])
    else:
        historical = next(
            (item for item in legacy_workbench._read_json_list(legacy_workbench.RUNTIME_RUNS_FILE) if legacy_workbench._runtime_run_id(item) == run_id),
            None,
        )
        if not historical:
            raise legacy_workbench.HTTPException(
                status_code=legacy_workbench.status.HTTP_404_NOT_FOUND,
                detail="run not found",
            )
        log_path = Path(str(historical.get("log_path", "")))
    if not log_path.exists():
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text("", encoding="utf-8")

    def event_stream():
        offset = 0
        while True:
            if log_path.exists():
                with log_path.open("r", encoding="utf-8", errors="ignore") as fp:
                    fp.seek(offset)
                    chunk = fp.read()
                    offset = fp.tell()
                if chunk:
                    for line in chunk.splitlines():
                        payload = {"run_id": run_id, "line": line}
                        yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
            current = legacy_workbench._get_job(run_id)
            current_status = ""
            if current:
                current_status = str(current.get("status", ""))
            else:
                past = next(
                    (item for item in legacy_workbench._read_json_list(legacy_workbench.RUNTIME_RUNS_FILE) if legacy_workbench._runtime_run_id(item) == run_id),
                    None,
                )
                current_status = str((past or {}).get("status", ""))
            if current_status in {"passed", "failed", "cancelled"}:
                end_payload = {"run_id": run_id, "event": "complete", "status": current_status}
                yield f"data: {json.dumps(end_payload, ensure_ascii=False)}\n\n"
                break
            time.sleep(0.5)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/api/workbench/runs/{run_id}/analysis")
def get_run_analysis(run_id: str) -> dict[str, Any]:
    legacy_workbench._sync_stage_a_workbench_state()
    legacy_workbench._ensure_dirs()
    run_item = legacy_workbench._get_job(run_id)
    if not run_item:
        historical = next(
            (item for item in legacy_workbench._read_json_list(legacy_workbench.RUNTIME_RUNS_FILE) if legacy_workbench._runtime_run_id(item) == run_id),
            None,
        )
        run_item = legacy_workbench._runtime_view_with_execution_record_preferred(historical) if historical else None
    if not run_item:
        raise legacy_workbench.HTTPException(
            status_code=legacy_workbench.status.HTTP_404_NOT_FOUND,
            detail="run not found",
        )
    artifacts_dir = Path(str(run_item.get("artifacts_dir", "")).strip())
    if artifacts_dir.exists():
        failures = [
            legacy_workbench._normalize_failure_entry_view(item)
            for item in legacy_workbench._collect_failure_entries()
            if legacy_workbench._is_within(Path(item["artifact_dir"]), artifacts_dir)
        ]
    else:
        failures = []
    if not failures and run_item.get("latest_failure"):
        failures = [legacy_workbench._normalize_failure_entry_view(run_item["latest_failure"])]
    return {
        "items": failures,
        "failure_source_summary": legacy_workbench._build_run_failure_source_summary(failures),
    }


@router.post("/api/workbench/runs/{run_id}/heal")
def heal_run(run_id: str) -> dict[str, Any]:
    legacy_workbench._sync_stage_a_workbench_state()
    legacy_workbench._ensure_dirs()
    run_item = legacy_workbench._get_job(run_id)
    if not run_item:
        historical = next(
            (item for item in legacy_workbench._read_json_list(legacy_workbench.RUNTIME_RUNS_FILE) if legacy_workbench._runtime_run_id(item) == run_id),
            None,
        )
        run_item = legacy_workbench._runtime_view_with_execution_record_preferred(historical) if historical else None
    if not run_item:
        raise legacy_workbench.HTTPException(
            status_code=legacy_workbench.status.HTTP_404_NOT_FOUND,
            detail="run not found",
        )
    case_path = Path(str(run_item.get("case_path", "")))
    if not case_path.exists():
        raise legacy_workbench.HTTPException(
            status_code=legacy_workbench.status.HTTP_404_NOT_FOUND,
            detail="case file not found for this run",
        )

    artifacts_dir = Path(str(run_item.get("artifacts_dir", "")))
    if not artifacts_dir.exists():
        raise legacy_workbench.HTTPException(
            status_code=legacy_workbench.status.HTTP_400_BAD_REQUEST,
            detail="artifact directory not found",
        )

    candidate_dirs = [path.parent for path in artifacts_dir.rglob("suggestion.json")]
    if not candidate_dirs:
        raise legacy_workbench.HTTPException(
            status_code=legacy_workbench.status.HTTP_400_BAD_REQUEST,
            detail="suggestion.json not found; cannot heal",
        )
    artifact_case_dir = max(candidate_dirs, key=lambda p: p.stat().st_mtime)

    command = [
        legacy_workbench._get_python_bin(),
        str(legacy_workbench.REPO_ROOT / "agents" / "self-healing-advisor-agent" / "apply_fix.py"),
        "auto-heal",
        "--case",
        str(case_path.resolve()),
        "--artifacts",
        str(artifact_case_dir.resolve()),
        "--previous-attempts",
        "0",
    ]
    result = legacy_workbench.subprocess.run(
        command,
        cwd=str(legacy_workbench.REPO_ROOT),
        text=True,
        capture_output=True,
        check=False,
    )
    output = (result.stdout or "") + ("\n" + result.stderr if result.stderr else "")
    payload = legacy_workbench._extract_json_from_text(output)
    if result.returncode != 0:
        raise legacy_workbench.HTTPException(
            status_code=legacy_workbench.status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "message": "self-healing failed",
                "return_code": result.returncode,
                "output": output[-3000:],
            },
        )

    legacy_workbench._append_history(
        {
            "timestamp": legacy_workbench._now_iso(),
            "action": "self_heal",
            "case_id": run_item.get("case_id", ""),
            "run_id": run_id,
            "artifact_dir": str(artifact_case_dir.resolve()),
            "status": payload.get("status", "success"),
        }
    )
    return {"item": payload, "raw_output": output}


@router.post("/api/workbench/runs/{run_id}/heal-and-rerun")
def heal_and_rerun_case(
    run_id: str,
    wait_seconds: int = Query(default=180, ge=5, le=900),
) -> dict[str, Any]:
    legacy_workbench._sync_stage_a_workbench_state()
    legacy_workbench._ensure_dirs()
    source_item = legacy_workbench._find_run_item(run_id)
    if not source_item:
        raise legacy_workbench.HTTPException(
            status_code=legacy_workbench.status.HTTP_404_NOT_FOUND,
            detail="run not found",
        )

    heal_ok = True
    heal_item: dict[str, Any] = {}
    heal_error: Any = None
    heal_run_fn = getattr(legacy_workbench, "heal_run")
    rerun_case_fn = getattr(legacy_workbench, "rerun_case")
    try:
        heal_resp = heal_run_fn(run_id)
        heal_item = heal_resp.get("item", {}) if isinstance(heal_resp, dict) else {}
    except legacy_workbench.HTTPException as exc:
        heal_ok = False
        heal_error = exc.detail
    except Exception as exc:  # pragma: no cover
        heal_ok = False
        heal_error = str(exc)

    rerun_resp = rerun_case_fn(run_id)
    rerun_job = rerun_resp.get("item", {})
    rerun_id = str(rerun_job.get("run_id", "")).strip()
    final_item, timed_out = legacy_workbench._wait_run_terminal(rerun_id, timeout_seconds=wait_seconds)
    status_value = str((final_item or rerun_job).get("status", "running")).strip().lower() or "running"

    summary = {
        "source_run_id": run_id,
        "source_status": source_item.get("status", ""),
        "heal": {
            "ok": heal_ok,
            "item": heal_item,
            "error": heal_error,
        },
        "rerun": {
            "run_id": rerun_id,
            "status": status_value,
            "timed_out": timed_out,
            "item": final_item or rerun_job,
        },
    }
    legacy_workbench._append_history(
        {
            "timestamp": legacy_workbench._now_iso(),
            "action": "heal_and_rerun_case",
            "case_id": source_item.get("case_id", ""),
            "from_run_id": run_id,
            "run_id": rerun_id,
            "heal_ok": heal_ok,
            "rerun_status": status_value,
        }
    )
    return {"item": summary}
