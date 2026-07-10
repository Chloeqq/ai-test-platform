"""Behavior Registry — Phase 0: 断言模板系统数据模型。

behavior_registry: 业务行为定义 (intent_type + scenario → behavior_code)
assertion_template: 行为对应的断言模板 (action + target + value)
assertion_execution_log: 断言生成审计日志
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


# ---------------------------------------------------------------------------
# IntentType — AI 输出的业务场景分类（预定义枚举）
# ---------------------------------------------------------------------------

INTENT_TYPES: tuple[str, ...] = (
    "AUTH_LOGIN",           # 登录认证
    "AUTH_LOGOUT",          # 退出登录
    "AUTH_SESSION",         # 会话管理
    "AUTH_ACCESS",          # 访问控制
    "INPUT_VALIDATION",     # 输入校验
    "PASSWORD_VISIBILITY",  # 密码可见性
    "RATE_LIMIT",           # 频率限制
)


# ---------------------------------------------------------------------------
# BehaviorCode — 系统确定的业务行为（预定义枚举）
# ---------------------------------------------------------------------------

BEHAVIOR_CODES: tuple[str, ...] = (
    "AUTH_LOGIN_SUCCESS",
    "AUTH_LOGIN_FAILED",
    "AUTH_INPUT_INVALID",
    "AUTH_ACCESS_BLOCKED",
    "AUTH_SESSION_PERSISTED",
    "AUTH_LOGOUT_COMPLETED",
    "PASSWORD_TOGGLE_WORKS",
    "RATE_LIMIT_TRIGGERED",
)


# ---------------------------------------------------------------------------
# Intent → Behavior 映射规则（确定性，不依赖 AI）
# ---------------------------------------------------------------------------

INTENT_BEHAVIOR_MAP: dict[str, dict[str, str]] = {
    "AUTH_LOGIN": {
        "positive": "AUTH_LOGIN_SUCCESS",
        "negative": "AUTH_LOGIN_FAILED",
        "boundary": "AUTH_INPUT_INVALID",
    },
    "AUTH_ACCESS": {
        "positive": "AUTH_SESSION_PERSISTED",
        "negative": "AUTH_ACCESS_BLOCKED",
    },
    "INPUT_VALIDATION": {
        "negative": "AUTH_INPUT_INVALID",
    },
    "AUTH_LOGOUT": {
        "positive": "AUTH_LOGOUT_COMPLETED",
    },
    "PASSWORD_VISIBILITY": {
        "positive": "PASSWORD_TOGGLE_WORKS",
    },
    "RATE_LIMIT": {
        "negative": "RATE_LIMIT_TRIGGERED",
    },
}


def resolve_behavior_code(intent_type: str, scenario: str) -> str | None:
    """确定性映射: intent_type + scenario → behavior_code。"""
    scenario_map = INTENT_BEHAVIOR_MAP.get(intent_type, {})
    return scenario_map.get(scenario)


# ---------------------------------------------------------------------------
# Execution Layer — 断言在哪个执行层执行
# ---------------------------------------------------------------------------

EXECUTION_LAYERS: tuple[str, ...] = (
    "ui",           # Playwright UI Runner
    "api",          # API Runner (HTTP)
    "database",     # DB SQL Runner
    "storage",      # 浏览器 storage (localStorage/sessionStorage/cookie)
)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class BehaviorRegistry(Base):
    """业务行为注册表。定义 intent_type + scenario → behavior_code 的映射。"""
    __tablename__ = "behavior_registry"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    behavior_code: Mapped[str] = mapped_column(String(120), index=True)
    intent_type: Mapped[str] = mapped_column(String(80), index=True)
    scenario: Mapped[str] = mapped_column(String(20), default="positive")
    scope: Mapped[str] = mapped_column(String(20), default="page")  # "page" | "domain"
    page_code: Mapped[str] = mapped_column(String(40), default="", index=True)
    domain: Mapped[str] = mapped_column(String(40), default="")
    context_filter: Mapped[dict] = mapped_column(JSON, default=dict)  # {"role": "admin"} or {}
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)  # active|draft|deprecated
    priority: Mapped[int] = mapped_column(Integer, default=1)  # 1=最高, 3=最低
    label: Mapped[str] = mapped_column(String(255), default="")
    capabilities: Mapped[list[str]] = mapped_column(JSON, default=list)  # ["SESSION_CREATED", "PAGE_REDIRECTED"]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
    )


class AssertionTemplate(Base):
    """断言模板。每个 behavior 包含多条 assertion，指定 action + target + value。"""
    __tablename__ = "assertion_templates"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    behavior_id: Mapped[int] = mapped_column(ForeignKey("behavior_registry.id", ondelete="CASCADE"), index=True)
    capability: Mapped[str] = mapped_column(String(80), default="")
    execution_layer: Mapped[str] = mapped_column(String(20), default="ui")  # ui|api|database|storage
    action: Mapped[str] = mapped_column(String(80), default="")  # assert_url|assert_visible|db_exists|...
    target: Mapped[str] = mapped_column(String(255), default="")  # element_code
    operator: Mapped[str] = mapped_column(String(40), default="eq")  # eq|contains|not_empty|exists
    value: Mapped[str] = mapped_column(Text, default="")  # 期望值, 支持 {{variable}}
    variable_schema: Mapped[dict] = mapped_column(JSON, default=dict)  # {"home_url": "env", ...}
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AssertionExecutionLog(Base):
    """断言生成审计日志。记录每次断言生成的输入/输出/来源/版本。"""
    __tablename__ = "assertion_execution_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    test_case_id: Mapped[str] = mapped_column(String(64), default="", index=True)
    intent_type: Mapped[str] = mapped_column(String(80), default="")
    scenario: Mapped[str] = mapped_column(String(20), default="")
    behavior_code: Mapped[str] = mapped_column(String(120), default="")
    behavior_version: Mapped[int] = mapped_column(Integer, default=0)
    source: Mapped[str] = mapped_column(String(20), default="")  # page_level|domain_level|not_configured
    compiled_assertions: Mapped[list] = mapped_column(JSON, default=list)
    execution_result: Mapped[dict] = mapped_column(JSON, default=dict)
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
