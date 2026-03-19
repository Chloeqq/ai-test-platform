import json
import os
import subprocess
import threading
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter, HTTPException, Query, Response, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

router = APIRouter(tags=["legacy-workbench"])

REPO_ROOT = Path(__file__).resolve().parents[3]
WEB_UI_STATE_ROOT = REPO_ROOT / "web-ui" / "state"
WEB_UI_DEFAULT_STATE_DIR = WEB_UI_STATE_ROOT / "default"
WEB_UI_RUNS_DIR = WEB_UI_STATE_ROOT / "runs"
WEB_UI_REPORTING_DIR = WEB_UI_STATE_ROOT / "reporting"
TEST_POINTS_ROOT = WEB_UI_STATE_ROOT / "test-points"
ASSETS_CASES_ROOT = REPO_ROOT / "assets" / "test-cases"
AI_CASES_ROOT = ASSETS_CASES_ROOT / "ai-generated"
PAGE_OBJECTS_ROOT = REPO_ROOT / "assets" / "page-objects" / "web"
RUNNER_ROOT = REPO_ROOT / "runners" / "web-playwright-python"
ALLURE_REPORT_ROOT = RUNNER_ROOT / "allure-report"
EXECUTION_REPORTS_ROOT = REPO_ROOT / "reports" / "executions"
HISTORY_FILE = WEB_UI_DEFAULT_STATE_DIR / "history.json"
RUNTIME_RUNS_FILE = WEB_UI_DEFAULT_STATE_DIR / "runtime-runs.json"
DEFECT_LINKS_FILE = WEB_UI_REPORTING_DIR / "defect-links.json"

_FILE_LOCK = threading.Lock()
_RUN_LOCK = threading.Lock()
_RUN_JOBS: dict[str, dict[str, Any]] = {}


class GenerateCasePayload(BaseModel):
    project: str = Field(default="default")
    page: str = Field(default="product")
    requirement: str = Field(default="", min_length=1)
    title: str = Field(default="")
    case_id: str = Field(default="")
    priority: str = Field(default="P1")
    tags: list[str] = Field(default_factory=lambda: ["ai-generated"])


class SaveCasePayload(BaseModel):
    project: str = Field(default="default")
    yaml_content: str = Field(min_length=1)


class RunCasePayload(BaseModel):
    project: str = Field(default="default")
    case_id: str = Field(min_length=1)
    case_path: str = Field(default="")
    source: str = Field(default="manual")


class DefectPayload(BaseModel):
    case_id: str = Field(min_length=1)
    defect_id: str = Field(min_length=1)
    defect_url: str = Field(default="")
    system: str = Field(default="manual")
    note: str = Field(default="")


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _ensure_dirs() -> None:
    WEB_UI_DEFAULT_STATE_DIR.mkdir(parents=True, exist_ok=True)
    WEB_UI_RUNS_DIR.mkdir(parents=True, exist_ok=True)
    WEB_UI_REPORTING_DIR.mkdir(parents=True, exist_ok=True)
    AI_CASES_ROOT.mkdir(parents=True, exist_ok=True)
    if not HISTORY_FILE.exists():
        HISTORY_FILE.write_text("[]\n", encoding="utf-8")
    if not RUNTIME_RUNS_FILE.exists():
        RUNTIME_RUNS_FILE.write_text("[]\n", encoding="utf-8")
    if not DEFECT_LINKS_FILE.exists():
        DEFECT_LINKS_FILE.write_text("[]\n", encoding="utf-8")


def _read_json_list(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict)]


def _write_json_list(path: Path, items: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(items, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _append_history(entry: dict[str, Any]) -> None:
    with _FILE_LOCK:
        items = _read_json_list(HISTORY_FILE)
        items.insert(0, entry)
        _write_json_list(HISTORY_FILE, items[:500])


def _append_runtime_run(entry: dict[str, Any]) -> None:
    with _FILE_LOCK:
        items = _read_json_list(RUNTIME_RUNS_FILE)
        items.insert(0, entry)
        _write_json_list(RUNTIME_RUNS_FILE, items[:1000])


def _update_runtime_run(run_id: str, updates: dict[str, Any]) -> None:
    with _FILE_LOCK:
        items = _read_json_list(RUNTIME_RUNS_FILE)
        changed = False
        for item in items:
            if str(item.get("run_id", "")) == run_id:
                item.update(updates)
                changed = True
                break
        if not changed:
            items.insert(0, {"run_id": run_id, **updates})
        _write_json_list(RUNTIME_RUNS_FILE, items[:1000])


def _safe_case_id(raw: str) -> str:
    text = str(raw).strip().upper()
    allowed = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in text)
    return allowed.strip("-_") or f"TC-AI-{datetime.now(UTC).strftime('%H%M%S')}"


def _state_project_dir(project: str) -> Path:
    return TEST_POINTS_ROOT / project


def _state_case_file(project: str, case_id: str) -> Path:
    return _state_project_dir(project) / f"{case_id}.json"


def _state_case_versions_dir(project: str, case_id: str) -> Path:
    return _state_project_dir(project) / "versions" / case_id


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except Exception:
        return False


def _resolve_case_yaml_path(project: str, case_id: str) -> Path:
    state_path = _state_case_file(project, case_id)
    if state_path.exists():
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except Exception:
            state = {}
        source_ref = str((state or {}).get("source_ref", "")).strip()
        if source_ref:
            candidate = Path(source_ref).expanduser()
            if not candidate.is_absolute():
                candidate = REPO_ROOT / candidate
            candidate = candidate.resolve()
            if candidate.exists() and _is_within(candidate, ASSETS_CASES_ROOT):
                return candidate
    fallback = AI_CASES_ROOT / f"{case_id}.yaml"
    return fallback.resolve()


def _read_case_yaml(path: Path) -> tuple[dict[str, Any], str]:
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"case file not found: {path}")
    content = path.read_text(encoding="utf-8")
    try:
        payload = yaml.safe_load(content) or {}
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"invalid yaml: {exc}") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="yaml root must be an object")
    return payload, content


def _write_case_yaml(path: Path, payload: dict[str, Any]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = yaml.safe_dump(payload, allow_unicode=True, sort_keys=False)
    path.write_text(text, encoding="utf-8")
    return text


def _infer_targets(page_name: str) -> tuple[str, str]:
    page_object_path = PAGE_OBJECTS_ROOT / f"{page_name}.page-object.yaml"
    menu_target = f"{page_name}_menu"
    assert_target = f"{page_name}_list_title"
    if not page_object_path.exists():
        return menu_target, assert_target

    try:
        payload = yaml.safe_load(page_object_path.read_text(encoding="utf-8")) or {}
    except Exception:
        return menu_target, assert_target
    elements = payload.get("elements", {})
    if not isinstance(elements, dict) or not elements:
        return menu_target, assert_target

    keys = list(elements.keys())
    for key in keys:
        if key.endswith("_menu") or "menu" in key:
            menu_target = key
            break
    for key in keys:
        if key.endswith("_list_title") or key.endswith("_table") or key.endswith("_list") or "title" in key:
            assert_target = key
            break
    return menu_target, assert_target


def _derive_points(case_yaml: dict[str, Any]) -> dict[str, Any]:
    execution = case_yaml.get("execution") or {}
    steps = execution.get("steps") or []
    if not isinstance(steps, list):
        steps = []
    point_types: list[str] = []
    point_keys: list[str] = []
    counts = {"precondition_count": 0, "navigation_count": 0, "input_count": 0, "assertion_count": 0, "action_count": 0}
    for index, step in enumerate(steps, start=1):
        action = str((step or {}).get("action", "")).strip()
        if action == "login":
            point_type = "precondition"
            counts["precondition_count"] += 1
        elif action in {"click", "goto"}:
            point_type = "navigation"
            counts["navigation_count"] += 1
        elif action in {"fill", "type"}:
            point_type = "input"
            counts["input_count"] += 1
        elif action in {"assert_visible", "assert_url", "wait_for"}:
            point_type = "assertion"
            counts["assertion_count"] += 1
        else:
            point_type = "action"
            counts["action_count"] += 1
        point_types.append(point_type)
        point_keys.append(f"{case_yaml.get('module', 'page')}-{index:02d}")
    return {
        "point_count": len(steps),
        "point_types": sorted(set(point_types)),
        "point_keys": point_keys,
        **counts,
    }


def _save_case_state(project: str, case_yaml: dict[str, Any], source_path: Path) -> dict[str, Any]:
    case_id = _safe_case_id(str(case_yaml.get("id", "")).strip())
    case_yaml["id"] = case_id
    state = {
        "asset_id": case_id,
        "version": 1,
        "updated_at": _now_iso(),
        "title": str(case_yaml.get("title", "")).strip() or case_id,
        "page": str((case_yaml.get("execution") or {}).get("page", case_yaml.get("module", "product"))).strip() or "product",
        "requirement": case_yaml.get("requirement") if isinstance(case_yaml.get("requirement"), list) else [],
        "priority": str(case_yaml.get("priority", "P1")).strip() or "P1",
        "source_type": "yaml_case",
        "source_name": case_id,
        "source_ref": str(source_path.resolve()),
        "references": [
            {
                "kind": "case_yaml",
                "path": str(source_path.resolve()),
                "case_id": case_id,
            }
        ],
    }
    state.update(_derive_points(case_yaml))

    state_file = _state_case_file(project, case_id)
    state_file.parent.mkdir(parents=True, exist_ok=True)
    if state_file.exists():
        try:
            previous = json.loads(state_file.read_text(encoding="utf-8")) or {}
        except Exception:
            previous = {}
        if isinstance(previous, dict):
            prev_version = int(previous.get("version", 1) or 1)
            state["version"] = prev_version + 1

    state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    versions_dir = _state_case_versions_dir(project, case_id)
    versions_dir.mkdir(parents=True, exist_ok=True)
    seq = len(list(versions_dir.glob("*.json"))) + 1
    version_file = versions_dir / f"{seq:04d}.json"
    version_file.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return state


def _parse_analysis_file(path: Path) -> dict[str, Any]:
    parsed: dict[str, Any] = {
        "summary": "",
        "failure_category": "",
        "likely_cause": "",
        "risk_level": "",
        "recommended_action": "",
        "confidence": "",
        "source_file": str(path),
    }
    key_map = {
        "Summary": "summary",
        "Failure Category": "failure_category",
        "Likely Cause": "likely_cause",
        "Risk Level": "risk_level",
        "Recommended Action": "recommended_action",
        "Confidence": "confidence",
    }
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return parsed
    for raw_line in text.splitlines():
        if ": " not in raw_line:
            continue
        prefix, value = raw_line.split(": ", 1)
        target = key_map.get(prefix.strip())
        if target:
            parsed[target] = value.strip()
    return parsed


def _collect_failure_entries() -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for artifact_root in [RUNNER_ROOT / "artifacts"] + sorted(WEB_UI_RUNS_DIR.glob("*-artifacts")):
        if not artifact_root.exists():
            continue
        for analysis_path in sorted(artifact_root.rglob("analysis.txt"), key=lambda p: p.stat().st_mtime, reverse=True):
            case_dir = analysis_path.parent
            execution_record_path = case_dir / "execution_record.json"
            suggestion_path = case_dir / "suggestion.json"
            screenshot_path = case_dir / "failed.png"
            html_path = case_dir / "page.html"
            meta_path = case_dir / "meta.txt"
            video_path = None
            video_candidates = list(case_dir.glob("*.webm"))
            if video_candidates:
                video_path = max(video_candidates, key=lambda p: p.stat().st_mtime)
            case_id = case_dir.name
            if execution_record_path.exists():
                try:
                    execution_record = json.loads(execution_record_path.read_text(encoding="utf-8")) or {}
                except Exception:
                    execution_record = {}
                case_id = str(execution_record.get("case_id", case_id)).strip() or case_id
                case_title = str(execution_record.get("case_title", case_id)).strip() or case_id
                finished_at = str(execution_record.get("finished_at", "")).strip()
            else:
                case_title = case_id
                finished_at = datetime.fromtimestamp(analysis_path.stat().st_mtime, tz=UTC).isoformat()

            analysis = _parse_analysis_file(analysis_path)
            suggestion_payload: dict[str, Any] = {}
            if suggestion_path.exists():
                try:
                    suggestion_payload = json.loads(suggestion_path.read_text(encoding="utf-8")) or {}
                except Exception:
                    suggestion_payload = {}
            entries.append(
                {
                    "case_id": case_id,
                    "case_title": case_title,
                    "finished_at": finished_at,
                    "analysis": analysis,
                    "suggestion": suggestion_payload,
                    "artifact_dir": str(case_dir.resolve()),
                    "analysis_path": str(analysis_path.resolve()),
                    "suggestion_path": str(suggestion_path.resolve()) if suggestion_path.exists() else "",
                    "screenshot_path": str(screenshot_path.resolve()) if screenshot_path.exists() else "",
                    "html_path": str(html_path.resolve()) if html_path.exists() else "",
                    "meta_path": str(meta_path.resolve()) if meta_path.exists() else "",
                    "video_path": str(video_path.resolve()) if video_path else "",
                }
            )
    entries.sort(key=lambda item: item.get("finished_at", ""), reverse=True)
    return entries[:200]


def _load_defects() -> list[dict[str, Any]]:
    with _FILE_LOCK:
        return _read_json_list(DEFECT_LINKS_FILE)


def _get_python_bin() -> str:
    venv_python = REPO_ROOT / ".venv" / "bin" / "python"
    if venv_python.exists():
        return str(venv_python)
    return "python3"


def _build_run_command(case_path: Path) -> tuple[list[str], dict[str, str]]:
    command = [
        _get_python_bin(),
        "-m",
        "pytest",
        "-s",
        str(REPO_ROOT / "runners" / "web-playwright-python" / "tests" / "test_yaml_ai_generated.py"),
    ]
    env = os.environ.copy()
    current_pythonpath = env.get("PYTHONPATH", "").strip()
    runner_path = str(REPO_ROOT / "runners" / "web-playwright-python")
    env["PYTHONPATH"] = f"{runner_path}:{current_pythonpath}" if current_pythonpath else runner_path
    env["RUN_MODE"] = "ai"
    env["RUN_SOURCE"] = "web-ui"
    env["TEST_CASE_PATH"] = str(case_path.resolve())
    env["SELF_HEALING_ENABLED"] = "0"
    env.setdefault("BASE_URL", "http://localhost:5173/login#/login")
    return command, env


def _update_job(run_id: str, updates: dict[str, Any]) -> None:
    with _RUN_LOCK:
        job = _RUN_JOBS.get(run_id)
        if not job:
            return
        job.update(updates)


def _get_job(run_id: str) -> dict[str, Any] | None:
    with _RUN_LOCK:
        job = _RUN_JOBS.get(run_id)
        if not job:
            return None
        return dict(job)


def _execute_run(job: dict[str, Any]) -> None:
    run_id = str(job["run_id"])
    case_path = Path(job["case_path"]).resolve()
    log_path = Path(job["log_path"]).resolve()
    artifacts_dir = Path(job["artifacts_dir"]).resolve()
    videos_dir = Path(job["videos_dir"]).resolve()
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    videos_dir.mkdir(parents=True, exist_ok=True)

    command, env = _build_run_command(case_path)
    env["PLAYWRIGHT_ARTIFACTS_DIR"] = str(artifacts_dir)
    env["PLAYWRIGHT_VIDEO_DIR"] = str(videos_dir)

    _update_job(run_id, {"status": "running", "started_at": _now_iso(), "command": " ".join(command)})
    _update_runtime_run(run_id, {"status": "running", "started_at": _now_iso()})

    with log_path.open("w", encoding="utf-8") as log_fp:
        log_fp.write(f"[run] id={run_id}\n")
        log_fp.write(f"[run] case={case_path}\n")
        log_fp.write(f"[run] command={' '.join(command)}\n")
        log_fp.write(f"[run] artifacts={artifacts_dir}\n")
        log_fp.flush()

        process = subprocess.Popen(
            command,
            cwd=str(REPO_ROOT),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        for line in iter(process.stdout.readline, ""):
            log_fp.write(line)
            log_fp.flush()
        process.stdout.close()
        return_code = process.wait()
        log_fp.write(f"\n[run] completed returncode={return_code}\n")
        log_fp.flush()

    status_value = "passed" if return_code == 0 else "failed"
    failure_entries = _collect_failure_entries()
    case_failure = next((item for item in failure_entries if item.get("case_id") == job["case_id"]), None)
    _update_job(
        run_id,
        {
            "status": status_value,
            "finished_at": _now_iso(),
            "return_code": return_code,
            "latest_failure": case_failure or {},
        },
    )
    _update_runtime_run(
        run_id,
        {
            "status": status_value,
            "finished_at": _now_iso(),
            "return_code": return_code,
            "artifacts_dir": str(artifacts_dir),
            "videos_dir": str(videos_dir),
            "latest_failure": case_failure or {},
        },
    )


def _start_run(*, project: str, case_id: str, case_path: Path, source: str) -> dict[str, Any]:
    run_id = uuid.uuid4().hex
    log_path = WEB_UI_RUNS_DIR / f"{run_id}.log"
    artifacts_dir = WEB_UI_RUNS_DIR / f"{run_id}-artifacts"
    videos_dir = WEB_UI_RUNS_DIR / f"{run_id}-videos"
    job = {
        "run_id": run_id,
        "project": project,
        "case_id": case_id,
        "case_path": str(case_path.resolve()),
        "source": source,
        "status": "queued",
        "created_at": _now_iso(),
        "started_at": "",
        "finished_at": "",
        "return_code": None,
        "log_path": str(log_path.resolve()),
        "artifacts_dir": str(artifacts_dir.resolve()),
        "videos_dir": str(videos_dir.resolve()),
        "latest_failure": {},
    }
    with _RUN_LOCK:
        _RUN_JOBS[run_id] = dict(job)
    _append_runtime_run(dict(job))
    _append_history(
        {
            "timestamp": _now_iso(),
            "action": "run_case",
            "case_id": case_id,
            "path": str(case_path.resolve()),
            "run_id": run_id,
            "queue_status": "queued",
        }
    )
    worker = threading.Thread(target=_execute_run, args=(job,), daemon=True)
    worker.start()
    return job


def _extract_json_from_text(text: str) -> dict[str, Any]:
    text = text.strip()
    if not text:
        return {}
    try:
        payload = json.loads(text)
        return payload if isinstance(payload, dict) else {}
    except Exception:
        pass
    start = text.rfind("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        candidate = text[start : end + 1]
        try:
            payload = json.loads(candidate)
            return payload if isinstance(payload, dict) else {}
        except Exception:
            return {}
    return {}


@router.get("/api/workbench/projects")
def list_projects() -> dict[str, Any]:
    _ensure_dirs()
    projects = []
    if TEST_POINTS_ROOT.exists():
        for item in sorted(TEST_POINTS_ROOT.iterdir()):
            if item.is_dir():
                projects.append(item.name)
    if "default" not in projects:
        projects.insert(0, "default")
    return {"items": projects}


@router.get("/api/workbench/cases")
def list_cases(project: str = Query(default="default")) -> dict[str, Any]:
    _ensure_dirs()
    project_dir = _state_project_dir(project)
    items: list[dict[str, Any]] = []
    if project_dir.exists():
        for file in sorted(project_dir.glob("*.json")):
            try:
                state = json.loads(file.read_text(encoding="utf-8")) or {}
            except Exception:
                state = {}
            case_id = str(state.get("asset_id", file.stem)).strip() or file.stem
            items.append(
                {
                    "case_id": case_id,
                    "title": str(state.get("title", case_id)).strip() or case_id,
                    "page": str(state.get("page", "product")).strip() or "product",
                    "priority": str(state.get("priority", "P1")).strip() or "P1",
                    "updated_at": str(state.get("updated_at", "")).strip(),
                    "path": str(_resolve_case_yaml_path(project, case_id)),
                }
            )

    known_ids = {item["case_id"] for item in items}
    for path in sorted(AI_CASES_ROOT.glob("*.yaml")):
        try:
            payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception:
            payload = {}
        case_id = str(payload.get("id", path.stem)).strip() or path.stem
        if case_id in known_ids:
            continue
        items.append(
            {
                "case_id": case_id,
                "title": str(payload.get("title", case_id)).strip() or case_id,
                "page": str((payload.get("execution") or {}).get("page", payload.get("module", "product"))).strip() or "product",
                "priority": str(payload.get("priority", "P1")).strip() or "P1",
                "updated_at": datetime.fromtimestamp(path.stat().st_mtime, tz=UTC).isoformat(),
                "path": str(path.resolve()),
            }
        )
    items.sort(key=lambda item: item.get("updated_at", ""), reverse=True)
    return {"items": items}


@router.get("/api/workbench/cases/{case_id}")
def get_case(case_id: str, project: str = Query(default="default")) -> dict[str, Any]:
    _ensure_dirs()
    normalized_case_id = _safe_case_id(case_id)
    case_path = _resolve_case_yaml_path(project, normalized_case_id)
    payload, content = _read_case_yaml(case_path)
    return {
        "item": {
            "case_id": normalized_case_id,
            "project": project,
            "path": str(case_path.resolve()),
            "title": str(payload.get("title", normalized_case_id)).strip() or normalized_case_id,
            "page": str((payload.get("execution") or {}).get("page", payload.get("module", "product"))).strip() or "product",
            "priority": str(payload.get("priority", "P1")).strip() or "P1",
            "yaml_content": content,
            "updated_at": datetime.fromtimestamp(case_path.stat().st_mtime, tz=UTC).isoformat(),
        }
    }


@router.put("/api/workbench/cases/{case_id}")
def save_case(case_id: str, payload: SaveCasePayload) -> dict[str, Any]:
    _ensure_dirs()
    normalized_case_id = _safe_case_id(case_id)
    case_path = _resolve_case_yaml_path(payload.project, normalized_case_id)
    try:
        case_yaml = yaml.safe_load(payload.yaml_content) or {}
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"invalid yaml: {exc}") from exc
    if not isinstance(case_yaml, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="yaml root must be an object")
    case_yaml["id"] = normalized_case_id
    final_text = _write_case_yaml(case_path, case_yaml)
    state_entry = _save_case_state(payload.project, case_yaml, case_path)
    _append_history(
        {
            "timestamp": _now_iso(),
            "action": "save_case",
            "case_id": normalized_case_id,
            "title": str(case_yaml.get("title", normalized_case_id)),
            "path": str(case_path.resolve()),
        }
    )
    return {
        "message": "case saved",
        "item": {
            "case_id": normalized_case_id,
            "project": payload.project,
            "path": str(case_path.resolve()),
            "yaml_content": final_text,
            "state": state_entry,
        },
    }


@router.post("/api/workbench/generate", status_code=status.HTTP_201_CREATED)
def generate_case(payload: GenerateCasePayload) -> dict[str, Any]:
    _ensure_dirs()
    case_id = _safe_case_id(payload.case_id or f"TC-{payload.page.upper()}-{datetime.now(UTC).strftime('%H%M%S')}")
    menu_target, assert_target = _infer_targets(payload.page)
    title = payload.title.strip() or f"AI Generated {payload.page.title()} Case"
    requirement_text = payload.requirement.strip()
    case_yaml: dict[str, Any] = {
        "version": "v4",
        "id": case_id,
        "title": title,
        "module": payload.page,
        "priority": payload.priority.strip() or "P1",
        "tags": [item.strip() for item in payload.tags if item.strip()] or ["ai-generated"],
        "owner": "qa-team",
        "status": "automated",
        "description": f"AI generated from requirement: {requirement_text}",
        "requirement": [requirement_text],
        "data": {},
        "execution": {
            "runner": "playwright",
            "page": payload.page,
            "variables": {},
            "steps": [
                {"action": "login"},
                {"action": "click", "target": menu_target},
                {"action": "wait_for", "target": assert_target},
                {"action": "assert_visible", "target": assert_target},
            ],
        },
    }
    case_path = AI_CASES_ROOT / f"{case_id}.yaml"
    final_text = _write_case_yaml(case_path, case_yaml)
    state_entry = _save_case_state(payload.project, case_yaml, case_path)
    _append_history(
        {
            "timestamp": _now_iso(),
            "action": "generate_case",
            "case_id": case_id,
            "title": title,
            "path": str(case_path.resolve()),
        }
    )
    return {
        "message": "case generated",
        "item": {
            "case_id": case_id,
            "project": payload.project,
            "path": str(case_path.resolve()),
            "yaml_content": final_text,
            "state": state_entry,
        },
    }


@router.post("/api/workbench/run")
def run_case(payload: RunCasePayload) -> dict[str, Any]:
    _ensure_dirs()
    normalized_case_id = _safe_case_id(payload.case_id)
    if payload.case_path.strip():
        case_path = Path(payload.case_path).expanduser()
        if not case_path.is_absolute():
            case_path = REPO_ROOT / case_path
        case_path = case_path.resolve()
    else:
        case_path = _resolve_case_yaml_path(payload.project, normalized_case_id)
    if not case_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"case file not found: {case_path}")
    if not _is_within(case_path, ASSETS_CASES_ROOT):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="case_path must stay under assets/test-cases")

    job = _start_run(project=payload.project, case_id=normalized_case_id, case_path=case_path, source=payload.source)
    return {"item": job}


@router.get("/api/workbench/runs")
def list_runs(limit: int = Query(default=30, ge=1, le=200)) -> dict[str, Any]:
    _ensure_dirs()
    items = _read_json_list(RUNTIME_RUNS_FILE)
    return {"items": items[:limit]}


@router.get("/api/workbench/runs/{run_id}")
def get_run(run_id: str) -> dict[str, Any]:
    _ensure_dirs()
    job = _get_job(run_id)
    if job:
        return {"item": job}
    for item in _read_json_list(RUNTIME_RUNS_FILE):
        if str(item.get("run_id", "")) == run_id:
            return {"item": item}
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run not found")


@router.get("/api/workbench/runs/{run_id}/events")
def stream_run_events(run_id: str) -> StreamingResponse:
    _ensure_dirs()
    run = _get_job(run_id)
    if run:
        log_path = Path(run["log_path"])
    else:
        historical = next((item for item in _read_json_list(RUNTIME_RUNS_FILE) if str(item.get("run_id", "")) == run_id), None)
        if not historical:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run not found")
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
            current = _get_job(run_id)
            current_status = ""
            if current:
                current_status = str(current.get("status", ""))
            else:
                past = next((item for item in _read_json_list(RUNTIME_RUNS_FILE) if str(item.get("run_id", "")) == run_id), None)
                current_status = str((past or {}).get("status", ""))

            if current_status in {"passed", "failed", "cancelled"}:
                end_payload = {"run_id": run_id, "event": "complete", "status": current_status}
                yield f"data: {json.dumps(end_payload, ensure_ascii=False)}\n\n"
                break
            time.sleep(0.5)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/api/workbench/runs/{run_id}/analysis")
def get_run_analysis(run_id: str) -> dict[str, Any]:
    _ensure_dirs()
    run_item = _get_job(run_id)
    if not run_item:
        run_item = next((item for item in _read_json_list(RUNTIME_RUNS_FILE) if str(item.get("run_id", "")) == run_id), None)
    if not run_item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run not found")

    artifacts_dir = Path(str(run_item.get("artifacts_dir", "")).strip())
    if artifacts_dir.exists():
        failures = [item for item in _collect_failure_entries() if _is_within(Path(item["artifact_dir"]), artifacts_dir)]
    else:
        failures = []
    if not failures and run_item.get("latest_failure"):
        failures = [run_item["latest_failure"]]
    return {"items": failures}


@router.post("/api/workbench/runs/{run_id}/heal")
def heal_run(run_id: str) -> dict[str, Any]:
    _ensure_dirs()
    run_item = _get_job(run_id)
    if not run_item:
        run_item = next((item for item in _read_json_list(RUNTIME_RUNS_FILE) if str(item.get("run_id", "")) == run_id), None)
    if not run_item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run not found")
    case_path = Path(str(run_item.get("case_path", "")))
    if not case_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="case file not found for this run")

    artifacts_dir = Path(str(run_item.get("artifacts_dir", "")))
    if not artifacts_dir.exists():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="artifact directory not found")

    candidate_dirs = [path.parent for path in artifacts_dir.rglob("suggestion.json")]
    if not candidate_dirs:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="suggestion.json not found; cannot heal")
    artifact_case_dir = max(candidate_dirs, key=lambda p: p.stat().st_mtime)

    command = [
        _get_python_bin(),
        str(REPO_ROOT / "agents" / "self-healing-advisor-agent" / "apply_fix.py"),
        "auto-heal",
        "--case",
        str(case_path.resolve()),
        "--artifacts",
        str(artifact_case_dir.resolve()),
        "--previous-attempts",
        "0",
    ]
    result = subprocess.run(command, cwd=str(REPO_ROOT), text=True, capture_output=True, check=False)
    output = (result.stdout or "") + ("\n" + result.stderr if result.stderr else "")
    payload = _extract_json_from_text(output)
    if result.returncode != 0:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "message": "self-healing failed",
                "return_code": result.returncode,
                "output": output[-3000:],
            },
        )

    _append_history(
        {
            "timestamp": _now_iso(),
            "action": "self_heal",
            "case_id": run_item.get("case_id", ""),
            "run_id": run_id,
            "artifact_dir": str(artifact_case_dir.resolve()),
            "status": payload.get("status", "success"),
        }
    )
    return {"item": payload, "raw_output": output}


@router.post("/api/workbench/runs/{run_id}/rerun")
def rerun_case(run_id: str) -> dict[str, Any]:
    _ensure_dirs()
    run_item = _get_job(run_id)
    if not run_item:
        run_item = next((item for item in _read_json_list(RUNTIME_RUNS_FILE) if str(item.get("run_id", "")) == run_id), None)
    if not run_item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run not found")
    case_path = Path(str(run_item.get("case_path", "")))
    if not case_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="case file not found for rerun")
    new_job = _start_run(
        project=str(run_item.get("project", "default")),
        case_id=str(run_item.get("case_id", "")).strip() or "UNKNOWN",
        case_path=case_path,
        source="rerun",
    )
    _append_history(
        {
            "timestamp": _now_iso(),
            "action": "rerun_case",
            "case_id": run_item.get("case_id", ""),
            "from_run_id": run_id,
            "run_id": new_job["run_id"],
            "path": str(case_path.resolve()),
            "queue_status": "queued",
        }
    )
    return {"item": new_job}


@router.get("/api/defects")
def list_defects(case_id: str = Query(default="")) -> dict[str, Any]:
    _ensure_dirs()
    items = _load_defects()
    if case_id.strip():
        items = [item for item in items if str(item.get("case_id", "")).strip() == case_id.strip()]
    items.sort(key=lambda item: str(item.get("linked_at", "")), reverse=True)
    return {"items": items}


@router.post("/api/defects", status_code=status.HTTP_201_CREATED)
def add_defect(payload: DefectPayload) -> dict[str, Any]:
    _ensure_dirs()
    entry = {
        "case_id": payload.case_id.strip(),
        "defect_id": payload.defect_id.strip(),
        "defect_url": payload.defect_url.strip(),
        "system": payload.system.strip() or "manual",
        "note": payload.note.strip(),
        "linked_at": _now_iso(),
    }
    with _FILE_LOCK:
        items = _read_json_list(DEFECT_LINKS_FILE)
        exists = any(
            str(item.get("case_id", "")).strip() == entry["case_id"]
            and str(item.get("defect_id", "")).strip() == entry["defect_id"]
            for item in items
        )
        if not exists:
            items.insert(0, entry)
            _write_json_list(DEFECT_LINKS_FILE, items[:1000])
    return {"item": entry}


@router.get("/api/report/overview")
def report_overview() -> dict[str, Any]:
    _ensure_dirs()
    runtime_runs = _read_json_list(RUNTIME_RUNS_FILE)
    total_runs = len(runtime_runs)
    passed = sum(1 for item in runtime_runs if str(item.get("status", "")).lower() == "passed")
    failed = sum(1 for item in runtime_runs if str(item.get("status", "")).lower() == "failed")
    pass_rate = round((passed / total_runs * 100) if total_runs else 0.0, 1)
    failure_entries = _collect_failure_entries()
    high_risk = sum(1 for item in failure_entries if str(item["analysis"].get("risk_level", "")).lower() == "high")
    actionable = sum(
        1
        for item in failure_entries
        if str((item.get("suggestion") or {}).get("advice_type", "")).strip() not in {"", "no_change"}
        and float((item.get("suggestion") or {}).get("confidence", 0) or 0) >= 0.5
    )
    health_score = max(0, min(100, int(pass_rate - high_risk * 6 - max(failed - passed, 0) * 2)))

    recent_failures = []
    defects = _load_defects()
    defect_map: dict[str, list[dict[str, Any]]] = {}
    for item in defects:
        defect_map.setdefault(str(item.get("case_id", "")).strip(), []).append(item)
    for item in failure_entries[:30]:
        case_id = str(item.get("case_id", "")).strip()
        links = defect_map.get(case_id, [])
        recent_failures.append(
            {
                "case_id": case_id,
                "case_title": item.get("case_title", case_id),
                "summary": item["analysis"].get("summary", ""),
                "risk_level": item["analysis"].get("risk_level", ""),
                "finished_at": item.get("finished_at", ""),
                "defects": links,
                "defect_count": len(links),
                "artifact_dir": item.get("artifact_dir", ""),
            }
        )

    return {
        "summary": {
            "total_runs": total_runs,
            "passed_runs": passed,
            "failed_runs": failed,
            "pass_rate": pass_rate,
            "health_score": health_score,
            "high_risk_failures": high_risk,
            "actionable_suggestions": actionable,
        },
        "recent_failures": recent_failures[:20],
    }


@router.get("/api/report/failures")
def report_failures(
    case_id: str = Query(default=""),
    keyword: str = Query(default=""),
    defect_status: str = Query(default="all"),
) -> dict[str, Any]:
    _ensure_dirs()
    defects = _load_defects()
    defect_map: dict[str, list[dict[str, Any]]] = {}
    for item in defects:
        defect_map.setdefault(str(item.get("case_id", "")).strip(), []).append(item)

    entries = _collect_failure_entries()
    rows: list[dict[str, Any]] = []
    for item in entries:
        normalized_case_id = str(item.get("case_id", "")).strip()
        links = defect_map.get(normalized_case_id, [])
        row = {
            "case_id": normalized_case_id,
            "case_title": item.get("case_title", normalized_case_id),
            "finished_at": item.get("finished_at", ""),
            "summary": item["analysis"].get("summary", ""),
            "failure_category": item["analysis"].get("failure_category", ""),
            "likely_cause": item["analysis"].get("likely_cause", ""),
            "risk_level": item["analysis"].get("risk_level", ""),
            "recommended_action": item["analysis"].get("recommended_action", ""),
            "confidence": item["analysis"].get("confidence", ""),
            "suggestion": item.get("suggestion", {}),
            "artifact_dir": item.get("artifact_dir", ""),
            "analysis_path": item.get("analysis_path", ""),
            "suggestion_path": item.get("suggestion_path", ""),
            "screenshot_path": item.get("screenshot_path", ""),
            "html_path": item.get("html_path", ""),
            "meta_path": item.get("meta_path", ""),
            "video_path": item.get("video_path", ""),
            "defects": links,
            "defect_count": len(links),
        }
        rows.append(row)

    if case_id.strip():
        rows = [item for item in rows if item["case_id"] == case_id.strip()]
    if keyword.strip():
        term = keyword.strip().lower()
        rows = [
            item
            for item in rows
            if term in item["case_id"].lower()
            or term in str(item.get("case_title", "")).lower()
            or term in str(item.get("summary", "")).lower()
            or any(term in str(link.get("defect_id", "")).lower() for link in item.get("defects", []))
        ]
    mode = defect_status.strip().lower()
    if mode == "linked":
        rows = [item for item in rows if item.get("defect_count", 0) > 0]
    elif mode == "unlinked":
        rows = [item for item in rows if item.get("defect_count", 0) == 0]

    return {"items": rows[:80]}


@router.get("/api/report/context")
def report_context() -> dict[str, Any]:
    _ensure_dirs()
    commit_id = ""
    commit_message = ""
    branch_name = ""
    try:
        commit_id = (
            subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(REPO_ROOT), capture_output=True, text=True, check=False)
            .stdout.strip()
        )
        commit_message = (
            subprocess.run(["git", "log", "-1", "--pretty=%s"], cwd=str(REPO_ROOT), capture_output=True, text=True, check=False)
            .stdout.strip()
        )
        branch_name = (
            subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=str(REPO_ROOT), capture_output=True, text=True, check=False)
            .stdout.strip()
        )
    except Exception:
        pass

    runtime_runs = _read_json_list(RUNTIME_RUNS_FILE)
    latest_run = runtime_runs[0] if runtime_runs else {}
    return {
        "git": {
            "commit_id": commit_id,
            "commit_message": commit_message,
            "branch": branch_name,
        },
        "build": {
            "build_version": commit_id[:12] if commit_id else "",
            "image_tag": os.getenv("IMAGE_TAG", ""),
            "build_time": latest_run.get("created_at", ""),
        },
        "execution": {
            "base_url": os.getenv("BASE_URL", "http://localhost:5173/login#/login"),
            "browser": os.getenv("PLAYWRIGHT_BROWSER", "chromium"),
            "environment": os.getenv("APP_ENV", "local"),
            "runner": "pytest + playwright",
            "latest_run_id": latest_run.get("run_id", ""),
        },
    }


@router.get("/api/report/performance")
def report_performance() -> dict[str, Any]:
    _ensure_dirs()
    runtime_runs = _read_json_list(RUNTIME_RUNS_FILE)
    duration_rows: list[dict[str, Any]] = []
    for item in runtime_runs:
        started = str(item.get("started_at", "")).strip()
        finished = str(item.get("finished_at", "")).strip()
        if not started or not finished:
            continue
        try:
            started_dt = datetime.fromisoformat(started)
            finished_dt = datetime.fromisoformat(finished)
            duration = max(0.0, (finished_dt - started_dt).total_seconds())
        except Exception:
            duration = 0.0
        duration_rows.append(
            {
                "run_id": item.get("run_id", ""),
                "case_id": item.get("case_id", ""),
                "status": item.get("status", ""),
                "duration_seconds": duration,
                "finished_at": finished,
            }
        )
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
    }


@router.get("/api/report/allure")
def report_allure() -> dict[str, Any]:
    return {
        "allure_index": "/allure/index.html",
        "available": (ALLURE_REPORT_ROOT / "index.html").exists(),
    }


@router.get("/api/workbench/history")
def workbench_history(limit: int = Query(default=50, ge=1, le=500)) -> dict[str, Any]:
    _ensure_dirs()
    return {"items": _read_json_list(HISTORY_FILE)[:limit]}


@router.get("/api/workbench/download-log/{run_id}")
def download_log(run_id: str) -> Response:
    _ensure_dirs()
    log_path = WEB_UI_RUNS_DIR / f"{run_id}.log"
    if not log_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="log not found")
    return Response(
        content=log_path.read_text(encoding="utf-8", errors="ignore"),
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={run_id}.log"},
    )
