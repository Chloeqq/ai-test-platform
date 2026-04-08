from __future__ import annotations

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
from app.routers import legacy_workbench
from app.routers.workbench_assets import router as workbench_assets_router
import app.schemas.test_case as test_case_schema
import app.schemas.test_project as test_project_schema
from app.services import test_case_service, test_project_service


@pytest.fixture()
def workbench_assets_client(
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

    assets_root = tmp_path / "test-cases"
    ai_cases_root = assets_root / "ai-generated"
    ai_cases_root.mkdir(parents=True, exist_ok=True)
    state_root = tmp_path / "test-points"
    state_root.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(legacy_workbench, "ASSETS_CASES_ROOT", assets_root)
    monkeypatch.setattr(legacy_workbench, "AI_CASES_ROOT", ai_cases_root)
    monkeypatch.setattr(legacy_workbench, "TEST_POINTS_ROOT", state_root)
    monkeypatch.setattr(legacy_workbench, "_sync_stage_a_workbench_state", lambda: None)
    monkeypatch.setattr(legacy_workbench, "_ensure_dirs", lambda: None)

    app = FastAPI()
    app.include_router(workbench_assets_router)

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


def test_workbench_case_save_blocked_when_project_inactive(
    workbench_assets_client: tuple[TestClient, Session],
) -> None:
    client, db_session = workbench_assets_client
    case_id = "atp-web-ret-query-sm-ai-0001"

    test_project_service.create_project(
        db_session,
        test_project_schema.TestProjectCreate(
            project_code="mall",
            project_name="Mall Platform",
        ),
    )
    test_case_service.create_test_case(
        db_session,
        test_case_schema.TestCaseCreate(
            project_code="mall",
            case_id=case_id,
            name="商城 workbench 编辑校验",
            product_line="商城",
            module="查询",
            priority="P1",
            test_type="ui",
            creator="qa",
            script_code="def test_workbench_edit(page):\n    assert True\n",
        ),
    )
    test_project_service.update_project(
        db_session,
        "mall",
        test_project_schema.TestProjectUpdate(status="inactive"),
    )

    case_file = legacy_workbench.AI_CASES_ROOT / f"{case_id}.yaml"
    case_file.write_text(
        "\n".join(
            [
                f"id: {case_id}",
                "title: 商城 workbench 编辑校验",
                "module: query",
                "priority: P1",
                "execution:",
                "  page: ret",
                "  steps:",
                "    - action: click",
                "      target: query_button",
                "",
            ]
        ),
        encoding="utf-8",
    )

    response = client.put(
        f"/api/workbench/cases/{case_id}",
        json={
            "project": "mall",
            "yaml_content": case_file.read_text(encoding="utf-8"),
        },
    )

    assert response.status_code == 409
    assert "project is inactive" in str(response.json().get("detail", "")).lower()
