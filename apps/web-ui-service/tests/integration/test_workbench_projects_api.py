from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.routers import legacy_workbench
from app.routers.workbench_tasks import router as workbench_tasks_router
import app.models.test_project  # noqa: F401
import app.schemas.test_project as test_project_schema
from app.services import test_project_service


@pytest.fixture()
def workbench_projects_client(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> tuple[TestClient, Session]:
    engine = create_engine(
        "sqlite://",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)
    Base.metadata.create_all(bind=engine)
    session = testing_session()

    state_root = tmp_path / "test-points"
    state_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(legacy_workbench, "TEST_POINTS_ROOT", state_root)
    monkeypatch.setattr(legacy_workbench, "_ensure_dirs", lambda: None)

    app = FastAPI()
    app.include_router(workbench_tasks_router)

    def override_get_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    client = TestClient(app)
    try:
        yield client, session
    finally:
        client.close()
        session.close()


def test_workbench_projects_api_merges_master_projects_and_legacy_state(
    workbench_projects_client: tuple[TestClient, Session],
) -> None:
    client, db_session = workbench_projects_client

    test_project_service.create_project(
        db_session,
        test_project_schema.TestProjectCreate(
            project_code="mall",
            project_name="Mall Platform",
        ),
    )
    state_root = legacy_workbench.TEST_POINTS_ROOT
    (state_root / "default").mkdir(parents=True, exist_ok=True)
    (state_root / "legacyproj").mkdir(parents=True, exist_ok=True)

    response = client.get("/api/workbench/projects")

    assert response.status_code == 200
    payload = response.json()
    assert payload["codes"][0] == "atp"
    assert "mall" in payload["codes"]
    assert "default" in payload["codes"]
    assert "legacyproj" in payload["codes"]

    items = {str(item["project_code"]): item for item in payload["items"]}
    assert items["atp"]["status"] == "active"
    assert items["mall"]["project_name"] == "Mall Platform"
    assert items["mall"]["status"] == "active"
    assert items["legacyproj"]["source"] == "legacy_state"
