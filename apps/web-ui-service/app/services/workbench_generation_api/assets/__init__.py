"""资产查询与统计子模块。

提供存量资产查询、覆盖率矩阵、统计工具和预览数据加载。
"""

from .coverage import coverage_matrix_from_requirement_spec
from .preview import candidate_snapshot, preview_requirement
from .queries import existing_test_point_asset_ids, find_existing_page_asset_for_upsert
from .statistics import first_candidate_title, intent_type_distribution

__all__ = [
    "preview_requirement",
    "candidate_snapshot",
    "existing_test_point_asset_ids",
    "find_existing_page_asset_for_upsert",
    "coverage_matrix_from_requirement_spec",
    "intent_type_distribution",
    "first_candidate_title",
]
