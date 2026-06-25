"""V2.0 Precondition Compiler — 将结构化预处理声明编译为可执行 setup 步骤。

支持的预处理类型：
- login: 注入登录流程（input + input + click + assert_visible）
- account_state: 基于状态关键词路由数据到池
- sql: 复用 setup_sql（已存在，透传）
- api_call: 预留（V2.5+）

调用方约定：compile_preconditions() 会修改 product_yaml 的 execution.variables
和 data 段（写入 setup 步骤需要的变量绑定和数据条目）。调用方应确保在
_enrich_dsl_v1_1_data_bindings() 之后调用，此时 variables 和 data 已归一化。
"""

from __future__ import annotations

import logging
from typing import Any

from shared_backend.execution_compiler import ExecutionCompilerError
from shared_backend.type_utils import str_value as _normalized_text

_LOGGER = logging.getLogger(__name__)

# ── Precondition type constants ─────────────────────────────────────────────
# RULE_005 也引用此常量，避免重复定义。

_PRECONDITION_TYPES: frozenset[str] = frozenset({
    "login", "account_state", "sql", "api_call",
})

# 登录流程的标准步骤模板：需要页面对象中的 username_input, password_input, login_button
_LOGIN_STEP_TEMPLATE: list[dict[str, Any]] = [
    {"action": "input", "target": "element:username_input",
     "value": "{{login_username}}", "target_name": "用户名输入框",
     "expected_result": "用户名输入框内容已填充"},
    {"action": "input", "target": "element:password_input",
     "value": "{{login_password}}", "target_name": "密码输入框",
     "expected_result": "密码输入框内容已填充"},
    {"action": "click", "target": "element:login_button",
     "target_name": "登录按钮", "expected_result": "已点击登录按钮"},
    {"action": "assert_visible", "target": "element:home_menu",
     "locator_type": "data-testid", "locator_value": "home-page",
     "target_name": "首页关键元素", "expected_result": "登录成功，首页可见"},
]


# ── API ─────────────────────────────────────────────────────────────────────

def compile_preconditions(
    *,
    product_yaml: dict[str, Any],
    page_object: dict[str, Any],
    seed_data_provider: Any = None,
) -> list[dict[str, Any]]:
    """编译 preconditions 块为可执行 setup 步骤列表。

    会修改 product_yaml:
    - execution.variables: 写入 setup 步骤需要的变量映射
    - data: _compile_account_state 会修改 data 条目的 source_type

    返回编译后的 setup 步骤列表（调用方负责插入到 execution.steps 之前）。
    """
    preconditions = product_yaml.get("preconditions")
    if not isinstance(preconditions, list) or not preconditions:
        return []

    setup_steps: list[dict[str, Any]] = []
    data = product_yaml.get("data") if isinstance(product_yaml.get("data"), dict) else {}
    execution = product_yaml.get("execution") if isinstance(product_yaml.get("execution"), dict) else {}
    variables = execution.get("variables") if isinstance(execution.get("variables"), dict) else {}

    for i, entry in enumerate(preconditions):
        if not isinstance(entry, dict):
            continue
        pc_type = _normalized_text(entry.get("type"))

        if pc_type not in _PRECONDITION_TYPES:
            raise ExecutionCompilerError(
                code="v2_0_unknown_precondition_type",
                message=f"preconditions[{i}]: unknown type '{pc_type}'",
                reason=f"supported types: {sorted(_PRECONDITION_TYPES)}",
                stage="v2_0_precondition_compile",
            )

        if pc_type == "login":
            steps = _compile_login(
                entry=entry, data=data, variables=variables,
                page_object=page_object,
            )
        elif pc_type == "account_state":
            steps = _compile_account_state(
                entry=entry, data=data,
                seed_data_provider=seed_data_provider,
            )
        elif pc_type == "sql":
            steps = _compile_sql(entry=entry, case_yaml=product_yaml)
        else:
            steps = []  # api_call: reserved

        setup_steps.extend(steps)

    # 写回 variables（_compile_login 可能已修改）
    if variables is not execution.get("variables"):
        execution["variables"] = variables

    return setup_steps


# ── Type compilers ──────────────────────────────────────────────────────────

def _compile_login(
    *,
    entry: dict[str, Any],
    data: dict[str, Any],
    variables: dict[str, str],
    page_object: dict[str, Any],
) -> list[dict[str, Any]]:
    """生成登录 setup 步骤。向 variables 写入 login_username/login_password 映射。"""
    data_ref = entry.get("data_ref") if isinstance(entry.get("data_ref"), dict) else {}

    # 解析凭据来源
    username_key = _resolve_data_ref(data_ref.get("username"), "username", data)
    password_key = _resolve_data_ref(data_ref.get("password"), "password", data)

    if not username_key or not password_key:
        raise ExecutionCompilerError(
            code="v2_0_precondition_missing_credentials",
            message="login precondition requires username and password in data_ref or data",
            reason=f"data_ref={data_ref}, data_keys={sorted(data.keys())}",
            stage="v2_0_precondition_compile",
        )

    # 确保 data 中有凭据条目，并写入 variables 映射
    for varname, dkey, pkey in [
        ("login_username", username_key, "username"),
        ("login_password", password_key, "password"),
    ]:
        if dkey not in data or data[dkey] is None:
            raw_val = data_ref.get(pkey)
            if raw_val and not isinstance(raw_val, str):
                raw_val = str(raw_val)
            if raw_val and not raw_val.startswith("$"):
                data[dkey] = {"source_type": "inline", "value": raw_val}
        # P0 fix: 写入 execution.variables，Runner 才能解析 {{login_username}}
        variables[varname] = f"{{{{{dkey}}}}}"

    # 对登录元素做基本校验（WARNING，不阻塞）
    elements = page_object.get("elements") if isinstance(page_object, dict) else {}
    for el in ("username_input", "password_input", "login_button", "home_menu"):
        if el not in elements:
            _LOGGER.warning(
                "precondition login: element '%s' not found in page_object, "
                "setup steps may fail at runtime", el,
            )

    # 复制模板步骤（模板值全是字符串，dict() 浅拷贝足够）
    steps: list[dict[str, Any]] = []
    for tmpl in _LOGIN_STEP_TEMPLATE:
        steps.append(dict(tmpl))

    return steps


def _compile_account_state(
    *,
    entry: dict[str, Any],
    data: dict[str, Any],
    seed_data_provider: Any = None,
) -> list[dict[str, Any]]:
    """account_state 预处理：将 data 路由到种子数据池中的特定状态。

    修改 data 中身份字段的 source_type（inline → pool），不改 steps。
    """
    state = _normalized_text(entry.get("state", ""))
    if not state:
        return []

    state_routing: dict[str, tuple[str, str]] = {
        "locked": ("login_accounts", "locked_user"),
        "disabled": ("login_accounts", "disabled_user"),
        "active": ("login_accounts", "active_user"),
    }

    route = state_routing.get(state)
    if not route:
        _LOGGER.warning(
            "precondition account_state: unknown state '%s', skipping pool routing",
            state,
        )
        return []

    pool_name, pool_key = route

    if seed_data_provider is not None and hasattr(seed_data_provider, "has_item"):
        if not seed_data_provider.has_item(pool_name, pool_key):  # type: ignore[union-attr]
            _LOGGER.warning(
                "precondition account_state: pool '%s' key '%s' not found in seed data",
                pool_name, pool_key,
            )

    identity_keys = {"username", "password", "user_id", "email"}
    for dk in list(data.keys()):
        if dk in identity_keys and isinstance(data[dk], dict):
            entry_data = data[dk]
            if _normalized_text(entry_data.get("source_type")) == "inline":
                entry_data["source_type"] = "pool"
                entry_data["pool_name"] = pool_name
                entry_data["key"] = f"{dk}_{state}" if dk == "username" else pool_key

    return []


def _compile_sql(
    *,
    entry: dict[str, Any],
    case_yaml: dict[str, Any],
) -> list[dict[str, Any]]:
    """sql 预处理：复用 setup_sql 字段。"""
    sql = _normalized_text(entry.get("sql", ""))
    if not sql:
        existing = _normalized_text(case_yaml.get("setup_sql", ""))
        if not existing:
            raise ExecutionCompilerError(
                code="v2_0_precondition_sql_missing",
                message="sql precondition requires 'sql' field or case.setup_sql",
                stage="v2_0_precondition_compile",
            )
    return []


# ── Helpers ─────────────────────────────────────────────────────────────────

def _resolve_data_ref(
    ref: Any,
    fallback_key: str,
    data: dict[str, Any],
) -> str | None:
    """解析 data_ref 引用为 data key。

    - "$test_data.user_001.username" → "username" (取最后一段)
    - "username" → "username"
    - None → 检查 data 中是否有 fallback_key
    """
    if isinstance(ref, str) and ref.startswith("$"):
        parts = ref.rsplit(".", 1)
        candidate = parts[-1] if len(parts) > 1 else ref.lstrip("$")
        if candidate in data:
            return candidate
        return candidate

    if isinstance(ref, str) and ref.strip():
        return ref.strip()

    if fallback_key in data:
        return fallback_key
    return None
