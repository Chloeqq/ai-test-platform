"""V2.5a: Locator 归一化 — 用 page object 正式定义覆盖 AI 生成的 locator。"""

from __future__ import annotations

import logging
from typing import Any

_LOGGER = logging.getLogger(__name__)


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

    from .generate_pipeline_format import _normalized_text

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
