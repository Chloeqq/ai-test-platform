"""测试 Phase 5.2.1: Quality Dashboard Service。"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from app.services.quality_dashboard_service import (
    build_summary,
    build_ranking,
    build_issue_distribution,
    build_timeline,
    _read_latest_snapshot,
    _read_all_latest_snapshots,
    _load_quality_with_fallback,
)


@pytest.fixture
def tmp_state(monkeypatch):
    """创建临时 state 目录，mock WEB_UI_STATE_ROOT + asset dir。"""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        from app.services import quality_dashboard_service as svc
        monkeypatch.setattr(svc.state_store, "WEB_UI_STATE_ROOT", root)
        # create asset dir
        (root / "test-points" / "mall").mkdir(parents=True)
        yield root


def _write_snapshot(state_root: Path, project: str, asset_id: str, lines: list[dict]) -> Path:
    snap_dir = state_root / "quality-snapshots" / project
    snap_dir.mkdir(parents=True, exist_ok=True)
    path = snap_dir / f"{asset_id}.jsonl"
    with open(path, "w", encoding="utf-8") as f:
        for line in lines:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")
    return path


def _write_asset(state_root: Path, project: str, asset_id: str, **overrides) -> Path:
    asset_dir = state_root / "test-points" / project
    asset_dir.mkdir(parents=True, exist_ok=True)
    asset = {
        "asset_id": asset_id,
        "version": 1,
        "updated_at": "2026-07-07T12:00:00Z",
        "source_type": "selection_save",
        "plan": {
            "points": [
                {"intent_id": "i1", "point_type": "functional",
                 "steps": [{"action": "input"}, {"action": "assert_visible"}], "warnings": []},
            ],
        },
        "warnings": [],
        **overrides,
    }
    path = asset_dir / f"{asset_id}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(asset, f, ensure_ascii=False)
    return path


def _make_snap(**overrides) -> dict:
    return {
        "project": "mall",
        "asset_id": "test-001",
        "version": 1,
        "at": "2026-07-07T12:00:00Z",
        "score": 90,
        "decision": "PASS",
        "point_count": 1,
        "zero_assertion_count": 0,
        "candidate_step_count": 0,
        "unprocessed_count": 0,
        "quality_warning_count": 0,
        "data_warning_count": 0,
        "source_type": "selection_save",
        "trigger": "upsert",
        **overrides,
    }


# ── Test 1: summary 多 asset 聚合 ──

def test_summary_aggregates_multiple_assets(tmp_state):
    _write_snapshot(tmp_state, "mall", "a1", [_make_snap(asset_id="a1", score=90, decision="PASS")])
    _write_snapshot(tmp_state, "mall", "a2", [_make_snap(asset_id="a2", score=60, decision="REJECT")])
    _write_asset(tmp_state, "mall", "a1")
    _write_asset(tmp_state, "mall", "a2")

    s = build_summary("mall")
    assert s["asset_count"] == 2
    assert s["avg_score"] == 75.0
    assert s["decision_summary"]["PASS"] == 1
    assert s["decision_summary"]["REJECT"] == 1


# ── Test 2: snapshot + realtime fallback ──

def test_summary_fallback_for_missing_snapshot(tmp_state):
    _write_snapshot(tmp_state, "mall", "a1", [_make_snap(asset_id="a1", score=80)])
    _write_asset(tmp_state, "mall", "a1")
    _write_asset(tmp_state, "mall", "a2")  # no snapshot → fallback

    s = build_summary("mall")
    assert s["asset_count"] == 2
    assert s["fallback_count"] >= 1


# ── Test 3: ranking score 排序 ──

def test_ranking_sorted_by_score_asc(tmp_state):
    _write_snapshot(tmp_state, "mall", "best", [_make_snap(asset_id="best", score=95)])
    _write_snapshot(tmp_state, "mall", "worst", [_make_snap(asset_id="worst", score=40)])
    _write_asset(tmp_state, "mall", "best")
    _write_asset(tmp_state, "mall", "worst")

    ranking = build_ranking("mall", limit=10)
    assert len(ranking) == 2
    assert ranking[0]["score"] <= ranking[1]["score"]
    assert ranking[0]["asset_id"] == "worst"


# ── Test 4: issue distribution 字段聚合 ──

def test_issue_distribution_aggregates_fields(tmp_state):
    _write_snapshot(tmp_state, "mall", "a1", [_make_snap(asset_id="a1", zero_assertion_count=2, quality_warning_count=3)])
    _write_snapshot(tmp_state, "mall", "a2", [_make_snap(asset_id="a2", zero_assertion_count=1, unprocessed_count=1)])
    _write_asset(tmp_state, "mall", "a1")
    _write_asset(tmp_state, "mall", "a2")

    d = build_issue_distribution("mall")
    assert d["issue_summary"]["zero_assertion_count"] == 3
    assert d["issue_summary"]["quality_warning_count"] == 3
    assert d["issue_summary"]["unprocessed_count"] == 1


# ── Test 5: timeline delta_score ──

def test_timeline_delta_score(tmp_state):
    _write_snapshot(tmp_state, "mall", "t1", [
        _make_snap(asset_id="t1", version=1, score=60),
        _make_snap(asset_id="t1", version=2, score=75),
        _make_snap(asset_id="t1", version=3, score=90),
    ])
    timeline = build_timeline("mall", "t1")
    assert len(timeline) == 3
    assert timeline[0]["delta_score"] == 0   # v1: no previous
    assert timeline[1]["delta_score"] == 15  # v2: 75-60
    assert timeline[2]["delta_score"] == 15  # v3: 90-75


# ── Test 6: v0 filtered ──

def test_v0_snapshot_filtered(tmp_state):
    _write_snapshot(tmp_state, "mall", "old", [
        {"version": 0, "score": 50, "decision": "PASS", "at": "old"},
        _make_snap(asset_id="old", version=1, score=80),
    ])
    _write_asset(tmp_state, "mall", "old")

    snap = _read_latest_snapshot("mall", "old")
    assert snap["version"] == 1
    assert snap["score"] == 80


# ── Test 7: orphan snapshot ignored ──

def test_orphan_snapshot_not_counted(tmp_state):
    # snapshot exists but no asset file
    _write_snapshot(tmp_state, "mall", "orphan", [_make_snap(asset_id="orphan", score=50)])
    # only a1 has an asset file
    _write_snapshot(tmp_state, "mall", "a1", [_make_snap(asset_id="a1", score=90)])
    _write_asset(tmp_state, "mall", "a1")

    s = build_summary("mall")
    assert s["asset_count"] == 1  # only a1, orphan excluded


# ── Test 8: latest version selected ──

def test_latest_version_selected(tmp_state):
    _write_snapshot(tmp_state, "mall", "multi", [
        _make_snap(asset_id="multi", version=1, score=60),
        _make_snap(asset_id="multi", version=2, score=90),
        _make_snap(asset_id="multi", version=3, score=70),
    ])
    _write_asset(tmp_state, "mall", "multi")

    snap = _read_latest_snapshot("mall", "multi")
    assert snap["version"] == 3
    assert snap["score"] == 70  # latest wins
