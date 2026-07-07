"""测试 Phase 5.1: append_quality_snapshot。"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest

from app.services.workbench_asset_views import append_quality_snapshot


@pytest.fixture
def tmp_state_root(monkeypatch):
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        from app.services import workbench_asset_views
        monkeypatch.setattr(
            workbench_asset_views.state_store,
            "WEB_UI_STATE_ROOT",
            root,
        )
        def _fake_now_iso():
            return "2026-07-07T12:00:00Z"
        monkeypatch.setattr(
            workbench_asset_views.state_store,
            "now_iso",
            _fake_now_iso,
        )
        yield root


def _make_asset(**overrides):
    return {
        "asset_id": "test-asset-001",
        "project": "mall",
        "version": 3,
        "updated_at": "2026-07-07T12:00:00Z",
        "source_type": "selection_save",
        "plan": {
            "points": [
                {
                    "intent_id": "intent-01",
                    "point_type": "functional",
                    "steps": [{"action": "input"}, {"action": "assert_visible"}],
                    "warnings": [],
                },
            ],
        },
        "warnings": [],
        **overrides,
    }


def test_first_snapshot_creates_file(tmp_state_root):
    """首次保存 → 生成 snapshot 文件，包含 1 行 JSON。"""
    asset = _make_asset()
    append_quality_snapshot(asset, trigger="upsert")

    snap_path = tmp_state_root / "quality-snapshots" / "mall" / "test-asset-001.jsonl"
    assert snap_path.exists()
    lines = snap_path.read_text().strip().split("\n")
    assert len(lines) == 1
    snap = json.loads(lines[0])
    assert snap["asset_id"] == "test-asset-001"
    assert snap["version"] == 3
    assert snap["score"] == 90
    assert snap["decision"] == "PASS"
    assert snap["point_count"] == 1
    assert snap["trigger"] == "upsert"


def test_multiple_saves_append_lines(tmp_state_root):
    """多次保存 → 追加行，版本递增。"""
    asset_v1 = _make_asset(version=1)
    asset_v2 = _make_asset(version=2)

    append_quality_snapshot(asset_v1, trigger="upsert")
    append_quality_snapshot(asset_v2, trigger="upsert")

    snap_path = tmp_state_root / "quality-snapshots" / "mall" / "test-asset-001.jsonl"
    lines = snap_path.read_text().strip().split("\n")
    assert len(lines) == 2
    v1 = json.loads(lines[0])
    v2 = json.loads(lines[1])
    assert v1["version"] == 1
    assert v2["version"] == 2


def test_zero_assertion_snapshot(tmp_state_root):
    """零断言 asset → snapshot 记录正确指标。"""
    asset = _make_asset(plan={
        "points": [
            {
                "intent_id": "intent-01",
                "point_type": "functional",
                "steps": [{"action": "input"}, {"action": "click"}],
                "warnings": ["assertion_missing: 无可执行断言"],
            },
        ],
    })
    append_quality_snapshot(asset, trigger="ai_save")

    snap_path = tmp_state_root / "quality-snapshots" / "mall" / "test-asset-001.jsonl"
    snap = json.loads(snap_path.read_text().strip())
    assert snap["zero_assertion_count"] == 1
    assert snap["decision"] == "REJECT"
    assert snap["trigger"] == "ai_save"


def test_save_failure_no_snapshot(tmp_state_root):
    """append_quality_snapshot 内部异常不抛到调用方（降级记录日志）。"""
    # 传入空 asset — 不应崩溃
    append_quality_snapshot({}, trigger="upsert")
    # 如果没崩溃，测试通过
    snap_dir = tmp_state_root / "quality-snapshots"
    assert not snap_dir.exists() or list(snap_dir.rglob("*.jsonl")) == []


def test_ai_save_version_from_asset(tmp_state_root):
    """P0: ai_save 路径 version 应来自 asset，不是固定 1。"""
    asset = _make_asset(version=8, source_type="selection_save")
    append_quality_snapshot(asset, trigger="ai_save")

    snap_path = tmp_state_root / "quality-snapshots" / "mall" / "test-asset-001.jsonl"
    snap = json.loads(snap_path.read_text().strip())
    assert snap["version"] == 8, f"expected version=8, got {snap['version']}"
    assert snap["trigger"] == "ai_save"


def test_snapshot_contains_project(tmp_state_root):
    """P1: snapshot JSON 行内应包含 project 字段。"""
    asset = _make_asset(project="atp")
    append_quality_snapshot(asset, trigger="upsert")

    snap_path = tmp_state_root / "quality-snapshots" / "atp" / "test-asset-001.jsonl"
    snap = json.loads(snap_path.read_text().strip())
    assert snap["project"] == "atp", f"expected project=atp, got {snap.get('project', 'MISSING')}"


def test_multi_version_sequential(tmp_state_root):
    """多次保存 → version 严格递增: 1, 2, 3。"""
    for v in (1, 2, 3):
        asset = _make_asset(version=v)
        append_quality_snapshot(asset, trigger="upsert")

    snap_path = tmp_state_root / "quality-snapshots" / "mall" / "test-asset-001.jsonl"
    lines = snap_path.read_text().strip().split("\n")
    assert len(lines) == 3
    versions = [json.loads(line)["version"] for line in lines]
    assert versions == [1, 2, 3], f"expected [1,2,3], got {versions}"
