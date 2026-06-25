"""V2.0 Precondition Compiler — 将结构化预处理声明编译为可执行 setup 步骤。

支持的预处理类型：
- login: 注入登录流程（input + input + click + assert_visible）
- account_state: 基于状态关键词路由数据到池
- sql: 复用 setup_sql（已存在，透传）
- api_call: 预留（V2.5+）
"""

from __future__ import annotations

import logging
from typing import Any

from shared_backend.execution_compiler import ExecutionCompilerError
from shared_backend.type_utils import str_value as _normalized_text

from .generate_pipeline_format import _is_variable_template, _variable_template_key

_LOGGER = logging.getLogger(__name__)

# ── Precondition type constants ─────────────────────────────────────────────

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
    case_yaml: dict[str, Any],
    page_object: dict[str, Any],
    seed_data_provider: Any = None,
) -> list[dict[str, Any]]:
    """编译 preconditions 块为可执行 setup 步骤列表。

    不修改 case_yaml，返回新步骤列表。
    调用方负责插入到 execution.steps 之前。
    """
    preconditions = case_yaml.get("preconditions")
    if not isinstance(preconditions, list) or not preconditions:
        return []

    setup_steps: list[dict[str, Any]] = []
    data = case_yaml.get("data") if isinstance(case_yaml.get("data"), dict) else {}

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
            steps = _compile_login(entry=entry, data=data, page_object=page_object)
        elif pc_type == "account_state":
            steps = _compile_account_state(
                entry=entry, data=data,
                seed_data_provider=seed_data_provider,
            )
        elif pc_type == "sql":
            steps = _compile_sql(entry=entry, case_yaml=case_yaml)
        else:
            steps = []  # api_call: reserved

        setup_steps.extend(steps)

    return setup_steps


# ── Type compilers ──────────────────────────────────────────────────────────

def _compile_login(
    *,
    entry: dict[str, Any],
    data: dict[str, Any],
    page_object: dict[str, Any],
) -> list[dict[str, Any]]:
    """生成登录 setup 步骤。

    从 data_ref 解析登录凭据。如果 data_ref 不提供，回退到 data 中的
    username/password 字段。
    """
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

    # 确保 data 中有凭据条目（如果 data_ref 指向 inline 值则无需创建）
    variables = {}
    for varname, dkey, pkey in [
        ("login_username", username_key, "username"),
        ("login_password", password_key, "password"),
    ]:
        if dkey not in data or data[dkey] is None:
            # data_ref 指向了不存在的 key → 尝试从 entry 直接获取值
            raw_val = data_ref.get(pkey)
            if raw_val and not isinstance(raw_val, str):
                raw_val = str(raw_val)
            if raw_val and not raw_val.startswith("$"):
                data[dkey] = {"source_type": "inline", "value": raw_val}
        variables[varname] = f"{{{{{dkey}}}}}"

    # 对登录元素做基本校验
    elements = page_object.get("elements") if isinstance(page_object, dict) else {}
    for el in ("username_input", "password_input", "login_button", "home_menu"):
        if el not in elements:
            _LOGGER.warning(
                "precondition login: element '%s' not found in page_object, "
                "setup steps may fail at runtime", el,
            )

    # 深拷贝模板步骤
    steps: list[dict[str, Any]] = []
    for tmpl in _LOGIN_STEP_TEMPLATE:
        step = dict(tmpl)
        steps.append(step)

    return steps


def _compile_account_state(
    *,
    entry: dict[str, Any],
    data: dict[str, Any],
    seed_data_provider: Any = None,
) -> list[dict[str, Any]]:
    """account_state 预处理：将 data 路由到种子数据池中的特定状态。

    例如：precondition type=account_state, state=locked
    → 自动将 username/password 的 source_type 从 inline 切换为 pool，
      指向 locked_user 的池数据。
    """
    state = _normalized_text(entry.get("state", ""))
    if not state:
        return []  # 无状态声明 → 不注入步骤

    # 复用 _apply_pool_routing 的关键词映射
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

    # 检查池是否可用
    if seed_data_provider is not None and hasattr(seed_data_provider, "has_item"):
        if not seed_data_provider.has_item(pool_name, pool_key):  # type: ignore[union-attr]
            _LOGGER.warning(
                "precondition account_state: pool '%s' key '%s' not found in seed data",
                pool_name, pool_key,
            )

    # 将身份相关的 data 条目路由到池
    identity_keys = {"username", "password", "user_id", "email"}
    for dk in list(data.keys()):
        if dk in identity_keys and isinstance(data[dk], dict):
            entry_data = data[dk]
            if _normalized_text(entry_data.get("source_type")) == "inline":
                entry_data["source_type"] = "pool"
                entry_data["pool_name"] = pool_name
                entry_data["key"] = f"{dk}_{state}" if dk == "username" else pool_key

    return []  # account_state 不改 steps，只改 data 路由


def _compile_sql(
    *,
    entry: dict[str, Any],
    case_yaml: dict[str, Any],
) -> list[dict[str, Any]]:
    """sql 预处理：复用 setup_sql 字段。不生成步骤，只做存在性验证。"""
    sql = _normalized_text(entry.get("sql", ""))
    if not sql:
        existing = _normalized_text(case_yaml.get("setup_sql", ""))
        if not existing:
            raise ExecutionCompilerError(
                code="v2_0_precondition_sql_missing",
                message="sql precondition requires 'sql' field or case.setup_sql",
                stage="v2_0_precondition_compile",
            )
    return []  # SQL 由 runner 处理，不注入步骤


# ── Helpers ─────────────────────────────────────────────────────────────────

def _resolve_data_ref(
    ref: Any,
    fallback_key: str,
    data: dict[str, Any],
) -> str | None:
    """解析 data_ref 引用为 data key。

    - "$test_data.user_001.username" → "username" (在 data 中查找)
    - "username" → "username"
    - None → 检查 data 中是否有 fallback_key
    """
    if isinstance(ref, str) and ref.startswith("$"):
        # $test_data.user_001.username → 取最后一段作为 data key
        parts = ref.rsplit(".", 1)
        candidate = parts[-1] if len(parts) > 1 else ref.lstrip("$")
        if candidate in data:
            return candidate
        return candidate  # 返回可能不存在的 key，由调用方处理

    if isinstance(ref, str) and ref.strip():
        return ref.strip()

    # 无 data_ref → 回退到 data 中的对应 key
    if fallback_key in data:
        return fallback_key
    return None
