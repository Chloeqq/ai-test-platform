from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import Base
from app.models.page_object import PageElement, PageObject
from app.services import test_case_service


@pytest.fixture()
def db_session() -> Iterator[Session]:
    engine = create_engine("sqlite:///:memory:", future=True)
    testing_session = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)
    Base.metadata.create_all(bind=engine)
    session = testing_session()
    try:
        yield session
    finally:
        session.close()


def _create_login_page_object(db: Session) -> None:
    page_object = PageObject(
        project_code="mall",
        client="web",
        page_code="login",
        page_name="登录页",
        page_url="http://localhost:5174/#/login",
        status="published",
        governance_status="approved",
    )
    db.add(page_object)
    db.flush()
    db.add_all(
        [
            PageElement(
                page_object_id=page_object.id,
                element_code="username_input",
                element_name="用户名输入框",
                locator_type="placeholder",
                locator_value="请输入用户名",
                business_type="input",
                role="textbox",
            ),
            PageElement(
                page_object_id=page_object.id,
                element_code="password_input",
                element_name="密码输入框",
                locator_type="placeholder",
                locator_value="请输入密码",
                business_type="input",
                role="textbox",
            ),
            PageElement(
                page_object_id=page_object.id,
                element_code="login_button",
                element_name="登录按钮",
                locator_type="role",
                locator_value="登录",
                business_type="button",
                role="button",
            ),
        ]
    )
    db.commit()


def test_login_step_repair_does_not_generate_default_credentials(db_session: Session) -> None:
    _create_login_page_object(db_session)

    repaired_steps = test_case_service._repair_execution_steps_for_storage(
        db_session,
        project_code="mall",
        client="web",
        page_code="login",
        scenario_context_text="首次登录成功，输入正确账号密码后进入工作台首页",
        steps=[
            {"action": "input", "target": "element:username_input", "value": ""},
            {"action": "input", "target": "element:password_input", "value": ""},
            {"action": "click", "target": "element:login_button"},
        ],
    )

    assert repaired_steps[0]["target"] == "element:username_input"
    assert repaired_steps[1]["target"] == "element:password_input"
    assert "value" not in repaired_steps[0]
    assert "value" not in repaired_steps[1]
    assert "test001" not in str(repaired_steps)
    assert "123456" not in str(repaired_steps)
