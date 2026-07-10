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
# Intent → Behavior 映射（确定性规则引擎）
#
# 初始种子值，后续通过 behavior_registry 表动态扩展。
# 领域无关设计：AUTH/ORDER/PAYMENT/PRODUCT 等任意业务域均可用。
# ---------------------------------------------------------------------------

# 初始 intent_type 种子（领域无关，按业务域前缀区分）
_INITIAL_INTENT_TYPES: tuple[str, ...] = (
    "AUTH_LOGIN",
    "AUTH_LOGOUT",
    "AUTH_SESSION",
    "AUTH_ACCESS",
    "INPUT_VALIDATION",
    "PASSWORD_VISIBILITY",
    "RATE_LIMIT",
    "NETWORK_TIMEOUT",
)

# 初始 behavior_code 种子
_INITIAL_BEHAVIOR_CODES: tuple[str, ...] = (
    "AUTH_LOGIN_SUCCESS",
    "AUTH_LOGIN_FAILED",
    "AUTH_INPUT_INVALID",
    "AUTH_ACCESS_BLOCKED",
    "AUTH_SESSION_PERSISTED",
    "AUTH_LOGOUT_COMPLETED",
    "PASSWORD_TOGGLE_WORKS",
    "RATE_LIMIT_TRIGGERED",
    "NETWORK_TIMEOUT_RECOVERY",
)

# Intent → Behavior 映射规则（确定性规则引擎）
# 领域无关：同一条规则对 login/order/payment 页面均生效。
# 扩展方式：在 behavior_registry 表中新增记录即可，不需改代码。
_INTENT_BEHAVIOR_RULES: dict[str, dict[str, str]] = {
    "AUTH_LOGIN": {
        "positive": "AUTH_LOGIN_SUCCESS",
        "negative": "AUTH_LOGIN_FAILED",
    },
    "AUTH_ACCESS": {
        "positive": "AUTH_SESSION_PERSISTED",
        "negative": "AUTH_ACCESS_BLOCKED",
    },
    "AUTH_LOGOUT": {
        "positive": "AUTH_LOGOUT_COMPLETED",
    },
    "AUTH_SESSION": {
        "positive": "AUTH_SESSION_PERSISTED",
    },
    "INPUT_VALIDATION": {
        "negative": "AUTH_INPUT_INVALID",
        "boundary": "AUTH_INPUT_INVALID",
    },
    "PASSWORD_VISIBILITY": {
        "positive": "PASSWORD_TOGGLE_WORKS",
    },
    "RATE_LIMIT": {
        "negative": "RATE_LIMIT_TRIGGERED",
    },
    "NETWORK_TIMEOUT": {
        "negative": "NETWORK_TIMEOUT_RECOVERY",
    },
}


def resolve_behavior_code(intent_type: str, scenario: str) -> str | None:
    """确定性映射: intent_type + scenario → behavior_code。

    查询顺序：
      1. behavior_registry 表 (scope=domain 的通用规则)
      2. _INTENT_BEHAVIOR_RULES 内置规则 (兜底)

    领域无关设计：intent_type 以业务域前缀区分 (AUTH_/ORDER_/PAYMENT_/...)
    """
    return _INTENT_BEHAVIOR_RULES.get(intent_type, {}).get(scenario)


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
