from __future__ import annotations

from copy import deepcopy
import json
import os
import sys
from pathlib import Path
from typing import Any

try:
    from shared_backend.data_pool_resolver import PoolResolutionError, resolve_pool_reference
except Exception:  # pragma: no cover - runner keeps fallback usability
    # Retry once by adding repo root to import path (mirror asset_toolkit).
    _repo_root = Path(__file__).resolve().parents[3]
    if str(_repo_root) not in sys.path:
        sys.path.insert(0, str(_repo_root))
    from shared_backend.data_pool_resolver import PoolResolutionError, resolve_pool_reference


def _text(value: Any) -> str:
    return str(value or "").strip()


def _load_pool_snapshot() -> dict[str, dict[str, Any]]:
    raw = os.getenv("DSL_DATA_POOL_JSON", "").strip()
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except Exception as exc:
        raise ValueError("runtime_data_source_resolve_failed: DSL_DATA_POOL_JSON is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("runtime_data_source_resolve_failed: DSL_DATA_POOL_JSON must be an object")
    normalized: dict[str, dict[str, Any]] = {}
    for pool_name, pool_items in payload.items():
        if not isinstance(pool_items, dict):
            continue
        normalized[_text(pool_name)] = dict(pool_items)
    return normalized


def _resolve_pool_value(*, key: str, source: dict[str, Any], pool_snapshot: dict[str, dict[str, Any]]) -> list[Any]:
    # 委托共享解析器（生成侧/运行时侧唯一事实源），保留 runtime_ 前缀的错误契约。
    try:
        value = resolve_pool_reference(
            field=key,
            pool_name=_text(source.get("pool_name")),
            item_key=_text(source.get("key")),
            pool_snapshot=pool_snapshot,
        )
    except PoolResolutionError as exc:
        raise ValueError(f"runtime_data_source_resolve_failed: {exc}") from exc
    return [value]


def _resolve_env_value(*, key: str, source: dict[str, Any]) -> list[Any]:
    env_key = _text(source.get("key"))
    if not env_key:
        raise ValueError(f"runtime_data_source_resolve_failed: env source requires key for `{key}`")
    env_value = os.getenv(env_key)
    if env_value is None:
        raise ValueError(
            f"runtime_data_source_resolve_failed: env var `{env_key}` is missing for `{key}`"
        )
    return [env_value]


def _resolve_inline_value(*, value: Any) -> list[Any]:
    if isinstance(value, list):
        if not value:
            raise ValueError("runtime_data_source_resolve_failed: inline list data must not be empty")
        return value
    return [value]


def _resolve_data_entry(*, key: str, value: Any, pool_snapshot: dict[str, dict[str, Any]]) -> list[Any]:
    if isinstance(value, dict):
        source_type = _text(value.get("source_type") or "inline").lower()
        if source_type == "inline":
            if "value" not in value:
                raise ValueError(
                    f"runtime_data_source_resolve_failed: inline source requires value for `{key}`"
                )
            return _resolve_inline_value(value=value.get("value"))
        if source_type == "pool":
            return _resolve_pool_value(key=key, source=value, pool_snapshot=pool_snapshot)
        if source_type == "env":
            return _resolve_env_value(key=key, source=value)
        raise ValueError(
            f"runtime_data_source_resolve_failed: unsupported source_type `{source_type}` for `{key}`"
        )

    # 兼容老格式：list/scalar 视作 inline。
    if isinstance(value, list):
        if not value:
            raise ValueError(f"runtime_data_source_resolve_failed: legacy list data for `{key}` must not be empty")
        return value
    return [value]


def _resolve_data_matrix(data: dict[str, Any]) -> dict[str, list[Any]]:
    pool_snapshot = _load_pool_snapshot()
    resolved: dict[str, list[Any]] = {}
    for raw_key, raw_value in data.items():
        key = _text(raw_key)
        if not key:
            continue
        resolved[key] = _resolve_data_entry(key=key, value=raw_value, pool_snapshot=pool_snapshot)
    return resolved


def _matrix_case_count(resolved: dict[str, list[Any]]) -> int:
    if not resolved:
        return 1
    lengths = [len(values) for values in resolved.values()]
    max_len = max(lengths)
    for key, values in resolved.items():
        if len(values) not in {1, max_len}:
            raise ValueError(
                "runtime_data_source_resolve_failed: data field lengths must be 1 or match max length, "
                f"got `{key}`={len(values)} while max={max_len}"
            )
    return max_len


def _matrix_value(values: list[Any], index: int) -> Any:
    if len(values) == 1:
        return values[0]
    return values[index]


def expand_test_case(test_case: dict) -> list[dict]:
    """
    根据 data 字段展开测试用例。
    支持 DSL V1.1 结构化来源：inline / pool / env，并兼容 legacy list/scalar。
    """
    data = test_case.get("data")
    if not data:
        return [test_case]
    if not isinstance(data, dict):
        raise ValueError("runtime_data_source_resolve_failed: data must be an object")

    resolved_data = _resolve_data_matrix(data)
    case_count = _matrix_case_count(resolved_data)
    cases: list[dict] = []

    for index in range(case_count):
        new_case = deepcopy(test_case)
        new_case["_data"] = {}
        for key, values in resolved_data.items():
            new_case["_data"][key] = _matrix_value(values, index)
        cases.append(new_case)

    return cases
