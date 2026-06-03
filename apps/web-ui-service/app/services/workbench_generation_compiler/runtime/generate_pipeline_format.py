"""generate_pipeline 产品格式化与 DSL V1.1 —— 提取自 generate_pipeline.py。"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Callable, Protocol
import yaml
from sqlalchemy.exc import OperationalError

from shared_backend.db import get_db_session as SessionLocal
from app.models.page_object import PageElement, PageObject
from app.repositories.page_object_repository import PageObjectRepository

from ..debug import debug_enabled, log_debug_event
from shared_backend.observability import summarize_http_context
from shared_backend.execution_compiler import ExecutionCompilerError, compile_execution_steps
from shared_backend.element_binding import build_element_alias_map
from shared_backend.intent_mapping import resolve_explicit_step
from shared_backend.schemas.contracts import normalize_test_point_plan_v1
from shared_backend.schemas.validator import ContractValidator
from shared_backend.type_utils import str_value as _normalized_text


# 从主模块导入 leaf 工具函数（无循环：主模块的所有定义在线 1-703 已加载）
from .generate_pipeline import (  # noqa: E402
    _normalized_text, _LOGGER, _YAML_PAGE_OBJECT_ROOT,
    _COMPILER_ERROR_CODES, _SUPPORTED_TOP_LEVEL_ASSERTIONS,
    _TOP_LEVEL_ASSERTION_KEYS, _VARIABLE_TEMPLATE_RE, _DSL_DATA_SOURCE_TYPES,
    _normalized_key, _normalize_json_list, _is_qualified_formal_element,
    _element_display_name, _infer_element_aliases,
    _looks_like_password_toggle_element, _is_password_input_element,
    _execution_intent_ids, _intent_product_metadata,
    _find_candidate_snapshot_by_intent,
)
def _product_description(title: str, expected: str) -> str:
    title = _normalized_text(title) or "AI生成用例"
    expected = _normalized_text(expected)
    title_key = _normalized_key(title)
    expected_key = _normalized_key(expected)
    if "首次登录成功" in title and any(token in expected for token in ["跳转", "工作台", "首页", "登录用户名"]):
        return f"{title} — 验证输入正确账号密码后可以成功登录并跳转至工作台首页"
    if title_key and expected_key and title_key == expected_key:
        return title
    if expected:
        return f"{title} — {expected[:180]}"
    return title


def _product_page_load_expected(page: str, page_object: dict[str, Any]) -> str:
    normalized_page = _normalized_text(page).lower()
    if normalized_page == "login":
        return "登录页面加载完成，显示账号输入框、密码输入框、登录按钮"
    element_names: list[str] = []
    elements = page_object.get("elements") if isinstance(page_object.get("elements"), dict) else {}
    for raw_meta in list(elements.values())[:3]:
        if not isinstance(raw_meta, dict):
            continue
        name = _normalized_text(raw_meta.get("name"))
        if name:
            element_names.append(name)
    if element_names:
        return f"{page or '目标'}页面加载完成，显示{'、'.join(element_names)}"
    return f"{page or '目标'}页面加载完成"


def _product_element_name(page: str, target_code: str, element_meta: dict[str, Any]) -> str:
    normalized_page = _normalized_text(page).lower()
    normalized_code = _normalized_text(target_code)
    if normalized_page == "login":
        if normalized_code == "username_input":
            return "用户名输入框"
        if normalized_code == "password_input":
            return "密码输入框"
        if normalized_code == "login_button":
            return "登录按钮"
        if normalized_code == "home_menu":
            return "首页菜单"
    return _normalized_text(element_meta.get("name") or element_meta.get("element_name")) or normalized_code


def _product_locator(
    *,
    page: str,
    target_code: str,
    locator_type: str,
    locator_value: str,
) -> tuple[str, str]:
    normalized_locator_type = _normalized_text(locator_type)
    normalized_locator_value = _normalized_text(locator_value)
    if normalized_locator_type and normalized_locator_value:
        return normalized_locator_type, normalized_locator_value
    normalized_page = _normalized_text(page).lower()
    normalized_code = _normalized_text(target_code)
    if normalized_page == "login":
        if normalized_code == "username_input":
            return (
                "css",
                "input[name='username'], #username, #username-input, "
                "input[placeholder*='请输入用户名'], input[placeholder*='用户名']",
            )
        if normalized_code == "password_input":
            return (
                "css",
                "input[type='password'], input[name='password'], #password, #password-input, "
                "input[placeholder*='请输入密码'], input[placeholder*='密码']",
            )
    return normalized_locator_type, normalized_locator_value


_LOGIN_DATA_TESTID_ELEMENT_CODES = {
    "username_input": "login-username-input",
    "password_input": "login-password-input",
    "login_button": "login-submit-btn",
    "home_menu": "home-page",
}


def _product_element_meta(
    *,
    page: str,
    target_code: str,
    elements: dict[str, Any],
) -> dict[str, Any]:
    """按语义 target 取页面对象元素；登录页优先桥接到真实 data-testid 元素。"""
    normalized_page = _normalized_text(page).lower()
    normalized_code = _normalized_text(target_code)
    if normalized_page == "login":
        testid_code = _LOGIN_DATA_TESTID_ELEMENT_CODES.get(normalized_code, "")
        testid_meta = elements.get(testid_code) if testid_code and isinstance(elements.get(testid_code), dict) else {}
        if _normalized_text(testid_meta.get("type") or testid_meta.get("locator_type")) == "data-testid":
            return testid_meta
    return elements.get(normalized_code) if isinstance(elements.get(normalized_code), dict) else {}


def _trusted_page_url(*, payload_page_url: Any, page_object: dict[str, Any]) -> str:
    governed_url = _normalized_text(page_object.get("page_url")) if isinstance(page_object, dict) else ""
    requested_url = _normalized_text(payload_page_url)
    if governed_url and requested_url and governed_url != requested_url:
        raise ExecutionCompilerError(
            code="dsl_v1_1_page_url_mismatch",
            message="DSL V1.1 page_url must match governed page object",
            reason=f"payload.page_url `{requested_url}` does not match page_object.page_url `{governed_url}`",
            stage="dsl_v1_1_enrichment",
        )
    return governed_url or requested_url


def _product_step_expected(
    *,
    action: str,
    target_name: str,
    target_code: str,
    value: Any,
    intent_expected: str,
    is_last_intent_step: bool,
    existing_expected: str,
) -> str:
    if existing_expected:
        return existing_expected
    if is_last_intent_step and intent_expected:
        return intent_expected
    normalized_action = _normalized_text(action).lower()
    value_text = _normalized_text(value)
    target_name = _normalized_text(target_name) or _normalized_text(target_code)
    if normalized_action == "input":
        if target_code == "password_input" or "密码" in target_name:
            return f"{target_name}内容以掩码形式显示"
        if value_text:
            return f"{target_name}内容显示为 {value_text}"
        return f"{target_name}内容已清空"
    if normalized_action == "click":
        return f"已点击{target_name}"
    return ""


def _format_product_execution_steps(
    *,
    compiled_steps: list[dict[str, Any]],
    page: str,
    page_url: str,
    page_object: dict[str, Any],
    expected_by_intent: dict[str, str],
) -> list[dict[str, Any]]:
    elements = page_object.get("elements") if isinstance(page_object.get("elements"), dict) else {}
    last_step_index_by_intent: dict[str, int] = {}
    for index, step in enumerate(compiled_steps):
        if not isinstance(step, dict):
            continue
        intent_id = _normalized_text(step.get("intent_id"))
        action = _normalized_text(step.get("action")).lower()
        if intent_id and intent_id != "__page_entry__" and action not in {"goto", "login"}:
            last_step_index_by_intent[intent_id] = index

    product_steps: list[dict[str, Any]] = []
    for index, raw_step in enumerate(compiled_steps):
        if not isinstance(raw_step, dict):
            continue
        raw_action = _normalized_text(raw_step.get("action")).lower()
        if raw_action in {"fill", "type"}:
            action = "input"
        else:
            action = raw_action or "custom_step"
        if action == "goto":
            value = _normalized_text(raw_step.get("value") or raw_step.get("target") or page_url)
            if not value and page_url:
                value = page_url
            step_payload = {
                "action": "goto",
                "value": value,
                "expected_result": _normalized_text(raw_step.get("expected_result"))
                or _product_page_load_expected(page, page_object),
            }
            product_steps.append(step_payload)
            continue

        target_code = _normalized_text(raw_step.get("target"))
        if target_code.startswith("element:"):
            target_code = target_code.removeprefix("element:").strip()
        element_meta = _product_element_meta(page=page, target_code=target_code, elements=elements)
        # 页面对象库是正式 locator 的事实源。旧编译步骤里可能携带 CSS/role 兜底，
        # 只能在页面对象缺少 locator 时使用，不能覆盖已治理的 data-testid/qa 定位。
        locator_type = _normalized_text(element_meta.get("type") or element_meta.get("locator_type") or raw_step.get("locator_type"))
        locator_value = _normalized_text(element_meta.get("selector") or element_meta.get("locator_value") or raw_step.get("locator_value") or raw_step.get("selector"))
        locator_type, locator_value = _product_locator(
            page=page,
            target_code=target_code,
            locator_type=locator_type,
            locator_value=locator_value,
        )
        target_name = _product_element_name(page, target_code, element_meta)
        intent_id = _normalized_text(raw_step.get("intent_id"))
        intent_expected = expected_by_intent.get(intent_id, "")
        step_payload: dict[str, Any] = {
            "action": action,
            "target": f"element:{target_code}" if target_code else "",
            "locator_type": locator_type,
            "locator_value": locator_value,
            "target_name": target_name,
        }
        role = _normalized_text(raw_step.get("role") or element_meta.get("role"))
        if locator_type == "role" and role:
            step_payload["role"] = role
        if raw_step.get("value") is not None:
            step_payload["value"] = raw_step.get("value")
        expected = _product_step_expected(
            action=action,
            target_name=target_name,
            target_code=target_code,
            value=raw_step.get("value"),
            intent_expected=intent_expected,
            is_last_intent_step=bool(intent_id and last_step_index_by_intent.get(intent_id) == index),
            existing_expected=_normalized_text(raw_step.get("expected_result") or raw_step.get("expected")),
        )
        if expected:
            step_payload["expected_result"] = expected
        product_steps.append(step_payload)
    _append_login_success_assertion(
        product_steps=product_steps,
        page=page,
        page_object=page_object,
        expected_by_intent=expected_by_intent,
    )
    return product_steps


def _append_login_success_assertion(
    *,
    product_steps: list[dict[str, Any]],
    page: str,
    page_object: dict[str, Any],
    expected_by_intent: dict[str, str],
) -> None:
    if _normalized_text(page).lower() != "login":
        return
    if any(_normalized_text(step.get("action")).lower().startswith("assert") for step in product_steps):
        return
    expected_text = " ".join(_normalized_text(value) for value in expected_by_intent.values()).lower()
    if not expected_text:
        return
    negative_tokens = ("失败", "错误", "请输入", "不跳转", "未跳转", "停留", "提示")
    success_tokens = ("登录成功", "跳转至平台工作台首页", "工作台首页", "权限导航菜单")
    if any(token in expected_text for token in negative_tokens):
        return
    if not any(token in expected_text for token in success_tokens):
        return

    elements = page_object.get("elements") if isinstance(page_object.get("elements"), dict) else {}
    home_meta = _product_element_meta(page="login", target_code="home_menu", elements=elements)
    locator_type = _normalized_text(home_meta.get("type") or home_meta.get("locator_type"))
    locator_value = _normalized_text(home_meta.get("selector") or home_meta.get("locator_value"))
    if not locator_type or not locator_value:
        return
    assertion_step: dict[str, Any] = {
        "action": "assert_visible",
        "target": "element:home_menu",
        "locator_type": locator_type,
        "locator_value": locator_value,
        "target_name": _product_element_name("login", "home_menu", home_meta),
        "expected_result": "登录后首页菜单可见，确认已离开登录页并进入工作台",
    }
    role = _normalized_text(home_meta.get("role"))
    if locator_type == "role" and role:
        assertion_step["role"] = role
    product_steps.append(assertion_step)


def _step_element_code(step: dict[str, Any]) -> str:
    target = _normalized_text(step.get("target") or step.get("element_code"))
    if target.startswith("element:"):
        target = target.removeprefix("element:").strip()
    return target


def _is_variable_template(value: Any) -> bool:
    return isinstance(value, str) and bool(_VARIABLE_TEMPLATE_RE.fullmatch(value.strip()))


def _variable_template_key(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    match = _VARIABLE_TEMPLATE_RE.fullmatch(value.strip())
    if not match:
        return ""
    return _normalized_text(match.group(1))


def _data_key_for_input(*, page: str, element_code: str) -> str:
    normalized_page = _normalized_text(page).lower()
    normalized_code = _normalized_text(element_code).lower()
    if normalized_page == "login" and normalized_code == "username_input":
        return "username"
    if normalized_page == "login" and normalized_code == "password_input":
        return "password"
    if normalized_code.endswith("_input"):
        normalized_code = normalized_code[: -len("_input")]
    data_key = re.sub(r"[^a-z0-9_]+", "_", normalized_code).strip("_")
    return data_key or "input_value"


def _variable_name_for_input(*, page: str, element_code: str, data_key: str) -> str:
    normalized_page = re.sub(r"[^a-z0-9_]+", "_", _normalized_text(page).lower()).strip("_")
    normalized_code = _normalized_text(element_code).lower()
    if normalized_page == "login" and normalized_code == "username_input":
        return "login_username"
    if normalized_page == "login" and normalized_code == "password_input":
        return "login_password"
    return f"{normalized_page}_{data_key}" if normalized_page else data_key


def _reserve_data_key(data: dict[str, Any], base_key: str, value: Any) -> str:
    def _existing_value_matches(raw_entry: Any) -> bool:
        if isinstance(raw_entry, dict):
            source_type = _normalized_data_source_type(raw_entry.get("source_type") or "inline")
            if source_type != "inline":
                return False
            return raw_entry.get("value") == value
        if isinstance(raw_entry, list):
            return raw_entry == [value]
        return raw_entry == value

    key = base_key
    suffix = 2
    while key in data and not _existing_value_matches(data.get(key)):
        key = f"{base_key}_{suffix}"
        suffix += 1
    return key


def _reserve_variable_name(variables: dict[str, Any], base_name: str, template: str) -> str:
    name = base_name
    suffix = 2
    while name in variables and variables.get(name) != template:
        name = f"{base_name}_{suffix}"
        suffix += 1
    return name


def _normalized_data_source_type(value: Any) -> str:
    return _normalized_text(value).lower()


def _normalize_data_source_entry(*, key: str, raw_value: Any) -> dict[str, Any]:
    if isinstance(raw_value, dict):
        source_type = _normalized_data_source_type(raw_value.get("source_type") or "inline")
        if source_type not in _DSL_DATA_SOURCE_TYPES:
            raise ExecutionCompilerError(
                code="dsl_v1_1_invalid_data_source",
                message=f"DSL V1.1 data source_type is invalid for key `{key}`",
                reason=f"unsupported source_type `{source_type}`",
                stage="dsl_v1_1_enrichment",
            )
        if source_type == "inline":
            if "value" not in raw_value:
                raise ExecutionCompilerError(
                    code="dsl_v1_1_invalid_data_source",
                    message=f"DSL V1.1 inline data requires value for key `{key}`",
                    reason="inline source missing value",
                    stage="dsl_v1_1_enrichment",
                )
            return {"source_type": "inline", "value": raw_value.get("value")}
        if source_type == "pool":
            pool_name = _normalized_text(raw_value.get("pool_name"))
            pool_key = _normalized_text(raw_value.get("key"))
            if not pool_name or not pool_key:
                raise ExecutionCompilerError(
                    code="dsl_v1_1_invalid_data_source",
                    message=f"DSL V1.1 pool data requires pool_name and key for `{key}`",
                    reason="pool source missing pool_name/key",
                    stage="dsl_v1_1_enrichment",
                )
            return {"source_type": "pool", "pool_name": pool_name, "key": pool_key}
        env_key = _normalized_text(raw_value.get("key"))
        if not env_key:
            raise ExecutionCompilerError(
                code="dsl_v1_1_invalid_data_source",
                message=f"DSL V1.1 env data requires key for `{key}`",
                reason="env source missing key",
                stage="dsl_v1_1_enrichment",
            )
        return {"source_type": "env", "key": env_key}
    if isinstance(raw_value, list):
        if not raw_value:
            raise ExecutionCompilerError(
                code="dsl_v1_1_invalid_data_source",
                message=f"DSL V1.1 inline data list for `{key}` must not be empty",
                reason="legacy list source is empty",
                stage="dsl_v1_1_enrichment",
            )
        return {"source_type": "inline", "value": raw_value}
    return {"source_type": "inline", "value": raw_value}


def _normalize_dsl_data_sources(product_yaml: dict[str, Any]) -> dict[str, Any]:
    raw_data = product_yaml.get("data")
    if raw_data is None:
        normalized: dict[str, Any] = {}
        product_yaml["data"] = normalized
        return normalized
    if not isinstance(raw_data, dict):
        raise ExecutionCompilerError(
            code="dsl_v1_1_invalid_data_source",
            message="DSL V1.1 data must be an object",
            reason="data section is not object",
            stage="dsl_v1_1_enrichment",
        )
    normalized: dict[str, Any] = {}
    for raw_key, raw_value in raw_data.items():
        key = _normalized_text(raw_key)
        if not key:
            continue
        normalized[key] = _normalize_data_source_entry(key=key, raw_value=raw_value)
    product_yaml["data"] = normalized
    return normalized


def _enrich_dsl_v1_1_data_bindings(product_yaml: dict[str, Any], *, page: str) -> None:
    """把步骤里已有的输入值提升为 DSL V1.1 data/variables，不在代码层猜测默认值。"""
    execution_payload = product_yaml.get("execution") if isinstance(product_yaml.get("execution"), dict) else {}
    steps = execution_payload.get("steps") if isinstance(execution_payload.get("steps"), list) else []
    data = _normalize_dsl_data_sources(product_yaml)
    variables = execution_payload.get("variables") if isinstance(execution_payload.get("variables"), dict) else {}
    product_yaml["data"] = data
    execution_payload["variables"] = variables

    input_count = 0
    for index, step in enumerate(steps, start=1):
        if not isinstance(step, dict):
            continue
        action = _normalized_text(step.get("action")).lower()
        if action not in {"input", "fill"}:
            continue
        input_count += 1
        if "value" not in step:
            raise ExecutionCompilerError(
                code="dsl_v1_1_missing_input_data_source",
                message="DSL V1.1 input step requires declared data source",
                reason=f"input step {index} missing value or data reference",
                stage="dsl_v1_1_enrichment",
            )
        raw_value = step.get("value")
        if _is_variable_template(raw_value):
            referenced_key = _variable_template_key(raw_value)
            if not referenced_key:
                raise ExecutionCompilerError(
                    code="dsl_v1_1_missing_input_data_source",
                    message="DSL V1.1 input step variable reference is invalid",
                    reason=f"input step {index} has invalid variable template",
                    stage="dsl_v1_1_enrichment",
                )
            # 允许直接引用 data key，也允许先引用 execution.variables 再转到 data key。
            if referenced_key not in data:
                variable_mapping = variables.get(referenced_key)
                data_key = _variable_template_key(variable_mapping) if variable_mapping is not None else ""
                if not data_key or data_key not in data:
                    raise ExecutionCompilerError(
                        code="dsl_v1_1_missing_input_data_source",
                        message="DSL V1.1 input step requires declared data source",
                        reason=f"input step {index} references variable `{referenced_key}` without declared data source",
                        stage="dsl_v1_1_enrichment",
                    )
            continue

        element_code = _step_element_code(step)
        base_data_key = _data_key_for_input(page=page, element_code=element_code)
        data_key = _reserve_data_key(data, base_data_key, raw_value)
        data[data_key] = {"source_type": "inline", "value": raw_value}
        variable_template = f"{{{{{data_key}}}}}"
        base_variable_name = _variable_name_for_input(page=page, element_code=element_code, data_key=data_key)
        variable_name = _reserve_variable_name(variables, base_variable_name, variable_template)
        variables[variable_name] = variable_template
        step["value"] = f"{{{{{variable_name}}}}}"

    if input_count and not data:
        raise ExecutionCompilerError(
            code="dsl_v1_1_missing_input_data_source",
            message="DSL V1.1 input steps require declared data source",
            reason="input steps were found but no data bindings were generated",
            stage="dsl_v1_1_enrichment",
        )


def _normalize_top_level_assertion(step: dict[str, Any]) -> dict[str, Any]:
    assertion = {
        key: value
        for key, value in step.items()
        if key in _TOP_LEVEL_ASSERTION_KEYS and value is not None
    }
    if not _normalized_text(assertion.get("locator_value")) and _normalized_text(step.get("selector")):
        assertion["locator_value"] = _normalized_text(step.get("selector"))
    if not _normalized_text(assertion.get("target")) and _normalized_text(step.get("element_code")):
        assertion["target"] = f"element:{_normalized_text(step.get('element_code'))}"
    return assertion


def _assertion_signature(assertion: dict[str, Any]) -> tuple[str, ...]:
    return (
        _normalized_text(assertion.get("action")).lower(),
        _normalized_text(assertion.get("target") or assertion.get("element_code")),
        _normalized_text(assertion.get("locator_type")),
        _normalized_text(assertion.get("locator_value") or assertion.get("selector")),
        _normalized_text(assertion.get("value")),
        _normalized_text(assertion.get("count")),
        _normalized_text(assertion.get("metric_rule") or assertion.get("rule")),
        _normalized_text(assertion.get("extract_regex")),
    )


def _normalize_dsl_v1_1_assertions(product_yaml: dict[str, Any]) -> None:
    """标准化顶层断言：保留步骤内断言时序，只做顶层补充与去重。"""
    execution_payload = product_yaml.get("execution") if isinstance(product_yaml.get("execution"), dict) else {}
    steps = execution_payload.get("steps") if isinstance(execution_payload.get("steps"), list) else []
    assertions_raw = product_yaml.get("assertions") if isinstance(product_yaml.get("assertions"), list) else []
    assertions: list[dict[str, Any]] = []
    seen: set[tuple[str, ...]] = set()
    step_assertion_signatures: set[tuple[str, ...]] = set()

    for step in steps:
        if not isinstance(step, dict):
            continue
        action = _normalized_text(step.get("action")).lower()
        if action not in _SUPPORTED_TOP_LEVEL_ASSERTIONS:
            continue
        normalized_step_assertion = _normalize_top_level_assertion({**step, "action": action})
        step_assertion_signatures.add(_assertion_signature(normalized_step_assertion))

    def add_assertion(raw: Any) -> None:
        if not isinstance(raw, dict):
            return
        action = _normalized_text(raw.get("action")).lower()
        if action not in _SUPPORTED_TOP_LEVEL_ASSERTIONS:
            return
        normalized = _normalize_top_level_assertion({**raw, "action": action})
        signature = _assertion_signature(normalized)
        if signature in step_assertion_signatures:
            return
        if signature in seen:
            return
        seen.add(signature)
        assertions.append(normalized)

    for raw in assertions_raw:
        add_assertion(raw)
    product_yaml["assertions"] = assertions


def _is_ai_automated_case(product_yaml: dict[str, Any]) -> bool:
    status = _normalized_text(product_yaml.get("status")).lower()
    tags = product_yaml.get("tags") if isinstance(product_yaml.get("tags"), list) else []
    normalized_tags = {_normalized_text(tag).lower() for tag in tags if _normalized_text(tag)}
    case_id = _normalized_text(product_yaml.get("id")).lower()
    return status == "automated" and ("ai-generated" in normalized_tags or "-ai-" in case_id)


def _validate_dsl_v1_1_minimum_contract(product_yaml: dict[str, Any]) -> None:
    """校验 V1.1 最小契约：来源身份完整，AI 自动化用例必须有真实断言。"""
    requirement = product_yaml.get("requirement") if isinstance(product_yaml.get("requirement"), dict) else {}
    execution_payload = product_yaml.get("execution") if isinstance(product_yaml.get("execution"), dict) else {}
    intent_id = _normalized_text(requirement.get("intent_id"))
    source_asset_id = _normalized_text(requirement.get("source_asset_id"))
    selected_ids = execution_payload.get("selected_intent_ids") if isinstance(execution_payload.get("selected_intent_ids"), list) else []
    normalized_selected_ids = {_normalized_text(item) for item in selected_ids if _normalized_text(item)}
    if not intent_id or not source_asset_id or normalized_selected_ids != {intent_id}:
        raise ExecutionCompilerError(
            code="dsl_v1_1_missing_source_identity",
            message="DSL V1.1 case requires source_asset_id and exactly one selected intent_id",
            reason="source identity is incomplete",
            stage="dsl_v1_1_enrichment",
        )
    if _is_ai_automated_case(product_yaml):
        steps = execution_payload.get("steps") if isinstance(execution_payload.get("steps"), list) else []
        step_assertion_count = 0
        for raw_step in steps:
            if not isinstance(raw_step, dict):
                continue
            action = _normalized_text(raw_step.get("action")).lower()
            if action in _SUPPORTED_TOP_LEVEL_ASSERTIONS:
                step_assertion_count += 1
        assertions = product_yaml.get("assertions") if isinstance(product_yaml.get("assertions"), list) else []
        if not assertions and step_assertion_count <= 0:
            raise ExecutionCompilerError(
                code="dsl_v1_1_missing_executable_assertion",
                message="DSL V1.1 AI automated case requires executable assertions",
                reason="expected_result is documentation only",
                stage="dsl_v1_1_enrichment",
            )


def _enrich_product_case_yaml_v1_1(product_yaml: dict[str, Any], *, page: str) -> dict[str, Any]:
    """生成器统一出口：写入 DB 的 script_code 必须先满足 DSL V1.1 契约。"""
    product_yaml["version"] = "v1.1"
    _enrich_dsl_v1_1_data_bindings(product_yaml, page=page)
    _normalize_dsl_v1_1_assertions(product_yaml)
    _validate_dsl_v1_1_minimum_contract(product_yaml)
    return product_yaml


