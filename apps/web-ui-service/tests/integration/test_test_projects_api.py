from __future__ import annotations

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
from app.routers.test_projects import router as projects_router
import app.schemas.test_case as test_case_schema
from app.services import test_case_service


@pytest.fixture()
def test_projects_client() -> tuple[TestClient, Session]:
    engine = create_engine(
        "sqlite://",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)
    Base.metadata.create_all(bind=engine)
    session = testing_session()

    app = FastAPI()
    app.include_router(projects_router)

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


def test_test_projects_api_supports_update_and_delete(
    test_projects_client: tuple[TestClient, Session],
) -> None:
    client, _db_session = test_projects_client
    create_resp = client.post(
        "/api/test-projects",
        json={
            "project_code": "mall",
            "project_name": "Mall Platform",
            "description": "",
            "created_by": "admin",
        },
    )
    assert create_resp.status_code == 201

    update_resp = client.put(
        "/api/test-projects/mall",
        json={
            "project_name": "Mall Commerce",
            "description": "商城主项目",
            "status": "inactive",
        },
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["item"]["project_name"] == "Mall Commerce"
    assert update_resp.json()["item"]["status"] == "inactive"

    delete_resp = client.delete("/api/test-projects/mall")
    assert delete_resp.status_code == 200
    assert delete_resp.json() == {"deleted": True, "project_code": "mall"}

    list_resp = client.get("/api/test-projects")
    codes = [item["project_code"] for item in list_resp.json()["items"]]
    assert "mall" not in codes
    assert "atp" in codes


def test_test_projects_api_blocks_delete_when_cases_exist(
    test_projects_client: tuple[TestClient, Session],
) -> None:
    client, db_session = test_projects_client
    create_resp = client.post(
        "/api/test-projects",
        json={
            "project_code": "mall",
            "project_name": "Mall Platform",
            "description": "",
            "created_by": "admin",
        },
    )
    assert create_resp.status_code == 201

    test_case_service.create_test_case(
        db_session,
        test_case_schema.TestCaseCreate(
            project_code="mall",
            name="商城项目查询用例",
            product_line="商城",
            module="查询",
            script_code="def test_mall_query(page):\n    assert True\n",
        ),
    )

    delete_resp = client.delete("/api/test-projects/mall")
    assert delete_resp.status_code == 409
    assert "test case" in str(delete_resp.json().get("detail", "")).lower()


def test_test_projects_api_blocks_delete_default_project(
    test_projects_client: tuple[TestClient, Session],
) -> None:
    client, _db_session = test_projects_client
    delete_resp = client.delete("/api/test-projects/atp")
    assert delete_resp.status_code == 400


def test_test_projects_api_allows_delete_for_inactive_project_without_refs(
    test_projects_client: tuple[TestClient, Session],
) -> None:
    client, _db_session = test_projects_client
    create_resp = client.post(
        "/api/test-projects",
        json={
            "project_code": "mall",
            "project_name": "Mall Platform",
            "description": "",
            "created_by": "admin",
        },
    )
    assert create_resp.status_code == 201

    update_resp = client.put(
        "/api/test-projects/mall",
        json={
            "project_name": "Mall Platform",
            "description": "",
            "status": "inactive",
        },
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["item"]["status"] == "inactive"

    delete_resp = client.delete("/api/test-projects/mall")
    assert delete_resp.status_code == 200
    assert delete_resp.json() == {"deleted": True, "project_code": "mall"}


def test_test_projects_api_update_with_empty_payload_is_idempotent(
    test_projects_client: tuple[TestClient, Session],
) -> None:
    client, _db_session = test_projects_client
    create_resp = client.post(
        "/api/test-projects",
        json={
            "project_code": "mall",
            "project_name": "Mall Platform",
            "description": "商城项目",
            "created_by": "admin",
        },
    )
    assert create_resp.status_code == 201

    update_resp = client.put("/api/test-projects/mall", json={})
    assert update_resp.status_code == 200
    item = update_resp.json()["item"]
    assert item["project_code"] == "mall"
    assert item["project_name"] == "Mall Platform"
    assert item["description"] == "商城项目"
    assert item["status"] == "active"


def test_test_projects_api_rejects_invalid_status_value(
    test_projects_client: tuple[TestClient, Session],
) -> None:
    client, _db_session = test_projects_client
    create_resp = client.post(
        "/api/test-projects",
        json={
            "project_code": "mall",
            "project_name": "Mall Platform",
            "description": "",
            "created_by": "admin",
        },
    )
    assert create_resp.status_code == 201

    update_resp = client.put(
        "/api/test-projects/mall",
        json={
            "project_name": "Mall Platform",
            "description": "",
            "status": "paused",
        },
    )
    assert update_resp.status_code == 400
    assert "status must be one of" in str(update_resp.json().get("detail", ""))
