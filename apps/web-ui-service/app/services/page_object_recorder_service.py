from __future__ import annotations

import json
from datetime import datetime
from shared_backend.datetime_compat import UTC
import importlib.util
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time
import uuid

from fastapi import HTTPException, status
from shared_backend.case_ids import normalize_client_code
from shared_backend.type_utils import normalize_project_code_strict as _normalize_project_code_strict
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models.page_object import PageObject, PageObjectCandidateElement, PageObjectCandidateGroup, PageObjectRecorderSession
from app.repositories.page_object_repository import PageObjectRepository
from app.repositories.recorder_repository import RecorderRepository
from app.repositories.recorder_session_repository import RecorderSessionRepository
from app.repositories.test_project_repository import TestProjectRepository
from app.models.test_project import TestProject
from app.schemas.page_object import PageObjectCreate, PageObjectRefCreate
from app.schemas.page_object_recorder import (
    RecorderSessionCreateCasePayload,
    RecorderSessionCreate,
    RecorderSessionHeartbeatPayload,
    RecorderSessionStopPayload,
)
from app.schemas.test_case import TestCaseCreate
from app.services.page_object_source_semantics import SourceSemanticCatalog, build_source_semantic_catalog
from app.services import page_object_service, test_case_service, test_project_service
from app.services.page_object_locator_scoring import (
    _ParsedLocator,
    _ParsedStep,
    _build_element_candidates,
    _business_domain_guess,
    _candidate_key_for_locator,
    _derive_page_url,
    _derive_precondition_state,
    _group_key_for_locator,
    _infer_locator_category,
    _is_locator_blocked_for_ingest,
    _locator_key,
    _locator_source,
    _looks_dynamic_text_locator,
    _normalize_business_element_code,
    _normalize_metric_text_locator,
    _normalize_page_route,
    _probe_availability,
    _score_to_tier,
    _short_hash,
    _source_enhanced_candidate_semantics,
)

SESSION_STATUS_VALUES = {"active", "stopped", "failed"}
_PROCESS_REGISTRY: dict[int, subprocess.Popen[bytes]] = {}
_RECORDER_ROOT = Path(__file__).resolve().parents[4] / "artifacts" / "page-recorder"
_IDENTIFIER_PATTERN = re.compile(r"[^a-zA-Z0-9_-]+")
_CODEGEN_STARTUP_WAIT_SECONDS = 2.5
_CODEGEN_STARTUP_POLL_INTERVAL_SECONDS = 0.05


def _stderr_log_path(script_path: Path) -> Path:
    name = script_path.name
    if name.endswith(".codegen.py"):
        return script_path.with_name(name.removesuffix(".py") + ".stderr.log")
    return script_path.with_suffix(".stderr.log")


def _tail_text_file(path: Path, *, max_chars: int = 2000) -> str:
    if not path.exists():
        return ""
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""
    if len(content) <= max_chars:
        return content.strip()
    return content[-max_chars:].strip()


def _format_codegen_launch_error(script_path: Path) -> str:
    stderr_tail = _tail_text_file(_stderr_log_path(script_path))
    lowered = stderr_tail.lower()
    if "missing x server" in lowered or "without having a xserver running" in lowered or "$display" in lowered:
        return (
            "录制启动失败：当前服务运行环境缺少图形桌面(Display/XServer)，无法弹出 Playwright 录制窗口。"
            "请在有桌面环境的本机启动 web-ui-service，或为运行环境配置可交互的桌面能力（如 XServer/VNC）。"
        )
    if "playwright" in lowered and "not found" in lowered:
        return "录制启动失败：Playwright 运行时不可用，请先安装 Playwright 及浏览器依赖。"
    if stderr_tail:
        compact = " ".join(stderr_tail.splitlines())
        return f"录制启动失败：{compact[:600]}"
    return "录制启动失败：录制进程启动后立即退出。"


def _is_process_alive(process_pid: int | None) -> bool:
    if process_pid is None or process_pid <= 0:
        return False
    process = _PROCESS_REGISTRY.get(process_pid)
    if process is None:
        # When process is not managed in current runtime registry (for example process started
        # before service restart), do not force-fail the session here to avoid false negatives.
        return True
    return process.poll() is None


def _sync_active_session_runtime_state(db: Session, item: PageObjectRecorderSession) -> PageObjectRecorderSession:
    if str(item.status or "").strip().lower() != "active":
        return item
    if _is_process_alive(item.process_pid):
        return item
    item.status = "failed"
    item.stopped_at = datetime.now(UTC)
    item.error_message = _format_codegen_launch_error(Path(item.script_path))
    item.process_pid = None
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def _normalize_project_code(value: str) -> str:
    try:
        return _normalize_project_code_strict(value, max_len=20)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


def _normalize_page_code(value: str) -> str:
    normalized = _IDENTIFIER_PATTERN.sub("-", str(value or "").strip()).strip("-").lower()
    if len(normalized) < 2 or len(normalized) > 40:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="page_code must be 2-40 chars and use letters/digits/_/-",
        )
    return normalized


def _normalize_session_id(value: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="session_id cannot be empty")
    return normalized


def _normalize_element_code(value: str) -> str:
    normalized = _IDENTIFIER_PATTERN.sub("-", str(value or "").strip()).strip("-").lower()
    if len(normalized) < 2:
        normalized = f"element-{uuid.uuid4().hex[:8]}"
    return normalized[:80]


def _ascii_slug(value: str, *, max_len: int = 24) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "-", str(value or "").strip().lower()).strip("-")
    if not normalized:
        return ""
    return normalized[:max_len].strip("-")


def _role_code_tag(role: str) -> str:
    normalized = str(role or "").strip().lower()
    if normalized == "button":
        return "btn"
    if normalized in {"textbox", "searchbox", "combobox", "spinbutton"}:
        return "input"
    if normalized == "link":
        return "link"
    if normalized == "menuitem":
        return "menu"
    if normalized == "tab":
        return "tab"
    if normalized == "checkbox":
        return "checkbox"
    if normalized == "radio":
        return "radio"
    if normalized == "switch":
        return "switch"
    return _ascii_slug(normalized, max_len=12) or "role"


def _derive_recorder_element_code(
    *,
    page_code: str,
    locator: _ParsedLocator,
    existing_codes: set[str],
) -> str:
    normalized_page = _normalize_page_code(page_code)
    locator_type = str(locator.locator_type or "").strip().lower()
    locator_value = str(locator.locator_value or "").strip()
    role = str(locator.role or "").strip().lower()
    ascii_value = _ascii_slug(locator_value, max_len=24)

    code_parts = [normalized_page]
    if locator_type == "role":
        code_parts.append(_role_code_tag(role))
    else:
        code_parts.append(_ascii_slug(locator_type, max_len=10) or "elm")

    if ascii_value:
        code_parts.append(ascii_value)
    else:
        code_parts.append(f"u{_short_hash(locator_type, role, locator_value)}")

    base_code = _normalize_element_code("-".join(code_parts))
    candidate = base_code
    counter = 2
    while candidate in existing_codes:
        suffix = f"-{counter}"
        trimmed = base_code[: max(2, 80 - len(suffix))]
        candidate = _normalize_element_code(f"{trimmed}{suffix}")
        counter += 1
    existing_codes.add(candidate)
    return candidate


def _serialize_session(item: PageObjectRecorderSession) -> dict[str, object]:
    recorded_steps = _load_recorded_steps(Path(item.script_path))
    if not recorded_steps:
        recorded_steps = _serialize_recorded_steps(_parse_codegen_steps(Path(item.script_path)))
    return {
        "id": item.id,
        "session_id": item.session_id,
        "project_code": item.project_code,
        "client": item.client,
        "page_code": item.page_code,
        "page_name": item.page_name,
        "url": item.url,
        "status": item.status,
        "process_pid": item.process_pid,
        "script_path": item.script_path,
        "started_by": item.started_by,
        "error_message": item.error_message,
        "started_at": item.started_at,
        "heartbeat_at": item.heartbeat_at,
        "stopped_at": item.stopped_at,
        "recorded_step_count": len(recorded_steps),
        "recorded_steps": recorded_steps,
    }


def _serialize_session_summary(
    item: PageObjectRecorderSession,
    db: Session | None = None,
    candidate_summary: dict[str, object] | None = None,
) -> dict[str, object]:
    script_path = Path(item.script_path)
    recorded_steps = _load_recorded_steps(script_path)
    recorded_step_count = len(recorded_steps)
    if recorded_step_count <= 0:
        recorded_step_count = len(_parse_codegen_steps(script_path))
    payload: dict[str, object] = {
        "id": item.id,
        "session_id": item.session_id,
        "project_code": item.project_code,
        "client": item.client,
        "page_code": item.page_code,
        "page_name": item.page_name,
        "url": item.url,
        "status": item.status,
        "process_pid": item.process_pid,
        "script_path": item.script_path,
        "started_by": item.started_by,
        "error_message": item.error_message,
        "started_at": item.started_at,
        "heartbeat_at": item.heartbeat_at,
        "stopped_at": item.stopped_at,
        "recorded_step_count": recorded_step_count,
    }
    if candidate_summary is not None:
        summary = candidate_summary
    elif db is not None:
        summary = _candidate_summary_for_session(db, item)
    else:
        summary = {}
    if summary:
        payload.update(summary)
        payload["candidate_summary"] = summary
    return payload


def _get_session_or_404(db: Session, session_id: str) -> PageObjectRecorderSession:
    normalized_session_id = _normalize_session_id(session_id)
    item = RecorderRepository(db).get_session_by_id(normalized_session_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"recorder session not found: {session_id}")
    return item


def _resolve_playwright_command() -> list[str]:
    if importlib.util.find_spec("playwright") is not None:
        return [sys.executable, "-m", "playwright"]
    playwright_bin = shutil.which("playwright")
    if playwright_bin:
        return [playwright_bin]
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=(
            "playwright runtime not available in current web-ui-service environment; "
            f"install it with '{sys.executable} -m pip install -r requirements-dev.txt' "
            f"and '{sys.executable} -m playwright install'"
        ),
    )


def _start_codegen_process(url: str, script_path: Path) -> int:
    playwright_command = _resolve_playwright_command()
    script_path.parent.mkdir(parents=True, exist_ok=True)
    stderr_path = _stderr_log_path(script_path)
    stderr_path.parent.mkdir(parents=True, exist_ok=True)
    stderr_handle = stderr_path.open("wb")
    try:
        process = subprocess.Popen(  # noqa: S603
            [
                *playwright_command,
                "codegen",
                str(url),
                "--target",
                "python",
                "--output",
                str(script_path),
            ],
            stdout=subprocess.DEVNULL,
            stderr=stderr_handle,
        )
    finally:
        stderr_handle.close()
    _PROCESS_REGISTRY[int(process.pid)] = process
    deadline = time.monotonic() + _CODEGEN_STARTUP_WAIT_SECONDS
    while time.monotonic() < deadline:
        if process.poll() is not None:
            _PROCESS_REGISTRY.pop(int(process.pid), None)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=_format_codegen_launch_error(script_path),
            )
        time.sleep(_CODEGEN_STARTUP_POLL_INTERVAL_SECONDS)
    return int(process.pid)


def _resolve_recorder_script_path(raw_script_path: str) -> Path:
    script_path = Path(str(raw_script_path or "").strip()).resolve()
    recorder_root = _RECORDER_ROOT.resolve()
    if not script_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="录制脚本不存在，无法回放。")
    if not script_path.is_file() or script_path.suffix != ".py":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="录制脚本路径无效，无法回放。")
    try:
        script_path.relative_to(recorder_root)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="录制脚本不在允许的录制产物目录内。") from exc
    return script_path


def _run_recorder_script(script_path: Path, *, timeout_seconds: int) -> dict[str, object]:
    started_at = datetime.now(UTC)
    env = os.environ.copy()
    try:
        completed = subprocess.run(  # noqa: S603
            [sys.executable, str(script_path)],
            cwd=str(script_path.parent),
            env=env,
            capture_output=True,
            text=True,
            timeout=max(5, min(int(timeout_seconds or 120), 600)),
            check=False,
        )
        finished_at = datetime.now(UTC)
        return {
            "status": "passed" if int(completed.returncode) == 0 else "failed",
            "exit_code": int(completed.returncode),
            "stdout_tail": str(completed.stdout or "")[-4000:].strip(),
            "stderr_tail": str(completed.stderr or "")[-4000:].strip(),
            "started_at": started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
            "duration_seconds": round((finished_at - started_at).total_seconds(), 3),
            "timed_out": False,
        }
    except subprocess.TimeoutExpired as exc:
        finished_at = datetime.now(UTC)
        stdout = exc.stdout.decode("utf-8", errors="ignore") if isinstance(exc.stdout, bytes) else str(exc.stdout or "")
        stderr = exc.stderr.decode("utf-8", errors="ignore") if isinstance(exc.stderr, bytes) else str(exc.stderr or "")
        return {
            "status": "timeout",
            "exit_code": None,
            "stdout_tail": stdout[-4000:].strip(),
            "stderr_tail": stderr[-4000:].strip(),
            "started_at": started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
            "duration_seconds": round((finished_at - started_at).total_seconds(), 3),
            "timed_out": True,
        }


def _stop_codegen_process(process_pid: int | None) -> None:
    if process_pid is None or process_pid <= 0:
        return
    process = _PROCESS_REGISTRY.pop(process_pid, None)
    if process is not None:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
        return
    try:
        os.kill(process_pid, signal.SIGTERM)
    except OSError:
        return


def _recorded_steps_path(script_path: Path) -> Path:
    return script_path.with_suffix(".steps.json")


def _quality_tier_from_score(score: int) -> str:
    if score >= 85:
        return "A"
    if score >= 72:
        return "B"
    if score >= 58:
        return "C"
    return "D"


def _candidate_summary_from_rows(rows: list[PageObjectCandidateElement]) -> dict[str, object]:
    group_keys = {str(row.group_key or "").strip() for row in rows if str(row.group_key or "").strip()}
    return {
        "candidate_count": len(rows),
        "candidate_group_count": len(group_keys),
        "promotable_count": sum(1 for row in rows if str(row.recommended_action or "") == "ingest"),
        "promoted_count": sum(1 for row in rows if str(row.candidate_status or "") == "promoted"),
        "rejected_count": sum(1 for row in rows if str(row.candidate_status or "") == "rejected"),
    }


def _candidate_summary_for_session(db: Session, session: PageObjectRecorderSession) -> dict[str, object]:
    rows = RecorderRepository(db).list_candidates_by_session(session.session_id)
    return _candidate_summary_from_rows(rows)


def _candidate_summaries_for_sessions(db: Session, session_ids: list[str]) -> dict[str, dict[str, object]]:
    normalized_ids = [str(session_id or "").strip() for session_id in session_ids if str(session_id or "").strip()]
    if not normalized_ids:
        return {}
    rows = RecorderRepository(db).list_candidates_by_sessions(normalized_ids)
    rows_by_session: dict[str, list[PageObjectCandidateElement]] = {session_id: [] for session_id in normalized_ids}
    for row in rows:
        rows_by_session.setdefault(str(row.session_id or ""), []).append(row)
    return {
        session_id: _candidate_summary_from_rows(session_rows)
        for session_id, session_rows in rows_by_session.items()
    }


def _candidate_summary_from_payload(element_candidates: list[dict[str, object]]) -> dict[str, object]:
    group_keys: set[str] = set()
    promotable_count = 0
    for item in element_candidates:
        locator = _ParsedLocator(
            locator_type=str(item.get("locator_type") or ""),
            locator_value=str(item.get("locator_value") or ""),
            role=str(item.get("role") or ""),
        )
        group_keys.add(_group_key_for_locator(locator))
        if str(item.get("recommended_action") or "") == "ingest":
            promotable_count += 1
    return {
        "candidate_count": len(element_candidates),
        "candidate_group_count": len(group_keys),
        "promotable_count": promotable_count,
        "promoted_count": 0,
        "rejected_count": 0,
    }


def _serialize_candidate_element(row: PageObjectCandidateElement) -> dict[str, object]:
    element_code = str(row.promoted_element_code or row.merged_to_element_code or "").strip()
    return {
        "candidate_key": str(row.candidate_key or ""),
        "group_key": str(row.group_key or ""),
        "locator_type": str(row.raw_locator_type or ""),
        "locator_value": str(row.raw_locator_value or ""),
        "role": str(row.raw_role or ""),
        "raw_text": str(row.raw_text or ""),
        "category": _infer_locator_category(
            _ParsedLocator(
                locator_type=str(row.raw_locator_type or ""),
                locator_value=str(row.raw_locator_value or ""),
                role=str(row.raw_role or ""),
            )
        ),
        "step_hit_count": int(row.step_hit_count or 0),
        "score": round(int(row.quality_score or 0) / 100, 2),
        "quality_tier": str(row.quality_tier or ""),
        "confidence": _score_to_tier(int(row.quality_score or 0) / 100)[1],
        "ingestible": str(row.recommended_action or "") in {"ingest", "review"},
        "recommended_action": str(row.recommended_action or ""),
        "candidate_status": str(row.candidate_status or ""),
        "ingest_block_reason": str(row.ingest_block_reason or ""),
        "risk_tags": list(row.risk_tags_json or []),
        "element_code": element_code,
        "proposed_element_code": str(row.proposed_element_code or ""),
        "proposed_element_name": str(row.proposed_element_name or ""),
        "business_type_guess": str(row.business_type_guess or ""),
        "ingested": bool(element_code),
        "probe": {
            "overall_status": "persisted",
            "status": str(row.probe_status or ""),
            "match_count": int(row.probe_match_count or 0),
            "visible": bool(row.probe_visible),
            "interactable": bool(row.probe_interactable),
        },
    }


def _candidate_elements_for_session(db: Session, session: PageObjectRecorderSession) -> list[dict[str, object]]:
    rows = RecorderRepository(db).list_candidates_by_session(session.session_id)
    return [_serialize_candidate_element(row) for row in rows]


def _sync_candidate_group(
    db: Session,
    *,
    project_code: str,
    client: str,
    page_code: str,
    group_key: str,
    latest_session_id: str,
    source_catalog: SourceSemanticCatalog,
) -> None:
    rows = RecorderRepository(db).list_candidates_by_group(
        project_code, client, page_code, group_key
    )
    if not rows:
        return
    sorted_rows = sorted(rows, key=lambda row: int(row.quality_score or 0), reverse=True)
    top = sorted_rows[0]
    scores = [int(row.quality_score or 0) for row in rows]
    action_priority = {"ingest": 3, "review": 2, "skip": 1}
    recommended_action = max(
        (str(row.recommended_action or "review") for row in rows),
        key=lambda value: action_priority.get(value, 0),
    )
    risk_tags: list[str] = []
    sample_texts: list[str] = []
    for row in sorted_rows:
        for tag in list(row.risk_tags_json or []):
            text = str(tag or "").strip()
            if text and text not in risk_tags:
                risk_tags.append(text)
        sample = str(row.raw_text or row.raw_locator_value or "").strip()
        if sample and sample not in sample_texts:
            sample_texts.append(sample)

    group = RecorderRepository(db).get_group(project_code, client, page_code, group_key)
    if group is None:
        group = PageObjectCandidateGroup(
            project_code=project_code,
            client=client,
            page_code=page_code,
            group_key=group_key,
            promotion_status="pending",
        )
    group.proposed_element_code = str(top.proposed_element_code or "")
    group.proposed_element_name = str(top.proposed_element_name or "")
    group.business_type_guess = str(top.business_type_guess or "")
    top_locator = _ParsedLocator(
        locator_type=str(top.raw_locator_type or ""),
        locator_value=str(top.raw_locator_value or ""),
        role=str(top.raw_role or ""),
    )
    source_hint = source_catalog.match(
        locator_type=top_locator.locator_type,
        locator_value=top_locator.locator_value,
        role=top_locator.role,
    )
    group.business_domain_guess = str(source_hint.business_domain or "").strip() if source_hint is not None else _business_domain_guess(page_code, top_locator)
    group.quality_tier = _quality_tier_from_score(max(scores))
    group.max_score = max(scores)
    group.avg_score = int(round(sum(scores) / len(scores)))
    group.session_count = len({str(row.session_id or "") for row in rows if str(row.session_id or "").strip()})
    group.candidate_count = len(rows)
    group.recommended_action = recommended_action
    group.route_scope = str(top.route or "")
    group.top_locator_source = _locator_source(str(top.raw_locator_type or ""))
    group.top_locator_type = str(top.raw_locator_type or "")
    group.top_locator_value = str(top.raw_locator_value or "")
    group.top_role = str(top.raw_role or "")
    group.risk_tags_json = risk_tags[:20]
    group.sample_texts_json = sample_texts[:10]
    group.latest_session_id = latest_session_id
    if not str(group.matched_existing_element_code or "").strip():
        group.matched_existing_element_code = str(top.merged_to_element_code or top.promoted_element_code or "")
    db.add(group)


def _persist_candidate_elements(
    db: Session,
    *,
    session: PageObjectRecorderSession,
    element_candidates: list[dict[str, object]],
    element_code_by_key: dict[tuple[str, str, str], str],
) -> dict[str, object]:
    route = _normalize_page_route(session.url)
    project = TestProjectRepository(db).get_by_code(session.project_code)
    configured_source_roots = list(project.source_roots_json or []) if project is not None else []
    configured_source_terms = dict(project.source_terms_json or {}) if project is not None else {}
    source_catalog = build_source_semantic_catalog(
        project_code=session.project_code,
        page_code=session.page_code,
        route=route,
        source_roots=configured_source_roots or None,
        semantic_terms=configured_source_terms or None,
    )
    touched_group_keys: set[str] = set()
    existing_rows = {
        str(row.candidate_key or ""): row
        for row in RecorderRepository(db).list_candidates_by_session(session.session_id)
    }
    for item in element_candidates:
        locator = _ParsedLocator(
            locator_type=str(item.get("locator_type") or ""),
            locator_value=str(item.get("locator_value") or ""),
            role=str(item.get("role") or ""),
        )
        if not locator.locator_type or not locator.locator_value:
            continue
        candidate_key = _candidate_key_for_locator(locator)
        group_key = _group_key_for_locator(locator)
        touched_group_keys.add(group_key)
        score = int(round(float(item.get("score") or 0) * 100))
        proposal_seed, proposed_name, business_type_guess, _business_domain_guess_value = _source_enhanced_candidate_semantics(
            locator=locator,
            page_code=session.page_code,
            catalog=source_catalog,
        )
        proposed_code = _normalize_business_element_code(proposal_seed, locator=locator)
        probe = item.get("probe") if isinstance(item.get("probe"), dict) else {}
        row = existing_rows.get(candidate_key)
        if row is None:
            row = PageObjectCandidateElement(
                project_code=session.project_code,
                client=session.client,
                page_code=session.page_code,
                session_id=session.session_id,
                candidate_key=candidate_key,
                candidate_status="pending",
            )
        row.group_key = group_key
        row.raw_locator_type = locator.locator_type
        row.raw_locator_value = locator.locator_value
        row.raw_role = locator.role
        row.raw_text = locator.locator_value if locator.locator_type in {"text", "role", "placeholder"} else ""
        row.dom_signature = _short_hash(locator.locator_type, locator.role, locator.locator_value)
        row.route = route
        row.step_hit_count = int(item.get("step_hit_count") or 0)
        row.quality_score = max(0, min(100, score))
        row.quality_tier = str(item.get("quality_tier") or _quality_tier_from_score(score))
        row.risk_tags_json = list(item.get("risk_tags") or [])
        row.recommended_action = str(item.get("recommended_action") or "review")
        if str(row.candidate_status or "") not in {"reviewed", "promoted", "rejected", "merged"}:
            row.candidate_status = "pending"
        row.ingest_block_reason = str(item.get("ingest_block_reason") or "")
        row.proposed_element_code = proposed_code
        row.proposed_element_name = proposed_name
        row.business_type_guess = business_type_guess
        row.probe_status = str(probe.get("status") or "unknown")
        row.probe_match_count = int(probe.get("match_count") or 0)
        row.probe_visible = bool(probe.get("visible") or False)
        row.probe_interactable = bool(probe.get("interactable") or False)
        matched_code = str(element_code_by_key.get(_locator_key(locator.locator_type, locator.locator_value, locator.role)) or "")
        if matched_code:
            row.merged_to_element_code = matched_code
        db.add(row)

    db.flush()
    for group_key in touched_group_keys:
        _sync_candidate_group(
            db,
            project_code=session.project_code,
            client=session.client,
            page_code=session.page_code,
            group_key=group_key,
            latest_session_id=session.session_id,
            source_catalog=source_catalog,
        )
    return _candidate_summary_for_session(db, session)


def _parse_locator_from_codegen_line(stripped: str) -> _ParsedLocator | None:
    locator_type = ""
    locator_value = ""
    role = ""
    match = re.search(r'get_by_role\("([^"]+)"\s*,\s*name="([^"]+)"\)', stripped)
    if match:
        locator_type = "role"
        role = str(match.group(1)).strip()
        locator_value = str(match.group(2)).strip()
    if not locator_type:
        match = re.search(r'get_by_test_id\("([^"]+)"\)', stripped)
        if match:
            locator_type = "data-testid"
            locator_value = str(match.group(1)).strip()
    if not locator_type:
        match = re.search(r'get_by_placeholder\("([^"]+)"\)', stripped)
        if match:
            locator_type = "placeholder"
            locator_value = str(match.group(1)).strip()
    if not locator_type:
        match = re.search(r'get_by_text\("([^"]+)"\)', stripped)
        if match:
            locator_type = "text"
            locator_value = _normalize_metric_text_locator(str(match.group(1)).strip())
    if not locator_type:
        match = re.search(r'locator\("([^"]+)"\)', stripped)
        if match:
            raw_locator = str(match.group(1)).strip()
            if raw_locator.startswith("xpath="):
                locator_type = "xpath"
                locator_value = raw_locator.removeprefix("xpath=").strip()
            else:
                locator_type = "css"
                locator_value = raw_locator
                if raw_locator.startswith("#"):
                    locator_type = "id"
                    locator_value = raw_locator.removeprefix("#").strip()
    if not locator_type or not locator_value:
        return None
    return _ParsedLocator(locator_type=locator_type, locator_value=locator_value, role=role)


def _parse_action_from_codegen_line(stripped: str) -> tuple[str, str]:
    if match := re.search(r'\.goto\("(.*?)"\)', stripped):
        return ("navigate", str(match.group(1)).strip())
    if ".dblclick()" in stripped:
        return ("dblclick", "")
    if ".uncheck()" in stripped:
        return ("uncheck", "")
    if ".check()" in stripped:
        return ("check", "")
    if ".click()" in stripped:
        return ("click", "")
    if ".hover()" in stripped:
        return ("hover", "")
    if match := re.search(r'\.fill\("(.*?)"\)', stripped):
        return ("fill", str(match.group(1)))
    if match := re.search(r'\.press\("(.*?)"\)', stripped):
        return ("press", str(match.group(1)))
    if match := re.search(r'\.select_option\("(.*?)"\)', stripped):
        return ("select_option", str(match.group(1)))
    return ("", "")


def _parse_codegen_script(script_path: Path, *, include_dynamic_text: bool = False) -> list[_ParsedLocator]:
    if not script_path.exists():
        return []
    content = script_path.read_text(encoding="utf-8", errors="ignore")
    parsed: list[_ParsedLocator] = []
    seen: set[tuple[str, str, str]] = set()
    for line in content.splitlines():
        stripped = line.strip()
        locator = _parse_locator_from_codegen_line(stripped)
        if locator is None:
            continue
        if not include_dynamic_text and locator.locator_type == "text" and _looks_dynamic_text_locator(locator.locator_value):
            continue
        key = _locator_key(locator.locator_type, locator.locator_value, locator.role)
        if key in seen:
            continue
        seen.add(key)
        parsed.append(locator)
    return parsed


def _parse_codegen_steps(script_path: Path) -> list[_ParsedStep]:
    if not script_path.exists():
        return []
    content = script_path.read_text(encoding="utf-8", errors="ignore")
    steps: list[_ParsedStep] = []
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        action, value = _parse_action_from_codegen_line(stripped)
        if not action:
            continue
        if action == "press" and str(value).strip().lower() in {"capslock", "numlock", "scrolllock"}:
            continue
        locator = _parse_locator_from_codegen_line(stripped)
        if action == "navigate":
            steps.append(
                _ParsedStep(
                    action=action,
                    locator_type="url",
                    locator_value=value,
                    role="",
                    value=value,
                    raw_line=stripped,
                )
            )
            continue
        if locator is None:
            continue
        steps.append(
            _ParsedStep(
                action=action,
                locator_type=locator.locator_type,
                locator_value=locator.locator_value,
                role=locator.role,
                value=value,
                raw_line=stripped,
            )
        )
    return _dedupe_recorded_steps(steps)


def _dedupe_recorded_steps(steps: list[_ParsedStep]) -> list[_ParsedStep]:
    if not steps:
        return []
    normalized: list[_ParsedStep] = []
    for step in steps:
        if normalized:
            previous = normalized[-1]
            if (
                step.action == "click"
                and previous.action == "click"
                and _locator_key(step.locator_type, step.locator_value, step.role)
                == _locator_key(previous.locator_type, previous.locator_value, previous.role)
            ):
                continue
        normalized.append(step)
    return normalized


def _serialize_recorded_steps(
    steps: list[_ParsedStep],
    *,
    element_code_by_key: dict[tuple[str, str, str], str] | None = None,
) -> list[dict[str, object]]:
    element_code_by_key = element_code_by_key or {}
    items: list[dict[str, object]] = []
    for index, step in enumerate(steps, start=1):
        items.append(
            {
                "index": index,
                "action": step.action,
                "locator_type": step.locator_type,
                "locator_value": step.locator_value,
                "role": step.role,
                "value": step.value,
                "element_code": element_code_by_key.get(
                    _locator_key(step.locator_type, step.locator_value, step.role),
                    "",
                ),
                "raw_line": step.raw_line,
            }
        )
    return items


def _save_recorded_steps(script_path: Path, steps: list[dict[str, object]]) -> None:
    artifact_path = _recorded_steps_path(script_path)
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(
        json.dumps(steps, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )



# ---- 以下函数体已移至 page_object_recorder_cases.py（从 _load_recorded_steps 起）----
# 导入放在文件末尾以避免循环依赖（新模块需要从此文件导入 helper 函数）
from app.services.page_object_recorder_cases import (  # noqa: E402
    _load_recorded_steps,
    _ensure_page_object,
    _load_page_object_snapshot,
    create_recorder_session,
    heartbeat_recorder_session,
    get_recorder_session,
    list_recorder_sessions,
    batch_delete_recorder_sessions,
    get_recorder_session_playback,
    replay_recorder_session,
    cleanup_orphan_recorder_artifacts,
    _normalize_step_value,
    _build_case_steps_from_recorded_steps,
    _build_case_script_from_recorded_steps,
    _dedupe_text_items,
    _link_case_refs_for_recorded_elements,
    create_test_case_draft_from_session,
    stop_recorder_session,
)
