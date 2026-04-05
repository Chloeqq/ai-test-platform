from __future__ import annotations

from typing import Any


def _normalize_text_list(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    items: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in items:
            items.append(text)
    return items


def build_management_items(
    left_items: list[dict[str, Any]],
    detail_panels: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    total = max(len(left_items), len(detail_panels))
    items: list[dict[str, Any]] = []
    for index in range(total):
        left = left_items[index] if index < len(left_items) else {}
        detail = detail_panels[index] if index < len(detail_panels) else {}
        title = str(left.get("title") or detail.get("title") or f"记录 {index + 1}").strip()
        meta = str(left.get("meta") or detail.get("meta") or "").strip()
        status = str(left.get("status") or detail.get("status") or left.get("badge") or "").strip()
        group = str(left.get("group") or detail.get("group") or "").strip()
        owner = str(left.get("owner") or detail.get("owner") or "").strip()
        updated_at = str(left.get("updated_at") or detail.get("updated_at") or "").strip()
        tags = _normalize_text_list(left.get("tags")) + [
            tag for tag in _normalize_text_list(detail.get("tags")) if tag not in _normalize_text_list(left.get("tags"))
        ]
        actions_raw = detail.get("actions")
        actions: list[Any] = actions_raw if isinstance(actions_raw, list) else []
        items.append(
            {
                "id": str(left.get("id") or detail.get("id") or f"panel-{index}").strip() or f"panel-{index}",
                "title": title,
                "meta": meta,
                "badge": str(left.get("badge") or detail.get("badge") or status or "").strip(),
                "status": status,
                "group": group,
                "owner": owner,
                "updated_at": updated_at,
                "tags": tags,
                "keywords": _normalize_text_list(left.get("keywords"))
                + [item for item in _normalize_text_list(detail.get("keywords")) if item not in _normalize_text_list(left.get("keywords"))]
                + [item for item in _normalize_text_list(detail.get("bullets")) if item not in _normalize_text_list(left.get("keywords"))],
                "detail_title": str(detail.get("title") or title).strip(),
                "detail_description": str(detail.get("description") or meta or "").strip(),
                "detail_bullets": _normalize_text_list(detail.get("bullets")),
                "detail_sections": detail.get("sections") if isinstance(detail.get("sections"), list) else [],
                "detail_actions": [
                    {
                        "label": str(action.get("label") or "").strip(),
                        "href": str(action.get("href") or "").strip(),
                    }
                    for action in actions
                    if isinstance(action, dict) and str(action.get("label") or "").strip()
                ],
            }
        )
    return items


def build_management_console_config(overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    config: dict[str, Any] = {
        "search_placeholder": "搜索标题 / 描述 / 标签",
        "advanced_placeholder": "补充关键词 / 责任人 / 分组",
        "status_label": "状态",
        "sort_options": [
            {"value": "default", "label": "默认排序"},
            {"value": "title_asc", "label": "标题 A-Z"},
            {"value": "status_asc", "label": "按状态"},
            {"value": "updated_desc", "label": "最近更新"},
        ],
        "empty_state": {
            "title": "当前筛选下暂无数据",
            "description": "可以重置筛选，或回到主流程继续生成、审核、执行与治理。",
        },
        "detail_empty_state": {
            "title": "请选择左侧记录",
            "description": "右侧会展示当前记录的职责说明、关键要点和下一步动作。",
        },
    }
    if isinstance(overrides, dict):
        for key, value in overrides.items():
            if key in {"empty_state", "detail_empty_state"} and isinstance(value, dict):
                config[key] = {**config[key], **value}
            else:
                config[key] = value
    return config
