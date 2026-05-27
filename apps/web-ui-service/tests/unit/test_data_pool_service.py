from __future__ import annotations

from collections.abc import Iterator

from fastapi import HTTPException
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import Base
import app.models.test_case  # noqa: F401
import app.models.test_data_pool  # noqa: F401
import app.models.test_project  # noqa: F401
import app.schemas.test_case as test_case_schema
import app.schemas.test_project as test_project_schema
from app.services import test_case_service, test_data_pool_service, test_project_service


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


def test_data_pool_item_delete_blocked_when_referenced(db_session: Session) -> None:
    test_project_service.create_project(
        db_session,
        test_project_schema.TestProjectCreate(project_code="mall", project_name="Mall Platform"),
    )
    test_data_pool_service.create_data_pool(
        db_session,
        pool_name="login_credentials",
        description="登录凭据池",
        status_value="active",
        created_by="qa-admin",
    )
    test_data_pool_service.upsert_data_pool_item(
        db_session,
        pool_name="login_credentials",
        item_key="login_password_valid",
        item_value="macro",
        status_value="active",
        changed_by="qa-admin",
        note="seed",
    )
    test_case_service.create_test_case(
        db_session,
        test_case_schema.TestCaseCreate(
            project_code="mall",
            case_id="mall-web-login-auth-fn-ai-0099",
            name="引用数据池凭据",
            page_code="login",
            product_line="商城",
            module="登录",
            script_code=(
                "id: mall-web-login-auth-fn-ai-0099\n"
                "title: 引用数据池凭据\n"
                "tags:\n"
                "  - ai-generated\n"
                "requirement:\n"
                "  source_asset_id: mall-web-login-auth-fn-ai-0021\n"
                "  intent_id: intent-01\n"
                "execution:\n"
                "  page: login\n"
                "  selected_intent_ids:\n"
                "    - intent-01\n"
                "  steps:\n"
                "    - action: input\n"
                "      target: element:password_input\n"
                "      value: \"{{login_password}}\"\n"
                "data:\n"
                "  login_password:\n"
                "    source_type: pool\n"
                "    pool_name: login_credentials\n"
                "    key: login_password_valid\n"
            ),
        ),
    )
    with pytest.raises(HTTPException) as exc_info:
        test_data_pool_service.delete_data_pool_item(
            db_session,
            pool_name="login_credentials",
            item_key="login_password_valid",
            changed_by="qa-admin",
            note="cleanup",
        )
    assert exc_info.value.status_code == 409
    detail = exc_info.value.detail
    assert isinstance(detail, dict)
    assert detail.get("code") == "data_pool_key_in_use"
    assert any(str(item.get("case_id")) == "mall-web-login-auth-fn-ai-0099" for item in detail.get("references", []))


def test_serialize_runner_data_pool_snapshot_only_keeps_active_records(db_session: Session) -> None:
    test_data_pool_service.create_data_pool(
        db_session,
        pool_name="login_credentials",
        description="登录凭据池",
        status_value="active",
        created_by="qa-admin",
    )
    test_data_pool_service.create_data_pool(
        db_session,
        pool_name="legacy_pool",
        description="旧池",
        status_value="inactive",
        created_by="qa-admin",
    )
    test_data_pool_service.upsert_data_pool_item(
        db_session,
        pool_name="login_credentials",
        item_key="login_account_valid",
        item_value="admin",
        status_value="active",
        changed_by="qa-admin",
        note="seed",
    )
    test_data_pool_service.upsert_data_pool_item(
        db_session,
        pool_name="login_credentials",
        item_key="login_account_disabled",
        item_value="disabled",
        status_value="inactive",
        changed_by="qa-admin",
        note="seed",
    )
    test_data_pool_service.upsert_data_pool_item(
        db_session,
        pool_name="legacy_pool",
        item_key="legacy_key",
        item_value="legacy",
        status_value="active",
        changed_by="qa-admin",
        note="seed",
    )
    snapshot_json = test_data_pool_service.serialize_runner_data_pool_snapshot(db_session)
    assert snapshot_json == '{"login_credentials": {"login_account_valid": "admin"}}'


def test_data_pool_rejects_invalid_status_value(db_session: Session) -> None:
    with pytest.raises(HTTPException) as exc_info:
        test_data_pool_service.create_data_pool(
            db_session,
            pool_name="invalid_status_pool",
            description="invalid",
            status_value="enabled",
            created_by="qa-admin",
        )
    assert exc_info.value.status_code == 422
    detail = exc_info.value.detail
    assert isinstance(detail, dict)
    assert detail.get("code") == "data_pool_invalid_status"


def test_list_pool_items_masks_item_value_by_default(db_session: Session) -> None:
    test_data_pool_service.create_data_pool(
        db_session,
        pool_name="login_credentials",
        description="登录凭据池",
        status_value="active",
        created_by="qa-admin",
    )
    test_data_pool_service.upsert_data_pool_item(
        db_session,
        pool_name="login_credentials",
        item_key="login_password_valid",
        item_value="macro",
        status_value="active",
        changed_by="qa-admin",
        note="seed",
    )
    masked = test_data_pool_service.list_data_pool_items(
        db_session,
        pool_name="login_credentials",
        reveal_secret=False,
    )
    assert masked[0]["item_value"] == ""
    assert masked[0]["has_value"] is True
    assert "***" in str(masked[0]["item_value_preview"])
    revealed = test_data_pool_service.list_data_pool_items(
        db_session,
        pool_name="login_credentials",
        reveal_secret=True,
    )
    assert revealed[0]["item_value"] == "macro"
