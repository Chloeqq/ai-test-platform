"""requirement.source_asset_id 兜底回填的特征测试。

部分 AI 候选把 source_asset_id 只写进 preconditions[].source_asset_id（如历史用例
0021），导致 requirement.source_asset_id 缺失、被 Runner 身份门禁跳过。生成器现在
在组装 requirement 时从 preconditions 兜底回填，保证 V1.1 身份铁律始终满足。
"""
from __future__ import annotations

# 先经规范入口初始化包，规避 runtime 子模块的循环导入。
import app.services.workbench_generation_compiler.runtime.generate_pipeline  # noqa: F401
from app.services.workbench_generation_compiler.runtime.generate_pipeline_orchestrate import (
    _source_asset_id_from_preconditions,
)


def test_picks_source_asset_id_from_preconditions() -> None:
    case_yaml = {
        "preconditions": [
            {"type": "account_state", "state": "disabled", "source_asset_id": "asset-99"},
        ]
    }
    assert _source_asset_id_from_preconditions(case_yaml) == "asset-99"


def test_returns_empty_when_no_source_asset_id_in_preconditions() -> None:
    case_yaml = {"preconditions": [{"type": "account_state", "state": "locked"}]}
    assert _source_asset_id_from_preconditions(case_yaml) == ""


def test_returns_empty_when_no_preconditions() -> None:
    assert _source_asset_id_from_preconditions({}) == ""
    assert _source_asset_id_from_preconditions({"preconditions": "nope"}) == ""


def test_returns_first_available_source_asset_id() -> None:
    case_yaml = {
        "preconditions": [
            {"type": "sql"},
            {"type": "account_state", "source_asset_id": "asset-A"},
            {"type": "account_state", "source_asset_id": "asset-B"},
        ]
    }
    assert _source_asset_id_from_preconditions(case_yaml) == "asset-A"
