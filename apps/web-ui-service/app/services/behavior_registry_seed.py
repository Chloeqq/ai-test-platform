"""Phase 0: Seed login page behavior registry + assertion templates."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.repositories.behavior_registry_repository import BehaviorRegistryRepository


def seed_login_behaviors(db: Session) -> None:
    """为 login 页面创建 4 个 behavior + 对应断言模板。幂等，可重复执行。"""
    repo = BehaviorRegistryRepository(db)

    # ---- Behavior 1: 登录成功 ----
    b1 = repo.upsert_behavior(
        behavior_code="AUTH_LOGIN_SUCCESS",
        intent_type="AUTH_LOGIN",
        scenario="positive",
        scope="page",
        page_code="login",
        domain="auth",
        version=1,
        status="active",
        priority=1,
        label="认证成功并跳转到首页",
        capabilities=["SESSION_CREATED", "PAGE_REDIRECTED", "TOKEN_STORED"],
    )
    _seed_templates(repo, b1.id, [
        # PAGE_REDIRECTED
        {"capability": "PAGE_REDIRECTED", "execution_layer": "ui",
         "action": "assert_url", "value": "{{home_url}}", "operator": "eq",
         "variable_schema": {"home_url": "env"},
         "description": "验证跳转到首页"},
        # TOKEN_STORED
        {"capability": "TOKEN_STORED", "execution_layer": "ui",
         "action": "assert_visible", "target": "dashboard", "operator": "exists",
         "description": "验证首页元素可见"},
        # SESSION_CREATED
        {"capability": "SESSION_CREATED", "execution_layer": "database",
         "action": "db_exists", "target": "sessions",
         "value": "{{user_id}}", "operator": "exists",
         "variable_schema": {"user_id": "runtime"},
         "description": "验证 session 已创建"},
    ])

    # ---- Behavior 2: 登录失败 ----
    b2 = repo.upsert_behavior(
        behavior_code="AUTH_LOGIN_FAILED",
        intent_type="AUTH_LOGIN",
        scenario="negative",
        scope="page",
        page_code="login",
        domain="auth",
        version=1,
        status="active",
        priority=1,
        label="认证失败显示错误提示",
        capabilities=["ERROR_DISPLAYED", "SESSION_NOT_CREATED"],
    )
    _seed_templates(repo, b2.id, [
        # ERROR_DISPLAYED
        {"capability": "ERROR_DISPLAYED", "execution_layer": "ui",
         "action": "assert_text", "target": "error-toast", "operator": "not_empty",
         "description": "验证错误提示出现"},
        {"capability": "ERROR_DISPLAYED", "execution_layer": "ui",
         "action": "assert_visible", "target": "login-page", "operator": "exists",
         "description": "验证未离开登录页"},
        # SESSION_NOT_CREATED
        {"capability": "SESSION_NOT_CREATED", "execution_layer": "database",
         "action": "db_not_exists", "target": "sessions",
         "value": "{{user_id}}", "operator": "exists",
         "variable_schema": {"user_id": "runtime"},
         "description": "验证未创建 session"},
    ])

    # ---- Behavior 3: 输入校验触发 ----
    b3 = repo.upsert_behavior(
        behavior_code="AUTH_INPUT_INVALID",
        intent_type="INPUT_VALIDATION",
        scenario="negative",
        scope="page",
        page_code="login",
        domain="auth",
        version=1,
        status="active",
        priority=1,
        label="输入校验被触发",
        capabilities=["ERROR_DISPLAYED"],
    )
    _seed_templates(repo, b3.id, [
        {"capability": "ERROR_DISPLAYED", "execution_layer": "ui",
         "action": "assert_text", "target": "error-toast", "operator": "not_empty",
         "description": "验证校验提示出现"},
        {"capability": "ERROR_DISPLAYED", "execution_layer": "ui",
         "action": "assert_visible", "target": "login-page", "operator": "exists",
         "description": "验证未离开登录页"},
    ])

    # ---- Behavior 4: 未登录拦截 ----
    b4 = repo.upsert_behavior(
        behavior_code="AUTH_ACCESS_BLOCKED",
        intent_type="AUTH_ACCESS",
        scenario="negative",
        scope="page",
        page_code="login",
        domain="auth",
        version=1,
        status="active",
        priority=1,
        label="未登录访问被拦截",
        capabilities=["PAGE_REDIRECTED"],
    )
    _seed_templates(repo, b4.id, [
        {"capability": "PAGE_REDIRECTED", "execution_layer": "ui",
         "action": "assert_url", "value": "#/login", "operator": "eq",
         "description": "验证跳转到登录页"},
    ])

    # ---- Behavior 5: 会话保持 (领域通用) ----
    b5 = repo.upsert_behavior(
        behavior_code="AUTH_SESSION_PERSISTED",
        intent_type="AUTH_SESSION",
        scenario="positive",
        scope="domain",
        page_code="",
        domain="auth",
        version=1,
        status="active",
        priority=2,
        label="会话保持有效",
        capabilities=["PAGE_REDIRECTED", "TOKEN_STORED"],
    )
    _seed_templates(repo, b5.id, [
        {"capability": "TOKEN_STORED", "execution_layer": "ui",
         "action": "assert_visible", "target": "dashboard", "operator": "exists",
         "description": "验证页面可正常访问"},
    ])

    # ---- Behavior 6: 频率限制 (领域通用) ----
    b6 = repo.upsert_behavior(
        behavior_code="RATE_LIMIT_TRIGGERED",
        intent_type="RATE_LIMIT",
        scenario="negative",
        scope="domain",
        page_code="",
        domain="general",
        version=1,
        status="active",
        priority=2,
        label="频率限制被触发",
        capabilities=["ERROR_DISPLAYED"],
    )
    _seed_templates(repo, b6.id, [
        {"capability": "ERROR_DISPLAYED", "execution_layer": "ui",
         "action": "assert_text", "target": "error-toast", "operator": "not_empty",
         "description": "验证频率限制提示出现"},
    ])

    # ---- Behavior 7: 网络超时 (领域通用) ----
    b7 = repo.upsert_behavior(
        behavior_code="NETWORK_TIMEOUT_RECOVERY",
        intent_type="NETWORK_TIMEOUT",
        scenario="negative",
        scope="domain",
        page_code="",
        domain="general",
        version=1,
        status="active",
        priority=2,
        label="网络超时恢复",
        capabilities=["ERROR_DISPLAYED"],
    )
    _seed_templates(repo, b7.id, [
        {"capability": "ERROR_DISPLAYED", "execution_layer": "ui",
         "action": "assert_text", "target": "error-toast", "operator": "not_empty",
         "description": "验证超时提示出现"},
    ])

    db.commit()


def _seed_templates(repo: BehaviorRegistryRepository, behavior_id: int, templates: list[dict]) -> None:
    """幂等创建断言模板。已有模板则补充新增的，不覆盖已存在的。"""
    existing = repo.list_templates_by_behavior(behavior_id)
    existing_desc = {t.description for t in existing if t.description}
    for t in templates:
        if t.get("description", "") not in existing_desc:
            repo.add_template(behavior_id=behavior_id, **t)
