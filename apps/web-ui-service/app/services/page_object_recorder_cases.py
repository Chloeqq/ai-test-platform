"""录制器用例创建函数 —— 从录制 steps 生成测试用例。

提取自 page_object_recorder_service.py 以控制单文件大小在 1000 行以内。
"""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from fastapi import HTTPException, status
from shared_backend.case_ids import normalize_client_code
from shared_backend.datetime_compat import UTC
from shared_backend.type_utils import normalize_project_code_strict as _normalize_project_code_strict
from sqlalchemy.orm import Session

from app.models.page_object import PageObjectCandidateElement, PageObjectRecorderSession
from app.repositories.page_object_repository import PageObjectRepository
from app.repositories.recorder_repository import RecorderRepository
from app.repositories.recorder_session_repository import RecorderSessionRepository
from app.schemas.page_object import PageObjectRefCreate
from app.schemas.page_object_recorder import RecorderSessionCreateCasePayload
from app.schemas.test_case import TestCaseCreate
from app.services import page_object_service, test_case_service, test_project_service

import logging
LOGGER = logging.getLogger(__name__)


def _svc():
    """惰性导入以避免循环依赖（此模块被 page_object_recorder_service 在底部导入）。"""
    from app.services import page_object_recorder_service as _svc_mod
    return _svc_mod

def _load_recorded_steps(script_path: Path) -> list[dict[str, object]]:
    artifact_path = _svc()._recorded_steps_path(script_path)
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
    project_code = _svc()._normalize_project_code(payload.project_code)
    test_project_service.ensure_project_active_for_write(db, project_code)
    client = normalize_client_code(payload.client)
    page_code = _svc()._normalize_page_code(payload.page_code)
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
    item = _svc()._sync_active_session_runtime_state(db, item)
    if str(item.status or "").strip().lower() == "failed":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(item.error_message or "").strip() or "录制启动失败",
        )
    return _svc()._serialize_session(item)


def heartbeat_recorder_session(
    db: Session,
    *,
    session_id: str,
    payload: RecorderSessionHeartbeatPayload,
) -> dict[str, object]:
    item = _svc()._sync_active_session_runtime_state(db, _svc()._get_session_or_404(db, session_id))
    if item.status != "active":
        return _svc()._serialize_session(item)
    item.heartbeat_at = datetime.now(UTC)
    db.add(item)
    db.commit()
    db.refresh(item)
    return _svc()._serialize_session(item)


def get_recorder_session(db: Session, *, session_id: str) -> dict[str, object]:
    item = _svc()._sync_active_session_runtime_state(db, _svc()._get_session_or_404(db, session_id))
    return _svc()._serialize_session(item)


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
    normalized_project_code = _svc()._normalize_project_code(project_code)
    normalized_client = normalize_client_code(client)
    normalized_page_code = _svc()._normalize_page_code(page_code) if str(page_code or "").strip() else ""
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
    rows = RecorderSessionRepository(db).list_sessions_paginated(
        project_code=normalized_project_code,
        client=normalized_client,
        page_code=normalized_page_code or None,
        status=normalized_status or None,
        offset=normalized_offset,
        limit=normalized_limit,
    )
    items: list[dict[str, object]] = []
    candidate_summaries = _svc()._candidate_summaries_for_sessions(
        db,
        [str(row.session_id or "") for row in rows],
    )
    for row in rows:
        synced = _svc()._sync_active_session_runtime_state(db, row)
        items.append(
            _svc()._serialize_session_summary(
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
    for path in (script_path, _svc()._recorded_steps_path(script_path), _stderr_log_path(script_path)):
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
    page_objects = PageObjectRepository(db).list_by_project_and_page_codes(
        project_code, client, sorted(page_codes)
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
    normalized_project_code = _svc()._normalize_project_code(project_code)
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

    sessions = RecorderRepository(db).list_sessions(
        project_code=normalized_project_code,
        client=normalized_client,
    )
    sessions = [s for s in sessions if str(s.session_id or "") in set(normalized_session_ids)]
    deleted_session_ids = [str(item.session_id or "") for item in sessions]
    affected_page_codes = {str(item.page_code or "") for item in sessions if str(item.page_code or "").strip()}
    artifact_deleted_count = 0
    for item in sessions:
        if str(item.status or "").strip().lower() == "active":
            _svc()._stop_codegen_process(item.process_pid)
        if delete_artifacts:
            artifact_deleted_count += _svc()._safe_delete_recorder_artifacts(str(item.script_path or ""))

    candidate_rows = RecorderRepository(db).list_candidates_by_sessions(deleted_session_ids)
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
        _rec_repo = RecorderRepository(db)
        for page_code, group_key in sorted(affected_group_keys):
            remaining_count = _rec_repo.count_candidates_by_group(
                normalized_project_code, normalized_client, page_code, group_key
            )
            if remaining_count == 0:
                empty_group_keys.append((page_code, group_key))
        for page_code, group_key in empty_group_keys:
            _rec_repo.delete_empty_groups(
                normalized_project_code, normalized_client, page_code, group_key
            )
        db.commit()
        _svc()._sync_page_metrics_for_recorder_pages(
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
    item = _svc()._sync_active_session_runtime_state(db, _svc()._get_session_or_404(db, session_id))
    script_path = Path(item.script_path)
    recorded_steps = _load_recorded_steps(script_path)
    if not recorded_steps:
        recorded_steps = _serialize_recorded_steps(_parse_codegen_steps(script_path))
    script_code = ""
    if script_path.exists():
        script_code = script_path.read_text(encoding="utf-8", errors="ignore")
    return {
        "session": _svc()._serialize_session_summary(item, db),
        "recorded_step_count": len(recorded_steps),
        "recorded_steps": recorded_steps,
        "script_code": script_code,
        "stderr_tail": _tail_text_file(_stderr_log_path(script_path), max_chars=4000),
        "can_replay": len(recorded_steps) > 0,
        "candidate_summary": _svc()._candidate_summary_for_session(db, item),
    }


def replay_recorder_session(db: Session, *, session_id: str, timeout_seconds: int = 120) -> dict[str, object]:
    item = _svc()._sync_active_session_runtime_state(db, _svc()._get_session_or_404(db, session_id))
    if str(item.status or "").strip().lower() == "active":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="录制会话仍在进行中，请先停止后再回放。")
    script_path = _svc()._resolve_recorder_script_path(str(item.script_path or ""))
    recorded_steps = _load_recorded_steps(script_path)
    if not recorded_steps:
        recorded_steps = _serialize_recorded_steps(_parse_codegen_steps(script_path))
    if not recorded_steps:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="录制会话没有可回放步骤。")

    result = _svc()._run_recorder_script(script_path, timeout_seconds=timeout_seconds)
    return {
        "session": _svc()._serialize_session_summary(item, db),
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
        steps_path = _svc()._recorded_steps_path(artifact_path)
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
    session_item = _svc()._get_session_or_404(db, session_id)
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
    item = _svc()._sync_active_session_runtime_state(db, _svc()._get_session_or_404(db, session_id))
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
        session_payload = _svc()._serialize_session(item)
        page_object_item, current_elements = _load_page_object_snapshot(
            db,
            project_code=item.project_code,
            client=item.client,
            page_code=item.page_code,
        )
        element_candidates = _svc()._candidate_elements_for_session(db, item)
        candidate_summary = _svc()._candidate_summary_for_session(db, item)
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

    _svc()._stop_codegen_process(item.process_pid)
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
    candidate_summary = _svc()._persist_candidate_elements(
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
        "session": _svc()._serialize_session(item),
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
