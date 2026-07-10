"""覆盖率矩阵 — 从需求规格提取或从 points 自动派生。"""

from __future__ import annotations

from typing import Any

from shared_backend.type_utils import as_text_list
from shared_backend.type_utils import str_value as _normalized_text


def coverage_matrix_from_requirement_spec(
    requirement_spec: dict[str, Any],
    *,
    points: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """从需求规格中提取覆盖率矩阵，若需求未提供则从 points 自动派生。"""
    point_by_intent = {
        _normalized_text(point.get("intent_id")): _normalized_text(point.get("key"))
        for point in points
        if isinstance(point, dict)
        and _normalized_text(point.get("intent_id"))
        and _normalized_text(point.get("key"))
    }
    raw_rows = requirement_spec.get("coverage_matrix")
    rows: list[dict[str, Any]] = []
    if isinstance(raw_rows, list):
        for index, raw_row in enumerate(raw_rows, start=1):
            if not isinstance(raw_row, dict):
                continue
            intent_ids = as_text_list(raw_row.get("intent_ids"))
            point_keys = [
                point_by_intent[intent_id]
                for intent_id in intent_ids
                if point_by_intent.get(intent_id)
            ]
            rows.append(
                {
                    "row_id": _normalized_text(raw_row.get("row_id"))
                    or f"coverage-row-{index:02d}",
                    "traceability_status": _normalized_text(
                        raw_row.get("traceability_status")
                    )
                    or "covered",
                    "source_ids": as_text_list(raw_row.get("source_ids")),
                    "intent_ids": intent_ids,
                    "point_keys": point_keys,
                    "changed_areas": as_text_list(raw_row.get("changed_areas")),
                    "explanation": _normalized_text(raw_row.get("explanation")),
                }
            )
    if rows:
        return rows
    intent_ids = as_text_list(
        [
            str(point.get("intent_id", "")).strip()
            for point in points
            if isinstance(point, dict) and str(point.get("intent_id", "")).strip()
        ]
    )
    point_keys = as_text_list(
        [
            str(point.get("key", "")).strip()
            for point in points
            if isinstance(point, dict) and str(point.get("key", "")).strip()
        ]
    )
    if not intent_ids and not point_keys:
        return []
    return [
        {
            "row_id": "selected-intents",
            "traceability_status": "covered",
            "source_ids": ["source-01"],
            "intent_ids": intent_ids,
            "point_keys": point_keys,
            "changed_areas": [],
            "explanation": "derived from selected test intents",
        }
    ]
# as_text_list 已迁移至 shared_backend.type_utils
