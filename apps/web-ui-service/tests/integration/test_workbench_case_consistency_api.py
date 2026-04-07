from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
import app.models.test_case  # noqa: F401
import app.models.test_project  # noqa: F401
import app.models.workbench_state  # noqa: F401
from app.models.test_case import TestCase
from app.routers import legacy_workbench
from app.routers.workbench_reporting import router as workbench_reporting_router


@pytest.fixture()
def case_consistency_client(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> tuple[TestClient, Session, Path, Path, Path, Path]:
    engine = create_engine(
        "sqlite://",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)
    Base.metadata.create_all(bind=engine)
    session = testing_session()

    valid_case_id = "atp-web-ret-query-fn-ai-0001"
    session.add(
        TestCase(
            case_id=valid_case_id,
            name="退货查询校验",
            product_line="退货",
            module="查询",
        )
    )
    session.commit()

    history_file = tmp_path / "history.json"
    runtime_runs_file = tmp_path / "runtime-runs.json"
    defect_links_file = tmp_path / "defect-links.json"
    reports_root = tmp_path / "reports"
    reports_root.mkdir(parents=True, exist_ok=True)

    history_file.write_text(
        json.dumps(
            [
                {"timestamp": "2026-04-06T00:00:00+00:00", "action": "run_case", "case_id": valid_case_id},
                {"timestamp": "2026-04-06T00:01:00+00:00", "action": "run_case", "case_id": "SMOKE-RETURNAPPLY-020005"},
            ],
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    runtime_runs_file.write_text(
        json.dumps(
            [
                {"run_id": "run-valid", "case_id": valid_case_id, "status": "passed"},
                {"run_id": "run-stale", "case_id": "TC-PRODUCT-GEN-001", "status": "failed"},
            ],
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    defect_links_file.write_text(
        json.dumps(
            [
                {"case_id": valid_case_id, "defect_id": "BUG-1", "linked_at": "2026-04-06T00:00:00+00:00"},
                {"case_id": "SMOKE-RETURNAPPLY-020005", "defect_id": "BUG-2", "linked_at": "2026-04-06T00:00:00+00:00"},
            ],
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    (reports_root / "atp-web-ret-query-fn-ai-0001.report.json").write_text(
        '{"case_id":"atp-web-ret-query-fn-ai-0001"}\n',
        encoding="utf-8",
    )
    (reports_root / "atp-web-ret-query-fn-ai-0001.report.md").write_text("ok\n", encoding="utf-8")
    (reports_root / "SMOKE-RETURNAPPLY-020005.report.json").write_text(
        '{"case_id":"SMOKE-RETURNAPPLY-020005"}\n',
        encoding="utf-8",
    )
    (reports_root / "SMOKE-RETURNAPPLY-020005.report.md").write_text("stale\n", encoding="utf-8")

    monkeypatch.setattr(legacy_workbench, "HISTORY_FILE", history_file)
    monkeypatch.setattr(legacy_workbench, "RUNTIME_RUNS_FILE", runtime_runs_file)
    monkeypatch.setattr(legacy_workbench, "DEFECT_LINKS_FILE", defect_links_file)
    monkeypatch.setattr(legacy_workbench, "EXECUTION_REPORTS_ROOT", reports_root)
    monkeypatch.setattr(legacy_workbench, "_sync_stage_a_workbench_state", lambda: None)
    monkeypatch.setattr(legacy_workbench, "_ensure_dirs", lambda: None)

    app = FastAPI()
    app.include_router(workbench_reporting_router)

    def override_get_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        yield client, session, history_file, runtime_runs_file, defect_links_file, reports_root
    finally:
        client.close()
        session.close()


def test_workbench_history_filters_non_case_center_records(
    case_consistency_client: tuple[TestClient, Session, Path, Path, Path, Path],
) -> None:
    client, _session, _history_file, _runtime_runs_file, _defect_links_file, _reports_root = (
        case_consistency_client
    )
    response = client.get("/api/workbench/history")
    assert response.status_code == 200
    payload = response.json()
    rows = payload.get("items", [])
    assert len(rows) == 1
    assert rows[0]["case_id"] == "atp-web-ret-query-fn-ai-0001"


def test_case_consistency_cleanup_removes_stale_state_and_reports(
    case_consistency_client: tuple[TestClient, Session, Path, Path, Path, Path],
) -> None:
    client, _session, history_file, runtime_runs_file, defect_links_file, reports_root = (
        case_consistency_client
    )
    response = client.post("/api/workbench/case-consistency/cleanup")
    assert response.status_code == 200
    payload = response.json()
    assert payload["history"]["removed_count"] == 1
    assert payload["runtime_runs"]["removed_count"] == 1
    assert payload["defect_links"]["removed_count"] == 1
    assert payload["execution_reports"]["removed_count"] >= 2

    history_rows = json.loads(history_file.read_text(encoding="utf-8"))
    runtime_rows = json.loads(runtime_runs_file.read_text(encoding="utf-8"))
    defect_rows = json.loads(defect_links_file.read_text(encoding="utf-8"))
    assert [row["case_id"] for row in history_rows] == ["atp-web-ret-query-fn-ai-0001"]
    assert [row["case_id"] for row in runtime_rows] == ["atp-web-ret-query-fn-ai-0001"]
    assert [row["case_id"] for row in defect_rows] == ["atp-web-ret-query-fn-ai-0001"]
    assert (reports_root / "atp-web-ret-query-fn-ai-0001.report.json").exists()
    assert not (reports_root / "SMOKE-RETURNAPPLY-020005.report.json").exists()
    assert not (reports_root / "SMOKE-RETURNAPPLY-020005.report.md").exists()
