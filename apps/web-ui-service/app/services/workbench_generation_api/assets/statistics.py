"""统计与查询工具 — intent_type 分布、资产标题等。"""

from __future__ import annotations

from typing import Any

from shared_backend.type_utils import str_value as _normalized_text

from .. import constants as _c


def intent_type_distribution(candidates: list[dict[str, Any]]) -> dict[str, int]:
    """统计候选测试点的 intent_type 分布。"""
    distribution: dict[str, int] = {}
    for candidate in candidates:
        intent_type = _normalized_text(candidate.get("intent_type")) or _c.DEFAULT_POINT_TYPE
        distribution[intent_type] = int(distribution.get(intent_type, 0) or 0) + 1
    return dict(sorted(distribution.items()))


def first_candidate_title(candidates: list[dict[str, Any]], *, page: str) -> str:
    """从候选测试点列表中选择第一个非空 title 作为资产标题。"""
    for candidate in candidates:
        title = _normalized_text(candidate.get("title")) or _normalized_text(
            candidate.get("summary")
        )
        if title:
            return title
    return _c.asset_title_for_page(page)
