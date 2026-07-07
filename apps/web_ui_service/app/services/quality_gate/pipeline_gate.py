"""Pipeline 集成层 — 从管线数据构建 GateContext 并调用 CaseQualityGate。

本模块是 quality_gate 包与 generation pipeline 之间的适配层。
管线只调用 evaluate_case_quality()，不直接接触 GateContext、Repository 等细节。
"""

from __future__ import annotations

import json
import logging
from typing import Any

from shared_backend.db import get_db_session as SessionLocal
from shared_backend.quality_gate import GateContext, ValidationReport

from .gate import CaseQualityGate
from .seed_data_provider import SimpleSeedDataProvider

_LOGGER = logging.getLogger(__name__)


def evaluate_case_quality(
    *,
    case_yaml: dict[str, Any],
    page_object: dict[str, Any],
    requirement_spec: dict[str, Any] | None,
    test_points: list[dict[str, Any]],
    project: str,
) -> tuple[ValidationReport, bool]:
    """对生成的用例执行质量门禁评估。

    从 DB 加载种子数据构造 seed_data_provider，
    构建 GateContext，调用 CaseQualityGate.evaluate()。

    返回 (ValidationReport, seed_data_available)。
    seed_data_available=False 表示 DB 不可用，依赖 seed data 的规则已跳过。
    """
    # 1. 加载种子数据 → SimpleSeedDataProvider
    provider, seed_data_available = _build_seed_data_provider()

    # 2. 构造 GateContext
    intent: dict[str, Any] = {}
    if isinstance(test_points, list) and test_points:
        for pt in test_points:
            if isinstance(pt, dict) and pt.get("intent_id"):
                intent = pt
                break
    if not intent and isinstance(requirement_spec, dict):
        intents = requirement_spec.get("test_intents")
        if isinstance(intents, list) and intents:
            intent = intents[0] if isinstance(intents[0], dict) else {}

    context = GateContext(
        case_yaml=case_yaml,
        requirement=requirement_spec if isinstance(requirement_spec, dict) else {},
        intent=intent,
        page_object=page_object if isinstance(page_object, dict) else {},
        seed_data_provider=provider,
        project=project,
    )

    # 3. 执行质量门
    gate = CaseQualityGate()
    return gate.evaluate(context), seed_data_available


def _build_seed_data_provider() -> tuple[SimpleSeedDataProvider, bool]:
    """从 DB 加载所有活跃数据池条目，构造 SimpleSeedDataProvider。

    返回 (provider, db_available)。
    db_available=False 表示 DB 不可用，调用方应向用户传递此信号。

    数据格式转换：
    DB rows: [(pool_name, item_key, item_value), ...]
    → provider pools: {pool_name: {item_key: item_value, ...}, ...}

    item_value 在 DB 中是 JSON 字符串，尝试解析为 Python 对象，
    解析失败则保留原始字符串。
    """
    pools: dict[str, dict[str, Any]] = {}
    db_available = False
    try:
        with SessionLocal() as session:
            from app.repositories.test_data_pool_repository import TestDataPoolRepository

            repo = TestDataPoolRepository(session)
            rows = repo.list_active_items_with_pool_name()
            db_available = True  # DB 连接成功（即使结果为空）
            for pool_name, item_key, item_value in rows:
                pool = pools.setdefault(pool_name, {})
                parsed = _try_parse_json(item_value)
                pool[item_key] = parsed if parsed is not None else item_value
    except Exception as exc:
        _LOGGER.warning(
            "quality_gate.pipeline_gate: failed to load seed data from DB, "
            "quality gate will run without seed_data_provider. error=%s",
            exc,
        )

    return SimpleSeedDataProvider(pools), db_available


def _try_parse_json(value: Any) -> Any:
    """尝试将字符串解析为 JSON 对象，失败返回 None。"""
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    if not stripped:
        return None
    try:
        return json.loads(stripped)
    except (json.JSONDecodeError, ValueError):
        return None
