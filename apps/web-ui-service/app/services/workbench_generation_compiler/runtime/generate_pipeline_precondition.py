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

import json
import logging
import re
from typing import Any

from shared_backend.execution_compiler import ExecutionCompilerError
from shared_backend.quality_gate import (
    PRECONDITION_TYPES as _PRECONDITION_TYPES,
    RESERVED_PRECONDITION_TYPES as _RESERVED_PRECONDITION_TYPES,
)
from shared_backend.type_utils import str_value as _normalized_text

_LOGGER = logging.getLogger(__name__)

# ── Precondition type constants ─────────────────────────────────────────────
# 唯一事实源在 shared_backend.quality_gate.PRECONDITION_TYPES，RULE_005 同源导入。

# 身份类数据键 — account_state / keyword 路由都按这些 key 把 inline 改为 pool 引用。
_IDENTITY_DATA_KEYS: frozenset[str] = frozenset({"username", "password", "user_id", "email"})

# 登录流程的元素角色映射 — 从 page_object 按这些 code 查找。
# input/click 步骤找不到元素则跳过（WARNING）；assert_visible 是登录成功的唯一验证，
# 找不到元素时退回默认 locator 而非跳过，确保失败的登录仍能在运行时被捕获。
_LOGIN_FLOW_ELEMENT_CODES: tuple[tuple[str, str, str | None, str], ...] = (
    # (element_code, action, value_template, expected_result)
    ("login-username-input", "input", "{{login_username}}", "用户名输入框内容已填充"),
    ("login-password-input", "input", "{{login_password}}", "密码输入框内容已填充"),
    ("login-submit-btn", "click", None, "已点击登录按钮"),
    ("home-page", "assert_visible", None, "登录成功，首页可见"),
)

# assert_visible 步骤找不到元素时的兜底 locator（跨页面注入的 home-page 元素）。
_LOGIN_ASSERT_FALLBACK: dict[str, str] = {
    "target_name": "首页关键元素",
    "locator_type": "data-testid",
    "locator_value": "home-page",
}


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
            # 类型在 PRECONDITION_TYPES 内（已过上方校验）但无编译分支 =
            # 预留未实现（当前仅 api_call）。硬失败而非静默返回空步骤，
            # 杜绝「校验通过却不执行任何 setup」的隐患。
            raise ExecutionCompilerError(
                code="v2_0_precondition_not_implemented",
                message=f"preconditions[{i}]: type '{pc_type}' is reserved but not implemented",
                reason=f"reserved types pending implementation: {sorted(_RESERVED_PRECONDITION_TYPES)} (V2.5+)",
                stage="v2_0_precondition_compile",
            )

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

    # 动态生成登录步骤：从 page_object 查找元素。
    elements = page_object.get("elements") if isinstance(page_object, dict) else {}
    steps: list[dict[str, Any]] = []
    for el_code, action, value_tmpl, expected in _LOGIN_FLOW_ELEMENT_CODES:
        el_def = elements.get(el_code)
        if not isinstance(el_def, dict):
            # assert_visible 是登录成功的唯一验证 — 退回默认 locator 而非跳过，
            # 否则失败的登录会被静默放过。input/click 步骤可安全跳过。
            if action == "assert_visible":
                _LOGGER.warning(
                    "precondition login: element '%s' not found in page_object, "
                    "using fallback locator for assert step", el_code,
                )
                steps.append({
                    "action": action,
                    "target": f"element:{el_code}",
                    "expected_result": expected,
                    **_LOGIN_ASSERT_FALLBACK,
                })
                continue
            _LOGGER.warning(
                "precondition login: element '%s' not found in page_object, "
                "skipping login step '%s'", el_code, action,
            )
            continue

        step: dict[str, Any] = {
            "action": action,
            "target": f"element:{el_code}",
            "target_name": _normalized_text(el_def.get("element_name", el_code)),
            "expected_result": expected,
        }
        if value_tmpl:
            step["value"] = value_tmpl
        # 从 page_object 复制 locator 信息
        locator_type = _normalized_text(el_def.get("locator_type") or el_def.get("type", ""))
        if locator_type:
            step["locator_type"] = locator_type
        locator_value = _normalized_text(el_def.get("locator_value") or el_def.get("selector", ""))
        if locator_value:
            step["locator_value"] = locator_value
        role = _normalized_text(el_def.get("role", ""))
        if locator_type == "role" and role:
            step["role"] = role
        steps.append(step)

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
    route_identity_data_to_pool(data, page=page, state=state)

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

def route_identity_data_to_pool(data: dict[str, Any], *, page: str, state: str) -> None:
    """将身份类 inline data 改写为数据池引用（就地修改 data）。

    池名按 V3.0 约定 = {page}（page 为空时退回 "login"）。
    key 按约定 = {data_key}_{state}（如 username_locked）。
    零硬编码池名/键名 — 全由 page 和 state 推导。account_state 预处理与
    关键词路由（_apply_pool_routing）共用此函数，避免逻辑漂移。
    """
    if not state:
        return
    pool_name = page or "login"
    for dk in list(data.keys()):
        entry = data.get(dk)
        if (
            dk in _IDENTITY_DATA_KEYS
            and isinstance(entry, dict)
            and _normalized_text(entry.get("source_type")) == "inline"
        ):
            data[dk] = {
                "source_type": "pool",
                "pool_name": pool_name,
                "key": f"{dk}_{state}",
            }


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
