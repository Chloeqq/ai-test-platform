from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from fastapi import HTTPException
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.api.workbench.facade import _persist_runtime_run_to_case_center
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


def test_get_detail_accepts_business_case_id(db_session: Session) -> None:
    case = test_case_service.create_test_case(
        db_session,
        test_case_schema.TestCaseCreate(
            case_id="ATP-WEB-RET-QUERY-SM-AI-9999",
            name="退货查询冒烟校验",
            product_line="退货",
            module="查询",
            priority="P0",
            test_type="ui",
            tags=["smoke", "ai-generated"],
            creator="qa",
            script_code="def test_return_query_smoke(page):\n    assert True\n",
        ),
    )

    detail_by_case_id = test_case_service.get_test_case_detail(db_session, case.case_id)
    detail_by_internal_id = test_case_service.get_test_case_detail(db_session, str(case.id))

    assert detail_by_case_id.case.id == case.id
    assert detail_by_case_id.case.case_id == "atp-web-ret-query-sm-ai-9999"
    assert detail_by_internal_id.case.id == case.id


def test_persist_runtime_run_to_case_center_does_not_fall_back_to_other_project_case(db_session: Session) -> None:
    test_case_service.create_test_case(
        db_session,
        test_case_schema.TestCaseCreate(
            case_id="mall-web-login-auth-fn-ai-0001",
            project_code="atp",
            name="登录成功",
            product_line="登录",
            module="认证",
            priority="P0",
            test_type="ui",
            creator="qa",
            script_code="def test_login_success(page):\n    assert True\n",
        ),
    )

    result = _persist_runtime_run_to_case_center(
        db_session,
        {
            "run_id": "run-001",
            "case_id": "mall-web-login-auth-fn-ai-0001",
            "project": "mall",
            "status": "passed",
            "started_at": "2026-05-21T10:00:00+00:00",
            "finished_at": "2026-05-21T10:01:00+00:00",
            "execution_record": {"status": "passed", "finished_at": "2026-05-21T10:01:00+00:00"},
        },
    )

    assert result is None
    executions = db_session.execute(select(test_case_model.TestCaseExecution)).scalars().all()
    assert executions == []


def test_get_detail_includes_project_status(db_session: Session) -> None:
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
            name="商城详情治理校验",
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

    detail = test_case_service.get_test_case_detail(db_session, str(case.id))

    assert detail.case.id == case.id
    assert detail.project_status == "inactive"


def test_get_detail_repairs_legacy_login_steps_and_sanitizes_script(db_session: Session) -> None:
    page_object = page_object_model.PageObject(
        project_code="atp",
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
                element_code="login-role---1",
                element_name="用户名输入框",
                locator_type="role",
                locator_value="请输入用户名",
                role="username",
                owner="qa",
            ),
            page_object_model.PageElement(
                page_object_id=page_object.id,
                element_code="login-role---2",
                element_name="密码输入框",
                locator_type="role",
                locator_value="请输入密码",
                role="password",
                owner="qa",
            ),
            page_object_model.PageElement(
                page_object_id=page_object.id,
                element_code="login-role---4",
                element_name="登录按钮",
                locator_type="role",
                locator_value="登录",
                role="button",
                owner="qa",
            ),
        ]
    )
    db_session.commit()

    case = test_case_service.create_test_case(
        db_session,
        test_case_schema.TestCaseCreate(
            case_id="atp-web-login-auth-fn-ai-0098",
            project_code="atp",
            page_code="login",
            name="登录页历史脏步骤修复",
            product_line="认证中心",
            module="登录",
            priority="P0",
            test_type="ui",
            creator="qa",
            expected_result="系统应给出符合业务规则的反馈。",
            script_code=(
                "id: atp-web-login-auth-fn-ai-0098\n"
                "title: 登录页历史脏步骤修复\n"
                "module: login\n"
                "requirement:\n"
                "  - 登录功能：\n"
                "  - 登录功能：\n"
                "  - source-01\n"
                "  - 用户名为空点击登录提示不能为空\n"
                "execution:\n"
                "  page: login\n"
                "  steps: []\n"
            ),
            test_steps=[
                {
                    "action": "custom_step",
                    "description": "在用户名输入框输入test001",
                    "target": "element:login-role---1",
                    "locator_type": "role",
                    "locator_value": "请输入用户名",
                    "value": "test001",
                },
                {
                    "action": "custom_step",
                    "description": "在密码输入框输入123456",
                    "target": "element:login-role---1",
                    "locator_type": "role",
                    "locator_value": "请输入用户名",
                    "value": "123456",
                },
                {
                    "action": "custom_step",
                    "description": "点击登录按钮",
                    "target": "element:login-role---1",
                    "locator_type": "role",
                    "locator_value": "请输入用户名",
                },
            ],
        ),
    )

    detail = test_case_service.get_test_case_detail(db_session, str(case.id))
    repaired = detail.case.test_steps if isinstance(detail.case.test_steps, list) else []

    assert [str(item.get("action")) for item in repaired] == ["input", "input", "click"]
    assert [str(item.get("target")) for item in repaired] == [
        "element:login-role---1",
        "element:login-role---2",
        "element:login-role---4",
    ]
    assert [str(item.get("target_name")) for item in repaired] == [
        "用户名输入框",
        "密码输入框",
        "登录按钮",
    ]
    assert "系统应给出符合业务规则的反馈" not in str(detail.case.expected_result or "")
    assert "source-01" not in str(detail.case.script_code or "")
    assert str(detail.case.script_code or "").count("用户名为空点击登录提示不能为空") == 1

    step_rows = (
        db_session.query(test_case_model.TestCaseStep)
        .filter_by(case_id=int(case.id))
        .order_by(test_case_model.TestCaseStep.step_index.asc())
        .all()
    )
    assert len(step_rows) == 3
    assert "username" in str(step_rows[0].locator_value)
    assert "password" in str(step_rows[1].locator_value)
    assert str(step_rows[2].locator_value) == "登录"


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
                    "value": "test001",
                },
                {
                    "action": "input",
                    "description": "input remember_password_checkbox 123456",
                    "target": "element:remember_password_checkbox",
                    "locator_type": "id",
                    "locator_value": "remember-password",
                    "value": "123456",
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
    repaired = detail.case.test_steps if isinstance(detail.case.test_steps, list) else []

    assert [str(item.get("target")) for item in repaired] == [
        "element:username_input",
        "element:password_input",
        "element:login_button",
    ]
    assert str(repaired[1].get("target_name")) == "密码输入框"
    assert str(repaired[1].get("locator_value")) != "remember-password"
    assert "登录失败" not in str(repaired[2].get("expected_result"))


def test_get_detail_repairs_login_like_steps_when_page_code_is_not_login(db_session: Session) -> None:
    page_object = page_object_model.PageObject(
        project_code="atp",
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
                element_code="login-role---1",
                element_name="用户名输入框",
                locator_type="role",
                locator_value="请输入用户名",
                role="username",
                owner="qa",
            ),
            page_object_model.PageElement(
                page_object_id=page_object.id,
                element_code="login-role---2",
                element_name="密码输入框",
                locator_type="role",
                locator_value="请输入密码",
                role="password",
                owner="qa",
            ),
            page_object_model.PageElement(
                page_object_id=page_object.id,
                element_code="login-role---4",
                element_name="登录按钮",
                locator_type="role",
                locator_value="登录",
                role="button",
                owner="qa",
            ),
        ]
    )
    db_session.commit()

    case = test_case_service.create_test_case(
        db_session,
        test_case_schema.TestCaseCreate(
            case_id="atp-web-prod-list-fn-ai-0999",
            project_code="atp",
            page_code="prod",
            name="登录语义修复-跨页面编码",
            product_line="商品",
            module="列表",
            priority="P1",
            test_type="ui",
            creator="qa",
            script_code="def test_login_like_case(page):\n    assert True\n",
            test_steps=[
                {
                    "action": "custom_step",
                    "description": "输入用户名 test001",
                    "target": "element:login-role---1",
                    "locator_type": "role",
                    "locator_value": "请输入用户名",
                    "value": "test001",
                },
                {
                    "action": "custom_step",
                    "description": "输入密码 123456",
                    "target": "element:login-role---1",
                    "locator_type": "role",
                    "locator_value": "请输入用户名",
                    "value": "123456",
                },
                {
                    "action": "custom_step",
                    "description": "点击登录按钮",
                    "target": "element:login-role---1",
                    "locator_type": "role",
                    "locator_value": "请输入用户名",
                },
            ],
        ),
    )

    detail = test_case_service.get_test_case_detail(db_session, str(case.id))
    repaired = detail.case.test_steps if isinstance(detail.case.test_steps, list) else []

    assert [str(item.get("action")) for item in repaired] == ["input", "input", "click"]
    assert [str(item.get("target")) for item in repaired] == [
        "element:login-role---1",
        "element:login-role---2",
        "element:login-role---4",
    ]


def test_batch_status_update_accepts_case_ids(db_session: Session) -> None:
    case = test_case_service.create_test_case(
        db_session,
        test_case_schema.TestCaseCreate(
            name="退货列表回归校验",
            product_line="退货",
            module="列表",
            priority="P1",
            test_type="ui",
            tags=["regression"],
            creator="qa",
            script_code="def test_return_list(page):\n    assert True\n",
        ),
    )

    updated_count = test_case_service.batch_update_test_case_status(
        db_session,
        test_case_schema.BatchStatusUpdatePayload(case_ids=[case.case_id], status="deprecated"),
    )
    refreshed = db_session.get(test_case_model.TestCase, case.id)

    assert updated_count == 1
    assert refreshed is not None
    assert refreshed.status == "deprecated"


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


def test_create_project_and_filter_cases_by_project_code(db_session: Session) -> None:
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
            project_code="atp",
            name="退货查询 ATP 冒烟",
            product_line="退货",
            module="查询",
            priority="P1",
            test_type="ui",
            tags=["smoke"],
            creator="qa",
            script_code="def test_case_atp(page):\n    assert True\n",
        ),
    )
    mall_case = test_case_service.create_test_case(
        db_session,
        test_case_schema.TestCaseCreate(
            project_code="mall",
            name="退货查询 Mall 冒烟",
            product_line="退货",
            module="查询",
            priority="P1",
            test_type="ui",
            tags=["smoke"],
            creator="qa",
            script_code="def test_case_mall(page):\n    assert True\n",
        ),
    )

    result = test_case_service.list_test_cases(
        db_session,
        q="",
        project_code="mall",
        source="",
        tag="",
        priority="",
        status="",
        creator="",
        last_result="",
        product_line="",
        module="",
        test_type="",
        sort_field="case_id",
        sort_order="asc",
        page=1,
        page_size=20,
    )

    assert [item.case_id for item in result.cases] == [mall_case.case_id]
    assert "mall" in result.filters["project_codes"]


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


def test_upsert_workbench_case_allows_self_asset_case_id_without_conflict(
    db_session: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assets_root = tmp_path / "test-cases"
    ai_generated_root = assets_root / "ai-generated"
    ai_generated_root.mkdir(parents=True, exist_ok=True)
    case_id = "atp-web-ret-query-fn-ai-0001"
    source_path = ai_generated_root / f"{case_id}.yaml"
    source_path.write_text(
        "id: atp-web-ret-query-fn-ai-0001\n"
        "title: workbench generated case\n"
        "module: query\n"
        "priority: P1\n"
        "tags:\n"
        "  - ai-generated\n"
        "execution:\n"
        "  page: ret\n"
        "  steps:\n"
        "    - action: click\n"
        "      target: query_button\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(test_case_service, "ASSETS_CASES_ROOT", assets_root)

    created = test_case_service.upsert_test_case_from_workbench(
        db_session,
        project_code="atp",
        case_yaml={
            "id": case_id,
            "title": "workbench generated case",
            "module": "query",
            "priority": "P1",
            "tags": ["ai-generated"],
            "execution": {
                "page": "ret",
                "steps": [{"action": "click", "target": "query_button"}],
            },
        },
        source_path=str(source_path),
    )

    assert created.case_id == case_id


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


def test_upsert_test_case_from_workbench_creates_and_updates_case(db_session: Session) -> None:
    case_yaml = {
        "id": "mall-web-ret-query-sm-ai-0001",
        "title": "退货申请页-订单查询-输入有效订单号-点击查询-展示订单信息",
        "module": "query",
        "priority": "P1",
        "tags": ["ai-generated", "smoke"],
        "requirement": ["验证退货申请页订单查询主流程"],
        "description": "AI 生成的退货查询草稿",
        "execution": {
            "page": "returnapply",
            "runner": "playwright",
            "steps": [
                {"action": "goto", "target": "returnapply_page"},
                {"action": "fill", "target": "order_no", "value": "1001"},
                {"action": "assert_visible", "target": "order_card", "expected": "展示订单信息"},
            ],
        },
    }

    created = test_case_service.upsert_test_case_from_workbench(
        db_session,
        project_code="mall",
        case_yaml=case_yaml,
        source_path="/tmp/mall-web-ret-query-sm-ai-0001.yaml",
    )

    case_yaml["title"] = "退货申请页-订单查询-输入历史订单号-点击查询-展示订单信息"
    updated = test_case_service.upsert_test_case_from_workbench(
        db_session,
        project_code="mall",
        case_yaml=case_yaml,
        source_path="/tmp/mall-web-ret-query-sm-ai-0001.yaml",
    )
    version_count = db_session.query(test_case_model.TestCaseVersion).filter_by(case_id=created.id).count()

    assert created.case_id == "mall-web-ret-query-sm-ai-0001"
    assert created.project_code == "mall"
    assert created.created_source == "ai"
    assert created.source_ref == "/tmp/mall-web-ret-query-sm-ai-0001.yaml"
    assert "title: " in created.script_code
    assert updated.id == created.id
    assert updated.name == "退货申请页-订单查询-输入历史订单号-点击查询-展示订单信息"
    assert version_count == 2


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
