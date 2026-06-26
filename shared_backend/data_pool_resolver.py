"""统一的数据池引用解析 — 生成侧与运行时侧共用的唯一事实源。

背景：历史上存在两套 `{source_type: pool, pool_name, key}` 解析逻辑：
- 生成侧（web-ui `_resolve_pool_data`）曾用 `json.loads(item_value)` + 按字段名取值，
  假定 item_value 是合并字典 `{"username":..., "password":...}`；
- 运行时侧（Runner `data_expander._resolve_pool_value`）做精确 key 匹配，返回整条值。

二者在「单字段标量」标准（state 编码进 key，如 username_locked → "locked_user"）下
语义不一致，且生成侧对标量值会 `json.loads` 崩溃。本模块把「按 (pool_name, key)
精确解析为标量值」的契约收敛到一处，两侧共同导入。

注意：本模块**不做**标签过滤。按标签挑选账号是另一种查找模式（见
`test_data_pool_service.resolve_pool_value` / 仓储 `list_items_by_pool_and_tags`），
返回的是整条账号记录，用途不同，保持独立。
"""
from __future__ import annotations

from typing import Any, Mapping

# 池快照形状：{pool_name: {item_key: value}} —— 与
# test_data_pool_service.build_runner_data_pool_snapshot 及运行时
# DSL_DATA_POOL_JSON 完全一致。
PoolSnapshot = Mapping[str, Mapping[str, Any]]


class PoolResolutionError(ValueError):
    """当 {pool_name, key} 引用无法在快照中解析时抛出。"""


def resolve_pool_reference(
    *,
    field: str,
    pool_name: str,
    item_key: str,
    pool_snapshot: PoolSnapshot,
) -> Any:
    """把单条 {pool_name, key} 引用解析为其存储的标量值。

    精确 key 契约（项目标准）：state 编码进 key，存储值为标量。
    不做标签过滤、不做 JSON 解码、不做合并字典字段抽取。

    :param field: 发起解析的数据字段名（如 "username"），仅用于错误信息定位。
    :param pool_name: 池名。
    :param item_key: 池内条目 key。
    :param pool_snapshot: {pool_name: {item_key: value}} 快照。
    :return: 该条目存储的值（通常为标量字符串）。
    :raises PoolResolutionError: pool_name/key 为空、池不存在或 key 不存在。
    """
    pool_name = (pool_name or "").strip()
    item_key = (item_key or "").strip()
    if not pool_name or not item_key:
        raise PoolResolutionError(
            f"pool source requires pool_name and key for `{field}`"
        )
    pool = pool_snapshot.get(pool_name)
    if not isinstance(pool, Mapping):
        raise PoolResolutionError(
            f"pool `{pool_name}` is not available for `{field}`"
        )
    if item_key not in pool:
        raise PoolResolutionError(
            f"key `{item_key}` not found in pool `{pool_name}` for `{field}`"
        )
    return pool[item_key]
