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
    "login", "account_state", "sql", "api_call", "network",
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

    page = _normalized_text(page_object.get("page", ""))

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
                page=page, product_yaml=product_yaml,
                seed_data_provider=seed_data_provider,
            )
        elif pc_type == "sql":
            steps = _compile_sql(entry=entry, case_yaml=product_yaml)
        elif pc_type == "network":
            steps = _compile_network(
                entry=entry, page=page, product_yaml=product_yaml,
                seed_data_provider=seed_data_provider,
            )
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
    page: str,
    product_yaml: dict[str, Any],
    seed_data_provider: Any = None,
) -> list[dict[str, Any]]:
    """account_state 预处理：路由数据到池 + 生成 setup_sql。

    1. 按约定 {page}_setup 池名查找 SQL 模板
    2. 解析模板中的 {{var}} 占位符
    3. 写入 product_yaml["setup_sql"]（Runner 执行前运行）
    4. 路由身份数据到种子数据池

    池不可用或 SQL 模板缺失 → 降级：仅路由数据，不发 SQL。
    无硬编码池名/键名，多项目按约定扩展。
    """
    state = _normalized_text(entry.get("state", ""))
    if not state:
        return []

    # ── 1. 路由身份数据到数据池 ─────────────────────────────────
    identity_keys = {"username", "password", "user_id", "email"}
    for dk in list(data.keys()):
        if dk in identity_keys and isinstance(data[dk], dict):
            entry_data = data[dk]
            if _normalized_text(entry_data.get("source_type")) == "inline":
                entry_data["source_type"] = "pool"
                entry_data["pool_name"] = page  # 按页面对应的池
                entry_data["key"] = f"{dk}_{state}"

    # ── 2. 查找 setup_sql 模板 ──────────────────────────────────
    sql = _resolve_setup_sql(
        page=page, state=state,
        seed_data_provider=seed_data_provider,
    )
    if sql:
        # 解析模板中的 {{var}} 占位符
        sql = _resolve_sql_template(sql, data)
        existing = _normalized_text(product_yaml.get("setup_sql", ""))
        if existing:
            sql = existing + ";\n" + sql
        product_yaml["setup_sql"] = sql
        _LOGGER.info(
            "precondition account_state: resolved setup_sql for state='%s' page='%s'",
            state, page,
        )

    return []  # account_state 不改 steps


def _resolve_setup_sql(
    *,
    page: str,
    state: str,
    seed_data_provider: Any = None,
) -> str | None:
    """从数据池查找 setup_sql 模板。按约定 {page}_setup 池名。

    查找优先级：{state}_user → {state} → None（降级）
    """
    if seed_data_provider is None or not hasattr(seed_data_provider, "get_item"):
        return None

    pool_name = f"{page}_setup"
    # 尝试多种 key 格式
    for candidate in (f"{state}_user", state):
        sql = seed_data_provider.get_item(pool_name, candidate)  # type: ignore[union-attr]
        if isinstance(sql, str) and sql.strip():
            return sql.strip()

    _LOGGER.debug(
        "precondition account_state: no setup_sql found in pool '%s' for state='%s'",
        pool_name, state,
    )
    return None


def _resolve_sql_template(sql: str, data: dict[str, Any]) -> str:
    """解析 SQL 模板中的 {{data_key}} 占位符，替换为实际值。"""
    import re
    result = sql
    for match in re.finditer(r"\{\{\s*(\w+)\s*\}\}", sql):
        var = match.group(1)
        entry = data.get(var)
        if isinstance(entry, dict):
            val = entry.get("value", "")
        else:
            val = str(entry) if entry is not None else ""
        result = result.replace(match.group(0), val)
    return result


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


def _compile_network(
    *,
    entry: dict[str, Any],
    page: str,
    product_yaml: dict[str, Any],
    seed_data_provider: Any = None,
) -> list[dict[str, Any]]:
    """V3.0: 网络条件预处理。从 {page}_network 池读取配置，应用到步骤。

    profile 可选值: timeout / slow / offline
    无池或无配置 → 降级：仅注入 wait 步骤。
    """
    profile = _normalized_text(entry.get("profile", ""))
    if not profile:
        return []

    config = _resolve_network_config(
        page=page, profile=profile,
        seed_data_provider=seed_data_provider,
    )

    if not config:
        if profile == "timeout":
            return [{
                "action": "wait",
                "timeout_ms": 5000,
                "expected_result": "等待请求超时（无网络配置池，使用默认 wait）",
            }]
        return []

    steps: list[dict[str, Any]] = []
    if isinstance(config, dict):
        action = _normalized_text(config.get("action", ""))
        if action == "set_timeout":
            timeout_ms = config.get("timeout_ms", 5000)
            exec_steps = product_yaml.get("execution", {}).get("steps", [])
            for s in exec_steps:
                if isinstance(s, dict) and s.get("action") not in ("goto",):
                    s["timeout_ms"] = timeout_ms
        elif action in ("set_throttle", "set_offline"):
            step: dict[str, Any] = {
                "action": "wait",
                "network_condition": profile,
                "expected_result": f"网络条件: {profile}",
            }
            if "timeout_ms" in config:
                step["timeout_ms"] = config["timeout_ms"]
            steps.append(step)
        else:
            steps.append({
                "action": "wait",
                "timeout_ms": config.get("timeout_ms", 5000),
                "expected_result": f"网络预处理: {profile}",
            })
        product_yaml.setdefault("_network_config", config)

    return steps


def _resolve_network_config(
    *,
    page: str,
    profile: str,
    seed_data_provider: Any = None,
) -> dict[str, Any] | None:
    """从 {page}_network 数据池查找网络配置。"""
    if seed_data_provider is None or not hasattr(seed_data_provider, "get_item"):
        return None

    pool_name = f"{page}_network"
    for candidate in (profile, f"{profile}_config"):
        item = seed_data_provider.get_item(pool_name, candidate)  # type: ignore[union-attr]
        if isinstance(item, dict):
            return item
        if isinstance(item, str):
            import json
            try:
                return json.loads(item)
            except (json.JSONDecodeError, ValueError):
                return {"action": "set_timeout", "timeout_ms": 5000}

    _LOGGER.debug(
        "precondition network: no config in pool '%s' for profile='%s'",
        pool_name, profile,
    )
    return None


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
