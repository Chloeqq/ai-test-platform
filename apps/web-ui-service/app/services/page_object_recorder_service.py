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
from app.repositories.recorder_repository import RecorderRepository
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
    rows = (
        db.execute(
            select(PageObjectCandidateElement).where(
                PageObjectCandidateElement.project_code == project_code,
                PageObjectCandidateElement.client == client,
                PageObjectCandidateElement.page_code == page_code,
                PageObjectCandidateElement.group_key == group_key,
            )
        )
        .scalars()
        .all()
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
    project = db.execute(
        select(TestProject).where(TestProject.project_code == session.project_code)
    ).scalar_one_or_none()
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


def _load_recorded_steps(script_path: Path) -> list[dict[str, object]]:
    artifact_path = _recorded_steps_path(script_path)
    if not artifact_path.exists():
        return []
    try:
        payload = json.loads(artifact_path.read_text(encoding="utf-8", errors="ignore"))
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, list):
        return []
    items: list[dict[str, object]] = []
    for index, item in enumerate(payload, start=1):
        if not isinstance(item, dict):
            continue
        items.append(
            {
                "index": int(item.get("index") or index),
                "action": str(item.get("action") or "").strip(),
                "locator_type": str(item.get("locator_type") or "").strip(),
                "locator_value": str(item.get("locator_value") or "").strip(),
                "role": str(item.get("role") or "").strip(),
                "value": str(item.get("value") or "").strip(),
                "element_code": str(item.get("element_code") or "").strip(),
                "raw_line": str(item.get("raw_line") or "").strip(),
            }
        )
    return items


def _ensure_page_object(
    db: Session,
    *,
    project_code: str,
    client: str,
    page_code: str,
    page_name: str,
    entry_url: str,
    started_by: str,
) -> tuple[dict[str, object], str]:
    try:
        item = page_object_service.get_page_object(
            db,
            page_code=page_code,
            project_code=project_code,
            client=client,
        )
        return item, "existing"
    except HTTPException as exc:
        if int(exc.status_code) != status.HTTP_404_NOT_FOUND:
            raise
        item = page_object_service.create_page_object(
            db,
            PageObjectCreate(
                project_code=project_code,
                client=client,
                page_code=page_code,
                page_name=page_name,
                page_url=_derive_page_url(entry_url, page_code=page_code, page_name=page_name),
                precondition_state=_derive_precondition_state(entry_url, page_code=page_code, page_name=page_name),
                status="draft",
                created_by=started_by,
            ),
        )
        return item, "created"


def _load_page_object_snapshot(
    db: Session,
    *,
    project_code: str,
    client: str,
    page_code: str,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    try:
        page_item = page_object_service.get_page_object(
            db,
            page_code=page_code,
            project_code=project_code,
            client=client,
        )
    except HTTPException as exc:
        if int(exc.status_code) == status.HTTP_404_NOT_FOUND:
            return {}, []
        raise
    elements = page_object_service.list_page_elements(
        db,
        page_code=page_code,
        project_code=project_code,
        client=client,
    )
    return page_item, list(elements)


def create_recorder_session(db: Session, payload: RecorderSessionCreate) -> dict[str, object]:
    project_code = _normalize_project_code(payload.project_code)
    test_project_service.ensure_project_active_for_write(db, project_code)
    client = normalize_client_code(payload.client)
    page_code = _normalize_page_code(payload.page_code)
    page_name = str(payload.page_name or "").strip()
    started_by = str(payload.started_by or "").strip() or "system"
    if not page_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="page_name cannot be empty")
    session_id = f"rec_{uuid.uuid4().hex[:16]}"
    script_path = (_RECORDER_ROOT / f"{session_id}.codegen.py").resolve()
    process_pid = _start_codegen_process(str(payload.url), script_path)
    item = PageObjectRecorderSession(
        session_id=session_id,
        project_code=project_code,
        client=client,
        page_code=page_code,
        page_name=page_name,
        url=str(payload.url).strip(),
        status="active",
        process_pid=process_pid,
        script_path=str(script_path),
        started_by=started_by,
        heartbeat_at=datetime.now(UTC),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    item = _sync_active_session_runtime_state(db, item)
    if str(item.status or "").strip().lower() == "failed":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(item.error_message or "").strip() or "录制启动失败",
        )
    return _serialize_session(item)


def heartbeat_recorder_session(
    db: Session,
    *,
    session_id: str,
    payload: RecorderSessionHeartbeatPayload,
) -> dict[str, object]:
    item = _sync_active_session_runtime_state(db, _get_session_or_404(db, session_id))
    if item.status != "active":
        return _serialize_session(item)
    item.heartbeat_at = datetime.now(UTC)
    db.add(item)
    db.commit()
    db.refresh(item)
    return _serialize_session(item)


def get_recorder_session(db: Session, *, session_id: str) -> dict[str, object]:
    item = _sync_active_session_runtime_state(db, _get_session_or_404(db, session_id))
    return _serialize_session(item)


def list_recorder_sessions(
    db: Session,
    *,
    project_code: str,
    client: str,
    page_code: str = "",
    status_text: str = "",
    limit: int = 50,
    offset: int = 0,
) -> dict[str, object]:
    normalized_project_code = _normalize_project_code(project_code)
    normalized_client = normalize_client_code(client)
    normalized_page_code = _normalize_page_code(page_code) if str(page_code or "").strip() else ""
    normalized_status = str(status_text or "").strip().lower()
    if normalized_status and normalized_status not in SESSION_STATUS_VALUES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"status must be one of {sorted(SESSION_STATUS_VALUES)}",
        )
    normalized_limit = max(1, min(int(limit or 50), 200))
    normalized_offset = max(0, int(offset or 0))

    conditions = [
        PageObjectRecorderSession.project_code == normalized_project_code,
        PageObjectRecorderSession.client == normalized_client,
    ]
    if normalized_page_code:
        conditions.append(PageObjectRecorderSession.page_code == normalized_page_code)
    if normalized_status:
        conditions.append(PageObjectRecorderSession.status == normalized_status)

    total = int(
        RecorderRepository(db).count_sessions(
            project_code=normalized_project_code,
            client=normalized_client,
            page_code=normalized_page_code or None,
            status=normalized_status or None,
        )
        or 0
    )
    rows = (
        db.execute(
            select(PageObjectRecorderSession)
            .where(*conditions)
            .order_by(PageObjectRecorderSession.started_at.desc(), PageObjectRecorderSession.id.desc())
            .offset(normalized_offset)
            .limit(normalized_limit)
        )
        .scalars()
        .all()
    )
    items: list[dict[str, object]] = []
    candidate_summaries = _candidate_summaries_for_sessions(
        db,
        [str(row.session_id or "") for row in rows],
    )
    for row in rows:
        synced = _sync_active_session_runtime_state(db, row)
        items.append(
            _serialize_session_summary(
                synced,
                candidate_summary=candidate_summaries.get(str(synced.session_id or "")),
            )
        )

    return {
        "items": items,
        "total": total,
        "filters": {
            "project_code": normalized_project_code,
            "client": normalized_client,
            "page_code": normalized_page_code,
            "status": normalized_status,
        },
        "pagination": {
            "limit": normalized_limit,
            "offset": normalized_offset,
            "has_more": (normalized_offset + len(items)) < total,
        },
    }


def _safe_delete_recorder_artifacts(raw_script_path: str) -> int:
    raw = str(raw_script_path or "").strip()
    if not raw:
        return 0
    try:
        script_path = Path(raw).expanduser().resolve()
        recorder_root = _RECORDER_ROOT.resolve()
        script_path.relative_to(recorder_root)
    except (OSError, ValueError):
        return 0
    deleted_count = 0
    for path in (script_path, _recorded_steps_path(script_path), _stderr_log_path(script_path)):
        try:
            if path.exists():
                path.unlink()
                deleted_count += 1
        except OSError:
            continue
    return deleted_count


def _sync_page_metrics_for_recorder_pages(
    db: Session,
    *,
    project_code: str,
    client: str,
    page_codes: set[str],
) -> None:
    if not page_codes:
        return
    page_objects = list(
        db.execute(
            select(PageObject).where(
                PageObject.project_code == project_code,
                PageObject.client == client,
                PageObject.page_code.in_(sorted(page_codes)),
            )
        ).scalars().all()
    )
    for page_object in page_objects:
        page_object_service._sync_page_object_metrics(db, page_object_id=int(page_object.id))
    db.commit()


def batch_delete_recorder_sessions(
    db: Session,
    *,
    project_code: str,
    client: str,
    session_ids: list[str],
    delete_artifacts: bool = True,
) -> dict[str, object]:
    normalized_project_code = _normalize_project_code(project_code)
    normalized_client = normalize_client_code(client)
    normalized_session_ids: list[str] = []
    seen: set[str] = set()
    for value in session_ids:
        session_id = str(value or "").strip()
        if not session_id or session_id in seen:
            continue
        seen.add(session_id)
        normalized_session_ids.append(session_id)
    if not normalized_session_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="session_ids cannot be empty")

    sessions = list(
        db.execute(
            select(PageObjectRecorderSession).where(
                PageObjectRecorderSession.project_code == normalized_project_code,
                PageObjectRecorderSession.client == normalized_client,
                PageObjectRecorderSession.session_id.in_(normalized_session_ids),
            )
        ).scalars().all()
    )
    deleted_session_ids = [str(item.session_id or "") for item in sessions]
    affected_page_codes = {str(item.page_code or "") for item in sessions if str(item.page_code or "").strip()}
    artifact_deleted_count = 0
    for item in sessions:
        if str(item.status or "").strip().lower() == "active":
            _stop_codegen_process(item.process_pid)
        if delete_artifacts:
            artifact_deleted_count += _safe_delete_recorder_artifacts(str(item.script_path or ""))

    candidate_rows = list(
        db.execute(
            select(PageObjectCandidateElement).where(
                PageObjectCandidateElement.project_code == normalized_project_code,
                PageObjectCandidateElement.client == normalized_client,
                PageObjectCandidateElement.session_id.in_(deleted_session_ids),
            )
        ).scalars().all()
    )
    affected_group_keys = {
        (str(row.page_code or ""), str(row.group_key or ""))
        for row in candidate_rows
        if str(row.page_code or "").strip() and str(row.group_key or "").strip()
    }
    if deleted_session_ids:
        RecorderRepository(db).delete_candidates_by_sessions(
            normalized_project_code, normalized_client, deleted_session_ids
        )
        RecorderRepository(db).delete_sessions(
            normalized_project_code, normalized_client, deleted_session_ids
        )
        db.flush()

        empty_group_keys: list[tuple[str, str]] = []
        for page_code, group_key in sorted(affected_group_keys):
            remaining_count = int(
                db.execute(
                    select(func.count()).select_from(PageObjectCandidateElement).where(
                        PageObjectCandidateElement.project_code == normalized_project_code,
                        PageObjectCandidateElement.client == normalized_client,
                        PageObjectCandidateElement.page_code == page_code,
                        PageObjectCandidateElement.group_key == group_key,
                    )
                ).scalar_one()
                or 0
            )
            if remaining_count == 0:
                empty_group_keys.append((page_code, group_key))
        for page_code, group_key in empty_group_keys:
            db.execute(
                delete(PageObjectCandidateGroup).where(
                    PageObjectCandidateGroup.project_code == normalized_project_code,
                    PageObjectCandidateGroup.client == normalized_client,
                    PageObjectCandidateGroup.page_code == page_code,
                    PageObjectCandidateGroup.group_key == group_key,
                )
            )
        db.commit()
        _sync_page_metrics_for_recorder_pages(
            db,
            project_code=normalized_project_code,
            client=normalized_client,
            page_codes=affected_page_codes,
        )

    missing_session_ids = [item for item in normalized_session_ids if item not in set(deleted_session_ids)]
    return {
        "deleted_session_count": len(deleted_session_ids),
        "deleted_session_ids": deleted_session_ids,
        "deleted_candidate_count": len(candidate_rows),
        "deleted_artifact_count": artifact_deleted_count,
        "missing_count": len(missing_session_ids),
        "missing_session_ids": missing_session_ids,
    }


def get_recorder_session_playback(db: Session, *, session_id: str) -> dict[str, object]:
    item = _sync_active_session_runtime_state(db, _get_session_or_404(db, session_id))
    script_path = Path(item.script_path)
    recorded_steps = _load_recorded_steps(script_path)
    if not recorded_steps:
        recorded_steps = _serialize_recorded_steps(_parse_codegen_steps(script_path))
    script_code = ""
    if script_path.exists():
        script_code = script_path.read_text(encoding="utf-8", errors="ignore")
    return {
        "session": _serialize_session_summary(item, db),
        "recorded_step_count": len(recorded_steps),
        "recorded_steps": recorded_steps,
        "script_code": script_code,
        "stderr_tail": _tail_text_file(_stderr_log_path(script_path), max_chars=4000),
        "can_replay": len(recorded_steps) > 0,
        "candidate_summary": _candidate_summary_for_session(db, item),
    }


def replay_recorder_session(db: Session, *, session_id: str, timeout_seconds: int = 120) -> dict[str, object]:
    item = _sync_active_session_runtime_state(db, _get_session_or_404(db, session_id))
    if str(item.status or "").strip().lower() == "active":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="录制会话仍在进行中，请先停止后再回放。")
    script_path = _resolve_recorder_script_path(str(item.script_path or ""))
    recorded_steps = _load_recorded_steps(script_path)
    if not recorded_steps:
        recorded_steps = _serialize_recorded_steps(_parse_codegen_steps(script_path))
    if not recorded_steps:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="录制会话没有可回放步骤。")

    result = _run_recorder_script(script_path, timeout_seconds=timeout_seconds)
    return {
        "session": _serialize_session_summary(item, db),
        "recorded_step_count": len(recorded_steps),
        "script_path": str(script_path),
        "timeout_seconds": max(5, min(int(timeout_seconds or 120), 600)),
        **result,
    }


def cleanup_orphan_recorder_artifacts(db: Session) -> dict[str, object]:
    _RECORDER_ROOT.mkdir(parents=True, exist_ok=True)
    active_session_ids = set(RecorderRepository(db).list_all_session_ids())
    orphan_files: list[str] = []
    cleaned_files: list[str] = []
    scanned_files = 0

    for artifact_path in sorted(_RECORDER_ROOT.glob("rec_*.codegen.py")):
        scanned_files += 1
        session_id = str(artifact_path.name).removesuffix(".codegen.py")
        if not session_id:
            continue
        if session_id in active_session_ids:
            continue
        orphan_files.append(str(artifact_path))
        steps_path = _recorded_steps_path(artifact_path)
        if artifact_path.exists():
            artifact_path.unlink()
            cleaned_files.append(str(artifact_path))
        if steps_path.exists():
            steps_path.unlink()
            cleaned_files.append(str(steps_path))

    for steps_path in sorted(_RECORDER_ROOT.glob("rec_*.codegen.steps.json")):
        scanned_files += 1
        session_id = str(steps_path.name).removesuffix(".codegen.steps.json")
        if not session_id:
            continue
        if session_id in active_session_ids:
            continue
        if str(steps_path) not in orphan_files:
            orphan_files.append(str(steps_path))
        if steps_path.exists():
            steps_path.unlink()
            cleaned_files.append(str(steps_path))

    for stderr_path in sorted(_RECORDER_ROOT.glob("rec_*.codegen.stderr.log")):
        scanned_files += 1
        session_id = str(stderr_path.name).removesuffix(".codegen.stderr.log")
        if not session_id:
            continue
        if session_id in active_session_ids:
            continue
        if str(stderr_path) not in orphan_files:
            orphan_files.append(str(stderr_path))
        if stderr_path.exists():
            stderr_path.unlink()
            cleaned_files.append(str(stderr_path))

    return {
        "scanned_file_count": scanned_files,
        "orphan_file_count": len(orphan_files),
        "cleaned_file_count": len(cleaned_files),
        "cleaned_files": cleaned_files,
    }


def _normalize_step_value(value: object) -> str:
    return str(value or "").strip()


def _build_case_steps_from_recorded_steps(recorded_steps: list[dict[str, object]]) -> list[dict[str, object]]:
    case_steps: list[dict[str, object]] = []
    for index, step in enumerate(recorded_steps, start=1):
        action = _normalize_step_value(step.get("action"))
        locator_type = _normalize_step_value(step.get("locator_type"))
        locator_value = _normalize_step_value(step.get("locator_value"))
        role = _normalize_step_value(step.get("role"))
        element_code = _normalize_step_value(step.get("element_code"))
        value = _normalize_step_value(step.get("value"))
        if not action:
            continue
        if element_code:
            target = f"element:{element_code}"
        elif locator_type and locator_value:
            target = f"{locator_type}:{locator_value}"
        elif locator_value:
            target = locator_value
        else:
            target = f"step-{index}"
        locator_hint = locator_type
        if role:
            locator_hint = f"{locator_type}({role})" if locator_type else role
        description = f"录制步骤{index} {action} {target}"
        if locator_hint and locator_value:
            description += f" [{locator_hint}={locator_value}]"
        case_steps.append(
            {
                "action": action,
                "target": target,
                "value": value,
                "description": description,
            }
        )
    return case_steps


def _build_case_script_from_recorded_steps(
    session: PageObjectRecorderSession,
    recorded_steps: list[dict[str, object]],
) -> str:
    fn_name = re.sub(r"[^a-zA-Z0-9_]+", "_", f"test_{session.page_code}_{session.session_id}").strip("_").lower()
    if not fn_name:
        fn_name = f"test_recorder_{uuid.uuid4().hex[:8]}"
    lines = [
        f"def {fn_name}(page):",
        f"    # Generated from recorder session {session.session_id}",
    ]
    normalized_url = str(session.url or "").strip()
    if normalized_url:
        lines.append(f"    page.goto({json.dumps(normalized_url, ensure_ascii=False)})")
    for index, step in enumerate(recorded_steps, start=1):
        raw_line = _normalize_step_value(step.get("raw_line"))
        if raw_line:
            lines.append(f"    # Step {index}: {raw_line}")
    lines.append("    assert True")
    return "\n".join(lines) + "\n"


def _dedupe_text_items(values: list[str]) -> list[str]:
    output: list[str] = []
    for raw in values:
        value = str(raw or "").strip()
        if value and value not in output:
            output.append(value)
    return output


def _link_case_refs_for_recorded_elements(
    db: Session,
    *,
    session: PageObjectRecorderSession,
    case_id: str,
    recorded_steps: list[dict[str, object]],
    created_by: str,
) -> dict[str, int]:
    element_codes = _dedupe_text_items([
        _normalize_step_value(step.get("element_code"))
        for step in recorded_steps
    ])
    linked_count = 0
    skipped_count = 0
    for element_code in element_codes:
        try:
            page_object_service.create_page_object_ref(
                db,
                page_code=session.page_code,
                element_code=element_code,
                project_code=session.project_code,
                client=session.client,
                payload=PageObjectRefCreate(
                    reference_type="test_case",
                    reference_key=case_id,
                    source="recorder",
                    created_by=created_by,
                ),
            )
            linked_count += 1
        except HTTPException as exc:
            if int(exc.status_code) in {status.HTTP_404_NOT_FOUND, status.HTTP_409_CONFLICT}:
                skipped_count += 1
                continue
            raise
    return {
        "linked_ref_count": linked_count,
        "skipped_ref_count": skipped_count,
    }


def create_test_case_draft_from_session(
    db: Session,
    *,
    session_id: str,
    payload: RecorderSessionCreateCasePayload,
) -> dict[str, object]:
    session_item = _get_session_or_404(db, session_id)
    if str(session_item.status or "").strip().lower() == "active":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="session is active; stop recorder session before generating test case draft",
        )
    script_path = Path(session_item.script_path)
    recorded_steps = _load_recorded_steps(script_path)
    if not recorded_steps:
        parsed_steps = _parse_codegen_steps(script_path)
        recorded_steps = _serialize_recorded_steps(parsed_steps)
    if not recorded_steps:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="no recorded steps found for this recorder session",
        )

    page_object_item, page_object_action = _ensure_page_object(
        db,
        project_code=session_item.project_code,
        client=session_item.client,
        page_code=session_item.page_code,
        page_name=session_item.page_name,
        entry_url=session_item.url,
        started_by=str(payload.creator or "").strip() or session_item.started_by or "system",
    )
    case_steps = _build_case_steps_from_recorded_steps(recorded_steps)
    if not case_steps:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="recorded steps cannot be converted to test case steps",
        )
    creator = str(payload.creator or "").strip() or session_item.started_by or "system"
    page_name = str(page_object_item.get("page_name") or session_item.page_name or session_item.page_code).strip()
    case_name = str(payload.name or "").strip() or f"{page_name} 录制回放草稿"
    product_line = str(payload.product_line or "").strip() or page_name or session_item.page_code
    module = str(payload.module or "").strip() or "录制回放"
    tags = _dedupe_text_items(
        [*list(payload.tags or []), "recorder", f"page:{session_item.page_code}", f"session:{session_item.session_id}"]
    )
    case = test_case_service.create_test_case(
        db,
        TestCaseCreate(
            mode="manual",
            project_code=session_item.project_code,
            client=session_item.client,
            page_code=session_item.page_code,
            name=case_name,
            product_line=product_line,
            module=module,
            priority=str(payload.priority or "").strip() or "P1",
            test_type="ui",
            precondition_state=str(page_object_item.get("precondition_state") or "").strip(),
            test_steps=case_steps,
            tags=tags,
            creator=creator,
            assignee=str(payload.assignee or "").strip(),
            status=str(payload.status or "").strip() or "active",
            source_ref=f"recorder:{session_item.session_id}",
            script_code=_build_case_script_from_recorded_steps(session_item, recorded_steps),
            expected_result="关键步骤可稳定回放，页面对象元素可被可靠引用。",
        ),
    )
    ref_result = {"linked_ref_count": 0, "skipped_ref_count": 0}
    if bool(payload.link_page_refs):
        ref_result = _link_case_refs_for_recorded_elements(
            db,
            session=session_item,
            case_id=str(case.case_id or ""),
            recorded_steps=recorded_steps,
            created_by=creator,
        )
    return {
        "id": int(case.id),
        "case_id": str(case.case_id or ""),
        "name": str(case.name or ""),
        "project_code": str(case.project_code or ""),
        "client": str(case.client or ""),
        "page_code": str(case.page_code or ""),
        "page_object_action": page_object_action,
        "recorded_step_count": len(recorded_steps),
        "case_step_count": len(case_steps),
        **ref_result,
    }


def stop_recorder_session(
    db: Session,
    *,
    session_id: str,
    payload: RecorderSessionStopPayload,
) -> dict[str, object]:
    item = _sync_active_session_runtime_state(db, _get_session_or_404(db, session_id))
    script_path = Path(item.script_path)
    parsed_steps = _parse_codegen_steps(script_path)
    parsed_locators_all = _parse_codegen_script(script_path, include_dynamic_text=True)
    parsed_locators = [locator for locator in parsed_locators_all if not _is_locator_blocked_for_ingest(locator)[0]]
    step_hit_count_by_key: dict[tuple[str, str, str], int] = {}
    for step in parsed_steps:
        if step.locator_type == "url":
            continue
        key = _locator_key(step.locator_type, step.locator_value, step.role)
        step_hit_count_by_key[key] = int(step_hit_count_by_key.get(key, 0)) + 1
    probe_by_key: dict[tuple[str, str, str], dict[str, object]] = {}
    probe_status = "not_requested"
    if bool(payload.verify_locators):
        probe_by_key, probe_status = _probe_availability(
            item.url,
            parsed_locators_all,
            timeout_ms=int(payload.verify_timeout_ms or 4000),
        )

    if item.status in {"stopped", "failed"}:
        session_payload = _serialize_session(item)
        page_object_item, current_elements = _load_page_object_snapshot(
            db,
            project_code=item.project_code,
            client=item.client,
            page_code=item.page_code,
        )
        element_candidates = _candidate_elements_for_session(db, item)
        candidate_summary = _candidate_summary_for_session(db, item)
        if int(candidate_summary["candidate_count"]) <= 0:
            element_candidates = _build_element_candidates(
                parsed_locators_all,
                step_hit_count_by_key=step_hit_count_by_key,
                element_code_by_key={},
                ingested_keys=set(),
                probe_by_key=probe_by_key,
                probe_status=probe_status,
            )
            candidate_summary = _candidate_summary_from_payload(element_candidates)
        return {
            "session": session_payload,
            "ingested_count": 0,
            "elements": [],
            "steps": list(session_payload.get("recorded_steps") or []),
            "element_candidates": element_candidates,
            "verification": {"requested": bool(payload.verify_locators), "status": probe_status},
            "page_object_action": "already_stopped",
            "page_match_status": "matched" if page_object_item else "missing",
            "page_object": page_object_item,
            "page_element_total_count": len(current_elements),
            "first_element_code": str(current_elements[0].get("element_code") or "") if current_elements else "",
            **candidate_summary,
        }

    _stop_codegen_process(item.process_pid)
    element_code_by_key: dict[tuple[str, str, str], str] = {}
    ingested_keys: set[tuple[str, str, str]] = set()
    page_object_item, page_object_action = _ensure_page_object(
        db,
        project_code=item.project_code,
        client=item.client,
        page_code=item.page_code,
        page_name=item.page_name,
        entry_url=item.url,
        started_by=item.started_by,
    )

    serialized_steps = _serialize_recorded_steps(parsed_steps, element_code_by_key=element_code_by_key)
    _save_recorded_steps(script_path, serialized_steps)
    element_candidates = _build_element_candidates(
        parsed_locators_all,
        step_hit_count_by_key=step_hit_count_by_key,
        element_code_by_key=element_code_by_key,
        ingested_keys=ingested_keys,
        probe_by_key=probe_by_key,
        probe_status=probe_status,
    )
    candidate_summary = _persist_candidate_elements(
        db,
        session=item,
        element_candidates=element_candidates,
        element_code_by_key=element_code_by_key,
    )

    item.status = "stopped"
    item.stopped_at = datetime.now(UTC)
    item.process_pid = None
    db.add(item)
    db.commit()
    db.refresh(item)
    snapshot_page_object, snapshot_elements = _load_page_object_snapshot(
        db,
        project_code=item.project_code,
        client=item.client,
        page_code=item.page_code,
    )
    if snapshot_page_object:
        page_object_item = snapshot_page_object
    ingested: list[dict[str, object]] = []
    first_element_code = ""
    if not first_element_code and snapshot_elements:
        first_element_code = str(snapshot_elements[0].get("element_code") or "")

    return {
        "session": _serialize_session(item),
        "ingested_count": len(ingested),
        "elements": ingested,
        "steps": serialized_steps,
        "element_candidates": element_candidates,
        "verification": {"requested": bool(payload.verify_locators), "status": probe_status},
        "page_object_action": page_object_action,
        "page_match_status": "matched" if page_object_item else "missing",
        "page_object": page_object_item,
        "page_element_total_count": len(snapshot_elements),
        "first_element_code": first_element_code,
        **candidate_summary,
    }
