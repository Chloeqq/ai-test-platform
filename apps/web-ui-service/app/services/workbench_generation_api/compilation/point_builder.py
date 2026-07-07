"""测试点编译 — 将单个候选测试点编译为可存储的 point 字典。"""

from __future__ import annotations

from typing import Any

from shared_backend.type_utils import str_value as _normalized_text, as_text_list, append_unique

from .. import constants as _c
from ..elements.resolver import ElementResolver
from ..hooks.base import PageHook
from ..assets.preview import candidate_snapshot
from .precondition import fallback_precondition
from ..steps.structurer import structured_steps_from_candidate


def build_point(
    candidate: dict[str, Any],
    *,
    index: int,
    resolver: ElementResolver | None = None,
    page_hook: PageHook | None = None,
    page_config: Any = None,  # PageConfig
) -> dict[str, Any]:
    """将单个候选测试点编译为可存储的 point 字典。

    处理流程：
    1. 字段提取：从 candidate 中取 intent_id / title / steps / expected 等
    2. 前置条件补齐
    3. action 判定：point_type 在 REVIEW_POINT_TYPES 中则标记为 "review"
    4. 步骤结构化：将自然语言→DSL 步骤
    5. 元素解析：将中文元素名→规范 code
    """
    intent_id = _normalized_text(candidate.get("intent_id")) or f"candidate-{index:02d}"
    title = _normalized_text(candidate.get("title")) or intent_id
    summary = _normalized_text(candidate.get("summary")) or title
    steps = as_text_list(candidate.get("steps"))
    involved_elements = as_text_list(candidate.get("involved_elements"))
    expected = _normalized_text(candidate.get("expected") or candidate.get("expected_result"))
    point_type = _normalized_text(candidate.get("intent_type")) or _c.DEFAULT_POINT_TYPE
    precondition = fallback_precondition(candidate, point_type=point_type, expected=expected)
    action = _c.POINT_ACTION_CANDIDATE
    if point_type in _c.REVIEW_POINT_TYPES:
        action = _c.POINT_ACTION_REVIEW

    point_steps, steps_hint, data, structure_warnings, involved_codes = structured_steps_from_candidate(
        candidate=candidate,
        steps=steps or [summary],
        expected=expected,
        resolver=resolver,
        page_hook=page_hook,
        page_config=page_config,
    )

    warnings: list[str] = []
    warnings.extend(structure_warnings)
    if not steps:
        warnings.append(_c.MSG_STEPS_MISSING)
    if not involved_elements:
        warnings.append(_c.MSG_ELEMENTS_MISSING)
    involved_elements = _resolve_involved_element_codes(involved_elements, involved_codes, resolver)

    return {
        "key": intent_id,
        "intent_id": intent_id,
        "point_type": point_type,
        "action": action,
        "description": summary,
        "step_index": index,
        "dependencies": [],
        "source_ids": [intent_id],
        "steps": point_steps,
        "steps_hint": steps_hint,
        "data": data,
        "warnings": warnings,
        "requires_review": bool(warnings),
        "involved_elements": involved_elements,
        "expected_result": expected,
        "precondition": precondition,
        "tags": as_text_list(candidate.get("tags")),
        "priority": _normalized_text(candidate.get("priority")) or _c.DEFAULT_PRIORITY,
        "confidence": _c.DEFAULT_CONFIDENCE_WITH_STEPS if steps else _c.DEFAULT_CONFIDENCE_WITHOUT_STEPS,
        "metadata": {
            "candidate_snapshot": candidate_snapshot(candidate),
            "traceability": {
                "source_ids": [intent_id],
                "intent_ids": [intent_id],
            },
            "dsl_v1_1_structuring": {
                "data_keys": sorted(data.keys()),
                "steps_hint_count": len(steps_hint),
                "has_precondition": bool(precondition and precondition != _c.FALLBACK_PRECONDITION),
            },
        },
    }


def _resolve_involved_element_codes(
    involved_elements: list[str],
    involved_codes: list[str],
    resolver: ElementResolver | None = None,
) -> list[str]:
    """将中文元素名归一化为 element_code 列表。"""
    canonical: list[str] = []
    for element_code in involved_codes:
        append_unique(canonical, element_code)
    if resolver is None:
        return canonical
    for raw_element in involved_elements:
        normalized = _normalized_text(raw_element)
        if not normalized or normalized in canonical:
            continue
        matched = resolver.resolve(normalized)
        if matched is None:
            continue
        element_code = matched[0]
        if element_code not in canonical:
            canonical.append(element_code)
    return canonical
