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
from app.models.test_case import TestCase as TestCaseModel
from app.models.test_project import TestProject as TestProjectModel
from app.api.workbench import service as workbench_service
from app.routers.workbench_tasks import router as workbench_tasks_router


def _task_item(*, task_id: str, case_id: str, project_code: str, status: str = "passed") -> dict[str, object]:
    return {
        "task_id": task_id,
        "run_id": f"run-{task_id}",
        "case_id": case_id,
        "project": project_code,
        "project_code": project_code,
        "page": "ret",
        "runner": "playwright",
        "status": status,
        "queue_status": "completed",
        "source": "manifest",
        "evidence_health": {"status": "healthy"},
        "evidence_freshness": {"status": "healthy"},
        "manifest_action": "ok",
        "strict_mode": {"status": "ready", "reason": "ok"},
        "retry": {"enabled": False},
        "dependency": {"has_dependencies": False},
        "multisource_summary": {"changed_areas": [], "source_types": []},
        "has_manifest": True,
    }


@pytest.fixture()
def workbench_tasks_client(monkeypatch: pytest.MonkeyPatch) -> tuple[TestClient, Session]:
    engine = create_engine(
        "sqlite://",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)
    Base.metadata.create_all(bind=engine)
    session = testing_session()

    atp_case_id = "atp-web-ret-query-fn-ai-0001"
    mall_case_id = "mall-web-ret-query-fn-ai-0001"
    session.add(
        TestProjectModel(
            project_code="mall",
            project_name="Mall Platform",
            description="",
            status="inactive",
            created_by="admin",
        )
    )
    session.add(
        TestCaseModel(
            case_id=atp_case_id,
            name="ATP 查询校验",
            product_line="退货",
            module="查询",
            project_code="atp",
        )
    )
    session.add(
        TestCaseModel(
            case_id=mall_case_id,
            name="Mall 查询校验",
            product_line="退货",
            module="查询",
            project_code="mall",
        )
    )
    session.commit()

    rows = [
        {"task": _task_item(task_id="task-atp", case_id=atp_case_id, project_code="atp")},
        {"task": _task_item(task_id="task-mall", case_id=mall_case_id, project_code="mall", status="failed")},
    ]

    monkeypatch.setattr(workbench_service, "_collect_execution_records_with_meta", lambda limit=0: (rows, {}))
    monkeypatch.setattr(workbench_service, "_build_execution_task_view", lambda row: dict(row["task"]))
    monkeypatch.setattr(
        workbench_service,
        "_build_execution_task_summary",
        lambda *, items, filter_snapshot, execution_meta: {
            "total_tasks": len(items),
            "queue_status_counts": {},
            "strict_mode_ready_task_count": 0,
            "governance_risk_priority": "none",
            "filter_snapshot": filter_snapshot,
        },
    )

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


def test_workbench_tasks_api_supports_project_filter_and_status(
    workbench_tasks_client: tuple[TestClient, Session],
) -> None:
    client, _session = workbench_tasks_client

    response = client.get("/api/workbench/tasks?project_code=mall")

    assert response.status_code == 200
    payload = response.json()
    items = payload.get("items", [])
    assert len(items) == 1
    assert items[0]["project_code"] == "mall"
    assert items[0]["project_status"] == "inactive"
    assert items[0]["case_id"] == "mall-web-ret-query-fn-ai-0001"


def test_workbench_task_detail_includes_project_status(
    workbench_tasks_client: tuple[TestClient, Session],
) -> None:
    client, _session = workbench_tasks_client

    response = client.get("/api/workbench/tasks/task-mall")

    assert response.status_code == 200
    payload = response.json()
    assert payload["item"]["project_code"] == "mall"
    assert payload["item"]["project_status"] == "inactive"
