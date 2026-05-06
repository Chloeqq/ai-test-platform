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
from app.api.workbench import constants as workbench_constants
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
    test_case_service.create_test_case(
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
    test_case_service.create_test_case(
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
