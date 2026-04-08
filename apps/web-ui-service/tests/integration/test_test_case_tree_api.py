from __future__ import annotations

from collections.abc import Iterator

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
import app.models.page_object  # noqa: F401
import app.models.test_case  # noqa: F401
import app.models.test_project  # noqa: F401
import app.models.workbench_state  # noqa: F401
from app.models.page_object import PageObjectRef
from app.models.test_case import TestCase as CaseModel
from app.routers.test_cases import router as cases_router
import app.schemas.page_object as page_object_schema
import app.schemas.test_case as test_case_schema
import app.schemas.test_project as test_project_schema
from app.services import page_object_service, test_case_service, test_project_service


@pytest.fixture()
def test_case_tree_client() -> Iterator[tuple[TestClient, Session]]:
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
    app.include_router(cases_router)

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


def _create_case(
    db_session: Session,
    *,
    project_code: str = "mall",
    product_line: str = "new",
    module: str = "核心流程",
) -> CaseModel:
    return test_case_service.create_test_case(
        db_session,
        test_case_schema.TestCaseCreate(
            project_code=project_code,
            name="商城核心流程可访问",
            product_line=product_line,
            module=module,
            priority="P1",
            test_type="ui",
            creator="qa-team",
            script_code="def test_demo(page):\n    assert True\n",
        ),
    )


def test_tree_api_includes_zero_count_module_node(
    test_case_tree_client: tuple[TestClient, Session],
) -> None:
    client, db_session = test_case_tree_client
    _create_case(db_session)

    create_node_resp = client.post(
        "/api/test-cases/tree/nodes",
        json={
            "project_code": "mall",
            "product_line": "new",
            "module": "结算中心",
        },
    )
    assert create_node_resp.status_code == 201

    tree_resp = client.get("/api/test-cases/tree", params={"project_code": "mall"})
    assert tree_resp.status_code == 200
    items = tree_resp.json()["items"]
    assert len(items) == 1
    assert items[0]["project_code"] == "mall"
    assert items[0]["product_line"] == "new"
    modules = {str(item["module"]): int(item["count"]) for item in items[0]["modules"]}
    assert modules["核心流程"] == 1
    assert modules["结算中心"] == 0


def test_tree_api_supports_update_and_delete_for_empty_node(
    test_case_tree_client: tuple[TestClient, Session],
) -> None:
    client, db_session = test_case_tree_client
    _create_case(db_session)
    create_node_resp = client.post(
        "/api/test-cases/tree/nodes",
        json={
            "project_code": "mall",
            "product_line": "new",
            "module": "回归专区",
        },
    )
    assert create_node_resp.status_code == 201

    update_resp = client.put(
        "/api/test-cases/tree/nodes",
        json={
            "project_code": "mall",
            "product_line": "new",
            "module": "回归专区",
            "new_product_line": "new",
            "new_module": "回归专区-v2",
        },
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["item"]["module"] == "回归专区-v2"
    assert int(update_resp.json()["item"]["updated_cases"]) == 0

    tree_after_update = client.get("/api/test-cases/tree", params={"project_code": "mall"})
    assert tree_after_update.status_code == 200
    updated_modules = {
        str(item["module"])
        for item in tree_after_update.json()["items"][0]["modules"]
    }
    assert "回归专区" not in updated_modules
    assert "回归专区-v2" in updated_modules

    delete_resp = client.request(
        "DELETE",
        "/api/test-cases/tree/nodes",
        json={
            "project_code": "mall",
            "product_line": "new",
            "module": "回归专区-v2",
            "cascade_cases": False,
        },
    )
    assert delete_resp.status_code == 200
    assert int(delete_resp.json()["item"]["deleted_cases"]) == 0

    tree_after_delete = client.get("/api/test-cases/tree", params={"project_code": "mall"})
    assert tree_after_delete.status_code == 200
    final_modules = {str(item["module"]) for item in tree_after_delete.json()["items"][0]["modules"]}
    assert "回归专区-v2" not in final_modules


def test_tree_api_delete_requires_cascade_for_non_empty_node(
    test_case_tree_client: tuple[TestClient, Session],
) -> None:
    client, db_session = test_case_tree_client
    _create_case(db_session)

    delete_without_cascade = client.request(
        "DELETE",
        "/api/test-cases/tree/nodes",
        json={
            "project_code": "mall",
            "product_line": "new",
            "module": "核心流程",
            "cascade_cases": False,
        },
    )
    assert delete_without_cascade.status_code == 409
    assert "cascade_cases=true" in str(delete_without_cascade.json().get("detail", ""))

    delete_with_cascade = client.request(
        "DELETE",
        "/api/test-cases/tree/nodes",
        json={
            "project_code": "mall",
            "product_line": "new",
            "module": "核心流程",
            "cascade_cases": True,
        },
    )
    assert delete_with_cascade.status_code == 200
    assert int(delete_with_cascade.json()["item"]["deleted_cases"]) == 1

    remaining_cases = list(
        db_session.execute(
            select(CaseModel).where(
                CaseModel.project_code == "mall",
                CaseModel.product_line == "new",
                CaseModel.module == "核心流程",
            )
        ).scalars().all()
    )
    assert remaining_cases == []


def test_tree_api_create_node_blocked_when_project_inactive(
    test_case_tree_client: tuple[TestClient, Session],
) -> None:
    client, db_session = test_case_tree_client
    test_project_service.create_project(
        db_session,
        test_project_schema.TestProjectCreate(
            project_code="mall",
            project_name="Mall Platform",
        ),
    )
    test_project_service.update_project(
        db_session,
        "mall",
        test_project_schema.TestProjectUpdate(status="inactive"),
    )

    create_node_resp = client.post(
        "/api/test-cases/tree/nodes",
        json={
            "project_code": "mall",
            "product_line": "new",
            "module": "结算中心",
        },
    )
    assert create_node_resp.status_code == 409
    assert "project is inactive" in str(create_node_resp.json().get("detail", "")).lower()


def test_tree_api_update_node_blocked_when_project_inactive(
    test_case_tree_client: tuple[TestClient, Session],
) -> None:
    client, db_session = test_case_tree_client
    _create_case(db_session)
    test_project_service.update_project(
        db_session,
        "mall",
        test_project_schema.TestProjectUpdate(status="inactive"),
    )

    update_resp = client.put(
        "/api/test-cases/tree/nodes",
        json={
            "project_code": "mall",
            "product_line": "new",
            "module": "核心流程",
            "new_product_line": "new",
            "new_module": "核心流程-v2",
        },
    )
    assert update_resp.status_code == 409
    assert "project is inactive" in str(update_resp.json().get("detail", "")).lower()


def test_cases_list_api_includes_project_status_for_items(
    test_case_tree_client: tuple[TestClient, Session],
) -> None:
    client, db_session = test_case_tree_client
    _create_case(db_session)
    test_project_service.update_project(
        db_session,
        "mall",
        test_project_schema.TestProjectUpdate(status="inactive"),
    )

    list_resp = client.get("/api/test-cases", params={"project_code": "mall"})
    assert list_resp.status_code == 200
    items = list_resp.json()["items"]
    assert len(items) == 1
    assert items[0]["project_code"] == "mall"
    assert items[0]["project_status"] == "inactive"


def test_case_detail_api_includes_project_status_for_basic_payload(
    test_case_tree_client: tuple[TestClient, Session],
) -> None:
    client, db_session = test_case_tree_client
    case = _create_case(db_session)
    test_project_service.update_project(
        db_session,
        "mall",
        test_project_schema.TestProjectUpdate(status="inactive"),
    )

    detail_resp = client.get(f"/api/test-cases/{case.case_id}")
    assert detail_resp.status_code == 200
    payload = detail_resp.json()
    assert payload["basic"]["case_id"] == case.case_id
    assert payload["basic"]["project_code"] == "mall"
    assert payload["basic"]["project_status"] == "inactive"


def test_batch_delete_test_case_also_cleans_page_object_refs(
    test_case_tree_client: tuple[TestClient, Session],
) -> None:
    client, db_session = test_case_tree_client
    case = _create_case(db_session, project_code="mall", product_line="new", module="核心流程")
    case_business_id = str(case.case_id)
    page_object_service.create_page_object(
        db_session,
        page_object_schema.PageObjectCreate(
            project_code="mall",
            client="web",
            page_code="home",
            page_name="首页",
            status="draft",
            created_by="qa-team",
        ),
    )
    page_object_service.create_page_element(
        db_session,
        page_code="home",
        project_code="mall",
        client="web",
        payload=page_object_schema.PageElementCreate(
            element_code="submit-btn",
            element_name="提交按钮",
            locator_type="css",
            locator_value="#submit",
            health_status=1,
            status="active",
            is_primary=True,
            owner="qa-team",
            changed_by="qa-team",
            change_summary="seed",
        ),
    )
    page_object_service.create_page_object_ref(
        db_session,
        page_code="home",
        element_code="submit-btn",
        project_code="mall",
        client="web",
        payload=page_object_schema.PageObjectRefCreate(
            reference_type="test_case",
            reference_key=case_business_id,
            source="manual",
            created_by="qa-team",
        ),
    )
    before_count = int(
        db_session.execute(
            select(func.count()).select_from(PageObjectRef).where(
                PageObjectRef.reference_type == "test_case",
                PageObjectRef.reference_key == case_business_id,
            )
        ).scalar_one()
        or 0
    )
    assert before_count == 1

    delete_resp = client.post("/api/test-cases/batch/delete", json={"ids": [int(case.id)]})
    assert delete_resp.status_code == 200
    assert int(delete_resp.json()["deleted_count"]) == 1

    after_count = int(
        db_session.execute(
            select(func.count()).select_from(PageObjectRef).where(
                PageObjectRef.reference_type == "test_case",
                PageObjectRef.reference_key == case_business_id,
            )
        ).scalar_one()
        or 0
    )
    assert after_count == 0
