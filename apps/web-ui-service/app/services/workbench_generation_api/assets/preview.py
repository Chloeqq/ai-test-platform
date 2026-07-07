"""预览数据加载 — 从前端预览快照恢复已解析的需求与候选测试点摘要。"""

from __future__ import annotations

from typing import Any

from shared_backend.type_utils import dict_value as _dict_value
from shared_backend.type_utils import str_value as _normalized_text

from .. import constants as _c
from .. import preview_store


def preview_requirement(preview_id: str) -> tuple[str, dict[str, Any]]:
    """从前端预览快照中恢复已解析的需求文本与需求规格。

    返回: (effective_requirement 文本, requirement_spec 字典)
    """
    normalized_preview_id = _normalized_text(preview_id)
    if not normalized_preview_id:
        return "", {}
    snapshot = preview_store.load_preview_snapshot(normalized_preview_id)
    preview_payload = _dict_value(snapshot.get("preview_payload"))
    item = _dict_value(preview_payload.get("item"))
    requirement_spec = _dict_value(item.get("requirement_spec"))
    requirement = (
        _normalized_text(requirement_spec.get("normalized_requirement"))
        or _normalized_text(requirement_spec.get("raw_requirement"))
        or _normalized_text(item.get("normalized_requirement"))
        or _normalized_text(item.get("raw_requirement"))
        or _normalized_text(snapshot.get("effective_requirement"))
    )
    return requirement, requirement_spec


def candidate_snapshot(candidate: dict[str, Any]) -> dict[str, Any]:
    """从 AI 生成的候选测试点中提取关键字段作为轻量快照。"""
    snapshot: dict[str, Any] = {}
    for key in _c.CANDIDATE_SNAPSHOT_KEYS:
        value = candidate.get(key)
        if isinstance(value, dict):
            if value:
                snapshot[key] = value
            continue
        if isinstance(value, list):
            rows = _list_text(value)
            if rows:
                snapshot[key] = rows
            continue
        text = _normalized_text(value)
        if text:
            snapshot[key] = text
    return snapshot


def _list_text(value: Any) -> list[str]:
    """将输入值规范化为去重的非空字符串列表。"""
    if not isinstance(value, list):
        return []
    items: list[str] = []
    for raw in value:
        text = _normalized_text(raw)
        if text and text not in items:
            items.append(text)
    return items
