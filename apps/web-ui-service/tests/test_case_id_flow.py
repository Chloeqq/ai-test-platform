from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from fastapi import HTTPException
import pytest
from shared_backend.case_ids import match_case_id
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import Base
import app.models.page_object as page_object_model  # noqa: F401
import app.models.test_case as test_case_model
import app.models.test_project  # noqa: F401
import app.models.workbench_state as workbench_state_model  # noqa: F401
import app.schemas.test_case as test_case_schema
import app.schemas.test_project as test_project_schema
from app.services import (
    test_case_bootstrap_service,
    test_case_service,
    test_project_service,
    workbench_project_service,
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


def test_create_test_case_generates_shared_backend_case_id(db_session: Session) -> None:
    case = test_case_service.create_test_case(
        db_session,
        test_case_schema.TestCaseCreate(
            name="退货查询基础校验",
            product_line="退货",
            module="查询",
            priority="P1",
            test_type="ui",
            tags=["smoke", "ai-generated"],
            creator="qa",
            script_code="def test_return_query(page):\n    assert True\n",
        ),
    )

    assert case.case_id
    assert case.case_id == case.case_id.lower()
    assert match_case_id(case.case_id)
    assert case.project_code == "atp"
    assert case.client == "web"


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
        page_url="http://localhost:5173/#/login",
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


def test_get_detail_repairs_login_like_steps_when_page_code_is_not_login(db_session: Session) -> None:
    page_object = page_object_model.PageObject(
        project_code="atp",
        client="web",
        page_code="login",
        page_name="登录页",
        page_url="http://localhost:5173/#/login",
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


def test_update_test_case_blocked_when_target_project_inactive(db_session: Session) -> None:
    case = test_case_service.create_test_case(
        db_session,
        test_case_schema.TestCaseCreate(
            project_code="atp",
            name="默认项目草稿",
            product_line="平台",
            module="回归",
            script_code="def test_atp_case(page):\n    assert True\n",
        ),
    )
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
        test_case_service.update_test_case(
            db_session,
            case.case_id,
            test_case_schema.TestCaseUpdate(project_code="mall"),
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


def test_list_test_cases_supports_source_filter_and_source_search_token(db_session: Session) -> None:
    ai_case = test_case_service.create_test_case(
        db_session,
        test_case_schema.TestCaseCreate(
            source="ai",
            name="AI 生成退货查询",
            product_line="退货",
            module="查询",
            priority="P1",
            test_type="ui",
            tags=["ai-generated", "smoke"],
            creator="qa",
            script_code="def test_case_ai(page):\n    assert True\n",
        ),
    )
    test_case_service.create_test_case(
        db_session,
        test_case_schema.TestCaseCreate(
            source="mn",
            name="人工编写退货查询",
            product_line="退货",
            module="查询",
            priority="P2",
            test_type="ui",
            tags=["manual"],
            creator="qa",
            script_code="def test_case_manual(page):\n    assert True\n",
        ),
    )

    filtered_by_source = test_case_service.list_test_cases(
        db_session,
        q="",
        project_code="atp",
        source="ai",
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
    filtered_by_query = test_case_service.list_test_cases(
        db_session,
        q="来源:AI",
        project_code="atp",
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

    assert [item.case_id for item in filtered_by_source.cases] == [ai_case.case_id]
    assert [item.case_id for item in filtered_by_query.cases] == [ai_case.case_id]
    assert filtered_by_query.search_context["source"] == "ai"


def test_list_test_cases_returns_stats_for_dashboard_cards(db_session: Session) -> None:
    case_passed = test_case_service.create_test_case(
        db_session,
        test_case_schema.TestCaseCreate(
            source="ai",
            name="统计卡片-通过场景",
            product_line="退货",
            module="查询",
            priority="P1",
            test_type="ui",
            tags=["smoke"],
            creator="qa",
            script_code="def test_case_passed(page):\n    assert True\n",
        ),
    )
    case_failed = test_case_service.create_test_case(
        db_session,
        test_case_schema.TestCaseCreate(
            source="mn",
            name="统计卡片-失败场景",
            product_line="退货",
            module="查询",
            priority="P1",
            test_type="ui",
            tags=["regression"],
            creator="qa",
            script_code="def test_case_failed(page):\n    assert True\n",
        ),
    )
    case_skipped = test_case_service.create_test_case(
        db_session,
        test_case_schema.TestCaseCreate(
            source="cv",
            name="统计卡片-跳过场景",
            product_line="退货",
            module="查询",
            priority="P2",
            test_type="ui",
            tags=["review"],
            creator="qa",
            script_code="def test_case_skipped(page):\n    assert True\n",
        ),
    )

    case_passed.last_execution_result = "passed"
    case_passed.automation_status = "automated"
    case_failed.last_execution_result = "failed"
    case_failed.automation_status = "manual"
    case_skipped.last_execution_result = "skipped"
    case_skipped.automation_status = "automated"
    db_session.add_all([case_passed, case_failed, case_skipped])
    db_session.commit()

    result = test_case_service.list_test_cases(
        db_session,
        q="统计卡片",
        project_code="atp",
        source="",
        tag="",
        priority="",
        status="",
        creator="",
        last_result="",
        product_line="",
        module="",
        test_type="",
        sort_field="updated_at",
        sort_order="desc",
        page=1,
        page_size=20,
    )

    assert result.stats["total"] == 3
    assert result.stats["passed"] == 1
    assert result.stats["failed"] == 1
    assert result.stats["skipped"] == 1
    assert result.stats["automated"] == 2
    assert result.stats["pass_rate"] == 33.3
    assert result.stats["automation_rate"] == 66.7


def test_list_test_cases_supports_multi_priority_filter(db_session: Session) -> None:
    case_p0 = test_case_service.create_test_case(
        db_session,
        test_case_schema.TestCaseCreate(
            name="优先级筛选-P0",
            product_line="退货",
            module="查询",
            priority="P0",
            test_type="ui",
            tags=["smoke"],
            creator="qa",
            script_code="def test_case_p0(page):\n    assert True\n",
        ),
    )
    case_p1 = test_case_service.create_test_case(
        db_session,
        test_case_schema.TestCaseCreate(
            name="优先级筛选-P1",
            product_line="退货",
            module="查询",
            priority="P1",
            test_type="ui",
            tags=["smoke"],
            creator="qa",
            script_code="def test_case_p1(page):\n    assert True\n",
        ),
    )
    test_case_service.create_test_case(
        db_session,
        test_case_schema.TestCaseCreate(
            name="优先级筛选-P2",
            product_line="退货",
            module="查询",
            priority="P2",
            test_type="ui",
            tags=["smoke"],
            creator="qa",
            script_code="def test_case_p2(page):\n    assert True\n",
        ),
    )

    result = test_case_service.list_test_cases(
        db_session,
        q="优先级筛选",
        project_code="atp",
        source="",
        tag="",
        priority="P0,P1",
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

    case_ids = [item.id for item in result.cases]
    assert case_p0.id in case_ids
    assert case_p1.id in case_ids
    assert result.search_context["priority"] == "P0,P1"


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


def test_workbench_project_codes_merge_master_data_and_legacy_state(
    db_session: Session,
    tmp_path: Path,
) -> None:
    test_project_service.create_project(
        db_session,
        test_project_schema.TestProjectCreate(
            project_code="mall",
            project_name="Mall Platform",
        ),
    )
    state_root = tmp_path / "test-points"
    (state_root / "default").mkdir(parents=True)
    (state_root / "legacyproj").mkdir(parents=True)

    items = workbench_project_service.list_project_codes(db_session, state_root=state_root)

    assert items[0] == "atp"
    assert "mall" in items
    assert "default" in items
    assert "legacyproj" in items


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


def test_delete_project_blocks_when_cases_exist(db_session: Session) -> None:
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
            name="商城项目查询",
            product_line="商城",
            module="查询",
            script_code="def test_mall_case(page):\n    assert True\n",
        ),
    )

    with pytest.raises(HTTPException) as exc_info:
        test_project_service.delete_project(db_session, "mall")

    assert exc_info.value.status_code == 409


def test_delete_project_blocks_when_workbench_runtime_refs_exist(db_session: Session) -> None:
    test_project_service.create_project(
        db_session,
        test_project_schema.TestProjectCreate(
            project_code="mall",
            project_name="Mall Platform",
        ),
    )
    db_session.add(
        workbench_state_model.WorkbenchRuntimeRun(
            run_id="run-mall-001",
            project="mall",
            page="order",
            status="running",
            payload={},
        )
    )
    db_session.commit()

    with pytest.raises(HTTPException) as exc_info:
        test_project_service.delete_project(db_session, "mall")

    assert exc_info.value.status_code == 409


def test_delete_project_blocks_when_state_dir_exists(db_session: Session, tmp_path: Path) -> None:
    test_project_service.create_project(
        db_session,
        test_project_schema.TestProjectCreate(
            project_code="mall",
            project_name="Mall Platform",
        ),
    )
    state_root = tmp_path / "test-points"
    project_dir = state_root / "mall"
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "mall-web-order-query-sm-ai-0001.json").write_text("{}", encoding="utf-8")

    with pytest.raises(HTTPException) as exc_info:
        test_project_service.delete_project(db_session, "mall", state_root=state_root)

    assert exc_info.value.status_code == 409


def test_delete_project_protects_default_project(db_session: Session) -> None:
    with pytest.raises(HTTPException) as exc_info:
        test_project_service.delete_project(db_session, "atp")

    assert exc_info.value.status_code == 400


def test_delete_project_removes_unused_project(db_session: Session) -> None:
    test_project_service.create_project(
        db_session,
        test_project_schema.TestProjectCreate(
            project_code="mall",
            project_name="Mall Platform",
        ),
    )

    deleted_code = test_project_service.delete_project(db_session, "mall")
    project_codes = [item.project_code for item in test_project_service.list_projects(db_session)]

    assert deleted_code == "mall"
    assert "mall" not in project_codes
