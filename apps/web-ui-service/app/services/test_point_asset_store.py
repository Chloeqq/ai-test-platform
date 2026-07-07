"""测试点资产存储 —— DB 为事实源,web-ui/state 文件为可重建缓存。

bundle = 资产完整 JSON(asset_id 唯一)。DB 存全量 raw_payload + 可查询列;
读/列表/删除以 DB 为准,文件仅作缓存与回填来源。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.models.test_point_asset import TestPointAsset
from app.repositories.test_point_asset_repository import TestPointAssetRepository


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


_table_ensured: bool = False


def init_table(db: Session) -> None:
    """一次性幂等建表，启动/bootstrap 时调用。"""
    global _table_ensured
    if _table_ensured:
        return
    TestPointAsset.__table__.create(bind=db.get_bind(), checkfirst=True)
    _table_ensured = True


def _ensure_table(db: Session) -> None:
    if not _table_ensured:
        init_table(db)


def _columns_from_bundle(project: str, bundle: dict[str, Any]) -> dict[str, Any]:
    return {
        "project_code": _text(project).lower() or "mall",
        "asset_id": _text(bundle.get("asset_id")),
        "page_code": _text(bundle.get("page")) or "common",
        "title": _text(bundle.get("title")),
        "priority": _text(bundle.get("priority")) or "P1",
        "source_type": _text(bundle.get("source_type")),
        "status": _text(bundle.get("status")) or "active",
        "point_count": _int(bundle.get("point_count")),
        "intent_count": _int(bundle.get("intent_count")),
        "requires_review": bool(bundle.get("requires_review")),
        "version": _int(bundle.get("version")) or 1,
        "raw_payload": bundle,
    }


def save_asset(db: Session, *, project: str, bundle: dict[str, Any]) -> bool:
    """DB 权威写入(文件缓存由调用方既有逻辑写穿)。返回是否写入。"""
    _ensure_table(db)
    cols = _columns_from_bundle(project, bundle)
    if not cols["asset_id"]:
        return False
    TestPointAssetRepository(db).upsert(**cols)
    return True


def load_asset(db: Session, *, project: str, asset_id: str) -> dict[str, Any] | None:
    _ensure_table(db)
    row = TestPointAssetRepository(db).get(_text(project).lower() or "mall", _text(asset_id))
    if row is None:
        return None
    payload = row.raw_payload if isinstance(row.raw_payload, dict) else {}
    return payload or None


def list_assets(db: Session, *, project: str, page_code: str | None = None,
                 source_type: str | None = None, keyword: str | None = None,
                 offset: int = 0, limit: int = 500) -> tuple[list[dict[str, Any]], int]:
    _ensure_table(db)
    rows, total = TestPointAssetRepository(db).list_by_project(
        _text(project).lower() or "mall",
        page_code=page_code,
        source_type=source_type,
        keyword=keyword,
        offset=offset,
        limit=limit,
    )
    payloads = [row.raw_payload for row in rows if isinstance(row.raw_payload, dict) and row.raw_payload]
    return payloads, total


def list_asset_ids(db: Session, *, project: str) -> list[str]:
    _ensure_table(db)
    rows, _total = TestPointAssetRepository(db).list_by_project(_text(project).lower() or "mall", limit=10000)
    return [_text(row.asset_id) for row in rows if _text(row.asset_id)]


def delete_asset(db: Session, *, project: str, asset_id: str) -> bool:
    _ensure_table(db)
    ok = TestPointAssetRepository(db).delete(_text(project).lower() or "mall", _text(asset_id))
    db.flush()
    return ok


def sync_cache_from_db(db: Session, *, project: str, project_dir: Path) -> int:
    """把 DB 中存在但缓存文件缺失的资产回写为缓存文件，保证文件枚举与 DB 一致。

    幂等、轻量:只补写缺失的缓存文件(不覆盖已有),用于「缓存丢失后从 DB 重建」。
    返回补写的文件数。
    """
    _ensure_table(db)
    rows, _total = TestPointAssetRepository(db).list_by_project(_text(project).lower() or "mall")
    if not rows:
        return 0
    project_dir.mkdir(parents=True, exist_ok=True)
    written = 0
    for row in rows:
        asset_id = _text(row.asset_id)
        if not asset_id:
            continue
        path = project_dir / f"{asset_id}.json"
        if path.exists():
            continue
        payload = row.raw_payload if isinstance(row.raw_payload, dict) else {}
        if not payload:
            continue
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        written += 1
    return written


def backfill_from_dir(db: Session, *, project: str, project_dir: Path) -> int:
    """把现有 web-ui/state 资产 JSON 一次性导入 DB（幂等 upsert）。返回导入数。"""
    _ensure_table(db)
    if not project_dir.exists():
        return 0
    repo = TestPointAssetRepository(db)
    count = 0
    for path in sorted(project_dir.glob("*.json")):
        try:
            bundle = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, ValueError):
            continue
        if not isinstance(bundle, dict):
            continue
        cols = _columns_from_bundle(project, bundle)
        if not cols["asset_id"]:
            continue
        repo.upsert(**cols)
        count += 1
    return count
