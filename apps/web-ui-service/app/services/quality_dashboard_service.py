"""Quality Dashboard Service — 只读质量数据聚合。

职责: snapshot 读取 / 聚合 / 排序 / 趋势 / fallback。
禁止: 修改 asset / 生成 snapshot / 调用 Gate / 修改 review 状态。
"""
from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.services import workbench_state_store as state_store
from app.services.workbench_asset_views import _build_quality_report

LOGGER = logging.getLogger(__name__)

_SNAPSHOT_DIR_NAME = "quality-snapshots"

ISSUE_FIELDS: tuple[str, ...] = (
    "zero_assertion_count",
    "candidate_step_count",
    "unprocessed_count",
    "quality_warning_count",
    "data_warning_count",
)

_UTC = UTC


# ── Snapshot reader ──────────────────────────────────────────────────────


def _snapshot_dir(project: str) -> Path:
    return state_store.WEB_UI_STATE_ROOT / _SNAPSHOT_DIR_NAME / project


def _read_latest_snapshot(project: str, asset_id: str) -> dict[str, Any] | None:
    """读取单 asset 的最新 snapshot（JSONL 最后一行，filter v0）。"""
    path = _snapshot_dir(project) / f"{asset_id}.jsonl"
    if not path.exists():
        return None
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.readlines()
        # reversed: 从最后一行向前找第一条有效数据
        for line in reversed(lines):
            line = line.strip()
            if not line:
                continue
            snap = json.loads(line)
            if int(snap.get("version", 0) or 0) > 0:
                return snap
    except Exception:
        LOGGER.warning("failed to read snapshot %s/%s", project, asset_id, exc_info=True)
    return None


def _read_all_latest_snapshots(project: str) -> dict[str, dict[str, Any]]:
    """读取项目下全部 asset 的最新 snapshot → {asset_id: snap}。"""
    snap_dir = _snapshot_dir(project)
    if not snap_dir.exists():
        return {}
    result: dict[str, dict[str, Any]] = {}
    for path in snap_dir.glob("*.jsonl"):
        asset_id = path.stem
        snap = _read_latest_snapshot(project, asset_id)
        if snap:
            result[asset_id] = snap
    return result


# ── Asset fallback ───────────────────────────────────────────────────────


def _list_asset_ids(project: str) -> list[str]:
    """枚举项目中全部 asset ID。"""
    asset_dir = state_store.WEB_UI_STATE_ROOT / "test-points" / project
    if not asset_dir.exists():
        return []
    return sorted(p.stem for p in asset_dir.glob("*.json") if p.stem != "index")


def _load_quality_with_fallback(project: str, asset_id: str) -> dict[str, Any]:
    """snapshot 优先，不存在则实时计算 quality_report。"""
    snap = _read_latest_snapshot(project, asset_id)
    if snap:
        return {"source": "snapshot", **snap}

    # fallback: 实时计算
    asset_path = state_store.WEB_UI_STATE_ROOT / "test-points" / project / f"{asset_id}.json"
    try:
        asset = json.loads(asset_path.read_text(encoding="utf-8"))
        qr = _build_quality_report(asset)
        return {
            "source": "realtime",
            "project": project,
            "asset_id": asset_id,
            "version": asset.get("version", 0),
            "at": asset.get("updated_at", ""),
            "score": qr["score"],
            "decision": qr["decision"],
            "point_count": qr["total_points"],
            "zero_assertion_count": qr["zero_assertion_count"],
            "candidate_step_count": qr.get("candidate_step_count", 0),
            "unprocessed_count": qr.get("unprocessed_count", 0),
            "quality_warning_count": len(qr.get("quality_warnings", [])),
            "data_warning_count": len(qr.get("data_warnings", [])),
            "source_type": asset.get("source_type", ""),
            "trigger": "realtime",
        }
    except Exception:
        LOGGER.warning("quality fallback failed for %s/%s", project, asset_id, exc_info=True)
        return {
            "source": "error",
            "project": project,
            "asset_id": asset_id,
            "score": 0,
            "decision": "UNKNOWN",
        }


def _now_iso() -> str:
    return datetime.now(_UTC).isoformat()


# ── Aggregation ──────────────────────────────────────────────────────────


def build_summary(project: str, db: Any = None) -> dict[str, Any]:  # db unused, kept for future
    """项目质量概览。"""
    snaps = _read_all_latest_snapshots(project)
    asset_ids = _list_asset_ids(project)
    total = len(asset_ids)
    snapshot_count = len(snaps)
    fallback_count = 0

    # fallback for assets without snapshot
    for aid in asset_ids:
        if aid not in snaps:
            fb = _load_quality_with_fallback(project, aid)
            if fb.get("source") != "error":
                snaps[aid] = fb
                fallback_count += 1

    if not snaps:
        return {
            "project": project,
            "generated_at": _now_iso(),
            "asset_count": 0,
            "snapshot_coverage": 0,
            "fallback_count": 0,
            "avg_score": 0,
            "decision_summary": {"PASS": 0, "REVIEW": 0, "REJECT": 0},
            "issue_summary": {f: 0 for f in ISSUE_FIELDS},
        }

    scores = [s["score"] for s in snaps.values()]
    decisions: dict[str, int] = {"PASS": 0, "REVIEW": 0, "REJECT": 0}
    issues: dict[str, int] = {f: 0 for f in ISSUE_FIELDS}
    for s in snaps.values():
        d = s.get("decision", "UNKNOWN")
        if d in decisions:
            decisions[d] += 1
        for f in ISSUE_FIELDS:
            issues[f] += int(s.get(f, 0) or 0)

    return {
        "project": project,
        "generated_at": _now_iso(),
        "asset_count": total,
        "snapshot_coverage": snapshot_count,
        "fallback_count": fallback_count,
        "avg_score": round(sum(scores) / len(scores), 1) if scores else 0,
        "decision_summary": decisions,
        "issue_summary": issues,
    }


def build_ranking(project: str, limit: int = 10) -> list[dict[str, Any]]:
    """Asset 质量排名（score ASC，最低质量优先）。"""
    snaps = _read_all_latest_snapshots(project)
    asset_ids = _list_asset_ids(project)

    items: list[dict[str, Any]] = []
    for aid in asset_ids:
        s = snaps.get(aid)
        if s is None:
            s = _load_quality_with_fallback(project, aid)
        items.append({
            "asset_id": s.get("asset_id", aid),
            "score": s.get("score", 0),
            "decision": s.get("decision", "UNKNOWN"),
            "version": s.get("version", 0),
            "updated_at": s.get("at", ""),
            "source": s.get("source", "unknown"),
        })

    items.sort(key=lambda x: (x["score"], x["asset_id"]))
    return items[:limit]


def build_issue_distribution(project: str) -> dict[str, Any]:
    """问题分布（按 asset 聚合 5 个指标）。"""
    snaps = _read_all_latest_snapshots(project)
    asset_ids = _list_asset_ids(project)

    issues: dict[str, int] = {f: 0 for f in ISSUE_FIELDS}
    for aid in asset_ids:
        s = snaps.get(aid)
        if s is None:
            s = _load_quality_with_fallback(project, aid)
        if s.get("source") == "error":
            continue
        for f in ISSUE_FIELDS:
            issues[f] += int(s.get(f, 0) or 0)

    return {
        "project": project,
        "generated_at": _now_iso(),
        "asset_count": len(asset_ids),
        "issue_summary": issues,
    }


# ── Timeline ─────────────────────────────────────────────────────────────


def build_timeline(project: str, asset_id: str) -> list[dict[str, Any]]:
    """单 asset 质量趋势，逐行读取 snapshot JSONL 计算 delta_score。"""
    path = _snapshot_dir(project) / f"{asset_id}.jsonl"
    if not path.exists():
        return []

    rows: list[dict[str, Any]] = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                snap = json.loads(line)
                if int(snap.get("version", 0) or 0) <= 0:
                    continue
                rows.append(snap)
    except Exception:
        LOGGER.warning("timeline read failed for %s/%s", project, asset_id, exc_info=True)
        return []

    result: list[dict[str, Any]] = []
    prev_score: int | None = None
    for snap in rows:
        score = int(snap.get("score", 0) or 0)
        delta = score - prev_score if prev_score is not None else 0
        prev_score = score
        result.append({
            "version": snap.get("version"),
            "at": snap.get("at"),
            "score": score,
            "decision": snap.get("decision"),
            "zero_assertion_count": snap.get("zero_assertion_count", 0),
            "unprocessed_count": snap.get("unprocessed_count", 0),
            "delta_score": delta,
        })
    return result
