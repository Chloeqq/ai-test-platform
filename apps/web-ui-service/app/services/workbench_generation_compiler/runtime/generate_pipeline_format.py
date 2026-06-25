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
    """
    生成用例的"产品化描述"（给人类看的标题，不是内部 ID）。

    - 如果标题含"首次登录"且预期里有跳转/首页等词 → 拼接完整登录场景描述
    - 如果标题和预期标准化后相同 → 说明预期只是标题的重复，直接返回标题
    - 如果预期有内容 → 拼接成"标题 — 预期"的形式（预期截取前 180 字符）
    - 兜底：返回原始标题或"AI生成用例"
    """
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
    """
    生成"页面加载完成"的预期结果文本。

    - 如果是登录页 → 返回固定文本：显示账号/密码/登录按钮
    - 如果页面对象有元素 → 取前 3 个元素名拼接成"XX页面加载完成，显示A、B、C"
    - 兜底：返回"XX页面加载完成"
    """
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
    """
    根据页面和目标 code，生成元素的"产品化中文名称"（用于展示给用户看）。

    登录页的元素有固定中文化映射（因为账号/密码/登录是最常用的页面）。
    其他页面从 element_meta 的 name/ element_name 取，取不到就用 target_code 本身。
    """
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
    """
    确定元素的定位方式（locator_type）和定位值（locator_value）。

    优先使用页面对象库已治理的 locator（从参数传入的 type/value）。
    如果没提供（空值），对登录页的 username_input / password_input 做硬编码 CSS 兜底。
    （这些是前端通用选择器，覆盖多种框架的命名习惯）
    """
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
    """
    按语义 target 取页面对象元素元数据。

    特殊逻辑：对登录页（page="login"），优先从真实 data-testid 代码名获取元素。
    因为登录页的 username_input 等是语义名，真正的页面代码里有 data-testid="login-username-input"，
    这个函数充当"语义名 → 真实测试 ID"的桥接。
    非登录页直接从 elements 字典里按 code 取。
    """
    normalized_page = _normalized_text(page).lower()
    normalized_code = _normalized_text(target_code)
    if normalized_page == "login":
        testid_code = _LOGIN_DATA_TESTID_ELEMENT_CODES.get(normalized_code, "")
        testid_meta = elements.get(testid_code) if testid_code and isinstance(elements.get(testid_code), dict) else {}
        if _normalized_text(testid_meta.get("type") or testid_meta.get("locator_type")) == "data-testid":
            return testid_meta
    return elements.get(normalized_code) if isinstance(elements.get(normalized_code), dict) else {}


def _trusted_page_url(*, payload_page_url: Any, page_object: dict[str, Any]) -> str:
    """
    校验并确定最终的 page_url。

    DSL V1.1 要求：如果页面对象库中已治理了 page_url，payload 里的 URL 必须一致。
    不一致则报错（防止生成器用了错误的页面 URL）。
    返回：治理的 URL（优先）或 payload 里的 URL。
    """
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
    """
    为单个执行步骤生成"预期的结果"文本（展示在用例报告里给人看）。

    优先级：
    1. 如果步骤已有 expected_result → 保留原样不动（不覆盖人工写的）
    2. 如果是意图的最后一步且意图有预期 → 用意图的预期（整个场景的总结）
    3. 根据 action 类型推测：
       - input（输入框）→ 密码字段显示"掩码显示"、有值显示"内容为XX"、空显示"已清空"
       - click → "已点击XX"
    4. 兜底：空字符串
    """
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
    """
    核心函数：把编译器生成的原始步骤（compiled_steps）"产品化"成最终用例步骤列表。

    做的事：
    - 统一动作名：fill/type → input
    - filter 出 goto 动作：从 raw_step 提取 URL，生成加载预期
    - 对其他动作：从页面对象库取定位信息（locator_type/value）、生成元素中文名、
      补充 expected_result
    - 为 fill/input 动作自动绑定 data-testid（如果已治理）
    - 最后追加登录成功断言（如果适用）

    这是 DSL V1.1 格式化的核心编排逻辑，所有步骤都在这里"变好看"。
    """
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
    _append_login_error_assertion(
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
    """
    在登录场景的步骤末尾追加一个"登录成功断言"（assert_visible home_menu）。

    前提条件（缺一不可）：
    1. 当前页面是 login 页
    2. 步骤里还没有任何 assert 动作（避免重复断言）
    3. 所有意图的预期文本汇总后不包含"失败/错误"等负面词汇
    4. 预期文本包含"登录成功"或"工作台首页"等成功信号
    5. 页面对象库中有 home_menu 的完整定位信息

    功能：确认登录后能看到首页菜单 → 证明已离开登录页进入工作台。
    """

    # V2.5b: 负向/异常场景不追加登录成功断言（登录应失败，home_menu 不会出现）
    all_expected = " ".join(expected_by_intent.values()).lower()
    error_keywords = ("错误", "失败", "提示", "异常", "无效", "非法", "锁定", "禁用")
    if any(kw in all_expected for kw in error_keywords):
        return

    # 避免重复：已有 home_menu 断言则跳过
    for s in product_steps:
        if isinstance(s, dict) and "home_menu" in str(s.get("target", "")):
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


def _append_login_error_assertion(
    *,
    product_steps: list[dict[str, Any]],
    page: str,
    page_object: dict[str, Any],
    expected_by_intent: dict[str, str],
) -> None:
    """V2.5b: 在负向登录场景追加错误提示断言（assert_visible error_message）。

    前提条件（缺一不可）：
    1. 当前页面是 login 页
    2. expected_by_intent 中存在负向/安全/异常场景的意图
       （expected 文本含"错误"/"失败"/"提示"等关键词）
    3. 步骤中还没有 error_message 的断言（避免重复）
    4. 页面对象库中有 error_message 的完整定位信息
    """
    if page != "login":
        return

    # 检查是否属于需要 error 断言的场景
    all_expected = " ".join(expected_by_intent.values()).lower()
    error_keywords = ("错误", "失败", "提示", "异常", "无效", "非法", "锁定", "禁用")
    if not any(kw in all_expected for kw in error_keywords):
        return

    # 避免重复：已有 error_message 断言则跳过
    for s in product_steps:
        if isinstance(s, dict) and "error_message" in str(s.get("target", "")):
            return

    elements = page_object.get("elements") if isinstance(page_object.get("elements"), dict) else {}
    error_meta = _product_element_meta(page="login", target_code="error_message", elements=elements)
    locator_type = _normalized_text(error_meta.get("type") or error_meta.get("locator_type"))
    locator_value = _normalized_text(error_meta.get("selector") or error_meta.get("locator_value"))
    if not locator_type or not locator_value:
        return

    assertion_step: dict[str, Any] = {
        "action": "assert_visible",
        "target": "element:error_message",
        "locator_type": locator_type,
        "locator_value": locator_value,
        "target_name": _product_element_name("login", "error_message", error_meta),
        "expected_result": "应显示错误提示信息",
    }
    role = _normalized_text(error_meta.get("role"))
    if locator_type == "role" and role:
        assertion_step["role"] = role
    product_steps.append(assertion_step)


def _step_element_code(step: dict[str, Any]) -> str:
    """
    从步骤字典中提取元素代码（element code）。

    元素代码有两种格式：
    - "element:username_input"（V1.1 标准化格式）→ 去掉前缀返回 "username_input"
    - "username_input"（旧格式）→ 直接返回
    """
    target = _normalized_text(step.get("target") or step.get("element_code"))
    if target.startswith("element:"):
        target = target.removeprefix("element:").strip()
    return target


def _is_variable_template(value: Any) -> bool:
    """
    判断一个值是不是 DSL 变量模板，例如 "{{username}}"。

    变量模板的格式由 _VARIABLE_TEMPLATE_RE 正则定义（一般为 "{{key}}" 形式）。
    """
    return isinstance(value, str) and bool(_VARIABLE_TEMPLATE_RE.fullmatch(value.strip()))


def _variable_template_key(value: Any) -> str:
    """
    从变量模板中提取 key 值。

    例：输入 "{{username}}" → 返回 "username"
    用途：当步骤里值是 "{{username}}" 时，知道它的数据来自 data 字典的 username 键。
    """
    if not isinstance(value, str):
        return ""
    match = _VARIABLE_TEMPLATE_RE.fullmatch(value.strip())
    if not match:
        return ""
    return _normalized_text(match.group(1))


def _data_key_for_input(*, page: str, element_code: str) -> str:
    """
    根据页面名和元素代码，生成输入数据在 data 字典里的 key 名。

    登录页有固定映射：username_input → "username", password_input → "password"
    其他页面：去掉元素代码末尾的 "_input" 后缀，把非法字符替换为下划线。
    """
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
    """
    生成变量名，用于 execution.variables 中引用 data。

    登录页固定映射：→ "login_username" / "login_password"
    其他页面："{page}_{data_key}"，page 内部的非法字符替换为下划线。
    """
    normalized_page = re.sub(r"[^a-z0-9_]+", "_", _normalized_text(page).lower()).strip("_")
    normalized_code = _normalized_text(element_code).lower()
    if normalized_page == "login" and normalized_code == "username_input":
        return "login_username"
    if normalized_page == "login" and normalized_code == "password_input":
        return "login_password"
    return f"{normalized_page}_{data_key}" if normalized_page else data_key


def _reserve_data_key(data: dict[str, Any], base_key: str, value: Any) -> str:
    """
    往 data 字典插入 key 时，如果 key 已存在且值不同，自动加后缀避免冲突。

    比如 data 里已有 "username"（值是 "admin"），现在要保留 "user"（也是 "admin"），
    发现已有且值相同 → 复用 "username"
    发现已有且值不同 → 改为 "username_2"
    再冲突 → "username_3" 以此类推
    """
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


# ── DSL V1.3 数据语义标注 ──────────────────────────────────────────────────
# 每条 data 条目可以声明 subtype，表达这条数据的测试语义。
# V1.1 兼容：subtype 是可选的，缺失时自动从 value 推断。

_DSL_DATA_SUBTYPES: frozenset[str] = frozenset({
    "valid", "invalid", "boundary", "empty",
    "whitespace", "special_chars", "generated", "pool",
})

# 检测自然语言描述值的模式
_NL_DESCRIPTION_KEYWORDS: frozenset[str] = frozenset({
    "最小", "最大", "合法", "非法", "无效", "有效",
    "边界", "超长", "超短", "空值", "空格",
})


def _infer_data_subtype(value: Any) -> str | None:
    """根据 value 自动推断 data subtype。仅适用于 inline 数据。

    返回 subtype 字符串，无法推断时返回 None。
    """
    if value is None:
        return "empty"
    if not isinstance(value, str):
        return None
    if value == "":
        return "empty"
    if value.strip() == "" and len(value) > 0:
        return "whitespace"
    if any(ch in value for ch in ("<", ">", "'", "\"", ";", "|", "&")):
        return "special_chars"
    return None  # 普通值，无法自动推断


def _is_natural_language_description(value: Any) -> bool:
    """检测值是否为自然语言描述而非测试数据。

    例："最小长度合法账号" → 是描述，不是能填入输入框的值。
        "admin"             → 是测试数据。

    返回 True 表示值看起来像描述文本。
    """
    if not isinstance(value, str) or not value.strip():
        return False
    stripped = value.strip()
    # 短字符串 (<8 chars) 不太可能是描述
    if len(stripped) < 8:
        return False
    # 含数字或英文字母 → 很可能是实际数据
    if any(ch.isdigit() for ch in stripped):
        return False
    if any(ch.isascii() and ch.isalpha() for ch in stripped):
        return False
    # 中文字符占比 > 80% 且含描述性关键词 → 可能是自然语言描述
    chinese_chars = sum(1 for ch in stripped if '一' <= ch <= '鿿')
    if len(stripped) >= 8 and chinese_chars / len(stripped) >= 0.8:
        match_count = sum(1 for kw in _NL_DESCRIPTION_KEYWORDS if kw in stripped)
        if match_count >= 1:
            return True
    return False


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
            raw_subtype = _normalized_text(raw_value.get("subtype", ""))
            entry: dict[str, Any] = {"source_type": "inline", "value": raw_value.get("value")}
            # V1.3: subtype 归一化
            if raw_subtype:
                if raw_subtype not in _DSL_DATA_SUBTYPES:
                    raise ExecutionCompilerError(
                        code="dsl_v1_3_invalid_data_subtype",
                        message=f"DSL V1.3 data subtype is invalid for key `{key}`",
                        reason=f"unsupported subtype `{raw_subtype}` (allowed: {sorted(_DSL_DATA_SUBTYPES)})",
                        stage="dsl_v1_3_enrichment",
                    )
                entry["subtype"] = raw_subtype
                # V1.3: 检测显式 subtype 与自动推断是否矛盾
                inferred = _infer_data_subtype(raw_value.get("value"))
                if inferred and inferred != raw_subtype:
                    _LOGGER.warning(
                        "DSL V1.3: data key '%s' explicit subtype='%s' contradicts "
                        "auto-inferred subtype='%s' from value=%s",
                        key, raw_subtype, inferred,
                        str(raw_value.get("value"))[:60],
                    )
            else:
                inferred = _infer_data_subtype(raw_value.get("value"))
                if inferred:
                    entry["subtype"] = inferred
            # V1.3: 自然语言描述检测 — 禁止将描述文本当作测试数据值
            if _is_natural_language_description(raw_value.get("value")):
                raise ExecutionCompilerError(
                    code="dsl_v1_3_natural_language_value",
                    message=f"DSL V1.3 data key `{key}` value is a natural language description",
                    reason=(
                        f"value='{str(raw_value.get('value'))[:80]}' looks like a description "
                        f"rather than test data. Use subtype annotation to declare test data "
                        f"semantics (valid/invalid/boundary/empty/whitespace/special_chars), "
                        f"and set value to the actual test input."
                    ),
                    stage="dsl_v1_3_enrichment",
                )
            return entry
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
    """
    标准化 DSL V1.1 的 data 段。

    - 如果 data 不存在 → 创建空字典
    - 如果 data 不是字典 → 报错（V1.1 要求 data 必须是对象）
    - 如果 data 是字典 → 逐条标准化每个数据源（inline / pool / env）

    返回标准化后的 data 字典。
    """
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
    """
    AI 生成的用例中，input 步骤的 value 是直接写在步骤里的。
    这个函数把它们抽取为 DSL V1.1 的 data + variables 格式。

    过程：
    1. 遍历所有 input/fill 步骤
    2. 如果步骤 value 已经是变量模板（"{{xxx}}"）→ 校验引用链是否有效
    3. 如果步骤 value 是字面值 → 在 data 里创建条目，在 execution.variables 里创建引用
    4. 步骤的 value 改为 "{{variable_name}}" 格式（通过变量间接引用 data）

    目的是实现"数据与步骤分离"：步骤只存"数据来自哪里"，不直接存硬编码值。
    """
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
    """
    标准化单条顶层断言：只保留断言相关的 key，补齐 selector/target 字段。

    入参可能是步骤字典或断言字典，只提取 _TOP_LEVEL_ASSERTION_KEYS 中定义的字段。
    如果 locator_value 为空但步骤里有 selector → 用 selector 补上
    如果 target 为空但步骤里有 element_code → 用 "element:{code}" 补上
    """
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
    """
    为断言生成"签名"（多个关键字段组成的元组），用于去重判断。

    如果两个断言的 action / target / locator_type / locator_value / value /
    count / rule / extract_regex 全部相同 → 视为重复断言。
    """
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
    """
    标准化顶层断言（product_yaml.assertions）。

    原则：
    - 步骤内已有的断言（如 assert_visible）保留原位不动（时序敏感）
    - 顶层 assertions 只做"补充"：不重复步骤已有的断言
    - 顶层 assertions 内部也去重（同一次接口调用可能重复返回断言条目）

    实现方式：先收集步骤中所有断言的签名，然后过滤顶层断言中签名重复的条目。
    """
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
    """
    判断一个用例是不是"AI 生成的自动化用例"。

    判断条件（同时满足）：
    - status == "automated"
    - tags 中有 "ai-generated"，或 case id 包含 "-ai-"

    AI 自动化用例必须包含可执行的断言（见 _validate_dsl_v1_1_minimum_contract）。
    """
    status = _normalized_text(product_yaml.get("status")).lower()
    tags = product_yaml.get("tags") if isinstance(product_yaml.get("tags"), list) else []
    normalized_tags = {_normalized_text(tag).lower() for tag in tags if _normalized_text(tag)}
    case_id = _normalized_text(product_yaml.get("id")).lower()
    return status == "automated" and ("ai-generated" in normalized_tags or "-ai-" in case_id)


def _validate_dsl_v1_1_minimum_contract(product_yaml: dict[str, Any]) -> None:
    """
    DSL V1.1 契约校验（写在最后一个 enrichment 步骤之后）。

    检查 2 个条件：
    1. 来源身份完整：requirement.intent_id、requirement.source_asset_id 必须存在，
       且 execution.selected_intent_ids 必须只包含 intent_id（不多也不少）
       → 确保用例能追溯到唯一的来源意图
    2. AI 自动化用例必须有可执行断言（步骤内的 assert_xxx 或顶层 assertions）
       → 光有 expected_result（文本述）不够，需要真正的 executable assertion
         因为 runner 执行时只认 assert_xxx 动作，不读 expected_result

    任何条件不满足 → 直接抛 ExecutionCompilerError，拒绝写入 DB。
    """
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
    """
    === DSL V1.1 格式化的统一出口 ===

    所有用例在写入 DB 的 script_code 之前，必须经过此函数。

    执行流程（3 步）：
    1. _enrich_dsl_v1_1_data_bindings — 把 input 步骤的硬编码值抽出为 data/variables
    2. _normalize_dsl_v1_1_assertions — 标准化并去重顶层断言
    3. _validate_dsl_v1_1_minimum_contract — 校验最小契约完整性

    任何一步失败都会抛 ExecutionCompilerError，不会写入错误格式的数据。
    """
    product_yaml["version"] = "v1.1"
    _enrich_dsl_v1_1_data_bindings(product_yaml, page=page)
    _normalize_dsl_v1_1_assertions(product_yaml)
    _validate_dsl_v1_1_minimum_contract(product_yaml)
    return product_yaml


# ── V2.5a: Locator 归一化 ─────────────────────────────────────────────────

def _normalize_step_locators(
    *,
    steps: list[dict[str, Any]],
    page_object: dict[str, Any],
) -> int:
    """V2.5a: 用 page object 的正式 locator 定义覆盖步骤中的 AI 生成值。

    对每个引用了 element 的步骤，在 page_object 中查找该 element 的定义，
    用其 locator_type/locator_value 替换步骤中的值。
    若 element 使用 role 定位，同步 role 字段。

    返回修改的步骤数。
    """
    elements = page_object.get("elements") if isinstance(page_object, dict) else None
    if not isinstance(elements, dict) or not elements:
        return 0

    normalized_count = 0
    for step in steps:
        if not isinstance(step, dict):
            continue

        target = str(step.get("target", ""))
        if not target.startswith("element:"):
            continue
        element_code = target[len("element:"):].strip()
        if not element_code:
            continue

        element_def = elements.get(element_code)
        if not isinstance(element_def, dict):
            continue

        po_type = _normalized_text(
            element_def.get("type") or element_def.get("locator_type") or ""
        )
        po_value = _normalized_text(
            element_def.get("selector") or element_def.get("locator_value") or ""
        )

        if po_type and po_type != _normalized_text(step.get("locator_type", "")):
            step["locator_type"] = po_type
            normalized_count += 1
        if po_value and po_value != _normalized_text(step.get("locator_value", "")):
            step["locator_value"] = po_value
        if po_type == "role" and element_def.get("role"):
            step["role"] = _normalized_text(element_def.get("role"))

    if normalized_count:
        _LOGGER.debug(
            "V2.5a locator normalization: %d steps updated to match page object",
            normalized_count,
        )

    return normalized_count



