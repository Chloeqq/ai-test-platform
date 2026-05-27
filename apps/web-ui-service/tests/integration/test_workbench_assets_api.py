from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
import app.models.test_case  # noqa: F401
import app.models.page_object  # noqa: F401
import app.models.test_project  # noqa: F401
import app.models.workbench_state  # noqa: F401
from app.api.workbench import constants as workbench_constants
from app.api.workbench import facade as workbench_facade
from app.models.page_object import PageElement, PageObject
from app.models.test_case import TestCase, TestCaseStep, TestCaseVersion
from app.routers.workbench_assets import router as workbench_assets_router
import app.schemas.test_case as test_case_schema
import app.schemas.test_project as test_project_schema
from app.services import test_case_service, test_project_service, workbench_asset_service


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

    monkeypatch.setattr(workbench_constants, "ASSETS_CASES_ROOT", assets_root)
    monkeypatch.setattr(workbench_constants, "AI_CASES_ROOT", ai_cases_root)
    monkeypatch.setattr(workbench_constants, "TEST_POINTS_ROOT", state_root)

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
    created_case = test_case_service.create_test_case(
        db_session,
        test_case_schema.TestCaseCreate(
            project_code="mall",
            case_id=case_id,
            name="商城页面-查询模块-输入条件-点击搜索-展示结果",
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

    case_file = workbench_constants.AI_CASES_ROOT / f"{case_id}.yaml"
    case_file.write_text(
        "\n".join(
            [
                f"id: {case_id}",
                "title: 商城页面-查询模块-输入条件-点击搜索-展示结果",
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

    assert response.status_code == 200
    assert response.json()["item"]["case_id"] == case_id


def test_test_point_assets_follow_generation_plan_snapshot(
    workbench_assets_client: tuple[TestClient, Session],
) -> None:
    client, db_session = workbench_assets_client
    project_code = "demo"
    case_id = "atp-web-login-fn-ai-0001"
    expected_asset_id = workbench_asset_service._safe_case_id(case_id)

    test_project_service.create_project(
        db_session,
        test_project_schema.TestProjectCreate(
            project_code=project_code,
            project_name="Demo",
        ),
    )
    created_case = test_case_service.create_test_case(
        db_session,
        test_case_schema.TestCaseCreate(
            project_code=project_code,
            case_id=case_id,
            name="登录功能-账号密码登录-成功",
            product_line="平台",
            module="login",
            priority="P1",
            test_type="ui",
            creator="qa",
            script_code="def test_login(page):\n    assert True\n",
        ),
    )

    plan = {
        "version": "TestPointPlanV1",
        "project": project_code,
        "case_id": case_id,
        "page": "login",
        "source_type": "generate_chain",
        "requirement": ["登录功能"],
        "generated_at": "2026-04-23T00:00:00+00:00",
        "points": [
            {
                "intent_id": "intent-01",
                "point_type": "action",
                "action": "click",
                "target": "login_button",
                "expected_result": "登录成功",
                "involved_elements": ["login_button"],
                "steps": [{"action": "click", "target": "login_button"}],
            }
        ],
        "coverage": {},
        "review_summary": {},
        "metadata": {},
        "involved_elements": ["login_button"],
        "confidence": 0.9,
        "warnings": [],
        "requires_review": False,
    }

    def _upsert_test_point_asset_snapshot(**kwargs: object) -> dict[str, object]:
        return workbench_asset_service.upsert_test_point_asset_snapshot(
            **kwargs,
            now_iso_fn=lambda: "2026-04-23T00:00:00+00:00",
            count_test_point_types_fn=workbench_asset_service.count_test_point_types,
            build_test_point_asset_semantic_summary_fn=lambda page, normalized_plan: {
                "page_type": "form",
                "business_domain": "generic",
                "primary_goal": "fill_form",
                "primary_actions": [],
                "reason_codes": [f"asset_page={page}", "asset_source_type=generate_chain"],
                "confidence": 1.0,
                "warnings": [],
                "requires_review": False,
                "source": "asset_plan",
            },
            build_test_point_asset_technique_summary_fn=lambda normalized_plan: workbench_asset_service.build_test_point_asset_technique_summary(
                normalized_plan=normalized_plan
            ),
            merge_reference_items_fn=workbench_asset_service.merge_reference_items,
        )

    plan_path = workbench_asset_service.save_test_point_plan(
        project=project_code,
        case_id=case_id,
        page="login",
        page_url="https://example.test/login",
        requirement="登录功能",
        plan=plan,
        now_iso_fn=lambda: "2026-04-23T00:00:00+00:00",
        normalize_test_point_plan_payload=lambda payload, strict=False: payload,
        upsert_test_point_asset_snapshot=_upsert_test_point_asset_snapshot,
        state_root=workbench_constants.TEST_POINTS_ROOT,
    )

    response = client.get(f"/api/workbench/test-point-assets?project={project_code}&source_type=generate_chain")
    assert response.status_code == 200
    payload = response.json()
    assert int(payload["selection_summary"]["total_assets"]) == 1
    item = payload["items"][0]
    assert item["asset_id"] == expected_asset_id
    assert item["source_type"] == "generate_chain"
    assert item["plan_path"] == str(plan_path.resolve())
    assert int(item["point_count"]) == 1

    detail = client.get(f"/api/workbench/test-point-assets/{case_id}?project={project_code}")
    assert detail.status_code == 200
    detail_item = detail.json()["item"]
    assert detail_item["asset_id"] == expected_asset_id
    assert detail_item["plan"]["source_type"] == "generate_chain"
    assert detail_item["coverage_matrix"]["summary"]["status"] in {"covered", "partial", "orphan", "gap"}


def test_test_point_asset_list_derives_business_title_and_source_label_for_saved_selection(
    workbench_assets_client: tuple[TestClient, Session],
) -> None:
    client, db_session = workbench_assets_client
    project_code = "demo"
    asset_id = "mall-web-login-auth-fn-ai-0020"

    test_project_service.create_project(
        db_session,
        test_project_schema.TestProjectCreate(
            project_code=project_code,
            project_name="Demo",
        ),
    )

    project_dir = workbench_constants.TEST_POINTS_ROOT / project_code
    (project_dir / "plans").mkdir(parents=True, exist_ok=True)
    (project_dir / f"{asset_id}.json").write_text(
        (
            "{"
            f"\"asset_id\":\"{asset_id}\","
            f"\"title\":\"{asset_id}\","
            "\"page\":\"login\","
            "\"source_type\":\"selection_save\","
            "\"requirement\":[\"原始登录需求\"],"
            "\"point_count\":1,"
            "\"confidence\":0.8,"
            "\"updated_at\":\"2026-04-24T12:33:30+00:00\""
            "}\n"
        ),
        encoding="utf-8",
    )
    (project_dir / "plans" / f"{asset_id}.json").write_text(
        (
            "{"
            "\"version\":\"TestPointPlanV1\","
            f"\"case_id\":\"{asset_id}\","
            "\"page\":\"login\","
            "\"source_type\":\"selection_save\","
            "\"requirement\":[\"原始登录需求\"],"
            "\"metadata\":{\"selected_candidates\":[{\"intent_id\":\"intent-20\",\"title\":\"密码输入非法字符登录\"}]},"
            "\"points\":[{\"key\":\"intent-20\",\"intent_id\":\"intent-20\",\"description\":\"密码输入非法字符登录\"}]"
            "}\n"
        ),
        encoding="utf-8",
    )

    response = client.get(f"/api/workbench/test-point-assets?project={project_code}&keyword=密码输入")
    assert response.status_code == 200
    payload = response.json()
    assert int(payload["selection_summary"]["total_assets"]) == 1
    item = payload["items"][0]
    assert item["title"] == "密码输入非法字符登录"
    assert item["source_type"] == "selection_save"
    assert item["source_label"] == "来自 AI 生成"
    assert int(item["intent_count"]) == 1

    detail = client.get(f"/api/workbench/test-point-assets/{asset_id}?project={project_code}")
    assert detail.status_code == 200
    detail_item = detail.json()["item"]
    assert detail_item["title"] == "密码输入非法字符登录"
    assert detail_item["source_label"] == "来自 AI 生成"
    assert detail_item["requirement"] == ["原始登录需求"]


def test_update_test_point_asset_preserves_multiple_selected_candidates(
    workbench_assets_client: tuple[TestClient, Session],
) -> None:
    client, db_session = workbench_assets_client
    project_code = "demo"
    asset_id = "mall-web-login-auth-fn-ai-0021"

    test_project_service.create_project(
        db_session,
        test_project_schema.TestProjectCreate(
            project_code=project_code,
            project_name="Demo",
        ),
    )

    response = client.put(
        f"/api/workbench/test-point-assets/{asset_id}",
        json={
            "project": project_code,
            "asset_id": asset_id,
            "page": "login",
            "title": "登录页身份验证测试点集",
            "priority": "P0",
            "requirement": "登录页原始需求",
            "source_type": "selection_save",
            "selected_candidates": [
                {
                    "intent_id": "intent-01",
                    "title": "首次登录成功",
                    "summary": "输入正确账号密码后登录成功",
                    "intent_type": "functional",
                    "priority": "P0",
                    "steps": ["输入账号 test001", "输入密码 123456", "点击登录按钮"],
                    "expected": "跳转至工作台首页",
                    "involved_elements": ["账号输入框", "密码输入框", "登录按钮"],
                },
                {
                    "intent_id": "intent-20",
                    "title": "密码输入非法字符登录",
                    "summary": "密码包含非法字符时应提示格式错误",
                    "intent_type": "format",
                    "priority": "P1",
                    "steps": ["输入账号 test001", "输入密码 1234@", "点击登录按钮"],
                    "expected": "页面弹出提示框，显示密码格式错误的信息",
                    "involved_elements": ["账号输入框", "密码输入框", "登录按钮"],
                },
            ],
        },
    )

    assert response.status_code == 200
    item = response.json()["item"]
    assert item["title"] == "登录页身份验证测试点集"
    assert item["source_label"] == "来自 AI 生成"
    assert int(item["point_count"]) == 2
    assert int(item["intent_count"]) == 2
    assert len(item["plan"]["points"]) == 2
    assert len(item["plan"]["metadata"]["selected_candidates"]) == 2
    assert [row["intent_id"] for row in item["plan"]["metadata"]["selected_candidates"]] == ["intent-01", "intent-20"]


def test_update_existing_test_point_asset_persists_plan_points(
    workbench_assets_client: tuple[TestClient, Session],
) -> None:
    client, db_session = workbench_assets_client
    project_code = "demo"
    asset_id = "mall-web-login-auth-fn-ai-0021"

    test_project_service.create_project(
        db_session,
        test_project_schema.TestProjectCreate(
            project_code=project_code,
            project_name="Demo",
        ),
    )
    page_object = PageObject(
        project_code=project_code,
        client="web",
        page_code="login",
        page_name="登录页",
        page_url="http://localhost:5174/#/login",
        status="published",
        governance_status="active",
    )
    db_session.add(page_object)
    db_session.flush()
    for element_code, element_name in [
        ("username_input", "用户名输入框"),
        ("password_input", "密码输入框"),
        ("login_button", "登录按钮"),
        ("home_menu", "首页菜单"),
    ]:
        db_session.add(
            PageElement(
                page_object_id=int(page_object.id),
                element_code=element_code,
                element_name=element_name,
                locator_type="data-testid",
                locator_value=element_code,
                review_status="approved",
                stability_level="high",
                status="active",
            )
        )
    db_session.commit()

    create_response = client.put(
        f"/api/workbench/test-point-assets/{asset_id}",
        json={
            "project": project_code,
            "asset_id": asset_id,
            "page": "login",
            "title": "登录页身份验证测试点集",
            "priority": "P0",
            "requirement": "登录页原始需求",
            "source_type": "selection_save",
            "selected_candidates": [
                {
                    "intent_id": "intent-01",
                    "title": "首次登录成功",
                    "summary": "输入正确账号密码后登录成功",
                    "intent_type": "functional",
                    "priority": "P0",
                    "steps": ["输入账号 admin", "输入密码 macro", "点击登录按钮"],
                    "expected": "跳转至工作台首页",
                    "involved_elements": ["账号输入框", "密码输入框", "登录按钮"],
                }
            ],
        },
    )
    assert create_response.status_code == 200
    created_point = create_response.json()["item"]["plan"]["points"][0]

    update_response = client.put(
        f"/api/workbench/test-point-assets/{asset_id}",
        json={
            "project": project_code,
            "asset_id": asset_id,
            "page": "login",
            "title": "登录页身份验证测试点集",
            "priority": "P0",
            "requirement": "登录页原始需求 - 已编辑",
            "source_type": "selection_save",
            "points": [
                {
                    **created_point,
                    "description": "编辑后的登录成功测试点",
                    "precondition": "用户未登录，处于登录页面，且已准备有效账号。",
                    "expected_result": "编辑后的预期结果",
                    "involved_elements": ["用户名输入框", "密码输入框", "登录按钮", "username_input", "password_input", "login_button", "home_menu"],
                    "steps": [
                        {
                            "action": "candidate_step",
                            "target": "",
                            "value": "编辑后的步骤",
                            "raw_text": "编辑后的步骤",
                        }
                    ],
                }
            ],
            "selected_candidates": [
                {
                    "intent_id": "intent-01",
                    "title": "这条旧候选不应覆盖 points",
                }
            ],
        },
    )

    assert update_response.status_code == 200
    detail = client.get(f"/api/workbench/test-point-assets/{asset_id}?project={project_code}")
    assert detail.status_code == 200
    point = detail.json()["item"]["plan"]["points"][0]
    assert point["description"] == "编辑后的登录成功测试点"
    assert point["precondition"] == "用户未登录，处于登录页面，且已准备有效账号。"
    assert point["expected_result"] == "编辑后的预期结果"
    assert point["involved_elements"] == ["username_input", "password_input", "login_button", "home_menu"]
    assert point["steps"][0]["raw_text"] == "编辑后的步骤"
    assert point["metadata"]["candidate_snapshot"]["title"] != "这条旧候选不应覆盖 points"


def test_test_point_reviews_flatten_assets_and_batch_review_updates_plan(
    workbench_assets_client: tuple[TestClient, Session],
) -> None:
    client, db_session = workbench_assets_client
    project_code = "demo"
    asset_id = "mall-web-login-auth-fn-ai-0022"

    test_project_service.create_project(
        db_session,
        test_project_schema.TestProjectCreate(
            project_code=project_code,
            project_name="Demo",
        ),
    )

    response = client.put(
        f"/api/workbench/test-point-assets/{asset_id}",
        json={
            "project": project_code,
            "asset_id": asset_id,
            "page": "login",
            "title": "登录页身份验证测试点集",
            "priority": "P0",
            "requirement": "登录页原始需求",
            "source_type": "selection_save",
            "selected_candidates": [
                {
                    "intent_id": "intent-01",
                    "title": "首次登录成功",
                    "intent_type": "functional",
                    "priority": "P0",
                    "steps": ["输入账号", "输入密码", "点击登录按钮"],
                    "expected": "跳转至工作台首页",
                    "involved_elements": ["账号输入框", "密码输入框", "登录按钮"],
                },
                {
                    "intent_id": "intent-02",
                    "title": "账号为空点击登录",
                    "intent_type": "negative",
                    "priority": "P1",
                    "steps": ["清空账号", "点击登录按钮"],
                    "expected": "提示请输入账号",
                    "involved_elements": ["账号输入框", "登录按钮"],
                },
            ],
        },
    )
    assert response.status_code == 200

    reviews = client.get(f"/api/workbench/test-point-reviews?project={project_code}&status=pending&page_size=50")
    assert reviews.status_code == 200
    payload = reviews.json()
    assert int(payload["summary"]["pending_count"]) == 2
    assert [item["review_status"] for item in payload["items"]] == ["pending", "pending"]
    assert all(item["can_generate"] is False for item in payload["items"])

    update = client.post(
        "/api/workbench/test-point-reviews/batch",
        json={
            "project": project_code,
            "status": "approved",
            "reviewed_by": "qa",
            "decisions": [{"asset_id": asset_id, "intent_id": "intent-02"}],
        },
    )
    assert update.status_code == 200
    assert int(update.json()["updated_count"]) == 1

    approved_reviews = client.get(f"/api/workbench/test-point-reviews?project={project_code}&status=approved&page_size=50")
    assert approved_reviews.status_code == 200
    approved_items = approved_reviews.json()["items"]
    assert len(approved_items) == 1
    assert approved_items[0]["intent_id"] == "intent-02"

    detail = client.get(f"/api/workbench/test-point-assets/{asset_id}?project={project_code}")
    assert detail.status_code == 200
    points = detail.json()["item"]["plan"]["points"]
    point = next(row for row in points if row["intent_id"] == "intent-02")
    assert point["review_status"] == "approved"
    assert point["metadata"]["candidate_snapshot"]["review_status"] == "approved"


def test_generate_cases_from_test_point_assets_blocks_when_page_url_empty(
    workbench_assets_client: tuple[TestClient, Session],
) -> None:
    client, db_session = workbench_assets_client
    project_code = "demo"
    asset_id = "mall-web-login-auth-fn-ai-0023"

    test_project_service.create_project(
        db_session,
        test_project_schema.TestProjectCreate(
            project_code=project_code,
            project_name="Demo",
        ),
    )
    page_object = PageObject(
        project_code=project_code,
        client="web",
        page_code="login",
        page_name="登录页",
        page_url="",
        status="published",
        governance_status="approved",
    )
    db_session.add(page_object)
    db_session.flush()
    db_session.add(
        PageElement(
            page_object_id=page_object.id,
            element_code="login_button",
            element_name="登录按钮",
            locator_type="css",
            locator_value="[data-testid='login-button']",
            aliases_json=["登录按钮"],
            business_type="button",
            status="active",
            review_status="approved",
            stability_level="medium",
        )
    )
    db_session.commit()

    response = client.put(
        f"/api/workbench/test-point-assets/{asset_id}",
        json={
            "project": project_code,
            "asset_id": asset_id,
            "page": "login",
            "title": "登录页测试点集",
            "priority": "P0",
            "requirement": "登录页原始需求",
            "source_type": "selection_save",
            "selected_candidates": [
                {
                    "intent_id": "intent-01",
                    "title": "首次登录成功",
                    "intent_type": "functional",
                    "priority": "P0",
                    "steps": ["点击登录按钮"],
                    "expected": "跳转至工作台首页",
                    "involved_elements": ["登录按钮"],
                    "review_status": "approved",
                }
            ],
        },
    )
    assert response.status_code == 200

    generate = client.post(
        "/api/workbench/test-point-assets/batch/generate-cases",
        json={
            "project": project_code,
            "asset_ids": [asset_id],
            "source": "asset_detail",
        },
    )
    assert generate.status_code == 422
    detail = generate.json()["detail"]
    assert detail["code"] == "page_object_url_missing"
    assert detail["message"] == "请到页面对象管理补齐页面 URL"


def test_preview_script_uses_page_object_locators_for_single_reviewed_intent(
    workbench_assets_client: tuple[TestClient, Session],
) -> None:
    client, db_session = workbench_assets_client
    project_code = "demo"
    asset_id = "mall-web-login-auth-fn-ai-0024"

    test_project_service.create_project(
        db_session,
        test_project_schema.TestProjectCreate(
            project_code=project_code,
            project_name="Demo",
        ),
    )
    page_object = PageObject(
        project_code=project_code,
        client="web",
        page_code="login",
        page_name="登录页",
        page_url="https://example.test/login",
        status="published",
        governance_status="approved",
    )
    db_session.add(page_object)
    db_session.flush()
    for element_code, element_name, locator_type, locator, role in [
        ("username_input", "账号输入框", "placeholder", "请输入用户名", ""),
        ("password_input", "密码输入框", "placeholder", "请输入密码", ""),
        ("login_button", "登录按钮", "role", "登录", "button"),
    ]:
        db_session.add(
            PageElement(
                page_object_id=page_object.id,
                element_code=element_code,
                element_name=element_name,
                locator_type=locator_type,
                locator_value=locator,
                role=role,
                aliases_json=[element_name],
                business_type="input" if element_code.endswith("_input") else "button",
                status="active",
                review_status="approved",
                stability_level="medium",
            )
        )
    db_session.commit()

    response = client.put(
        f"/api/workbench/test-point-assets/{asset_id}",
        json={
            "project": project_code,
            "asset_id": asset_id,
            "page": "login",
            "title": "登录页测试点集",
            "priority": "P0",
            "requirement": "登录页原始需求",
            "source_type": "selection_save",
            "selected_candidates": [
                {
                    "intent_id": "intent-01",
                    "title": "首次登录成功",
                    "intent_type": "functional",
                    "priority": "P0",
                    "steps": ["输入账号", "输入密码", "点击登录按钮"],
                    "steps_hint": [
                        "input:账号输入框=test001",
                        "input:密码输入框=123456",
                        "click:登录按钮",
                    ],
                    "expected": "跳转至工作台首页",
                    "involved_elements": ["账号输入框", "密码输入框", "登录按钮"],
                    "review_status": "approved",
                }
            ],
        },
    )
    assert response.status_code == 200

    preview = client.get(
        f"/api/workbench/preview-script?project={project_code}&asset_id={asset_id}&intent_id=intent-01"
    )
    assert preview.status_code == 200
    script_code = preview.json()["item"]["script_code"]
    assert 'driver.get("https://example.test/login")' in script_code
    assert "By.CSS_SELECTOR" in script_code
    assert 'input[placeholder*=\\"请输入用户名\\"]' in script_code
    assert 'input[placeholder*=\\"请输入密码\\"]' in script_code
    assert "By.XPATH" in script_code
    assert "send_keys(\"test001\")" in script_code


def test_generate_cases_from_test_point_assets_normalizes_page_trigger_source_to_ai(
    workbench_assets_client: tuple[TestClient, Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, db_session = workbench_assets_client
    project_code = "demo"
    asset_id = "mall-web-login-auth-fn-ai-0027"
    seen_sources: list[str] = []

    class _FakeGenerateUsecase:
        def execute(self, payload):
            seen_sources.append(str(payload.source))
            return {"item": {"case_id": "demo-web-login-fn-ai-0001", "source": payload.source}}

    monkeypatch.setattr(workbench_facade, "build_generate_case_usecase", lambda _db: _FakeGenerateUsecase())

    test_project_service.create_project(
        db_session,
        test_project_schema.TestProjectCreate(
            project_code=project_code,
            project_name="Demo",
        ),
    )
    page_object = PageObject(
        project_code=project_code,
        client="web",
        page_code="login",
        page_name="登录页",
        page_url="https://example.test/login",
        status="published",
        governance_status="approved",
    )
    db_session.add(page_object)
    db_session.flush()
    db_session.add(
        PageElement(
            page_object_id=page_object.id,
            element_code="login_button",
            element_name="登录按钮",
            locator_type="css",
            locator_value="[data-testid='login-button']",
            aliases_json=["登录按钮"],
            business_type="button",
            status="active",
            review_status="approved",
            stability_level="medium",
        )
    )
    db_session.commit()

    response = client.put(
        f"/api/workbench/test-point-assets/{asset_id}",
        json={
            "project": project_code,
            "asset_id": asset_id,
            "page": "login",
            "title": "登录页测试点集",
            "priority": "P0",
            "requirement": "登录页原始需求",
            "source_type": "selection_save",
            "selected_candidates": [
                {
                    "intent_id": "intent-01",
                    "title": "首次登录成功",
                    "intent_type": "functional",
                    "priority": "P0",
                    "steps": ["点击登录按钮"],
                    "expected": "跳转至工作台首页",
                    "involved_elements": ["登录按钮"],
                    "review_status": "approved",
                }
            ],
        },
    )
    assert response.status_code == 200

    generate = client.post(
        "/api/workbench/test-point-assets/batch/generate-cases",
        json={
            "project": project_code,
            "asset_ids": [asset_id],
            "source": "asset_detail",
        },
    )
    assert generate.status_code == 200
    assert generate.json()["count"] == 1
    assert seen_sources == ["ai"]


def test_generate_cases_from_test_point_assets_keeps_partial_success_when_one_intent_fails(
    workbench_assets_client: tuple[TestClient, Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, db_session = workbench_assets_client
    project_code = "demo"
    asset_id = "mall-web-login-auth-fn-ai-0028"
    seen_intents: list[str] = []

    class _FakeGenerateUsecase:
        def execute(self, payload):
            intent_id = str((payload.selected_intent_ids or [""])[0])
            seen_intents.append(intent_id)
            if intent_id == "intent-02":
                raise HTTPException(
                    status_code=422,
                    detail={
                        "code": "execution_compiler_intent_coverage_failed",
                        "message": "compiled steps do not strictly match selected intents",
                    },
                )
            return {"item": {"case_id": f"demo-web-login-fn-ai-{len(seen_intents):04d}", "intent_id": intent_id}}

    monkeypatch.setattr(workbench_facade, "build_generate_case_usecase", lambda _db: _FakeGenerateUsecase())

    test_project_service.create_project(
        db_session,
        test_project_schema.TestProjectCreate(
            project_code=project_code,
            project_name="Demo",
        ),
    )
    page_object = PageObject(
        project_code=project_code,
        client="web",
        page_code="login",
        page_name="登录页",
        page_url="https://example.test/login",
        status="published",
        governance_status="approved",
    )
    db_session.add(page_object)
    db_session.flush()
    db_session.add(
        PageElement(
            page_object_id=page_object.id,
            element_code="login_button",
            element_name="登录按钮",
            locator_type="css",
            locator_value="[data-testid='login-button']",
            aliases_json=["登录按钮"],
            business_type="button",
            status="active",
            review_status="approved",
            stability_level="medium",
        )
    )
    db_session.commit()

    response = client.put(
        f"/api/workbench/test-point-assets/{asset_id}",
        json={
            "project": project_code,
            "asset_id": asset_id,
            "page": "login",
            "title": "登录页测试点集",
            "priority": "P0",
            "requirement": "登录页原始需求",
            "source_type": "selection_save",
            "selected_candidates": [
                {
                    "intent_id": "intent-01",
                    "title": "首次登录成功",
                    "intent_type": "functional",
                    "priority": "P0",
                    "steps": ["点击登录按钮"],
                    "expected": "跳转至工作台首页",
                    "involved_elements": ["登录按钮"],
                    "review_status": "approved",
                },
                {
                    "intent_id": "intent-02",
                    "title": "账号为空点击登录",
                    "intent_type": "negative",
                    "priority": "P1",
                    "steps": ["点击登录按钮"],
                    "expected": "提示请输入账号",
                    "involved_elements": ["登录按钮"],
                    "review_status": "approved",
                },
                {
                    "intent_id": "intent-03",
                    "title": "密码为空点击登录",
                    "intent_type": "negative",
                    "priority": "P1",
                    "steps": ["点击登录按钮"],
                    "expected": "提示请输入密码",
                    "involved_elements": ["登录按钮"],
                    "review_status": "approved",
                },
            ],
        },
    )
    assert response.status_code == 200

    generate = client.post(
        "/api/workbench/test-point-assets/batch/generate-cases",
        json={
            "project": project_code,
            "asset_ids": [asset_id],
            "source": "asset_detail",
        },
    )

    assert generate.status_code == 200
    payload = generate.json()
    assert payload["count"] == 2
    assert seen_intents == ["intent-01", "intent-02", "intent-03"]
    assert payload["summary"]["skipped_assets"] == 1
    assert payload["summary"]["skipped"][0]["intent_id"] == "intent-02"
    assert "execution_compiler_intent_coverage_failed" in payload["summary"]["skipped"][0]["reason"]


def test_generate_cases_from_test_point_assets_reuses_existing_case_for_same_source_intent(
    workbench_assets_client: tuple[TestClient, Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, db_session = workbench_assets_client
    project_code = "demo"
    asset_id = "mall-web-login-auth-fn-ai-0029"
    existing_case_id = "demo-web-login-fn-ai-0007"
    seen_case_ids: list[str] = []

    class _FakeGenerateUsecase:
        def execute(self, payload):
            seen_case_ids.append(str(payload.case_id))
            return {"item": {"case_id": payload.case_id or "demo-web-login-fn-ai-0008"}}

    monkeypatch.setattr(workbench_facade, "build_generate_case_usecase", lambda _db: _FakeGenerateUsecase())

    test_project_service.create_project(
        db_session,
        test_project_schema.TestProjectCreate(
            project_code=project_code,
            project_name="Demo",
        ),
    )
    page_object = PageObject(
        project_code=project_code,
        client="web",
        page_code="login",
        page_name="登录页",
        page_url="https://example.test/login",
        status="published",
        governance_status="approved",
    )
    db_session.add(page_object)
    db_session.flush()
    db_session.add(
        PageElement(
            page_object_id=page_object.id,
            element_code="login_button",
            element_name="登录按钮",
            locator_type="css",
            locator_value="[data-testid='login-button']",
            aliases_json=["登录按钮"],
            business_type="button",
            status="active",
            review_status="approved",
            stability_level="medium",
        )
    )
    db_session.add(
        TestCase(
            case_id=existing_case_id,
            project_code=project_code,
            client="web",
            page_code="login",
            page_name="登录页",
            module_code="login",
            module_name="登录",
            case_type="fn",
            source="ai",
            name="首次登录成功",
            product_line="登录页",
            module="登录",
            priority="P0",
            test_type="ui",
            status="active",
            automation_status="automated",
            script_code=(
                "version: v1\n"
                f"id: {existing_case_id}\n"
                "project: demo\n"
                "module: login\n"
                "title: 首次登录成功\n"
                "requirement:\n"
                "  intent_id: intent-01\n"
                "  title: 首次登录成功\n"
                "  source_asset_id: mall-web-login-auth-fn-ai-0029\n"
                "execution:\n"
                "  page: login\n"
                "  selected_intent_ids:\n"
                "    - intent-01\n"
            ),
        )
    )
    db_session.commit()

    response = client.put(
        f"/api/workbench/test-point-assets/{asset_id}",
        json={
            "project": project_code,
            "asset_id": asset_id,
            "page": "login",
            "title": "登录页测试点集",
            "priority": "P0",
            "requirement": "登录页原始需求",
            "source_type": "selection_save",
            "selected_candidates": [
                {
                    "intent_id": "intent-01",
                    "title": "首次登录成功",
                    "intent_type": "functional",
                    "priority": "P0",
                    "steps": ["点击登录按钮"],
                    "expected": "跳转至工作台首页",
                    "involved_elements": ["登录按钮"],
                    "review_status": "approved",
                }
            ],
        },
    )
    assert response.status_code == 200

    generate = client.post(
        "/api/workbench/test-point-assets/batch/generate-cases",
        json={
            "project": project_code,
            "asset_ids": [asset_id],
            "source": "asset_detail",
        },
    )

    assert generate.status_code == 200
    assert seen_case_ids == [existing_case_id]


def test_generate_cases_from_test_point_assets_filters_selected_intents_before_generation(
    workbench_assets_client: tuple[TestClient, Session],
) -> None:
    client, db_session = workbench_assets_client
    project_code = "demo"
    asset_id = "mall-web-login-auth-fn-ai-0025"

    test_project_service.create_project(
        db_session,
        test_project_schema.TestProjectCreate(
            project_code=project_code,
            project_name="Demo",
        ),
    )
    page_object = PageObject(
        project_code=project_code,
        client="web",
        page_code="login",
        page_name="登录页",
        page_url="https://example.test/login",
        status="published",
        governance_status="approved",
    )
    db_session.add(page_object)
    db_session.flush()
    db_session.add(
        PageElement(
            page_object_id=page_object.id,
            element_code="login_button",
            element_name="登录按钮",
            locator_type="css",
            locator_value="[data-testid='login-button']",
            aliases_json=["登录按钮"],
            business_type="button",
            status="active",
            review_status="approved",
            stability_level="medium",
        )
    )
    db_session.commit()

    response = client.put(
        f"/api/workbench/test-point-assets/{asset_id}",
        json={
            "project": project_code,
            "asset_id": asset_id,
            "page": "login",
            "title": "登录页测试点集",
            "priority": "P0",
            "requirement": "登录页原始需求",
            "source_type": "selection_save",
            "selected_candidates": [
                {
                    "intent_id": "intent-01",
                    "title": "首次登录成功",
                    "intent_type": "functional",
                    "priority": "P0",
                    "steps": ["点击登录按钮"],
                    "expected": "跳转至工作台首页",
                    "involved_elements": ["登录按钮"],
                    "review_status": "approved",
                },
                {
                    "intent_id": "intent-02",
                    "title": "账号为空点击登录",
                    "intent_type": "negative",
                    "priority": "P1",
                    "steps": ["点击登录按钮"],
                    "expected": "提示请输入账号",
                    "involved_elements": ["登录按钮"],
                    "review_status": "pending",
                },
            ],
        },
    )
    assert response.status_code == 200

    generate = client.post(
        "/api/workbench/test-point-assets/batch/generate-cases",
        json={
            "project": project_code,
            "asset_ids": [asset_id],
            "intent_ids": ["intent-02"],
            "source": "review_detail",
        },
    )
    assert generate.status_code == 422
    detail = generate.json()["detail"]
    assert detail["code"] == "selected_intents_not_approved_or_missing"
    assert detail["message"] == "所选测试点未通过审核或不存在，无法生成"


def test_workbench_test_cases_links_generated_case_to_source_asset_by_selected_intents(
    workbench_assets_client: tuple[TestClient, Session],
) -> None:
    client, db_session = workbench_assets_client
    project_code = "demo"
    asset_id = "mall-web-login-auth-fn-ai-0026"
    case_id = "demo-web-login-fn-ai-0001"

    test_project_service.create_project(
        db_session,
        test_project_schema.TestProjectCreate(
            project_code=project_code,
            project_name="Demo",
        ),
    )
    project_dir = workbench_constants.TEST_POINTS_ROOT / project_code
    (project_dir / "plans").mkdir(parents=True, exist_ok=True)
    (project_dir / f"{asset_id}.json").write_text(
        json.dumps(
            {
                "asset_id": asset_id,
                "title": "登录页测试点集",
                "page": "login",
                "source_type": "selection_save",
                "updated_at": "2026-04-24T12:33:30+00:00",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    (project_dir / "plans" / f"{asset_id}.json").write_text(
        json.dumps(
            {
                "case_id": asset_id,
                "page": "login",
                "points": [
                    {
                        "key": "intent-01",
                        "intent_id": "intent-01",
                        "description": "首次登录成功",
                        "metadata": {
                            "candidate_snapshot": {
                                "intent_id": "intent-01",
                                "title": "首次登录成功",
                                "intent_type": "functional",
                            }
                        },
                    }
                ],
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    created_case = test_case_service.create_test_case(
        db_session,
        test_case_schema.TestCaseCreate(
            project_code=project_code,
            case_id=case_id,
            name="首次登录成功",
            product_line="login",
            module="login",
            page_code="login",
            priority="P0",
            test_type="ui",
            creator="qa",
            test_steps=[{"action": "click", "target": "login_button"}],
            script_code=(
                "id: demo-web-login-fn-ai-0001\n"
                "title: 首次登录成功\n"
                "execution:\n"
                "  page: login\n"
                "  selected_intent_ids:\n"
                "    - intent-01\n"
                "  steps:\n"
                "    - action: click\n"
                "      target: login_button\n"
            ),
        ),
    )

    response = client.get(f"/api/workbench/test-cases?project={project_code}&source_asset={asset_id}")
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["case_id"] == created_case.case_id
    assert items[0]["source_asset_id"] == asset_id
    assert items[0]["source_asset_title"] == "登录页测试点集"


def test_workbench_test_case_detail_uses_structured_requirement_metadata(
    workbench_assets_client: tuple[TestClient, Session],
) -> None:
    client, db_session = workbench_assets_client
    project_code = "demo"
    case_id = "demo-web-login-fn-ai-0002"

    test_project_service.create_project(
        db_session,
        test_project_schema.TestProjectCreate(
            project_code=project_code,
            project_name="Demo",
        ),
    )
    created_case = test_case_service.create_test_case(
        db_session,
        test_case_schema.TestCaseCreate(
            project_code=project_code,
            case_id=case_id,
            name="首次登录成功",
            product_line="login",
            module="login",
            page_code="login",
            priority="P0",
            test_type="ui",
            creator="qa",
            script_code=(
                "id: demo-web-login-fn-ai-0002\n"
                "title: 首次登录成功\n"
                "requirement:\n"
                "  intent_id: intent-01\n"
                "  title: 首次登录成功\n"
                "  type: functional\n"
                "  precondition: 用户未登录，处于登录页面\n"
                "  source_asset_id: mall-web-login-auth-fn-ai-0021\n"
                "  source_asset_title: 登录页身份验证测试点集\n"
                "execution:\n"
                "  page: login\n"
                "  selected_intent_ids:\n"
                "    - intent-01\n"
                "  steps:\n"
                "    - action: click\n"
                "      target: login_button\n"
                "      intent_id: intent-01\n"
            ),
        ),
    )

    response = client.get(f"/api/workbench/test-cases/{created_case.case_id}?project={project_code}")

    assert response.status_code == 200
    item = response.json()["item"]
    assert item["precondition"] == "用户未登录，处于登录页面"
    assert item["source_asset_id"] == "mall-web-login-auth-fn-ai-0021"
    assert item["source_asset_title"] == "登录页身份验证测试点集"
    assert item["intent_type"] == "functional"
    assert item["intent_ids"] == ["intent-01"]


def test_workbench_test_cases_can_be_physically_deleted(
    workbench_assets_client: tuple[TestClient, Session],
) -> None:
    client, db_session = workbench_assets_client
    project_code = "delproj"
    other_project_code = "keepproj"

    for code in (project_code, other_project_code):
        test_project_service.create_project(
            db_session,
            test_project_schema.TestProjectCreate(
                project_code=code,
                project_name=code,
            ),
        )

    first_case = test_case_service.create_test_case(
        db_session,
        test_case_schema.TestCaseCreate(
            project_code=project_code,
            case_id="delproj-web-login-auth-fn-ai-0001",
            name="首次登录成功",
            product_line="login",
            module="login",
            page_code="login",
            priority="P0",
            test_type="ui",
            creator="qa",
            test_steps=[{"action": "click", "target": "login_button"}],
            script_code="def test_login_success():\n    assert True\n",
        ),
    )
    second_case = test_case_service.create_test_case(
        db_session,
        test_case_schema.TestCaseCreate(
            project_code=project_code,
            case_id="delproj-web-login-auth-fn-ai-0002",
            name="账号为空登录",
            product_line="login",
            module="login",
            page_code="login",
            priority="P1",
            test_type="ui",
            creator="qa",
            test_steps=[{"action": "click", "target": "login_button"}],
            script_code="def test_login_empty_account():\n    assert True\n",
        ),
    )
    keep_case = test_case_service.create_test_case(
        db_session,
        test_case_schema.TestCaseCreate(
            project_code=other_project_code,
            case_id="keepproj-web-login-auth-fn-ai-0001",
            name="其他项目用例",
            product_line="login",
            module="login",
            page_code="login",
            priority="P1",
            test_type="ui",
            creator="qa",
            test_steps=[{"action": "click", "target": "login_button"}],
            script_code="def test_other_project():\n    assert True\n",
        ),
    )
    first_db_id = int(first_case.id)
    first_case_id = str(first_case.case_id)
    second_case_id = str(second_case.case_id)
    keep_case_id = str(keep_case.case_id)

    response = client.delete(f"/api/workbench/test-cases/{first_case_id}?project={project_code}")
    assert response.status_code == 200
    assert response.json()["deleted_count"] == 1
    assert db_session.query(TestCase).filter(TestCase.case_id == first_case_id).one_or_none() is None
    assert db_session.query(TestCaseStep).filter(TestCaseStep.case_id == first_db_id).count() == 0
    assert db_session.query(TestCaseVersion).filter(TestCaseVersion.case_id == first_db_id).count() == 0

    response = client.post(
        "/api/workbench/test-cases/batch/delete",
        json={"project": project_code, "delete_all": True},
    )
    assert response.status_code == 200
    assert response.json()["deleted_count"] == 1
    assert response.json()["deleted_case_ids"] == [second_case_id]
    assert db_session.query(TestCase).filter(TestCase.project_code == project_code).count() == 0
    assert db_session.query(TestCase).filter(TestCase.case_id == keep_case_id).count() == 1


def test_test_point_asset_coverage_matrix_groups_derived_points_into_one_row(
    workbench_assets_client: tuple[TestClient, Session],
) -> None:
    client, db_session = workbench_assets_client
    project_code = "demo"
    asset_id = "mall-web-login-auth-fn-ai-0030"

    test_project_service.create_project(
        db_session,
        test_project_schema.TestProjectCreate(
            project_code=project_code,
            project_name="Demo",
        ),
    )

    project_dir = workbench_constants.TEST_POINTS_ROOT / project_code
    (project_dir / "plans").mkdir(parents=True, exist_ok=True)
    points = [
        {
            "key": f"intent-{index:02d}",
            "intent_id": f"intent-{index:02d}",
            "description": f"登录测试点 {index:02d}",
            "metadata": {
                "traceability": {
                    "source_ids": [f"intent-{index:02d}"],
                    "intent_ids": [f"intent-{index:02d}"],
                }
            },
        }
        for index in range(1, 4)
    ]
    (project_dir / f"{asset_id}.json").write_text(
        '{"asset_id":"%s","title":"登录页测试点集","page":"login","source_type":"selection_save","updated_at":"2026-04-24T12:33:30+00:00"}\n'
        % asset_id,
        encoding="utf-8",
    )
    (project_dir / "plans" / f"{asset_id}.json").write_text(
        (
            '{"case_id":"%s","page":"login","source_type":"selection_save","requirement":["登录需求"],'
            '"points":%s,"metadata":{"selected_intent_ids":["intent-01","intent-02","intent-03"]}}\n'
        )
        % (asset_id, json.dumps(points, ensure_ascii=False)),
        encoding="utf-8",
    )

    response = client.get(f"/api/workbench/test-point-assets/{asset_id}/coverage-matrix?project={project_code}")
    assert response.status_code == 200
    matrix = response.json()["item"]
    assert int(matrix["row_count"]) == 1
    assert int(matrix["summary"]["covered_count"]) == 3
    assert matrix["summary"]["status"] == "covered"
    assert matrix["rows"][0]["source_ids"] == ["source-01"]
    assert matrix["rows"][0]["intent_ids"] == ["intent-01", "intent-02", "intent-03"]


def test_batch_delete_test_point_assets_hard_delete_persists_after_refresh(
    workbench_assets_client: tuple[TestClient, Session],
) -> None:
    client, db_session = workbench_assets_client
    project_code = "demo"
    other_project_code = "shadow"
    case_id = "atp-web-login-auth-fn-ai-0006"
    normalized_case_id = workbench_asset_service._safe_case_id(case_id)

    test_project_service.create_project(
        db_session,
        test_project_schema.TestProjectCreate(
            project_code=project_code,
            project_name="Demo",
        ),
    )

    # Seed same asset id under multiple project state buckets to simulate cross-project resurrection.
    for bucket in (project_code, other_project_code):
        bucket_dir = workbench_constants.TEST_POINTS_ROOT / bucket
        (bucket_dir / "plans").mkdir(parents=True, exist_ok=True)
        (bucket_dir / "versions" / normalized_case_id).mkdir(parents=True, exist_ok=True)
        (bucket_dir / f"{normalized_case_id}.json").write_text(
            '{"asset_id":"%s","title":"首次登录成功","page":"login","source_type":"generate_chain","updated_at":"2026-04-24T12:33:30+00:00"}\n'
            % normalized_case_id,
            encoding="utf-8",
        )
        (bucket_dir / "plans" / f"{normalized_case_id}.json").write_text(
            '{"case_id":"%s","page":"login","points":[]}\n' % normalized_case_id,
            encoding="utf-8",
        )
        (bucket_dir / "versions" / normalized_case_id / "0001.json").write_text(
            '{"version":1}\n',
            encoding="utf-8",
        )

    # Seed YAML case assets that could be used by subsequent sync flows.
    yaml_primary = workbench_constants.ASSETS_CASES_ROOT / "ai-generated" / f"{normalized_case_id}.yaml"
    yaml_secondary = workbench_constants.ASSETS_CASES_ROOT / "manual" / f"{normalized_case_id}.yaml"
    yaml_primary.parent.mkdir(parents=True, exist_ok=True)
    yaml_secondary.parent.mkdir(parents=True, exist_ok=True)
    yaml_primary.write_text(f"id: {normalized_case_id}\n", encoding="utf-8")
    yaml_secondary.write_text(f"id: {normalized_case_id}\n", encoding="utf-8")

    before_delete = client.get(f"/api/workbench/test-point-assets?project={project_code}")
    assert before_delete.status_code == 200
    assert any(str(item.get("asset_id", "")).strip() == normalized_case_id for item in before_delete.json().get("items", []))

    response = client.post(
        "/api/workbench/test-point-assets/batch/delete",
        json={
            "project": project_code,
            "asset_ids": [case_id],
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert int(payload.get("deleted_count", 0)) == 1
    assert normalized_case_id in [str(item).strip() for item in payload.get("deleted_asset_ids", [])]

    # Simulate "refresh": list again and verify deleted asset is gone.
    after_delete = client.get(f"/api/workbench/test-point-assets?project={project_code}")
    assert after_delete.status_code == 200
    assert all(str(item.get("asset_id", "")).strip() != normalized_case_id for item in after_delete.json().get("items", []))

    # Verify physical deletion across state buckets and linked yaml files.
    for bucket in (project_code, other_project_code):
        bucket_dir = workbench_constants.TEST_POINTS_ROOT / bucket
        assert not (bucket_dir / f"{normalized_case_id}.json").exists()
        assert not (bucket_dir / "plans" / f"{normalized_case_id}.json").exists()
        assert not (bucket_dir / "versions" / normalized_case_id).exists()
    assert not yaml_primary.exists()
    assert not yaml_secondary.exists()


def test_batch_delete_test_point_assets_supports_legacy_raw_asset_id_files(
    workbench_assets_client: tuple[TestClient, Session],
) -> None:
    client, db_session = workbench_assets_client
    project_code = "demo"
    raw_asset_id = "atp-web-delete-smoke-ai-9999"
    normalized_asset_id = workbench_asset_service._safe_case_id(raw_asset_id)

    test_project_service.create_project(
        db_session,
        test_project_schema.TestProjectCreate(
            project_code=project_code,
            project_name="Demo",
        ),
    )

    project_dir = workbench_constants.TEST_POINTS_ROOT / project_code
    (project_dir / "plans").mkdir(parents=True, exist_ok=True)
    (project_dir / "versions" / raw_asset_id).mkdir(parents=True, exist_ok=True)
    (project_dir / f"{raw_asset_id}.json").write_text(
        '{"asset_id":"%s","title":"legacy id","page":"login","source_type":"manual","updated_at":"2026-04-24T12:33:30+00:00"}\n'
        % raw_asset_id,
        encoding="utf-8",
    )
    (project_dir / "plans" / f"{raw_asset_id}.json").write_text(
        '{"case_id":"%s","page":"login","points":[]}\n' % raw_asset_id,
        encoding="utf-8",
    )
    (project_dir / "versions" / raw_asset_id / "0001.json").write_text(
        '{"version":1}\n',
        encoding="utf-8",
    )

    list_before = client.get(f"/api/workbench/test-point-assets?project={project_code}&keyword={raw_asset_id}")
    assert list_before.status_code == 200
    assert any(str(item.get("asset_id", "")).strip() in {raw_asset_id, normalized_asset_id} for item in list_before.json().get("items", []))

    response = client.post(
        "/api/workbench/test-point-assets/batch/delete",
        json={
            "project": project_code,
            "asset_ids": [raw_asset_id],
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert int(payload.get("deleted_count", 0)) == 1
    assert int(payload.get("missing_count", 0)) == 0

    assert not (project_dir / f"{raw_asset_id}.json").exists()
    assert not (project_dir / "plans" / f"{raw_asset_id}.json").exists()
    assert not (project_dir / "versions" / raw_asset_id).exists()

    list_after = client.get(f"/api/workbench/test-point-assets?project={project_code}&keyword={normalized_asset_id}")
    assert list_after.status_code == 200
    assert all(str(item.get("asset_id", "")).strip() != normalized_asset_id for item in list_after.json().get("items", []))
