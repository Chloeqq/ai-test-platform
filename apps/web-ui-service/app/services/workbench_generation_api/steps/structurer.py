"""将自然语言步骤转换为 DSL V1.1 结构化步骤。

核心编译函数，负责：
1. 解析 AI 的 steps_hint 构建 hint_value_map
2. 处理前置条件（通过 PageHook）
3. 遍历步骤：识别元素 → 分类 action → 提取输入值 → 构造 DSL step
4. 从 expected 文本生成对应的断言步骤
"""

from __future__ import annotations

from typing import Any

from shared_backend.step_fields import (
    ACTION_ASSERT_ATTRIBUTE,
    ACTION_ASSERT_TEXT,
    ACTION_ASSERT_URL,
    ACTION_ASSERT_VISIBLE,
    ACTION_CANDIDATE,
    ACTION_CLICK,
    ACTION_GOTO,
    ACTION_INPUT,
    HINT_INPUT_ACTIONS,
    HINT_SEP_ACTION,
    HINT_SEP_VALUE,
    format_steps_hint,
)
from shared_backend.text_utils import (
    extract_error_message,
    extract_input_value,
    has_negation_before,
)
from shared_backend.type_utils import append_unique
from shared_backend.type_utils import str_value as _normalized_text

from .. import constants as _c
from ..elements.resolver import ElementResolver, _data_ref_for_element
from ..hooks.base import PageHook


def structured_steps_from_candidate(
    *,
    candidate: dict[str, Any],
    steps: list[str],
    expected: str,
    resolver: ElementResolver | None = None,
    page_hook: PageHook | None = None,
    page_config: Any = None,  # PageConfig (lazy import to avoid circular dep)
    point_type: str = "",
) -> tuple[list[dict[str, Any]], list[str], dict[str, dict[str, Any]], list[str], list[str], int]:
    """将候选测试点步骤治理成 DSL V1.1 可消费的结构化步骤、steps_hint 与 data。

    返回:
      structured_steps: DSL step dict 列表
      steps_hint: AI/编译器之间的精简协议字符串列表
      data: 测试数据字典 {data_ref: {source_type, value}}
      warnings: 结构化过程中的警告信息
      involved_codes: 步骤中涉及的所有 element_code
    """
    structured_steps: list[dict[str, Any]] = []
    steps_hint: list[str] = []
    data: dict[str, dict[str, Any]] = {}
    warnings: list[str] = []
    involved_codes: list[str] = []

    if resolver is None:
        resolver = ElementResolver()

    # 预解析 AI 的 steps_hint，构建 target → value 映射
    hint_value_map: dict[str, str] = _parse_hint_value_map(candidate.get("steps_hint") or [])

    # 处理需要补步骤的前置条件（如密码可见性切换）
    if page_hook is not None:
        precondition_text = _normalized_text(candidate.get("precondition"))
        precondition_setup = page_hook.setup_precondition_steps(precondition_text)
        for setup_step in precondition_setup:
            structured_steps.append(setup_step)
            if setup_step["action"] == ACTION_INPUT:
                data[_c.PASSWORD_DATA_REF] = {
                    "source_type": _c.SOURCE_TYPE_INLINE,
                    "value": setup_step["value"],
                }
                append_unique(
                    steps_hint,
                    format_steps_hint(ACTION_INPUT, setup_step["target_name"], str(setup_step["value"])),
                )
            elif setup_step["action"] == ACTION_CLICK:
                append_unique(steps_hint, format_steps_hint(ACTION_CLICK, setup_step["target_name"]))
            append_unique(involved_codes, setup_step["target"].removeprefix(_c.ELEMENT_PREFIX))

    # 主步骤循环
    for raw_step in steps:
        step_text = _normalized_text(raw_step)
        if not step_text:
            continue
        element = resolver.resolve(step_text)

        # ── input 步骤 ──
        if any(token in step_text for token in _c.INPUT_ACTION_TOKENS) and element is not None:
            _build_input_step(
                step_text, element, hint_value_map,
                resolver, structured_steps, steps_hint, data, warnings, involved_codes,
            )
            continue

        # ── click 步骤 ──
        if _c.CLICK_ACTION_TOKEN in step_text and element is not None:
            _build_click_step(
                step_text, element, expected,
                resolver, page_hook, structured_steps, steps_hint, involved_codes,
            )
            continue

        # ── goto 步骤 ──
        if any(token in step_text for token in _c.GOTO_ACTION_TOKENS):
            route = page_config.default_route if page_config else _c.GOTO_DEFAULT_ROUTE
            structured_steps.append(
                {"action": ACTION_GOTO, "value": route, "raw_text": step_text}
            )
            append_unique(steps_hint, format_steps_hint(ACTION_GOTO, route))
            continue

        # ── 无法分类 → 降级 ──
        structured_steps.append(
            {"action": ACTION_CANDIDATE, "target": "", "value": step_text, "raw_text": step_text}
        )
        warnings.append(f"{_c.MSG_NEEDS_MANUAL_STRUCTURING}{step_text}")

    # expected 断言
    assertion_count = _build_expected_assertions(
        expected=expected,
        involved_codes=involved_codes,
        structured_steps=structured_steps,
        steps_hint=steps_hint,
        page_config=page_config,
        point_type=point_type,
    )

    # 完全为空时用 summary/title 做 fallback
    if not structured_steps:
        fallback = _normalized_text(candidate.get("summary") or candidate.get("title"))
        if fallback:
            structured_steps.append(
                {"action": ACTION_CANDIDATE, "target": "", "value": fallback, "raw_text": fallback}
            )
            warnings.append(_c.MSG_NO_STRUCTURABLE_STEPS)

    return structured_steps, steps_hint, data, warnings, involved_codes, assertion_count


# ── 内部辅助函数 ──────────────────────────────────────────────────────────────

# FIX(Phase B): button-like element codes that should NOT be used as assert_text targets
_BUTTON_LIKE_CODES = frozenset({"btn", "button", "submit", "login-btn", "login-submit-btn", "submit-btn"})


def _find_assert_target(involved_codes: list[str]) -> str:
    """Find a suitable target for assert_text from involved_codes.

    Filters out button-like elements (submit/login/submit-btn).
    If no suitable target found, returns empty string — caller should
    not generate an assert_text step with a bad target.
    """
    if not involved_codes:
        return ""
    for code in involved_codes:
        if code.lower() in _BUTTON_LIKE_CODES:
            continue
        # Also skip codes that contain button-like suffixes
        if any(suffix in code.lower() for suffix in ("btn", "-btn", "button", "submit")):
            continue
        return code
    return ""


def _parse_hint_value_map(steps_hint_items: list[Any]) -> dict[str, str]:
    """解析 AI 的 steps_hint 列表，构建 target → value 映射。

    输入: ["input:username=", "input:password=123456", "click:loginButton"]
    输出: {"username": "", "password": "123456"}
    """
    hint_value_map: dict[str, str] = {}
    for hint in steps_hint_items:
        hint_text = _normalized_text(hint)
        if not hint_text or HINT_SEP_ACTION not in hint_text:
            continue
        action_raw, _, payload = hint_text.partition(HINT_SEP_ACTION)
        if _normalized_text(action_raw) not in HINT_INPUT_ACTIONS:
            continue
        target, _, value = payload.partition(HINT_SEP_VALUE)
        target = _normalized_text(target)
        value = _normalized_text(value)
        if target:
            hint_value_map[target] = value
    return hint_value_map


def _build_input_step(
    step_text: str,
    element: tuple[str, str, str],
    hint_value_map: dict[str, str],
    resolver: ElementResolver,
    structured_steps: list[dict[str, Any]],
    steps_hint: list[str],
    data: dict[str, dict[str, Any]],
    warnings: list[str],
    involved_codes: list[str],
) -> None:
    """构造 input 步骤并追加到各列表中。"""
    element_code, element_name, data_key_hint = element
    has_value, value = extract_input_value(
        step_text,
        empty_tokens=_c.EMPTY_INPUT_TOKENS,
        space_token=_c.SPACE_INPUT_TOKEN,
        input_value_pattern=_c.INPUT_VALUE_PATTERN,
    )
    data_ref = _data_ref_for_element(element_code, data_key_hint)
    fallback_value = ""

    step: dict[str, Any] = {
        "action": ACTION_INPUT,
        "target": f"{_c.ELEMENT_PREFIX}{element_code}",
        "target_name": element_name,
        "data_ref": data_ref,
        "raw_text": step_text,
    }

    if has_value:
        step["value"] = value
        data[data_ref] = {"source_type": _c.SOURCE_TYPE_INLINE, "value": value}
        if value == " ":
            warnings.append(
                _c.MSG_SPACE_INPUT_STEPS_HINT_LIMITATION.format(element_name=element_name)
            )
        else:
            append_unique(steps_hint, format_steps_hint(ACTION_INPUT, element_name, str(value)))
    else:
        fallback_value = ""
        for hint_name, hint_val in hint_value_map.items():
            hint_elem = resolver.resolve(hint_name)
            if hint_elem is not None and hint_elem[0] == element_code:
                fallback_value = hint_val
                break
        if fallback_value:
            step["value"] = fallback_value
            data[data_ref] = {"source_type": _c.SOURCE_TYPE_INLINE, "value": fallback_value}
            append_unique(
                steps_hint, format_steps_hint(ACTION_INPUT, element_name, str(fallback_value))
            )
        else:
            warnings.append(
                _c.MSG_INPUT_STEP_MISSING_DATA.format(
                    element_name=element_name, step_text=step_text
                )
            )

    structured_steps.append(step)
    append_unique(involved_codes, element_code)


def _build_click_step(
    step_text: str,
    element: tuple[str, str, str],
    expected: str,
    resolver: ElementResolver,
    page_hook: PageHook | None,
    structured_steps: list[dict[str, Any]],
    steps_hint: list[str],
    involved_codes: list[str],
) -> None:
    """构造 click 步骤并追加到各列表中。"""
    element_code, element_name, _data_key = element
    _ = resolver

    structured_steps.append(
        {
            "action": ACTION_CLICK,
            "target": f"{_c.ELEMENT_PREFIX}{element_code}",
            "target_name": element_name,
            "raw_text": step_text,
        }
    )
    append_unique(steps_hint, format_steps_hint(ACTION_CLICK, element_name))
    append_unique(involved_codes, element_code)

    # 页面 Hook：click 后补充断言
    if page_hook is not None:
        for extra_step in page_hook.post_click_assertions(element_code, expected):
            structured_steps.append(extra_step)
            if extra_step.get("action") == ACTION_ASSERT_ATTRIBUTE:
                append_unique(
                    steps_hint,
                    format_steps_hint(
                        ACTION_ASSERT_ATTRIBUTE,
                        extra_step["target_name"],
                        f"{extra_step.get('attribute', '')}={extra_step.get('value', '')}",
                    ),
                )
                append_unique(
                    involved_codes,
                    extra_step["target"].removeprefix(_c.ELEMENT_PREFIX),
                )


def _build_expected_assertions(
    *,
    expected: str,
    involved_codes: list[str],
    structured_steps: list[dict[str, Any]],
    steps_hint: list[str],
    page_config: Any = None,
    point_type: str = "",
) -> int:
    """从 expected 文本生成对应的 DSL 断言步骤。返回生成的断言数量。

    质量规则 (P0):
    - negative/boundary/format: 必须用 assert_text 验证错误文案，不可降级为 assert_url
    - functional: 无可匹配 token 时不捏造断言，由调用方标记 requires_review
    """
    expected_text = _normalized_text(expected)
    count_before = len(structured_steps)

    home_code = page_config.home_element_code if page_config else _c.HOME_ELEMENT_CODE
    home_name = page_config.home_element_name if page_config else _c.HOME_ELEMENT_NAME
    fallback_code = page_config.fallback_element_code if page_config else _c.LAST_ELEMENT_FALLBACK_CODE

    _needs_strong_assertion = point_type in _c.STRONG_ASSERTION_REQUIRED_TYPES

    if any(token in expected_text for token in _c.ASSERT_VISIBLE_TOKENS):
        structured_steps.append(
            {
                "action": ACTION_ASSERT_VISIBLE,
                "target": f"{_c.ELEMENT_PREFIX}{home_code}",
                "target_name": home_name,
                "raw_text": expected_text or _c.ASSERT_VISIBLE_FALLBACK_TEXT,
            }
        )
        append_unique(steps_hint, format_steps_hint(ACTION_ASSERT_VISIBLE, home_name))
    elif any(token in expected_text for token in _c.ASSERT_TEXT_TOKENS):
        error_msg = extract_error_message(expected_text)
        # FIX(Phase B): 不使用 involved_codes[-1] 作为 assert_text 的 target。
        # 最后一个操作元素通常是 button(如 login-submit-btn)，错误信息不会出现在 button 上。
        # 查找 role 匹配的元素，找不到则留空标记 RESOLVE_NEEDED。
        target_code = _find_assert_target(involved_codes)
        if target_code:
            structured_steps.append(
                {
                    "action": ACTION_ASSERT_TEXT,
                    "target": f"{_c.ELEMENT_PREFIX}{target_code}",
                    "target_name": target_code,
                    "value": error_msg,
                    "raw_text": expected_text or _c.ASSERT_TEXT_FALLBACK_TEXT,
                }
            )
            append_unique(steps_hint, format_steps_hint(ACTION_ASSERT_TEXT, target_code, error_msg))
        else:
            warnings.append(
                _c.MSG_NEEDS_MANUAL_STRUCTURING + f"assert_text target not found for '{error_msg[:30]}'"
            )
    elif any(token in expected_text for token in _c.ASSERT_URL_TOKENS):
        if not has_negation_before(expected_text, _c.ASSERT_URL_TOKENS):
            # P0: negative/boundary/format 场景禁止只生成 assert_url
            # 必须生成 assert_text 验证错误文案
            if _needs_strong_assertion:
                error_msg = extract_error_message(expected_text)
                # FIX(Phase B): 同上方修复，不使用 involved_codes[-1] 作为 target
                target_code = _find_assert_target(involved_codes)
                if target_code:
                    structured_steps.append(
                        {
                            "action": ACTION_ASSERT_TEXT,
                            "target": f"{_c.ELEMENT_PREFIX}{target_code}",
                            "target_name": target_code,
                            "value": error_msg,
                            "raw_text": expected_text or _c.ASSERT_TEXT_FALLBACK_TEXT,
                        }
                    )
                    append_unique(
                        steps_hint,
                        format_steps_hint(ACTION_ASSERT_TEXT, target_code, error_msg),
                    )
                else:
                    warnings.append(
                        _c.MSG_NEEDS_MANUAL_STRUCTURING + f"strong assertion target not found for '{error_msg[:30]}'"
                    )
            else:
                url_fallback = page_config.login_url if page_config else _c.ASSERT_URL_FALLBACK
                structured_steps.append(
                    {
                        "action": ACTION_ASSERT_URL,
                        "value": url_fallback,
                        "raw_text": expected_text or _c.ASSERT_URL_FALLBACK_TEXT,
                    }
                )
                append_unique(steps_hint, format_steps_hint(ACTION_ASSERT_URL, url_fallback))

    return len(structured_steps) - count_before



