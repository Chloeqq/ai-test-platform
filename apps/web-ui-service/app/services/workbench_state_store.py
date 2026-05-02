from __future__ import annotations

import json
import os
import threading
from datetime_compat import UTC
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import delete, select

from app.core.database import SessionLocal
from app.models.workbench_state import (
    WorkbenchDefectLink,
    WorkbenchExecutionGateDecision,
    WorkbenchFailureSourceCalibration,
    WorkbenchHistoryEvent,
    WorkbenchReviewDecision,
    WorkbenchRuntimeRun,
)

REPO_ROOT = Path(__file__).resolve().parents[4]
WEB_UI_STATE_ROOT = REPO_ROOT / "web-ui" / "state"
WEB_UI_DEFAULT_STATE_DIR = WEB_UI_STATE_ROOT / "default"
WEB_UI_RUNS_DIR = WEB_UI_STATE_ROOT / "runs"
WEB_UI_REPORTING_DIR = WEB_UI_STATE_ROOT / "reporting"
TEST_POINTS_ROOT = WEB_UI_STATE_ROOT / "test-points"
ASSETS_CASES_ROOT = REPO_ROOT / "assets" / "test-cases"
AI_CASES_ROOT = ASSETS_CASES_ROOT / "ai-generated"
RUNNER_ROOT = REPO_ROOT / "runners" / "web-playwright-python"
ALLURE_RESULTS_ROOT = RUNNER_ROOT / "allure-results"
ALLURE_REPORT_ROOT = RUNNER_ROOT / "allure-report"
EXECUTION_REPORTS_ROOT = REPO_ROOT / "reports" / "executions"
ALLURE_SNAPSHOTS_ROOT = REPO_ROOT / "runners" / "web-playwright-python" / "allure-report-snapshots"

HISTORY_FILE = WEB_UI_DEFAULT_STATE_DIR / "history.json"
RUNTIME_RUNS_FILE = WEB_UI_DEFAULT_STATE_DIR / "runtime-runs.json"
DEFECT_LINKS_FILE = WEB_UI_REPORTING_DIR / "defect-links.json"
REVIEW_DECISIONS_FILE = WEB_UI_REPORTING_DIR / "review-decisions.json"
EXECUTION_GATE_DECISIONS_FILE = WEB_UI_REPORTING_DIR / "execution-gate-decisions.json"
FAILURE_SOURCE_CALIBRATIONS_FILE = WEB_UI_REPORTING_DIR / "failure-source-calibrations.json"

FILE_LOCK = threading.Lock()


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def now_iso() -> str:
    return _now_iso()


def _resolve_state_backend() -> str:
    raw = str(os.getenv("WORKBENCH_STATE_BACKEND", "database")).strip().lower()
    if raw in {"file", "database"}:
        return raw
    if raw == "auto":
        database_url = str(os.getenv("DATABASE_URL", "")).strip().lower()
        if database_url.startswith("postgresql"):
            return "database"
        return "file"
    raise RuntimeError(f"invalid WORKBENCH_STATE_BACKEND: {raw}")


def _is_db_enabled_for_path(path: Path) -> bool:
    if _resolve_state_backend() != "database":
        return False
    return path in {
        HISTORY_FILE,
        RUNTIME_RUNS_FILE,
        DEFECT_LINKS_FILE,
        REVIEW_DECISIONS_FILE,
        EXECUTION_GATE_DECISIONS_FILE,
        FAILURE_SOURCE_CALIBRATIONS_FILE,
    }


def _db_model_for_path(path: Path):
    if path == HISTORY_FILE:
        return WorkbenchHistoryEvent
    if path == RUNTIME_RUNS_FILE:
        return WorkbenchRuntimeRun
    if path == DEFECT_LINKS_FILE:
        return WorkbenchDefectLink
    if path == REVIEW_DECISIONS_FILE:
        return WorkbenchReviewDecision
    if path == EXECUTION_GATE_DECISIONS_FILE:
        return WorkbenchExecutionGateDecision
    if path == FAILURE_SOURCE_CALIBRATIONS_FILE:
        return WorkbenchFailureSourceCalibration
    return None


def _normalize_payload(item: dict[str, Any]) -> dict[str, Any]:
    return dict(item) if isinstance(item, dict) else {}


def _upsert_db_item(path: Path, item: dict[str, Any]) -> None:
    model = _db_model_for_path(path)
    if model is None:
        return
    payload = _normalize_payload(item)
    with SessionLocal() as db:
        if model is WorkbenchRuntimeRun:
            run_id = str(payload.get("run_id", "")).strip()
            if not run_id:
                return
            existing_run = db.execute(
                select(WorkbenchRuntimeRun).where(WorkbenchRuntimeRun.run_id == run_id)
            ).scalar_one_or_none()
            if existing_run is None:
                existing_run = WorkbenchRuntimeRun(run_id=run_id)
                db.add(existing_run)
            existing_run.project = str(payload.get("project", "mall")).strip() or "mall"
            existing_run.page = str(payload.get("page", "")).strip()
            existing_run.status = str(payload.get("status", "")).strip()
            existing_run.payload = payload
        elif model is WorkbenchReviewDecision:
            project = str(payload.get("project", "mall")).strip() or "mall"
            run_id = str(payload.get("run_id", "")).strip()
            page = str(payload.get("page", "")).strip()
            review_type = str(payload.get("review_type", "")).strip()
            if not review_type:
                return
            existing_review = db.execute(
                select(WorkbenchReviewDecision).where(
                    WorkbenchReviewDecision.project == project,
                    WorkbenchReviewDecision.run_id == run_id,
                    WorkbenchReviewDecision.page == page,
                    WorkbenchReviewDecision.review_type == review_type,
                )
            ).scalar_one_or_none()
            if existing_review is None:
                existing_review = WorkbenchReviewDecision(
                    project=project,
                    run_id=run_id,
                    page=page,
                    review_type=review_type,
                )
                db.add(existing_review)
            existing_review.status = str(payload.get("status", "")).strip()
            existing_review.payload = payload
        elif model is WorkbenchExecutionGateDecision:
            project = str(payload.get("project", "mall")).strip() or "mall"
            run_id = str(payload.get("run_id", "")).strip()
            page = str(payload.get("page", "")).strip()
            existing_gate = db.execute(
                select(WorkbenchExecutionGateDecision).where(
                    WorkbenchExecutionGateDecision.project == project,
                    WorkbenchExecutionGateDecision.run_id == run_id,
                    WorkbenchExecutionGateDecision.page == page,
                )
            ).scalar_one_or_none()
            if existing_gate is None:
                existing_gate = WorkbenchExecutionGateDecision(
                    project=project,
                    run_id=run_id,
                    page=page,
                )
                db.add(existing_gate)
            existing_gate.decision = str(payload.get("decision", "")).strip()
            existing_gate.payload = payload
        elif model is WorkbenchHistoryEvent:
            event = WorkbenchHistoryEvent(
                run_id=str(payload.get("run_id", "")).strip(),
                action=str(payload.get("action", "")).strip(),
                page=str(payload.get("page", "")).strip(),
                status=str(payload.get("status", "")).strip(),
                actor_display=str(payload.get("actor_display", "")).strip(),
                detail_summary=str(payload.get("detail_summary", "")).strip(),
                payload=payload,
            )
            db.add(event)
        elif model is WorkbenchDefectLink:
            case_id = str(payload.get("case_id", "")).strip()
            defect_id = str(payload.get("defect_id", "")).strip()
            if not case_id or not defect_id:
                return
            existing_link = db.execute(
                select(WorkbenchDefectLink).where(
                    WorkbenchDefectLink.case_id == case_id,
                    WorkbenchDefectLink.defect_id == defect_id,
                )
            ).scalar_one_or_none()
            if existing_link is None:
                existing_link = WorkbenchDefectLink(case_id=case_id, defect_id=defect_id)
                db.add(existing_link)
            existing_link.linked_at = str(payload.get("linked_at", "")).strip()
            existing_link.payload = payload
        elif model is WorkbenchFailureSourceCalibration:
            sample_id = str(payload.get("sample_id", "")).strip()
            if not sample_id:
                return
            existing_sample = db.execute(
                select(WorkbenchFailureSourceCalibration).where(
                    WorkbenchFailureSourceCalibration.sample_id == sample_id
                )
            ).scalar_one_or_none()
            if existing_sample is None:
                existing_sample = WorkbenchFailureSourceCalibration(sample_id=sample_id)
                db.add(existing_sample)
            existing_sample.run_id = str(payload.get("run_id", "")).strip()
            existing_sample.case_id = str(payload.get("case_id", "")).strip()
            existing_sample.page = str(payload.get("page", "")).strip()
            existing_sample.human_decision = str(payload.get("human_decision", "")).strip()
            existing_sample.predicted_failure_source = str(payload.get("predicted_failure_source", "")).strip()
            existing_sample.confirmed_failure_source = str(payload.get("confirmed_failure_source", "")).strip()
            existing_sample.payload = payload
        db.commit()


def _replace_db_items(path: Path, items: list[dict[str, Any]]) -> None:
    model = _db_model_for_path(path)
    if model is None:
        return
    with SessionLocal() as db:
        db.execute(delete(model))
        db.commit()
        for item in items:
            payload = _normalize_payload(item)
            if model is WorkbenchRuntimeRun:
                db.add(
                    WorkbenchRuntimeRun(
                        run_id=str(payload.get("run_id", "")).strip(),
                        project=str(payload.get("project", "mall")).strip() or "mall",
                        page=str(payload.get("page", "")).strip(),
                        status=str(payload.get("status", "")).strip(),
                        payload=payload,
                    )
                )
            elif model is WorkbenchReviewDecision:
                db.add(
                    WorkbenchReviewDecision(
                        project=str(payload.get("project", "mall")).strip() or "mall",
                        run_id=str(payload.get("run_id", "")).strip(),
                        page=str(payload.get("page", "")).strip(),
                        review_type=str(payload.get("review_type", "")).strip(),
                        status=str(payload.get("status", "")).strip(),
                        payload=payload,
                    )
                )
            elif model is WorkbenchExecutionGateDecision:
                db.add(
                    WorkbenchExecutionGateDecision(
                        project=str(payload.get("project", "mall")).strip() or "mall",
                        run_id=str(payload.get("run_id", "")).strip(),
                        page=str(payload.get("page", "")).strip(),
                        decision=str(payload.get("decision", "")).strip(),
                        payload=payload,
                    )
                )
            elif model is WorkbenchHistoryEvent:
                db.add(
                    WorkbenchHistoryEvent(
                        run_id=str(payload.get("run_id", "")).strip(),
                        action=str(payload.get("action", "")).strip(),
                        page=str(payload.get("page", "")).strip(),
                        status=str(payload.get("status", "")).strip(),
                        actor_display=str(payload.get("actor_display", "")).strip(),
                        detail_summary=str(payload.get("detail_summary", "")).strip(),
                        payload=payload,
                    )
                )
            elif model is WorkbenchDefectLink:
                db.add(
                    WorkbenchDefectLink(
                        case_id=str(payload.get("case_id", "")).strip(),
                        defect_id=str(payload.get("defect_id", "")).strip(),
                        linked_at=str(payload.get("linked_at", "")).strip(),
                        payload=payload,
                    )
                )
            elif model is WorkbenchFailureSourceCalibration:
                db.add(
                    WorkbenchFailureSourceCalibration(
                        sample_id=str(payload.get("sample_id", "")).strip(),
                        run_id=str(payload.get("run_id", "")).strip(),
                        case_id=str(payload.get("case_id", "")).strip(),
                        page=str(payload.get("page", "")).strip(),
                        human_decision=str(payload.get("human_decision", "")).strip(),
                        predicted_failure_source=str(payload.get("predicted_failure_source", "")).strip(),
                        confirmed_failure_source=str(payload.get("confirmed_failure_source", "")).strip(),
                        payload=payload,
                    )
                )
        db.commit()


def _read_db_items(path: Path) -> list[dict[str, Any]]:
    model = _db_model_for_path(path)
    if model is None:
        return []
    with SessionLocal() as db:
        if model is WorkbenchRuntimeRun:
            runtime_rows = db.execute(
                select(WorkbenchRuntimeRun).order_by(WorkbenchRuntimeRun.updated_at.desc(), WorkbenchRuntimeRun.id.desc())
            ).scalars().all()
            return [dict(row.payload) for row in runtime_rows if isinstance(row.payload, dict)]
        elif model is WorkbenchReviewDecision:
            review_rows = db.execute(
                select(WorkbenchReviewDecision).order_by(
                    WorkbenchReviewDecision.updated_at.desc(), WorkbenchReviewDecision.id.desc()
                )
            ).scalars().all()
            return [dict(row.payload) for row in review_rows if isinstance(row.payload, dict)]
        elif model is WorkbenchExecutionGateDecision:
            gate_rows = db.execute(
                select(WorkbenchExecutionGateDecision).order_by(
                    WorkbenchExecutionGateDecision.updated_at.desc(), WorkbenchExecutionGateDecision.id.desc()
                )
            ).scalars().all()
            return [dict(row.payload) for row in gate_rows if isinstance(row.payload, dict)]
        elif model is WorkbenchDefectLink:
            defect_rows = db.execute(
                select(WorkbenchDefectLink).order_by(WorkbenchDefectLink.updated_at.desc(), WorkbenchDefectLink.id.desc())
            ).scalars().all()
            return [dict(row.payload) for row in defect_rows if isinstance(row.payload, dict)]
        elif model is WorkbenchFailureSourceCalibration:
            calibration_rows = db.execute(
                select(WorkbenchFailureSourceCalibration).order_by(
                    WorkbenchFailureSourceCalibration.updated_at.desc(),
                    WorkbenchFailureSourceCalibration.id.desc(),
                )
            ).scalars().all()
            return [dict(row.payload) for row in calibration_rows if isinstance(row.payload, dict)]
        else:
            history_rows = db.execute(
                select(WorkbenchHistoryEvent).order_by(WorkbenchHistoryEvent.id.desc())
            ).scalars().all()
            return [dict(row.payload) for row in history_rows if isinstance(row.payload, dict)]


def ensure_dirs() -> None:
    WEB_UI_DEFAULT_STATE_DIR.mkdir(parents=True, exist_ok=True)
    WEB_UI_RUNS_DIR.mkdir(parents=True, exist_ok=True)
    WEB_UI_REPORTING_DIR.mkdir(parents=True, exist_ok=True)
    AI_CASES_ROOT.mkdir(parents=True, exist_ok=True)
    ALLURE_SNAPSHOTS_ROOT.mkdir(parents=True, exist_ok=True)
    if _resolve_state_backend() == "file":
        if not HISTORY_FILE.exists():
            HISTORY_FILE.write_text("[]\n", encoding="utf-8")
        if not RUNTIME_RUNS_FILE.exists():
            RUNTIME_RUNS_FILE.write_text("[]\n", encoding="utf-8")
        if not DEFECT_LINKS_FILE.exists():
            DEFECT_LINKS_FILE.write_text("[]\n", encoding="utf-8")
        if not REVIEW_DECISIONS_FILE.exists():
            REVIEW_DECISIONS_FILE.write_text("[]\n", encoding="utf-8")
        if not EXECUTION_GATE_DECISIONS_FILE.exists():
            EXECUTION_GATE_DECISIONS_FILE.write_text("[]\n", encoding="utf-8")
        if not FAILURE_SOURCE_CALIBRATIONS_FILE.exists():
            FAILURE_SOURCE_CALIBRATIONS_FILE.write_text("[]\n", encoding="utf-8")


def read_json_list(path: Path) -> list[dict[str, Any]]:
    if _is_db_enabled_for_path(path):
        return _read_db_items(path)
    return _read_file_json_list(path)


def _read_file_json_list(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict)]


def write_json_list(path: Path, items: list[dict[str, Any]]) -> None:
    if _is_db_enabled_for_path(path):
        _replace_db_items(path, items)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(items, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def append_history(entry: dict[str, Any]) -> None:
    with FILE_LOCK:
        if _is_db_enabled_for_path(HISTORY_FILE):
            payload = dict(entry)
            payload.setdefault("timestamp", _now_iso())
            _upsert_db_item(HISTORY_FILE, payload)
            return
        items = read_json_list(HISTORY_FILE)
        items.insert(0, entry)
        write_json_list(HISTORY_FILE, items[:500])


def append_runtime_run(entry: dict[str, Any]) -> None:
    with FILE_LOCK:
        if _is_db_enabled_for_path(RUNTIME_RUNS_FILE):
            payload = dict(entry)
            payload.setdefault("updated_at", _now_iso())
            _upsert_db_item(RUNTIME_RUNS_FILE, payload)
            return
        items = read_json_list(RUNTIME_RUNS_FILE)
        items.insert(0, entry)
        write_json_list(RUNTIME_RUNS_FILE, items[:1000])


def update_runtime_run(run_id: str, updates: dict[str, Any]) -> None:
    normalized_run_id = str(run_id or "").strip()
    if not normalized_run_id:
        return
    with FILE_LOCK:
        if _is_db_enabled_for_path(RUNTIME_RUNS_FILE):
            items = _read_db_items(RUNTIME_RUNS_FILE)
            updated = False
            for item in items:
                if str(item.get("run_id", "")).strip() != normalized_run_id:
                    continue
                item.update(updates)
                item["run_id"] = normalized_run_id
                item.setdefault("updated_at", _now_iso())
                updated = True
                _upsert_db_item(RUNTIME_RUNS_FILE, item)
                break
            if not updated:
                payload = {"run_id": normalized_run_id, **updates, "updated_at": _now_iso()}
                _upsert_db_item(RUNTIME_RUNS_FILE, payload)
            return
        items = read_json_list(RUNTIME_RUNS_FILE)
        updated = False
        for item in items:
            if str(item.get("run_id", "")).strip() != normalized_run_id:
                continue
            item.update(updates)
            updated = True
            break
        if not updated:
            items.insert(0, {"run_id": normalized_run_id, **updates})
        write_json_list(RUNTIME_RUNS_FILE, items[:1000])
