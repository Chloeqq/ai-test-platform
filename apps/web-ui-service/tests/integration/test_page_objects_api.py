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
from app.models.page_object import (
    PageElement,
    PageElementHealthCheck,
    PageElementLocator,
    PageElementVersion,
    PageObject,
    PageObjectCandidateElement,
    PageObjectCandidateGroup,
    PageObjectGovernanceLog,
    PageObjectRecorderSession,
    PageObjectRef,
)
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
    session.add(
        test_project_model.TestProject(
            project_code="atp",
            project_name="ATP",
            description="integration test project",
            created_by="pytest",
            status="active",
        )
    )
    session.commit()

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


def test_page_object_data_testid_import_preview_and_apply(
    page_objects_client: tuple[TestClient, Session],
) -> None:
    client, db_session = page_objects_client
    page_object = PageObject(
        project_code="atp",
        client="web",
        page_code="login",
        page_name="登录页",
        page_url="http://localhost:5174/#/login",
        route_pattern="/login",
        governance_status="active",
        status="published",
        created_by="pytest",
    )
    db_session.add(page_object)
    db_session.flush()
    legacy_element = PageElement(
        page_object_id=page_object.id,
        element_code="login-submit-btn",
        element_name="登录按钮",
        locator_type="css",
        locator_value=".login-button",
        business_type="button",
        locator_source="css",
        match_strategy="exact",
        stability_level="low",
        review_status="pending",
        status="active",
    )
    db_session.add(legacy_element)
    db_session.commit()

    markdown = """# data-testid

## 1. 命名规范

- `product-search-submit-btn`

## 3. 已落地清单（首批高频核心页面）

### 登录与布局

- `src/views/normal/login/index.vue`
  - `login-page`、`login-form`
  - `login-username-input`、`login-password-input`
  - `login-submit-btn`、`login-trial-account-btn`

### 商品列表 `src/views/pms/product/index.vue`

- 行级：`product-row-${id}-edit-btn`

## 4. 待落地清单
""".encode("utf-8")
    preview_resp = client.post(
        "/api/page-objects/imports/preview",
        data={"project_code": "atp", "client": "web", "source_type": "data_testid_guidelines"},
        files={"data_testid_guidelines": ("data-testid-guidelines.md", markdown, "text/markdown")},
    )
    assert preview_resp.status_code == 200
    preview_item = preview_resp.json()["item"]
    assert preview_item["summary"]["element_count"] == 7
    assert preview_item["summary"]["upgrade_count"] == 1
    assert preview_item["summary"]["template_count"] == 1
    assert not any(row["testid"] == "product-search-submit-btn" for row in preview_item["elements"])
    dynamic_row = next(row for row in preview_item["elements"] if row["testid"] == "product-row-${id}-edit-btn")
    assert dynamic_row["match_strategy"] == "template"

    apply_resp = client.post(f"/api/page-objects/imports/{preview_item['import_id']}/apply", params={"operator": "qa-admin"})
    assert apply_resp.status_code == 200
    apply_item = apply_resp.json()["item"]["apply_result"]
    assert apply_item["created_element_count"] == 6
    assert apply_item["upgraded_element_count"] == 1

    db_session.expire_all()
    login_page = db_session.query(PageObject).filter_by(project_code="atp", client="web", page_code="login").one()
    assert login_page.page_url == "http://localhost:5174/#/login"
    upgraded = db_session.query(PageElement).filter_by(page_object_id=login_page.id, element_code="login-submit-btn").one()
    assert upgraded.locator_type == "data-testid"
    assert upgraded.locator_value == "login-submit-btn"
    assert upgraded.testid_value == "login-submit-btn"
    assert upgraded.locator_source == "testid"
    assert upgraded.stability_level == "high"
    assert upgraded.review_status == "approved"
    assert db_session.query(PageElementVersion).filter_by(page_element_id=upgraded.id).count() >= 1
    assert db_session.query(PageObjectGovernanceLog).filter_by(entity_key="login-submit-btn", action="import_upgrade").count() == 1

    product_page = db_session.query(PageObject).filter_by(project_code="atp", client="web", page_code="product").one()
    template = db_session.query(PageElement).filter_by(page_object_id=product_page.id, element_code="product-row-id-edit-btn").one()
    assert template.match_strategy == "template"
    assert template.testid_value == "product-row-${id}-edit-btn"
    assert "dynamic-row-template" in template.semantic_tags_json


def test_page_object_data_testid_import_rejects_empty_file(
    page_objects_client: tuple[TestClient, Session],
) -> None:
    client, _db_session = page_objects_client

    preview_resp = client.post(
        "/api/page-objects/imports/preview",
        data={"project_code": "atp", "client": "web", "source_type": "data_testid_guidelines"},
        files={"data_testid_guidelines": ("data-testid-guidelines.md", b"", "text/markdown")},
    )

    assert preview_resp.status_code == 400
    assert "上传文件为空" in preview_resp.json()["detail"]


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
            "element_code": "submit_button",
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
    assert element_item["element_code"] == "submit_button"
    assert element_item["backup_locator"] == "[data-testid='submit']"
    assert int(element_item["health_status"]) == 1
    assert int(element_item["version"]) == 1
    assert int(element_item["latest_version_no"]) == 1

    update_element_resp = client.put(
        "/api/page-objects/ret-query/elements/submit_button",
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
        "/api/page-objects/ret-query/elements/submit_button/versions",
        params={"project_code": "atp", "client": "web"},
        json={"changed_by": "qa-admin", "change_summary": "发布前手工快照"},
    )
    assert snapshot_resp.status_code == 201
    assert int(snapshot_resp.json()["item"]["version_no"]) == 3

    list_versions_resp = client.get(
        "/api/page-objects/ret-query/elements/submit_button/versions",
        params={"project_code": "atp", "client": "web"},
    )
    assert list_versions_resp.status_code == 200
    versions = list_versions_resp.json()["items"]
    assert [int(item["version_no"]) for item in versions] == [3, 2, 1]

    create_ref_resp = client.post(
        "/api/page-objects/ret-query/elements/submit_button/refs",
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
        "/api/page-objects/ret-query/elements/submit_button/refs",
        params={"project_code": "atp", "client": "web"},
    )
    assert list_refs_resp.status_code == 200
    refs = list_refs_resp.json()["items"]
    assert len(refs) == 1
    assert refs[0]["reference_type"] == "test_case"

    delete_element_resp = client.delete(
        "/api/page-objects/ret-query/elements/submit_button",
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
            "element_code": "search_input",
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


def test_formal_element_code_policy_blocks_dirty_names(
    page_objects_client: tuple[TestClient, Session],
) -> None:
    client, _db_session = page_objects_client
    create_page_resp = client.post(
        "/api/page-objects",
        json={
            "project_code": "atp",
            "client": "web",
            "page_code": "login",
            "page_name": "登录页",
            "description": "",
            "status": "draft",
            "created_by": "qa-admin",
        },
    )
    assert create_page_resp.status_code == 201

    dirty_resp = client.post(
        "/api/page-objects/login/elements",
        params={"project_code": "atp", "client": "web"},
        json={
            "element_code": "page_login_username_input",
            "element_name": "账号输入框",
            "locator_type": "placeholder",
            "locator_value": "请输入账号",
            "business_type": "input",
            "changed_by": "qa-admin",
        },
    )
    assert dirty_resp.status_code == 400
    assert "invalid_element_code" in str(dirty_resp.json()["detail"])
    assert "username_input" in str(dirty_resp.json()["detail"])

    clean_resp = client.post(
        "/api/page-objects/login/elements",
        params={"project_code": "atp", "client": "web"},
        json={
            "element_code": "username_input",
            "element_name": "账号输入框",
            "locator_type": "placeholder",
            "locator_value": "请输入账号",
            "business_type": "input",
            "changed_by": "qa-admin",
        },
    )
    assert clean_resp.status_code == 201
    assert clean_resp.json()["item"]["element_code"] == "username_input"


def test_dirty_legacy_element_can_be_renamed_and_approved_without_losing_refs(
    page_objects_client: tuple[TestClient, Session],
) -> None:
    client, db_session = page_objects_client
    create_page_resp = client.post(
        "/api/page-objects",
        json={
            "project_code": "atp",
            "client": "web",
            "page_code": "legacy-login",
            "page_name": "历史登录页",
            "description": "",
            "status": "draft",
            "created_by": "qa-admin",
        },
    )
    assert create_page_resp.status_code == 201
    page_object = db_session.query(PageObject).filter_by(
        project_code="atp",
        client="web",
        page_code="legacy-login",
    ).one()
    dirty_element = PageElement(
        page_object_id=page_object.id,
        element_code="legacy-css-i-path-3",
        element_name="历史脏元素",
        locator_type="css",
        locator_value=".login i:nth-child(3)",
        business_type="",
        business_domain="",
        locator_source="css",
        match_strategy="exact",
        stability_level="low",
        review_status="pending",
        status="active",
        is_primary=True,
        owner="legacy",
    )
    db_session.add(dirty_element)
    db_session.flush()
    dirty_element_id = int(dirty_element.id)
    db_session.add(
        PageObjectRef(
            page_element_id=dirty_element_id,
            reference_type="test_case",
            reference_key="legacy-case-001",
            source="legacy",
            created_by="qa-admin",
        )
    )
    db_session.commit()

    repair_resp = client.put(
        "/api/page-objects/legacy-login/elements/legacy-css-i-path-3",
        params={"project_code": "atp", "client": "web"},
        json={
            "element_code": "password_toggle",
            "element_name": "密码显隐切换",
            "business_type": "password_toggle",
            "business_domain": "auth",
            "locator_type": "role",
            "locator_value": "密码显隐切换",
            "role": "button",
            "locator_source": "role_name",
            "stability_level": "medium",
            "review_status": "approved",
            "changed_by": "qa-admin",
            "change_summary": "人工修复历史脏编码",
        },
    )
    assert repair_resp.status_code == 200
    item = repair_resp.json()["item"]
    assert item["element_code"] == "password_toggle"
    assert item["business_type"] == "password_toggle"
    assert item["review_status"] == "approved"

    assert db_session.query(PageObjectRef).filter_by(page_element_id=dirty_element_id).count() == 1
    list_refs_resp = client.get(
        "/api/page-objects/legacy-login/elements/password_toggle/refs",
        params={"project_code": "atp", "client": "web"},
    )
    assert list_refs_resp.status_code == 200
    assert list_refs_resp.json()["items"][0]["reference_key"] == "legacy-case-001"

    governance_log = db_session.query(PageObjectGovernanceLog).filter_by(
        page_code="legacy-login",
        entity_type="page_element",
        entity_key="password_toggle",
        action="edit",
    ).one_or_none()
    assert governance_log is not None
    assert governance_log.before_payload["element_code"] == "legacy-css-i-path-3"
    assert governance_log.after_payload["element_code"] == "password_toggle"


def test_approved_mappable_element_requires_governed_locator_contract(
    page_objects_client: tuple[TestClient, Session],
) -> None:
    client, _db_session = page_objects_client
    create_page_resp = client.post(
        "/api/page-objects",
        json={
            "project_code": "atp",
            "client": "web",
            "page_code": "contract-login",
            "page_name": "契约登录页",
            "description": "",
            "status": "draft",
            "created_by": "qa-admin",
        },
    )
    assert create_page_resp.status_code == 201
    create_element_resp = client.post(
        "/api/page-objects/contract-login/elements",
        params={"project_code": "atp", "client": "web"},
        json={
            "element_code": "legacy_button",
            "element_name": "历史按钮",
            "locator_type": "css",
            "locator_value": ".legacy-btn",
            "business_type": "button",
            "locator_source": "css",
            "changed_by": "qa-admin",
        },
    )
    assert create_element_resp.status_code == 201

    invalid_resp = client.put(
        "/api/page-objects/contract-login/elements/legacy_button",
        params={"project_code": "atp", "client": "web"},
        json={
            "review_status": "approved",
            "stability_level": "high",
            "changed_by": "qa-admin",
        },
    )
    assert invalid_resp.status_code == 400
    assert "approved high stability element requires locator_source testid or qa" in str(invalid_resp.json()["detail"])

    create_role_element_resp = client.post(
        "/api/page-objects/contract-login/elements",
        params={"project_code": "atp", "client": "web"},
        json={
            "element_code": "submit_button",
            "element_name": "提交按钮",
            "locator_type": "role",
            "locator_value": "提交",
            "role": "button",
            "business_type": "button",
            "locator_source": "role_name",
            "changed_by": "qa-admin",
        },
    )
    assert create_role_element_resp.status_code == 201
    key_without_contract_resp = client.put(
        "/api/page-objects/contract-login/elements/submit_button",
        params={"project_code": "atp", "client": "web"},
        json={
            "is_key_element": True,
            "review_status": "approved",
            "stability_level": "medium",
            "changed_by": "qa-admin",
        },
    )
    assert key_without_contract_resp.status_code == 400
    assert "approved key element requires testid_value or qa_value" in str(key_without_contract_resp.json()["detail"])


def test_candidate_group_list_does_not_apply_mall_terms_to_other_projects(
    page_objects_client: tuple[TestClient, Session],
) -> None:
    client, db_session = page_objects_client
    create_page_resp = client.post(
        "/api/page-objects",
        json={
            "project_code": "atp",
            "client": "web",
            "page_code": "product",
            "page_name": "商品页",
            "description": "",
            "status": "draft",
            "created_by": "qa-admin",
        },
    )
    assert create_page_resp.status_code == 201
    db_session.add(
        PageObjectCandidateGroup(
            project_code="atp",
            client="web",
            page_code="product",
            group_key="role:product-sn",
            proposed_element_code="",
            proposed_element_name="商品货号：输入框",
            business_type_guess="input",
            quality_tier="A",
            max_score=92,
            avg_score=92,
            candidate_count=1,
            session_count=1,
            recommended_action="ingest",
            promotion_status="pending",
            top_locator_type="role",
            top_locator_value="商品货号：",
            latest_session_id="session-product-1",
        )
    )
    db_session.commit()

    groups_resp = client.get(
        "/api/page-objects/product/candidate-groups",
        params={"project_code": "atp", "client": "web"},
    )
    assert groups_resp.status_code == 200
    assert groups_resp.json()["items"][0]["proposed_element_code"] != "product_sn_input"


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


def test_page_object_governance_fields_and_summary(
    page_objects_client: tuple[TestClient, Session],
) -> None:
    client, db_session = page_objects_client

    create_page_resp = client.post(
        "/api/page-objects",
        json={
            "project_code": "atp",
            "client": "web",
            "page_code": "governance-login",
            "page_name": "治理登录页",
            "page_url": "/login",
            "route_pattern": "/login",
            "anchor_config_json": {"page_title": "登录"},
            "governance_status": "governing",
            "testability_score": 72,
            "description": "",
            "status": "draft",
            "created_by": "qa-admin",
        },
    )
    assert create_page_resp.status_code == 201
    page_item = create_page_resp.json()["item"]
    assert page_item["route_pattern"] == "/login"
    assert page_item["anchor_config_json"] == {"page_title": "登录"}
    assert page_item["governance_status"] == "governing"
    assert int(page_item["testability_score"]) == 72

    create_element_resp = client.post(
        "/api/page-objects/governance-login/elements",
        params={"project_code": "atp", "client": "web"},
        json={
            "element_code": "username_input",
            "element_name": "用户名输入框",
            "locator_type": "data-testid",
            "locator_value": "username_input",
            "backup_locator": "",
            "business_type": "input",
            "business_domain": "auth",
            "aliases_json": ["账号输入框"],
            "semantic_tags_json": ["credential"],
            "locator_source": "testid",
            "match_strategy": "exact",
            "stability_level": "high",
            "review_status": "approved",
            "route_scope": "/login",
            "anchor_required": False,
            "is_key_element": True,
            "testid_value": "username_input",
            "qa_value": "",
            "governance_note": "关键登录元素",
            "health_status": 1,
            "role": "textbox",
            "status": "active",
            "is_primary": True,
            "owner": "qa-team",
            "changed_by": "qa-admin",
            "change_summary": "治理审核后创建",
        },
    )
    assert create_element_resp.status_code == 201
    element_item = create_element_resp.json()["item"]
    assert element_item["business_type"] == "input"
    assert element_item["business_domain"] == "auth"
    assert element_item["aliases_json"] == ["账号输入框"]
    assert element_item["semantic_tags_json"] == ["credential"]
    assert element_item["locator_source"] == "testid"
    assert element_item["stability_level"] == "low"
    assert element_item["review_status"] == "pending"
    assert element_item["is_key_element"] is True
    assert element_item["testid_value"] == "username_input"

    update_element_resp = client.put(
        "/api/page-objects/governance-login/elements/username_input",
        params={"project_code": "atp", "client": "web"},
        json={
            "stability_level": "high",
            "review_status": "approved",
            "changed_by": "qa-admin",
            "change_summary": "人工审核通过",
        },
    )
    assert update_element_resp.status_code == 200
    assert update_element_resp.json()["item"]["stability_level"] == "high"
    assert update_element_resp.json()["item"]["review_status"] == "approved"

    governance_log = db_session.query(PageObjectGovernanceLog).filter_by(
        page_code="governance-login",
        entity_type="page_element",
        entity_key="username_input",
        action="edit",
    ).one_or_none()
    assert governance_log is not None
    assert governance_log.before_payload["review_status"] == "pending"
    assert governance_log.after_payload["review_status"] == "approved"

    db_session.add(
        PageObjectCandidateGroup(
            project_code="atp",
            client="web",
            page_code="governance-login",
            group_key="role:textbox:password",
            proposed_element_code="password_input",
            proposed_element_name="密码输入框",
            business_type_guess="input",
            quality_tier="A",
            candidate_count=2,
            session_count=1,
            promotion_status="pending",
            latest_session_id="session-governance-1",
        )
    )
    db_session.commit()

    summary_resp = client.get(
        "/api/page-objects/governance-login/governance/summary",
        params={"project_code": "atp", "client": "web"},
    )
    assert summary_resp.status_code == 200
    summary = summary_resp.json()["item"]
    assert int(summary["formal_element_count"]) == 1
    assert int(summary["approved_element_count"]) == 1
    assert int(summary["key_element_count"]) == 1
    assert int(summary["pending_candidate_group_count"]) == 1
    assert float(summary["key_element_coverage"]) == 1.0
    assert int(summary["testability_score"]) == 72
    assert summary["governance_status"] == "governing"


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
            "element_code": "only_one",
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
        "/api/page-objects/cleanup-elements-page/elements/only_one",
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


def test_list_page_elements_dedupes_same_locator_identity(
    page_objects_client: tuple[TestClient, Session],
) -> None:
    client, _db_session = page_objects_client

    create_page_resp = client.post(
        "/api/page-objects",
        json={
            "project_code": "atp",
            "client": "web",
            "page_code": "login",
            "page_name": "登录页",
            "description": "",
            "status": "draft",
            "created_by": "qa-admin",
        },
    )
    assert create_page_resp.status_code == 201

    create_first_element_resp = client.post(
        "/api/page-objects/login/elements",
        params={"project_code": "atp", "client": "web"},
        json={
            "element_code": "primary_login_button",
            "element_name": "录制元素3",
            "locator_type": "role",
            "locator_value": "登录",
            "backup_locator": "",
            "health_status": 1,
            "role": "",
            "status": "active",
            "is_primary": True,
            "owner": "qa-team",
            "changed_by": "qa-admin",
            "change_summary": "首次录制",
        },
    )
    assert create_first_element_resp.status_code == 201

    create_second_element_resp = client.post(
        "/api/page-objects/login/elements",
        params={"project_code": "atp", "client": "web"},
        json={
            "element_code": "secondary_login_button",
            "element_name": "录制元素4",
            "locator_type": "role",
            "locator_value": "登录",
            "backup_locator": "",
            "health_status": 1,
            "role": "button",
            "status": "active",
            "is_primary": True,
            "owner": "qa-team",
            "changed_by": "qa-admin",
            "change_summary": "二次录制",
        },
    )
    assert create_second_element_resp.status_code == 201

    list_resp = client.get(
        "/api/page-objects/login/elements",
        params={"project_code": "atp", "client": "web"},
    )
    assert list_resp.status_code == 200
    assert len(list_resp.json()["items"]) == 2

    list_resp = client.get(
        "/api/page-objects/login/elements",
        params={"project_code": "atp", "client": "web", "purge_duplicates": True},
    )
    assert list_resp.status_code == 200
    items = list_resp.json()["items"]
    assert len(items) == 1
    assert items[0]["locator_type"] == "role"
    assert items[0]["locator_value"] == "登录"
    assert items[0]["role"] == "button"

    old_element_resp = client.get(
        "/api/page-objects/login/elements/primary_login_button",
        params={"project_code": "atp", "client": "web"},
    )
    assert old_element_resp.status_code == 404


def test_batch_delete_page_elements_physically_removes_dependencies(
    page_objects_client: tuple[TestClient, Session],
) -> None:
    client, db_session = page_objects_client

    create_page_resp = client.post(
        "/api/page-objects",
        json={
            "project_code": "atp",
            "client": "web",
            "page_code": "batch-delete-elements",
            "page_name": "批量删除元素页",
            "status": "draft",
        },
    )
    assert create_page_resp.status_code == 201
    for element_code in ["first_button", "second_button"]:
        create_resp = client.post(
            "/api/page-objects/batch-delete-elements/elements",
            params={"project_code": "atp", "client": "web"},
            json={
                "element_code": element_code,
                "element_name": element_code,
                "locator_type": "css",
                "locator_value": f"#{element_code}",
                "changed_by": "qa-admin",
            },
        )
        assert create_resp.status_code == 201

    target = db_session.query(PageElement).filter_by(element_code="first_button").one()
    db_session.add(PageElementHealthCheck(page_element_id=target.id, check_status="ok"))
    db_session.add(PageElementLocator(page_element_id=target.id, locator_type="css", locator_value="#first_button", role=""))
    db_session.add(PageObjectRef(page_element_id=target.id, reference_type="test_case", reference_key="case-1"))
    db_session.commit()

    delete_resp = client.post(
        "/api/page-objects/batch-delete-elements/elements/batch/delete",
        params={"project_code": "atp", "client": "web"},
        json={"element_codes": ["first_button"]},
    )
    assert delete_resp.status_code == 200
    assert delete_resp.json()["item"]["deleted_count"] == 1
    assert db_session.query(PageElement).filter_by(element_code="first_button").count() == 0
    assert db_session.query(PageElementVersion).filter_by(page_element_id=target.id).count() == 0
    assert db_session.query(PageElementLocator).filter_by(page_element_id=target.id).count() == 0
    assert db_session.query(PageElementHealthCheck).filter_by(page_element_id=target.id).count() == 0
    assert db_session.query(PageObjectRef).filter_by(page_element_id=target.id).count() == 0

    list_resp = client.get(
        "/api/page-objects/batch-delete-elements/elements",
        params={"project_code": "atp", "client": "web"},
    )
    assert list_resp.status_code == 200
    assert [item["element_code"] for item in list_resp.json()["items"]] == ["second_button"]


def test_batch_delete_candidates_physically_removes_groups_and_empty_groups(
    page_objects_client: tuple[TestClient, Session],
) -> None:
    client, db_session = page_objects_client

    page_resp = client.post(
        "/api/page-objects",
        json={
            "project_code": "atp",
            "client": "web",
            "page_code": "batch-delete-candidates",
            "page_name": "批量删除候选页",
            "status": "draft",
        },
    )
    assert page_resp.status_code == 201
    db_session.add_all(
        [
            PageObjectCandidateGroup(
                project_code="atp",
                client="web",
                page_code="batch-delete-candidates",
                group_key="role:save",
                proposed_element_code="save_button",
                candidate_count=2,
                session_count=2,
                promotion_status="pending",
            ),
            PageObjectCandidateElement(
                project_code="atp",
                client="web",
                page_code="batch-delete-candidates",
                session_id="session-a",
                candidate_key="cand-save-a",
                group_key="role:save",
                raw_locator_type="role",
                raw_locator_value="保存",
                quality_score=80,
            ),
            PageObjectCandidateElement(
                project_code="atp",
                client="web",
                page_code="batch-delete-candidates",
                session_id="session-b",
                candidate_key="cand-save-b",
                group_key="role:save",
                raw_locator_type="role",
                raw_locator_value="保存",
                quality_score=90,
            ),
            PageObjectCandidateGroup(
                project_code="atp",
                client="web",
                page_code="batch-delete-candidates",
                group_key="role:cancel",
                proposed_element_code="cancel_button",
                candidate_count=1,
                session_count=1,
                promotion_status="pending",
            ),
            PageObjectCandidateElement(
                project_code="atp",
                client="web",
                page_code="batch-delete-candidates",
                session_id="session-c",
                candidate_key="cand-cancel",
                group_key="role:cancel",
                raw_locator_type="role",
                raw_locator_value="取消",
                quality_score=70,
            ),
        ]
    )
    db_session.commit()

    delete_candidate_resp = client.post(
        "/api/page-objects/batch-delete-candidates/candidate-elements/batch/delete",
        params={"project_code": "atp", "client": "web"},
        json={"candidate_keys": ["cand-save-a"]},
    )
    assert delete_candidate_resp.status_code == 200
    assert delete_candidate_resp.json()["item"]["deleted_candidate_count"] == 1
    save_group = db_session.query(PageObjectCandidateGroup).filter_by(group_key="role:save").one()
    assert int(save_group.candidate_count) == 1
    assert int(save_group.session_count) == 1
    assert db_session.query(PageObjectCandidateElement).filter_by(candidate_key="cand-save-a").count() == 0

    delete_group_resp = client.post(
        "/api/page-objects/batch-delete-candidates/candidate-groups/batch/delete",
        params={"project_code": "atp", "client": "web"},
        json={"group_keys": ["role:cancel"]},
    )
    assert delete_group_resp.status_code == 200
    assert delete_group_resp.json()["item"]["deleted_group_count"] == 1
    assert delete_group_resp.json()["item"]["deleted_candidate_count"] == 1
    assert db_session.query(PageObjectCandidateGroup).filter_by(group_key="role:cancel").count() == 0
    assert db_session.query(PageObjectCandidateElement).filter_by(candidate_key="cand-cancel").count() == 0

def test_candidate_group_governance_api_promote_merge_and_reject(
    page_objects_client: tuple[TestClient, Session],
) -> None:
    client, db_session = page_objects_client
    create_page_resp = client.post(
        "/api/page-objects",
        json={
            "project_code": "atp",
            "client": "web",
            "page_code": "candidate-governance",
            "page_name": "候选治理页",
            "description": "",
            "status": "draft",
            "created_by": "qa-admin",
        },
    )
    assert create_page_resp.status_code == 201

    db_session.add_all(
        [
            PageObjectCandidateGroup(
                project_code="atp",
                client="web",
                page_code="candidate-governance",
                group_key="testid:login-submit",
                proposed_element_code="login_submit",
                proposed_element_name="登录按钮",
                business_type_guess="button",
                business_domain_guess="auth",
                quality_tier="A",
                max_score=98,
                avg_score=98,
                candidate_count=1,
                session_count=1,
                recommended_action="ingest",
                promotion_status="pending",
                top_locator_source="testid",
                top_locator_type="data-testid",
                top_locator_value="login-submit",
                latest_session_id="session-1",
            ),
            PageObjectCandidateElement(
                project_code="atp",
                client="web",
                page_code="candidate-governance",
                session_id="session-1",
                candidate_key="cand-login-submit",
                group_key="testid:login-submit",
                raw_locator_type="data-testid",
                raw_locator_value="login-submit",
                raw_role="button",
                step_hit_count=1,
                quality_score=98,
                quality_tier="A",
                recommended_action="ingest",
                candidate_status="pending",
                proposed_element_code="login_submit",
                proposed_element_name="登录按钮",
                business_type_guess="button",
            ),
            PageObjectCandidateGroup(
                project_code="atp",
                client="web",
                page_code="candidate-governance",
                group_key="role:cancel",
                proposed_element_code="cancel_button",
                proposed_element_name="取消按钮",
                business_type_guess="button",
                business_domain_guess="common",
                quality_tier="B",
                max_score=82,
                avg_score=82,
                candidate_count=1,
                session_count=1,
                recommended_action="review",
                promotion_status="pending",
                top_locator_source="role_name",
                top_locator_type="role",
                top_locator_value="取消",
                top_role="button",
                latest_session_id="session-1",
            ),
            PageObjectCandidateElement(
                project_code="atp",
                client="web",
                page_code="candidate-governance",
                session_id="session-1",
                candidate_key="cand-cancel",
                group_key="role:cancel",
                raw_locator_type="role",
                raw_locator_value="取消",
                raw_role="button",
                step_hit_count=1,
                quality_score=82,
                quality_tier="B",
                recommended_action="review",
                candidate_status="pending",
                proposed_element_code="cancel_button",
                proposed_element_name="取消按钮",
                business_type_guess="button",
            ),
            PageObjectCandidateGroup(
                project_code="atp",
                client="web",
                page_code="candidate-governance",
                group_key="text:noise",
                proposed_element_code="",
                proposed_element_name="动态文本",
                business_type_guess="metric_value",
                quality_tier="D",
                max_score=30,
                avg_score=30,
                candidate_count=1,
                session_count=1,
                recommended_action="skip",
                promotion_status="pending",
                top_locator_source="manual",
                top_locator_type="text",
                top_locator_value="100000",
                latest_session_id="session-2",
            ),
            PageObjectCandidateElement(
                project_code="atp",
                client="web",
                page_code="candidate-governance",
                session_id="session-2",
                candidate_key="cand-noise",
                group_key="text:noise",
                raw_locator_type="text",
                raw_locator_value="100000",
                step_hit_count=1,
                quality_score=30,
                quality_tier="D",
                recommended_action="skip",
                candidate_status="pending",
                proposed_element_name="动态文本",
                business_type_guess="metric_value",
            ),
        ]
    )
    db_session.commit()

    groups_resp = client.get(
        "/api/page-objects/candidate-governance/candidate-groups",
        params={"project_code": "atp", "client": "web"},
    )
    assert groups_resp.status_code == 200
    assert len(groups_resp.json()["items"]) == 3

    detail_resp = client.get(
        "/api/page-objects/candidate-governance/candidate-groups/testid:login-submit",
        params={"project_code": "atp", "client": "web"},
    )
    assert detail_resp.status_code == 200
    assert len(detail_resp.json()["item"]["candidates"]) == 1

    promote_resp = client.post(
        "/api/page-objects/candidate-governance/candidate-groups/testid:login-submit/promote",
        params={"project_code": "atp", "client": "web"},
        json={
            "element_code": "login_submit",
            "element_name": "登录按钮",
            "business_type": "button",
            "business_domain": "auth",
            "is_key_element": True,
            "locator_type": "data-testid",
            "locator_value": "login-submit",
            "locator_source": "testid",
            "testid_value": "login-submit",
            "operator": "qa-admin",
        },
    )
    assert promote_resp.status_code == 200
    promoted_element = promote_resp.json()["item"]["element"]
    assert promoted_element["review_status"] == "approved"
    assert promoted_element["stability_level"] == "high"
    assert promote_resp.json()["item"]["group"]["promotion_status"] == "promoted"

    create_element_resp = client.post(
        "/api/page-objects/candidate-governance/elements",
        params={"project_code": "atp", "client": "web"},
        json={
            "element_code": "cancel_button",
            "element_name": "取消按钮",
            "locator_type": "role",
            "locator_value": "取消",
            "role": "button",
            "changed_by": "qa-admin",
        },
    )
    assert create_element_resp.status_code == 201

    merge_resp = client.post(
        "/api/page-objects/candidate-governance/candidate-groups/role:cancel/merge",
        params={"project_code": "atp", "client": "web"},
        json={"target_element_code": "cancel_button", "operator": "qa-admin", "review_note": "合并重复候选"},
    )
    assert merge_resp.status_code == 200
    assert merge_resp.json()["item"]["group"]["matched_existing_element_code"] == "cancel_button"
    merged_target = merge_resp.json()["item"]["target_element"]
    assert merged_target["governance_note"] == "合并重复候选"
    assert int(merged_target["locator_count"]) >= 1
    assert any(locator["is_primary"] for locator in merged_target["locators"])
    assert db_session.query(PageElementLocator).count() >= 1

    merged_detail_resp = client.get(
        "/api/page-objects/candidate-governance/elements/cancel_button",
        params={"project_code": "atp", "client": "web"},
    )
    assert merged_detail_resp.status_code == 200
    merged_detail = merged_detail_resp.json()["item"]
    assert merged_detail["governance_note"] == "合并重复候选"
    assert int(merged_detail["locator_count"]) >= 1
    assert any(locator["locator_type"] == "role" and locator["locator_value"] == "取消" for locator in merged_detail["locators"])

    dirty_promote_resp = client.post(
        "/api/page-objects/candidate-governance/candidate-groups/text:noise/promote",
        params={"project_code": "atp", "client": "web"},
        json={
            "element_code": "sales_text",
            "element_name": "销售额",
            "business_type": "metric_value",
            "business_domain": "dashboard",
            "locator_type": "text",
            "locator_value": "100000",
            "locator_source": "manual",
            "operator": "qa-admin",
        },
    )
    assert dirty_promote_resp.status_code == 400
    assert "metric_value" in str(dirty_promote_resp.json()["detail"])

    reject_resp = client.post(
        "/api/page-objects/candidate-governance/candidate-groups/text:noise/reject",
        params={"project_code": "atp", "client": "web"},
        json={"operator": "qa-admin", "review_note": "动态文本不作为页面对象元素"},
    )
    assert reject_resp.status_code == 200
    assert reject_resp.json()["item"]["group"]["promotion_status"] == "rejected"

    logs = db_session.query(PageObjectGovernanceLog).filter_by(page_code="candidate-governance").all()
    assert {str(item.action) for item in logs} >= {"promote", "merge", "reject"}


def test_deduplicate_page_elements_endpoint_physically_removes_history_duplicates(
    page_objects_client: tuple[TestClient, Session],
) -> None:
    client, _db_session = page_objects_client

    create_page_resp = client.post(
        "/api/page-objects",
        json={
            "project_code": "atp",
            "client": "web",
            "page_code": "login",
            "page_name": "登录页",
            "description": "",
            "status": "draft",
            "created_by": "qa-admin",
        },
    )
    assert create_page_resp.status_code == 201

    for element_code in ["primary_login_button", "secondary_login_button"]:
        create_element_resp = client.post(
            "/api/page-objects/login/elements",
            params={"project_code": "atp", "client": "web"},
            json={
                "element_code": element_code,
                "element_name": "录制元素",
                "locator_type": "role",
                "locator_value": "登录",
                "backup_locator": "",
                "health_status": 1,
                "role": "" if element_code.endswith("---3") else "button",
                "status": "active",
                "is_primary": True,
                "owner": "qa-team",
                "changed_by": "qa-admin",
                "change_summary": "录制",
            },
        )
        assert create_element_resp.status_code == 201

    dedupe_resp = client.post(
        "/api/page-objects/deduplicate",
        params={"project_code": "atp", "client": "web"},
    )
    assert dedupe_resp.status_code == 200
    summary = dedupe_resp.json()["item"]
    assert int(summary["scanned_page_count"]) == 1
    assert int(summary["affected_page_count"]) == 1
    assert int(summary["duplicate_deleted_count"]) == 1

    list_resp = client.get(
        "/api/page-objects/login/elements",
        params={"project_code": "atp", "client": "web"},
    )
    assert list_resp.status_code == 200
    items = list_resp.json()["items"]
    assert len(items) == 1
