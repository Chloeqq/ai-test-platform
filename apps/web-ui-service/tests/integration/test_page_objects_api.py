from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
import app.models.page_object  # noqa: F401
from app.models.page_object import PageObjectRecorderSession
import app.models.test_case  # noqa: F401
import app.models.test_project as test_project_model
import app.models.test_project  # noqa: F401
import app.models.workbench_state  # noqa: F401
from app.routers.page_objects import router as page_objects_router
from app.services import page_object_service


@pytest.fixture()
def page_objects_client() -> Iterator[tuple[TestClient, Session]]:
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
    app.include_router(page_objects_router)

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


def test_page_object_crud_element_version_and_refs(
    page_objects_client: tuple[TestClient, Session],
) -> None:
    client, _db_session = page_objects_client

    create_page_resp = client.post(
        "/api/page-objects",
        json={
            "project_code": "atp",
            "client": "web",
            "page_code": "ret-query",
            "page_name": "退货查询页",
            "page_url": "/ret/query",
            "precondition_state": "已完成登录并进入退货中心",
            "module_id": 11,
            "health_status": 1,
            "description": "页面对象初始化",
            "status": "draft",
            "created_by": "qa-admin",
        },
    )
    assert create_page_resp.status_code == 201
    page_item = create_page_resp.json()["item"]
    assert page_item["project_code"] == "atp"
    assert page_item["client"] == "web"
    assert page_item["page_code"] == "ret-query"
    assert page_item["page_url"] == "/ret/query"
    assert page_item["precondition_state"] == "已完成登录并进入退货中心"
    assert int(page_item["module_id"]) == 11
    assert int(page_item["health_status"]) == 1
    assert int(page_item["element_count"]) == 0

    list_page_resp = client.get("/api/page-objects", params={"project_code": "atp", "client": "web"})
    assert list_page_resp.status_code == 200
    assert len(list_page_resp.json()["items"]) == 1

    update_page_resp = client.put(
        "/api/page-objects/ret-query",
        params={"project_code": "atp", "client": "web"},
        json={
            "page_name": "退货查询页V2",
            "status": "published",
            "page_url": "/ret/query/v2",
            "precondition_state": "需先进入售后工作台",
            "module_id": 12,
        },
    )
    assert update_page_resp.status_code == 200
    assert update_page_resp.json()["item"]["page_name"] == "退货查询页V2"
    assert update_page_resp.json()["item"]["status"] == "published"
    assert update_page_resp.json()["item"]["page_url"] == "/ret/query/v2"
    assert update_page_resp.json()["item"]["precondition_state"] == "需先进入售后工作台"
    assert int(update_page_resp.json()["item"]["module_id"]) == 12

    create_element_resp = client.post(
        "/api/page-objects/ret-query/elements",
        params={"project_code": "atp", "client": "web"},
        json={
            "element_code": "submit-btn",
            "element_name": "提交按钮",
            "locator_type": "css",
            "locator_value": "#submit",
            "backup_locator": "[data-testid='submit']",
            "health_status": 1,
            "role": "button",
            "status": "active",
            "is_primary": True,
            "owner": "qa-team",
            "changed_by": "qa-admin",
            "change_summary": "首次录制",
        },
    )
    assert create_element_resp.status_code == 201
    element_item = create_element_resp.json()["item"]
    assert element_item["element_code"] == "submit-btn"
    assert element_item["backup_locator"] == "[data-testid='submit']"
    assert int(element_item["health_status"]) == 1
    assert int(element_item["version"]) == 1
    assert int(element_item["latest_version_no"]) == 1

    update_element_resp = client.put(
        "/api/page-objects/ret-query/elements/submit-btn",
        params={"project_code": "atp", "client": "web"},
        json={
            "locator_type": "css",
            "locator_value": "#submit-primary",
            "backup_locator": "[data-testid='submit-primary']",
            "health_status": 0,
            "changed_by": "qa-admin",
            "change_summary": "页面升级后定位调整",
        },
    )
    assert update_element_resp.status_code == 200
    assert update_element_resp.json()["item"]["locator_value"] == "#submit-primary"
    assert update_element_resp.json()["item"]["backup_locator"] == "[data-testid='submit-primary']"
    assert int(update_element_resp.json()["item"]["health_status"]) == 0
    assert int(update_element_resp.json()["item"]["version"]) == 2
    assert int(update_element_resp.json()["item"]["latest_version_no"]) == 2

    get_page_resp = client.get(
        "/api/page-objects/ret-query",
        params={"project_code": "atp", "client": "web"},
    )
    assert get_page_resp.status_code == 200
    assert int(get_page_resp.json()["item"]["element_count"]) == 1
    assert int(get_page_resp.json()["item"]["health_status"]) == 0

    snapshot_resp = client.post(
        "/api/page-objects/ret-query/elements/submit-btn/versions",
        params={"project_code": "atp", "client": "web"},
        json={"changed_by": "qa-admin", "change_summary": "发布前手工快照"},
    )
    assert snapshot_resp.status_code == 201
    assert int(snapshot_resp.json()["item"]["version_no"]) == 3

    list_versions_resp = client.get(
        "/api/page-objects/ret-query/elements/submit-btn/versions",
        params={"project_code": "atp", "client": "web"},
    )
    assert list_versions_resp.status_code == 200
    versions = list_versions_resp.json()["items"]
    assert [int(item["version_no"]) for item in versions] == [3, 2, 1]

    create_ref_resp = client.post(
        "/api/page-objects/ret-query/elements/submit-btn/refs",
        params={"project_code": "atp", "client": "web"},
        json={
            "reference_type": "test_case",
            "reference_key": "atp-web-ret-query-sm-ai-0001",
            "source": "ai",
            "created_by": "qa-admin",
        },
    )
    assert create_ref_resp.status_code == 201
    assert create_ref_resp.json()["item"]["reference_key"] == "atp-web-ret-query-sm-ai-0001"

    list_refs_resp = client.get(
        "/api/page-objects/ret-query/elements/submit-btn/refs",
        params={"project_code": "atp", "client": "web"},
    )
    assert list_refs_resp.status_code == 200
    refs = list_refs_resp.json()["items"]
    assert len(refs) == 1
    assert refs[0]["reference_type"] == "test_case"

    delete_element_resp = client.delete(
        "/api/page-objects/ret-query/elements/submit-btn",
        params={"project_code": "atp", "client": "web"},
    )
    assert delete_element_resp.status_code == 200
    assert delete_element_resp.json()["item"]["deleted"] is True

    delete_page_resp = client.delete(
        "/api/page-objects/ret-query",
        params={"project_code": "atp", "client": "web", "cascade_elements": False},
    )
    assert delete_page_resp.status_code == 200
    assert delete_page_resp.json()["item"]["page_code"] == "ret-query"


def test_page_object_delete_requires_cascade_when_has_elements(
    page_objects_client: tuple[TestClient, Session],
) -> None:
    client, _db_session = page_objects_client
    create_page_resp = client.post(
        "/api/page-objects",
        json={
            "project_code": "atp",
            "client": "web",
            "page_code": "ret-list",
            "page_name": "退货列表页",
            "description": "",
            "status": "draft",
            "created_by": "qa-admin",
        },
    )
    assert create_page_resp.status_code == 201

    create_element_resp = client.post(
        "/api/page-objects/ret-list/elements",
        params={"project_code": "atp", "client": "web"},
        json={
            "element_code": "search-input",
            "element_name": "搜索框",
            "locator_type": "css",
            "locator_value": "#search",
            "backup_locator": "",
            "health_status": 1,
            "role": "textbox",
            "status": "active",
            "is_primary": True,
            "owner": "qa-team",
            "changed_by": "qa-admin",
            "change_summary": "首次录制",
        },
    )
    assert create_element_resp.status_code == 201

    delete_without_cascade_resp = client.delete(
        "/api/page-objects/ret-list",
        params={"project_code": "atp", "client": "web", "cascade_elements": False},
    )
    assert delete_without_cascade_resp.status_code == 409
    assert "cascade_elements=true" in str(delete_without_cascade_resp.json().get("detail", ""))

    delete_with_cascade_resp = client.delete(
        "/api/page-objects/ret-list",
        params={"project_code": "atp", "client": "web", "cascade_elements": True},
    )
    assert delete_with_cascade_resp.status_code == 200
    assert int(delete_with_cascade_resp.json()["item"]["deleted_element_count"]) == 1

    get_after_delete_resp = client.get(
        "/api/page-objects/ret-list",
        params={"project_code": "atp", "client": "web"},
    )
    assert get_after_delete_resp.status_code == 404


def test_page_object_create_blocked_when_project_inactive(
    page_objects_client: tuple[TestClient, Session],
) -> None:
    client, db_session = page_objects_client
    db_session.add(
        test_project_model.TestProject(
            project_code="mall",
            project_name="Mall",
            description="",
            status="inactive",
            created_by="qa-admin",
        )
    )
    db_session.commit()

    create_page_resp = client.post(
        "/api/page-objects",
        json={
            "project_code": "mall",
            "client": "web",
            "page_code": "mall-list",
            "page_name": "商城列表页",
            "description": "",
            "status": "draft",
            "created_by": "qa-admin",
        },
    )
    assert create_page_resp.status_code == 409
    assert "project is inactive" in str(create_page_resp.json().get("detail", "")).lower()


def test_delete_page_object_cleans_recorder_sessions_and_artifacts(
    page_objects_client: tuple[TestClient, Session],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client, db_session = page_objects_client
    monkeypatch.setattr(page_object_service, "_RECORDER_ROOT", tmp_path.resolve())

    create_page_resp = client.post(
        "/api/page-objects",
        json={
            "project_code": "atp",
            "client": "web",
            "page_code": "cleanup-page",
            "page_name": "清理页",
            "description": "",
            "status": "draft",
            "created_by": "qa-admin",
        },
    )
    assert create_page_resp.status_code == 201

    script_path = tmp_path / "cleanup-session.codegen.py"
    script_path.write_text('page.get_by_text("demo").click()', encoding="utf-8")
    steps_path = script_path.with_suffix(".steps.json")
    steps_path.write_text("[]", encoding="utf-8")
    db_session.add(
        PageObjectRecorderSession(
            session_id="cleanup-session-1",
            project_code="atp",
            client="web",
            page_code="cleanup-page",
            page_name="清理页",
            url="http://127.0.0.1:8013/demo",
            status="stopped",
            process_pid=None,
            script_path=str(script_path.resolve()),
            started_by="qa-admin",
        )
    )
    db_session.commit()

    delete_page_resp = client.delete(
        "/api/page-objects/cleanup-page",
        params={"project_code": "atp", "client": "web", "cascade_elements": False},
    )
    assert delete_page_resp.status_code == 200
    item = delete_page_resp.json()["item"]
    assert int(item["recorder_sessions_removed_count"]) == 1
    assert int(item["recorder_artifacts_removed_count"]) == 2
    assert not script_path.exists()
    assert not steps_path.exists()
    remaining = db_session.query(PageObjectRecorderSession).filter_by(session_id="cleanup-session-1").one_or_none()
    assert remaining is None


def test_delete_last_element_cleans_recorder_sessions_and_artifacts(
    page_objects_client: tuple[TestClient, Session],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client, db_session = page_objects_client
    monkeypatch.setattr(page_object_service, "_RECORDER_ROOT", tmp_path.resolve())

    create_page_resp = client.post(
        "/api/page-objects",
        json={
            "project_code": "atp",
            "client": "web",
            "page_code": "cleanup-elements-page",
            "page_name": "元素清理页",
            "description": "",
            "status": "draft",
            "created_by": "qa-admin",
        },
    )
    assert create_page_resp.status_code == 201

    create_element_resp = client.post(
        "/api/page-objects/cleanup-elements-page/elements",
        params={"project_code": "atp", "client": "web"},
        json={
            "element_code": "only-one",
            "element_name": "唯一元素",
            "locator_type": "css",
            "locator_value": "#only-one",
            "backup_locator": "",
            "health_status": 1,
            "role": "button",
            "status": "active",
            "is_primary": True,
            "owner": "qa-team",
            "changed_by": "qa-admin",
            "change_summary": "首次录制",
        },
    )
    assert create_element_resp.status_code == 201

    script_path = tmp_path / "cleanup-session-2.codegen.py"
    script_path.write_text('page.get_by_text("demo").click()', encoding="utf-8")
    steps_path = script_path.with_suffix(".steps.json")
    steps_path.write_text("[]", encoding="utf-8")
    db_session.add(
        PageObjectRecorderSession(
            session_id="cleanup-session-2",
            project_code="atp",
            client="web",
            page_code="cleanup-elements-page",
            page_name="元素清理页",
            url="http://127.0.0.1:8013/demo",
            status="failed",
            process_pid=None,
            script_path=str(script_path.resolve()),
            started_by="qa-admin",
        )
    )
    db_session.commit()

    delete_element_resp = client.delete(
        "/api/page-objects/cleanup-elements-page/elements/only-one",
        params={"project_code": "atp", "client": "web"},
    )
    assert delete_element_resp.status_code == 200
    item = delete_element_resp.json()["item"]
    assert item["deleted"] is True
    assert int(item["recorder_sessions_removed_count"]) == 1
    assert int(item["recorder_artifacts_removed_count"]) == 2
    assert not script_path.exists()
    assert not steps_path.exists()
    remaining = db_session.query(PageObjectRecorderSession).filter_by(session_id="cleanup-session-2").one_or_none()
    assert remaining is None
