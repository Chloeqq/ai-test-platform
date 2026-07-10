"""SeedDataProvider 最小实现。

从内存中的种子数据快照提供惰性查询。
未来可替换为 DB 查询或 API 调用。
"""

from __future__ import annotations

import json
from typing import Any


class SimpleSeedDataProvider:
    """基于内存快照的 SeedDataProvider 实现。

    pool_snapshot: {"pool_name": {"item_key": "item_value"}, ...}
    """

    def __init__(self, pool_snapshot: dict[str, dict[str, Any]] | None = None) -> None:
        self._pools: dict[str, dict[str, Any]] = dict(pool_snapshot) if pool_snapshot else {}

    def get_pool(self, pool_name: str) -> dict[str, Any]:
        return self._pools.get(pool_name, {})

    def get_item(self, pool_name: str, item_key: str) -> Any:
        pool = self._pools.get(pool_name, {})
        return pool.get(item_key)

    def has_item(self, pool_name: str, item_key: str) -> bool:
        return item_key in self._pools.get(pool_name, {})

    def resolve_value(self, item_key: str, *, field: str = "") -> str | None:
        """根据 pool item_key 解析实际数据值。

        遍历所有池查找 item_key，从条目值中提取 field 对应字段。
        支持 dict、JSON string、扁平 string 三种条目值格式。

        返回 None 表示未找到。
        """
        if not item_key or not item_key.strip():
            return None

        for _pool_name, items in self._pools.items():
            if item_key not in items:
                continue
            item_value = items[item_key]

            # dict 格式：{"username": "admin", "password": "xxx"}
            if isinstance(item_value, dict):
                if field:
                    extracted = item_value.get(field)
                    if extracted is not None:
                        return str(extracted)
                # 无 field 提示时返回第一个字符串值
                for v in item_value.values():
                    if isinstance(v, str):
                        return v
                return None

            # JSON string 格式
            if isinstance(item_value, str):
                try:
                    obj = json.loads(item_value)
                    if isinstance(obj, dict) and field:
                        extracted = obj.get(field)
                        if extracted is not None:
                            return str(extracted)
                    if isinstance(obj, str):
                        return obj
                except (json.JSONDecodeError, ValueError):
                    pass
                return item_value

            # 其他类型 → 字符串化
            return str(item_value)

        return None

    def has_value_in_any_pool(self, value: str, *, field: str = "username") -> bool:
        """检查指定值是否在任意池中存在（按字段匹配）。

        支持 JSON 对象值（如 {"username": "admin"}）和扁平字符串值。
        """
        if not value or not value.strip():
            return True  # 空值不视为外部依赖

        for _pool_name, items in self._pools.items():
            for item_key, item_value in items.items():
                # 检查 item_key 是否匹配（如 username_admin → admin）
                if self._item_key_matches(item_key, value, field=field):
                    return True

                # 检查 JSON 对象值中的字段
                extracted = self._extract_field(item_value, field)
                if extracted and str(extracted).strip() == value.strip():
                    return True

                # 检查扁平字符串值
                if isinstance(item_value, str) and item_value.strip() == value.strip():
                    return True

        return False

    @staticmethod
    def _extract_field(item_value: Any, field: str) -> Any:
        """从 JSON 字符串中提取字段值。"""
        if isinstance(item_value, dict):
            return item_value.get(field)
        if isinstance(item_value, str):
            try:
                obj = json.loads(item_value)
                if isinstance(obj, dict):
                    return obj.get(field)
            except (json.JSONDecodeError, ValueError):
                pass
        return None

    @staticmethod
    def _item_key_matches(item_key: str, value: str, *, field: str = "username") -> bool:
        """检查 item_key 是否语义上匹配目标值。

        例如 item_key="username_admin" 匹配 value="admin"。
        """
        prefix = f"{field}_"
        if item_key.startswith(prefix):
            suffix = item_key[len(prefix):]
            return suffix == value
        return False
