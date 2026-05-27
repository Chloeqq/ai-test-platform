# ruff: noqa: E402
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

WEB_UI_ROOT = Path(__file__).resolve().parents[2]
if str(WEB_UI_ROOT) not in sys.path:
    sys.path.insert(0, str(WEB_UI_ROOT))

from app.core.database import Base
from app.models.workbench_state import WorkbenchDefectLink, WorkbenchFailureSourceCalibration
from app.services import workbench_review_service as review_service
from app.services import workbench_state_store as state_store
from shared_backend.case_ids import normalize_case_id


def test_state_store_roundtrip_and_append(tmp_path: Path, monkeypatch) -> None:
    history_file = tmp_path / "history.json"
    runtime_file = tmp_path / "runtime-runs.json"
    review_file = tmp_path / "review-decisions.json"
    gate_file = tmp_path / "execution-gate-decisions.json"
    defect_file = tmp_path / "defect-links.json"
    calibration_file = tmp_path / "failure-source-calibrations.json"

    monkeypatch.setattr(state_store, "WEB_UI_DEFAULT_STATE_DIR", tmp_path)
    monkeypatch.setattr(state_store, "WEB_UI_RUNS_DIR", tmp_path / "runs")
    monkeypatch.setattr(state_store, "WEB_UI_REPORTING_DIR", tmp_path / "reporting")
    monkeypatch.setattr(state_store, "AI_CASES_ROOT", tmp_path / "ai-generated")
    monkeypatch.setattr(state_store, "ALLURE_SNAPSHOTS_ROOT", tmp_path / "snapshots")
    monkeypatch.setattr(state_store, "HISTORY_FILE", history_file)
    monkeypatch.setattr(state_store, "RUNTIME_RUNS_FILE", runtime_file)
    monkeypatch.setattr(state_store, "DEFECT_LINKS_FILE", defect_file)
    monkeypatch.setattr(state_store, "REVIEW_DECISIONS_FILE", review_file)
    monkeypatch.setattr(state_store, "EXECUTION_GATE_DECISIONS_FILE", gate_file)
    monkeypatch.setattr(state_store, "FAILURE_SOURCE_CALIBRATIONS_FILE", calibration_file)

    state_store.ensure_dirs()
    state_store.write_json_list(history_file, [{"action": "seed"}])
    assert state_store.read_json_list(history_file) == [{"action": "seed"}]

    state_store.append_history({"action": "review_confirmed"})
    state_store.append_runtime_run({"run_id": "run-1"})
    state_store.update_runtime_run("run-1", {"status": "passed"})

    assert state_store.read_json_list(history_file)[0]["action"] == "review_confirmed"
    assert state_store.read_json_list(runtime_file)[0]["status"] == "passed"
    assert history_file.exists()
    assert runtime_file.exists()
    assert review_file.exists()
    assert gate_file.exists()
    assert defect_file.exists()
    assert calibration_file.exists()


def test_review_service_upsert_and_timeline(tmp_path: Path, monkeypatch) -> None:
    review_file = tmp_path / "review-decisions.json"
    history_file = tmp_path / "history.json"

    monkeypatch.setattr(state_store, "REVIEW_DECISIONS_FILE", review_file)
    monkeypatch.setattr(state_store, "HISTORY_FILE", history_file)
    monkeypatch.setattr(state_store, "WEB_UI_DEFAULT_STATE_DIR", tmp_path)
    monkeypatch.setattr(state_store, "WEB_UI_RUNS_DIR", tmp_path / "runs")
    monkeypatch.setattr(state_store, "WEB_UI_REPORTING_DIR", tmp_path / "reporting")
    monkeypatch.setattr(state_store, "AI_CASES_ROOT", tmp_path / "ai-generated")
    monkeypatch.setattr(state_store, "ALLURE_SNAPSHOTS_ROOT", tmp_path / "snapshots")

    payload = SimpleNamespace(
        project="default",
        run_id="RUN-123",
        case_id="tc-product-001",
        page="product",
        review_type="test_point",
        status="confirmed",
        items=[
            {
                "key": "tp-1",
                "label": "确认测试点",
                "decision": "confirmed",
                "confidence": 0.8,
                "warnings": ["w1"],
            }
        ],
        note="ok",
    )

    record = review_service.upsert_review_decision(
        payload,
        actor={"confirmed_by": "betty", "confirmed_by_role": "admin", "confirmed_by_source": "x-user-name"},
    )

    assert record["review_type"] == "test_point"
    assert record["confirmed_by"] == "betty"
    assert json.loads(review_file.read_text(encoding="utf-8"))[0]["case_id"] == normalize_case_id("tc-product-001")

    monkeypatch.setattr(
        state_store,
        "HISTORY_FILE",
        history_file,
    )
    state_store.write_json_list(
        history_file,
        [
            {
                "timestamp": "2026-03-22T10:00:00+00:00",
                "action": "review_confirmed",
                "run_id": "RUN-123",
                "page": "product",
                "review_type": "test_point",
                "status": "confirmed",
                "confirmed_by": "betty",
                "confirmed_by_role": "admin",
                "actor_display": "betty (admin)",
                "detail_summary": "test_point 确认 1 项",
            }
        ],
    )

    summary = review_service.build_review_audit_summary(
        {
            "test_point": {
                "status": "confirmed",
                "candidate_count": 1,
                "confirmed_by": "betty",
                "confirmed_by_role": "admin",
                "actor_display": "betty (admin)",
                "updated_at": "2026-03-22T10:00:00+00:00",
            },
            "pending_sections": 0,
            "confirmed_sections": 1,
        }
    )
    timeline = review_service.build_review_audit_timeline(run_id="RUN-123", page="product")

    assert summary["confirmed_sections"] == 1
    assert summary["latest_actor_display"] == "betty (admin)"
    assert timeline[0]["action"] == "review_confirmed"
    assert timeline[0]["actor_display"] == "betty (admin)"


def test_state_store_database_backend_defect_and_calibration_migration_backfill(tmp_path: Path, monkeypatch) -> None:
    defect_file = tmp_path / "reporting" / "defect-links.json"
    calibration_file = tmp_path / "reporting" / "failure-source-calibrations.json"
    history_file = tmp_path / "history.json"
    runtime_file = tmp_path / "runtime-runs.json"
    review_file = tmp_path / "review-decisions.json"
    gate_file = tmp_path / "execution-gate-decisions.json"

    db_file = tmp_path / "workbench_state.db"
    engine = create_engine(f"sqlite:///{db_file}", future=True)
    Base.metadata.create_all(bind=engine)
    test_session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    monkeypatch.setenv("WORKBENCH_STATE_BACKEND", "database")
    monkeypatch.setattr(state_store, "SessionLocal", test_session_local)
    monkeypatch.setattr(state_store, "WEB_UI_DEFAULT_STATE_DIR", tmp_path)
    monkeypatch.setattr(state_store, "WEB_UI_RUNS_DIR", tmp_path / "runs")
    monkeypatch.setattr(state_store, "WEB_UI_REPORTING_DIR", tmp_path / "reporting")
    monkeypatch.setattr(state_store, "AI_CASES_ROOT", tmp_path / "ai-generated")
    monkeypatch.setattr(state_store, "ALLURE_SNAPSHOTS_ROOT", tmp_path / "snapshots")
    monkeypatch.setattr(state_store, "HISTORY_FILE", history_file)
    monkeypatch.setattr(state_store, "RUNTIME_RUNS_FILE", runtime_file)
    monkeypatch.setattr(state_store, "REVIEW_DECISIONS_FILE", review_file)
    monkeypatch.setattr(state_store, "EXECUTION_GATE_DECISIONS_FILE", gate_file)
    monkeypatch.setattr(state_store, "DEFECT_LINKS_FILE", defect_file)
    monkeypatch.setattr(state_store, "FAILURE_SOURCE_CALIBRATIONS_FILE", calibration_file)

    state_store.ensure_dirs()

    defect_seed = [
        {
            "case_id": "TC-DEFECT-001",
            "defect_id": "BUG-1001",
            "linked_at": "2026-03-23T09:00:00+00:00",
            "system": "jira",
        }
    ]
    defect_file.write_text(json.dumps(defect_seed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    loaded_defects = state_store.read_json_list(defect_file)
    assert loaded_defects == defect_seed
    with test_session_local() as db:
        assert db.execute(select(WorkbenchDefectLink)).scalars().all()[0].defect_id == "BUG-1001"

    defect_updated = [
        {
            "case_id": "TC-DEFECT-002",
            "defect_id": "BUG-1002",
            "linked_at": "2026-03-23T10:00:00+00:00",
            "system": "jira",
        }
    ]
    state_store.write_json_list(defect_file, defect_updated)
    with test_session_local() as db:
        rows = db.execute(select(WorkbenchDefectLink)).scalars().all()
        assert len(rows) == 1
        assert rows[0].case_id == "TC-DEFECT-002"
        assert rows[0].defect_id == "BUG-1002"
    assert json.loads(defect_file.read_text(encoding="utf-8"))[0]["defect_id"] == "BUG-1002"

    calibration_seed = [
        {
            "sample_id": "SAMPLE-001",
            "run_id": "RUN-001",
            "case_id": "TC-001",
            "page": "product",
            "human_decision": "accepted",
            "predicted_failure_source": "page_object",
            "confirmed_failure_source": "page_object",
        }
    ]
    calibration_file.write_text(json.dumps(calibration_seed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    loaded_calibrations = state_store.read_json_list(calibration_file)
    assert loaded_calibrations == calibration_seed
    with test_session_local() as db:
        assert db.execute(select(WorkbenchFailureSourceCalibration)).scalars().all()[0].sample_id == "SAMPLE-001"

    calibration_updated = [
        {
            "sample_id": "SAMPLE-002",
            "run_id": "RUN-002",
            "case_id": "TC-002",
            "page": "order",
            "human_decision": "corrected",
            "predicted_failure_source": "unknown",
            "confirmed_failure_source": "app_bug",
        }
    ]
    state_store.write_json_list(calibration_file, calibration_updated)
    with test_session_local() as db:
        calibration_rows = db.execute(select(WorkbenchFailureSourceCalibration)).scalars().all()
        assert len(calibration_rows) == 1
        assert calibration_rows[0].sample_id == "SAMPLE-002"
        assert calibration_rows[0].confirmed_failure_source == "app_bug"
    assert json.loads(calibration_file.read_text(encoding="utf-8"))[0]["sample_id"] == "SAMPLE-002"
