"""V2.5b: 断言编译器 — 负向用例自动生成 error 断言。

使用 lazy import 避免与 generate_pipeline_format 的循环引用。
"""

from __future__ import annotations

from typing import Any

from shared_backend.quality_gate.models import NEGATIVE_SCENARIO_KEYWORDS


def _append_login_error_assertion(
    *,
    product_steps: list[dict[str, Any]],
    page: str,
    page_object: dict[str, Any],
    expected_by_intent: dict[str, str],
) -> None:
    """V2.5b: 在负向登录场景追加错误提示断言（assert_visible error_message）。"""
    if page != "login":
        return

    all_expected = " ".join(expected_by_intent.values()).lower()
    if not any(kw in all_expected for kw in NEGATIVE_SCENARIO_KEYWORDS):
        return

    for s in product_steps:
        if isinstance(s, dict) and "error_message" in str(s.get("target", "")):
            return

    # lazy imports — 避免循环引用
    from .generate_pipeline_format import (
        _normalized_text,
        _product_element_meta,
        _product_element_name,
    )

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
