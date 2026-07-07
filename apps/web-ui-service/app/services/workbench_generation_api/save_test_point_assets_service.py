"""保存测试点资产 — 向后兼容 re-export 模块。

Phase 2 重构后，所有实现已迁移到独立子模块：
  elements/   — 元素解析与 DB 加载
  steps/      — 步骤结构化
  hooks/      — 页面级 Hook（如密码可见性）
  compilation/ — 测试点编译
  assets/     — 资产查询与统计

新代码请直接从子模块或 save_service 导入。
"""

from __future__ import annotations

# ── Service 入口 ──
from .save_service import SaveTestPointAssetsService

# ── 元素解析 ──
from .elements import load_alias_map, ElementResolver
from .elements.resolver import _data_ref_for_element

# ── 步骤结构化 ──
from .steps.structurer import structured_steps_from_candidate as _structured_steps_from_candidate

# ── 页面 Hook ──
from .hooks.base import PageHook
from .hooks.login_password_visibility import LoginPasswordVisibilityHook

# ── 测试点编译 ──
from .compilation.point_builder import build_point as _build_point
from .compilation.precondition import fallback_precondition as _fallback_precondition

# ── 资产查询 ──
from .assets.preview import preview_requirement as _preview_requirement, candidate_snapshot as _candidate_snapshot
from .assets.queries import existing_test_point_asset_ids as _existing_test_point_asset_ids
from .assets.queries import find_existing_page_asset_for_upsert as _find_existing_page_asset_for_upsert
from .assets.coverage import coverage_matrix_from_requirement_spec as _coverage_matrix_from_requirement_spec
from .assets.statistics import intent_type_distribution as _intent_type_distribution, first_candidate_title as _first_candidate_title

# ── 工具函数（已迁移至 shared_backend） ──
from shared_backend.type_utils import as_text_list as _list_text, append_unique as _append_unique
from shared_backend.text_utils import extract_input_value as _input_value_from_text

# ── 后向兼容（旧代码引用这些函数名） ──
from .compilation.point_builder import _resolve_involved_element_codes
from .hooks.login_password_visibility import _assertion_step as _password_visibility_assertion_step
from .hooks.login_password_visibility import _precondition_setup as _password_visibility_precondition_setup
from .elements.resolver import _data_ref_for_element

__all__ = [
    "SaveTestPointAssetsService",
    "_structured_steps_from_candidate",
    "_build_point",
    "_fallback_precondition",
    "_login_element_from_text",
    "_input_value_from_text",
    "_data_ref_for_element",
    "_password_visibility_assertion_step",
    "_password_visibility_precondition_setup",
    "_resolve_involved_element_codes",
    "_list_text",
    "_append_unique",
    "_preview_requirement",
    "_candidate_snapshot",
    "_existing_test_point_asset_ids",
    "_find_existing_page_asset_for_upsert",
    "_coverage_matrix_from_requirement_spec",
    "_intent_type_distribution",
    "_first_candidate_title",
]
