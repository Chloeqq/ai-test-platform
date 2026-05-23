from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace

from fastapi import HTTPException
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.api.workbench import facade as workbench_facade
from app.api.workbench.facade import WorkbenchFacade, _persist_runtime_run_to_case_center
from app.core.database import Base
import app.models.page_object as page_object_model  # noqa: F401
import app.models.test_case as test_case_model
import app.models.test_project  # noqa: F401
import app.schemas.test_case as test_case_schema
import app.schemas.test_project as test_project_schema
from app.services import (
    test_case_bootstrap_service,
    test_case_service,
    test_project_service,
)


@pytest.fixture()
def db_session(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[Session]:
    isolated_assets_root = tmp_path / "test-cases"
    monkeypatch.setattr(test_case_service, "ASSETS_CASES_ROOT", isolated_assets_root)
    monkeypatch.setattr(test_case_bootstrap_service, "ASSETS_CASES_ROOT", isolated_assets_root)

    engine = create_engine("sqlite:///:memory:", future=True)
    testing_session = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)
    Base.metadata.create_all(bind=engine)

    session = testing_session()
    try:
        yield session
    finally:
        session.close()

def test_get_detail_does_not_repair_password_input_to_remember_checkbox(db_session: Session) -> None:
    page_object = page_object_model.PageObject(
        project_code="mall",
        client="web",
        page_code="login",
        page_name="登录页",
        page_url="http://localhost:5174/#/login",
        status="online",
        created_by="qa",
    )
    db_session.add(page_object)
    db_session.flush()
    db_session.add_all(
        [
            page_object_model.PageElement(
                page_object_id=page_object.id,
                element_code="remember_password_checkbox",
                element_name="记住密码复选框",
                locator_type="id",
                locator_value="remember-password",
                business_type="checkbox",
                role="checkbox",
                owner="qa",
            ),
            page_object_model.PageElement(
                page_object_id=page_object.id,
                element_code="username_input",
                element_name="用户名输入框",
                locator_type="placeholder",
                locator_value="请输入用户名",
                role="username",
                business_type="input",
                owner="qa",
            ),
            page_object_model.PageElement(
                page_object_id=page_object.id,
                element_code="password_input",
                element_name="密码输入框",
                locator_type="placeholder",
                locator_value="请输入密码",
                role="password",
                business_type="input",
                owner="qa",
            ),
            page_object_model.PageElement(
                page_object_id=page_object.id,
                element_code="login_button",
                element_name="登录按钮",
                locator_type="role",
                locator_value="登录",
                role="button",
                business_type="button",
                owner="qa",
            ),
        ]
    )
    db_session.commit()

    case = test_case_service.create_test_case(
        db_session,
        test_case_schema.TestCaseCreate(
            case_id="mall-web-login-auth-fn-ai-0100",
            project_code="mall",
            page_code="login",
            name="首次登录成功",
            product_line="商城",
            module="login",
            priority="P0",
            test_type="ui",
            creator="qa",
            expected_result="页面跳转至平台工作台首页，顶部展示当前登录用户名 admin。",
            script_code="def test_login_success(page):\n    assert True\n",
            test_steps=[
                {
                    "action": "input",
                    "description": "input username_input test001",
                    "target": "element:username_input",
                    "locator_type": "placeholder",
                    "locator_value": "请输入用户名",
                    "value": "admin",
                },
                {
                    "action": "input",
                    "description": "input remember_password_checkbox 123456",
                    "target": "element:remember_password_checkbox",
                    "locator_type": "id",
                    "locator_value": "remember-password",
                    "value": "macro123",
                },
                {
                    "action": "click",
                    "description": "click login_button",
                    "target": "element:login_button",
                    "locator_type": "role",
                    "locator_value": "登录",
                    "expected_result": "登录失败，页面展示与当前场景匹配的错误提示",
                },
            ],
        ),
    )

    detail = test_case_service.get_test_case_detail(db_session, str(case.id))
    current_steps = detail.case.test_steps if isinstance(detail.case.test_steps, list) else []

    assert [str(item.get("target")) for item in current_steps] == [
        "element:username_input",
        "element:remember_password_checkbox",
        "element:login_button",
    ]
    assert str(current_steps[1].get("locator_value")) == "remember-password"
    assert "登录失败" in str(current_steps[2].get("expected_result"))


def test_batch_status_update_blocked_when_project_inactive(db_session: Session) -> None:
    test_project_service.create_project(
        db_session,
        test_project_schema.TestProjectCreate(
            project_code="mall",
            project_name="Mall Platform",
        ),
    )
    case = test_case_service.create_test_case(
        db_session,
        test_case_schema.TestCaseCreate(
            project_code="mall",
            name="商城回归校验",
            product_line="商城",
            module="列表",
            script_code="def test_mall_case(page):\n    assert True\n",
        ),
    )
    test_project_service.update_project(
        db_session,
        "mall",
        test_project_schema.TestProjectUpdate(status="inactive"),
    )

    with pytest.raises(HTTPException) as exc_info:
        test_case_service.batch_update_test_case_status(
            db_session,
            test_case_schema.BatchStatusUpdatePayload(case_ids=[case.case_id], status="deprecated"),
        )

    assert exc_info.value.status_code == 409
    assert "project is inactive" in str(exc_info.value.detail).lower()


def test_batch_tags_update_blocked_when_project_inactive(db_session: Session) -> None:
    test_project_service.create_project(
        db_session,
        test_project_schema.TestProjectCreate(
            project_code="mall",
            project_name="Mall Platform",
        ),
    )
    case = test_case_service.create_test_case(
        db_session,
        test_case_schema.TestCaseCreate(
            project_code="mall",
            name="商城标签治理",
            product_line="商城",
            module="列表",
            script_code="def test_mall_tags(page):\n    assert True\n",
        ),
    )
    test_project_service.update_project(
        db_session,
        "mall",
        test_project_schema.TestProjectUpdate(status="inactive"),
    )

    with pytest.raises(HTTPException) as exc_info:
        test_case_service.batch_update_test_case_tags(
            db_session,
            test_case_schema.BatchTagsUpdatePayload(case_ids=[case.case_id], tags=["governance"], mode="append"),
        )

    assert exc_info.value.status_code == 409
    assert "project is inactive" in str(exc_info.value.detail).lower()


def test_create_test_case_blocked_when_project_inactive(db_session: Session) -> None:
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

    with pytest.raises(HTTPException) as exc_info:
        test_case_service.create_test_case(
            db_session,
            test_case_schema.TestCaseCreate(
                project_code="mall",
                name="商城查询草稿",
                product_line="商城",
                module="查询",
                script_code="def test_mall_query(page):\n    assert True\n",
            ),
        )

    assert exc_info.value.status_code == 409
    assert "project is inactive" in str(exc_info.value.detail).lower()


def test_add_defect_blocked_when_project_inactive(db_session: Session) -> None:
    test_project_service.create_project(
        db_session,
        test_project_schema.TestProjectCreate(
            project_code="mall",
            project_name="Mall Platform",
        ),
    )
    case = test_case_service.create_test_case(
        db_session,
        test_case_schema.TestCaseCreate(
            project_code="mall",
            name="商城缺陷回归",
            product_line="商城",
            module="详情",
            script_code="def test_mall_detail(page):\n    assert True\n",
        ),
    )
    test_project_service.update_project(
        db_session,
        "mall",
        test_project_schema.TestProjectUpdate(status="inactive"),
    )

    with pytest.raises(HTTPException) as exc_info:
        test_case_service.add_test_case_defect(
            db_session,
            case.case_id,
            "BUG-1001",
            "",
        )

    assert exc_info.value.status_code == 409
    assert "project is inactive" in str(exc_info.value.detail).lower()


def test_update_script_blocked_when_project_inactive(db_session: Session) -> None:
    test_project_service.create_project(
        db_session,
        test_project_schema.TestProjectCreate(
            project_code="mall",
            project_name="Mall Platform",
        ),
    )
    case = test_case_service.create_test_case(
        db_session,
        test_case_schema.TestCaseCreate(
            project_code="mall",
            name="商城脚本维护",
            product_line="商城",
            module="详情",
            script_code="def test_mall_detail(page):\n    assert True\n",
        ),
    )
    test_project_service.update_project(
        db_session,
        "mall",
        test_project_schema.TestProjectUpdate(status="inactive"),
    )

    with pytest.raises(HTTPException) as exc_info:
        test_case_service.update_script(
            db_session,
            case.case_id,
            test_case_schema.TestCaseScriptUpdate(
                script_code="def test_mall_detail(page):\n    assert False\n",
                changed_by="qa-admin",
            ),
        )

    assert exc_info.value.status_code == 409
    assert "project is inactive" in str(exc_info.value.detail).lower()


def test_run_case_uses_db_script_code_when_source_yaml_is_missing(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    test_project_service.create_project(
        db_session,
        test_project_schema.TestProjectCreate(
            project_code="mall",
            project_name="Mall Platform",
        ),
    )
    script_code = (
        "id: mall-web-login-auth-fn-ai-0201\n"
        "title: DB 脚本优先执行\n"
        "module: login\n"
        "execution:\n"
        "  runner: playwright\n"
        "  page: login\n"
        "  steps:\n"
        "    - action: goto\n"
        "      value: http://localhost:5174/#/login\n"
    )
    test_case_service.create_test_case(
        db_session,
        test_case_schema.TestCaseCreate(
            project_code="mall",
            case_id="mall-web-login-auth-fn-ai-0201",
            name="DB 脚本优先执行",
            page_code="login",
            product_line="商城",
            module="登录",
            source_ref=str(tmp_path / "missing-source.yaml"),
            script_code=script_code,
        ),
    )

    assets_root = tmp_path / "assets" / "test-cases"
    ai_cases_root = assets_root / "ai-generated"
    runs_root = tmp_path / "runs"
    monkeypatch.setattr(workbench_facade.constants, "ASSETS_CASES_ROOT", assets_root)
    monkeypatch.setattr(workbench_facade.constants, "AI_CASES_ROOT", ai_cases_root)
    monkeypatch.setattr(workbench_facade.constants, "WEB_UI_RUNS_DIR", runs_root)
    monkeypatch.setattr(workbench_facade.store, "ensure_dirs", lambda: None)

    captured: dict[str, object] = {}

    def _fake_start_run(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {
            "run_id": "run-db-script",
            "status": "queued",
            "case_path": str(kwargs["case_path"]),
        }

    monkeypatch.setattr(workbench_facade.workbench_runtime_service, "start_run", _fake_start_run)

    response = WorkbenchFacade().run_case(
        payload=SimpleNamespace(project="mall", case_id="mall-web-login-auth-fn-ai-0201", source="manual", case_path=""),
        db=db_session,
    )

    assert response["item"]["run_id"] == "run-db-script"
    assert captured["runtime_case_script"] == script_code.strip()
    assert captured["case_path"] == (ai_cases_root / "mall-web-login-auth-fn-ai-0201.yaml").resolve()
    assert not (tmp_path / "missing-source.yaml").exists()


def test_update_script_refreshes_projection_from_script_code(db_session: Session) -> None:
    test_project_service.create_project(
        db_session,
        test_project_schema.TestProjectCreate(
            project_code="mall",
            project_name="Mall Platform",
        ),
    )
    case = test_case_service.create_test_case(
        db_session,
        test_case_schema.TestCaseCreate(
            project_code="mall",
            case_id="mall-web-login-auth-fn-ai-0101",
            name="脚本更新同步展示字段",
            page_code="login",
            product_line="商城",
            module="登录",
            script_code=(
                "id: mall-web-login-auth-fn-ai-0101\n"
                "title: 脚本更新同步展示字段\n"
                "precondition_state: 已登录\n"
                "expected_result: 页面跳转成功\n"
                "execution:\n"
                "  page: login\n"
                "  steps:\n"
                "    - action: click\n"
                "      target: login_button\n"
                "      target_name: 登录按钮\n"
                "      locator_type: role\n"
                "      locator_value: 登录\n"
                "      element_code: login_button\n"
                "      source_point_key: intent-01\n"
                "      intent_id: intent-01\n"
            ),
            test_steps=[{"action": "click", "target": "old_button"}],
            precondition_state="旧前置",
            expected_result="旧预期",
        ),
    )

    result_version = test_case_service.update_script(
        db_session,
        case.case_id,
        test_case_schema.TestCaseScriptUpdate(
            script_code=(
                "id: mall-web-login-auth-fn-ai-0101\n"
                "title: 脚本更新同步展示字段\n"
                "precondition_state: 已完成登录\n"
                "expected_result: 登录成功后进入首页\n"
                "execution:\n"
                "  page: login\n"
                "  steps:\n"
                "    - action: input\n"
                "      target: username_input\n"
                "      target_name: 用户名输入框\n"
                "      value: admin\n"
                "      locator_type: placeholder\n"
                "      locator_value: 请输入用户名\n"
                "    - action: click\n"
                "      target: login_button\n"
                "      target_name: 登录按钮\n"
                "      locator_type: role\n"
                "      locator_value: 登录\n"
                "      element_code: login_button\n"
                "      source_point_key: intent-01\n"
                "      intent_id: intent-01\n"
                "    - action: assert_count\n"
                "      target: element:login_error_message\n"
                "      element_code: login_error_message\n"
                "      count: 1\n"
                "      metric_rule: equals\n"
                "      rule: equals\n"
                "      extract_regex: \"错误(.+)\"\n"
                "      metric_label: 登录错误提示\n"
                "      source_point_key: intent-01\n"
            ),
            changed_by="qa-admin",
        ),
    )

    refreshed = test_case_service.get_test_case_detail(db_session, case.case_id).case
    assert result_version == 2
    assert str(refreshed.precondition_state) == "已完成登录"
    assert [str(step.get("action")) for step in refreshed.test_steps or []] == ["input", "click", "assert_count"]
    assert str(refreshed.test_steps_text).startswith("Step1")
    assert "登录成功后进入首页" in str(refreshed.expected_result)
    assert str((refreshed.test_steps or [])[1].get("element_code")) == "login_button"
    assert str((refreshed.test_steps or [])[1].get("source_point_key")) == "intent-01"
    assert str((refreshed.test_steps or [])[2].get("element_code")) == "login_error_message"
    assert str((refreshed.test_steps or [])[2].get("count")) == "1"
    assert str((refreshed.test_steps or [])[2].get("metric_rule")) == "equals"
    assert str((refreshed.test_steps or [])[2].get("rule")) == "equals"
    assert str((refreshed.test_steps or [])[2].get("extract_regex")) == "错误(.+)"
    assert str((refreshed.test_steps or [])[2].get("metric_label")) == "登录错误提示"
    assert str((refreshed.test_steps or [])[2].get("source_point_key")) == "intent-01"
    step_rows = (
        db_session.query(test_case_model.TestCaseStep)
        .filter_by(case_id=int(refreshed.id))
        .order_by(test_case_model.TestCaseStep.step_index.asc())
        .all()
    )
    assert len(step_rows) == 3
    assert str(step_rows[0].target) == "username_input"
    assert str(step_rows[0].locator_type) == "placeholder"
    assert str(step_rows[1].target) == "login_button"
    assert str(step_rows[2].target) == "element:login_error_message"
    assert str(step_rows[2].raw_payload.get("element_code")) == "login_error_message"
    assert str(step_rows[2].raw_payload.get("metric_rule")) == "equals"
    assert str(step_rows[2].raw_payload.get("source_point_key")) == "intent-01"




def test_upsert_workbench_case_blocked_when_project_inactive(
    db_session: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assets_root = tmp_path / "test-cases"
    ai_generated_root = assets_root / "ai-generated"
    ai_generated_root.mkdir(parents=True, exist_ok=True)
    case_id = "mall-web-ret-query-fn-ai-0001"
    source_path = ai_generated_root / f"{case_id}.yaml"
    source_path.write_text("id: mall-web-ret-query-fn-ai-0001\n", encoding="utf-8")
    monkeypatch.setattr(test_case_service, "ASSETS_CASES_ROOT", assets_root)

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

    with pytest.raises(HTTPException) as exc_info:
        test_case_service.upsert_test_case_from_workbench(
            db_session,
            project_code="mall",
            case_yaml={
                "id": case_id,
                "title": "workbench generated case",
                "module": "query",
                "execution": {"page": "ret", "steps": []},
            },
            source_path=str(source_path),
        )

    assert exc_info.value.status_code == 409
    assert "project is inactive" in str(exc_info.value.detail).lower()

def test_upsert_test_case_from_workbench_reuses_case_by_source_asset_and_intent(db_session: Session) -> None:
    existing = test_case_service.create_test_case(
        db_session,
        test_case_schema.TestCaseCreate(
            project_code="mall",
            case_id="mall-web-login-auth-fn-ai-0001",
            name="首次登录成功",
            product_line="login",
            module="login",
            page_code="login",
            priority="P0",
            test_type="ui",
            creator="qa",
            test_steps=[{"action": "click", "target": "login_button", "intent_id": "intent-01"}],
            script_code=(
                "version: v1\n"
                "id: mall-web-login-auth-fn-ai-0001\n"
                "project: mall\n"
                "module: login\n"
                "title: 首次登录成功\n"
                "requirement:\n"
                "  intent_id: intent-01\n"
                "  title: 首次登录成功\n"
                "  source_asset_id: mall-web-login-auth-fn-ai-0021\n"
                "execution:\n"
                "  page: login\n"
                "  selected_intent_ids:\n"
                "    - intent-01\n"
            ),
        ),
    )

    synchronized = test_case_service.upsert_test_case_from_workbench(
        db_session,
        project_code="mall",
        case_yaml={
            "id": "mall-web-login-auth-fn-ai-0003",
            "title": "首次登录成功-重新生成",
            "module": "login",
            "priority": "P0",
            "tags": ["ai-generated"],
            "requirement": {
                "intent_id": "intent-01",
                "title": "首次登录成功",
                "type": "functional",
                "source_asset_id": "mall-web-login-auth-fn-ai-0021",
            },
            "execution": {
                "page": "login",
                "selected_intent_ids": ["intent-01"],
                "steps": [{"action": "click", "target": "login_button"}],
            },
        },
        source_path="/tmp/mall-web-login-auth-fn-ai-0003.yaml",
    )

    assert synchronized.id == existing.id
    assert synchronized.case_id == "mall-web-login-auth-fn-ai-0001"
    assert synchronized.name == "首次登录成功-重新生成"
    assert db_session.query(test_case_model.TestCase).count() == 1
    assert "id: mall-web-login-auth-fn-ai-0001" in synchronized.script_code


def test_update_project_updates_name_description_and_status(db_session: Session) -> None:
    test_project_service.create_project(
        db_session,
        test_project_schema.TestProjectCreate(
            project_code="mall",
            project_name="Mall Platform",
        ),
    )

    updated = test_project_service.update_project(
        db_session,
        "mall",
        test_project_schema.TestProjectUpdate(
            project_name="Mall Commerce",
            description="商城主项目",
            status="inactive",
        ),
    )

    assert updated.project_code == "mall"
    assert updated.project_name == "Mall Commerce"
    assert updated.description == "商城主项目"
    assert updated.status == "inactive"


def test_update_project_is_idempotent_when_payload_same(db_session: Session) -> None:
    test_project_service.create_project(
        db_session,
        test_project_schema.TestProjectCreate(
            project_code="mall",
            project_name="Mall Platform",
            description="商城项目",
        ),
    )
    unchanged = test_project_service.update_project(
        db_session,
        "mall",
        test_project_schema.TestProjectUpdate(
            project_name="Mall Platform",
            description="商城项目",
            status="active",
        ),
    )

    assert unchanged.project_code == "mall"
    assert unchanged.project_name == "Mall Platform"
    assert unchanged.description == "商城项目"
    assert unchanged.status == "active"
