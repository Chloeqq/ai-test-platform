from __future__ import annotations

import json
from datetime_compat import UTC
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

DEFAULT_PENDING_RETENTION_DAYS = 7
DEFAULT_CLEANED_ARCHIVE_DAYS = 30


def load_registry_entries(registry_path: Path) -> list[dict[str, Any]]:
    if not registry_path.exists():
        return []
    try:
        payload = json.loads(registry_path.read_text(encoding="utf-8"))
    except Exception:
        return []
    return payload if isinstance(payload, list) else []


def save_registry_entries(registry_path: Path, items: list[dict[str, Any]]) -> None:
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(
        json.dumps(items[:1000], ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def append_registry_entry(registry_path: Path, entry: dict[str, Any]) -> dict[str, Any]:
    items = load_registry_entries(registry_path)
    request_id = str(entry.get("request_id", "")).strip()
    filtered = [item for item in items if str(item.get("request_id", "")).strip() != request_id]
    filtered.insert(0, dict(entry))
    save_registry_entries(registry_path, filtered)
    return dict(entry)


def mark_registry_entry_cleaned(registry_path: Path, *, request_id: str) -> dict[str, Any] | None:
    normalized_request_id = str(request_id or "").strip()
    if not normalized_request_id:
        return None
    items = load_registry_entries(registry_path)
    for item in items:
        if str(item.get("request_id", "")).strip() != normalized_request_id:
            continue
        item["cleanup_status"] = "cleaned"
        item["status"] = "cleaned"
        if not str(item.get("cleaned_at", "")).strip():
            item["cleaned_at"] = datetime.now(UTC).isoformat()
        save_registry_entries(registry_path, items)
        return dict(item)
    return None


def _parse_created_at(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except Exception:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _build_retention_item(
    item: dict[str, Any],
    *,
    effective_now: datetime,
    age_anchor: str,
    anchor_value: str,
    anchor_dt: datetime | None,
) -> dict[str, Any]:
    age_seconds = None
    age_days = None
    if anchor_dt is not None:
        age_seconds = max(0, int((effective_now - anchor_dt).total_seconds()))
        age_days = round(age_seconds / 86400, 3)
    return {
        "request_id": str(item.get("request_id", "")).strip(),
        "project": str(item.get("project", "default")).strip() or "default",
        "environment": str(item.get("environment", "test")).strip() or "test",
        "status": str(item.get("status", "unknown")).strip() or "unknown",
        "cleanup_status": str(item.get("cleanup_status", "unknown")).strip() or "unknown",
        "created_at": str(item.get("created_at", "")).strip(),
        "cleaned_at": str(item.get("cleaned_at", "")).strip(),
        "age_anchor": age_anchor,
        "age_anchor_value": anchor_value,
        "age_seconds": age_seconds,
        "age_days": age_days,
        "total_records": int(item.get("total_records", 0) or 0),
        "requirement_ids": list(item.get("requirement_ids", [])) if isinstance(item.get("requirement_ids"), list) else [],
    }


def summarize_registry_entries(registry_path: Path) -> dict[str, Any]:
    items = load_registry_entries(registry_path)
    project_counts: dict[str, int] = {}
    environment_counts: dict[str, int] = {}
    status_counts: dict[str, int] = {}
    cleanup_status_counts: dict[str, int] = {}
    oldest_pending_item: dict[str, Any] | None = None
    latest_created_at = ""

    for item in items:
        project = str(item.get("project", "default")).strip() or "default"
        environment = str(item.get("environment", "test")).strip() or "test"
        status = str(item.get("status", "unknown")).strip() or "unknown"
        cleanup_status = str(item.get("cleanup_status", "unknown")).strip() or "unknown"
        created_at = str(item.get("created_at", "")).strip()

        project_counts[project] = project_counts.get(project, 0) + 1
        environment_counts[environment] = environment_counts.get(environment, 0) + 1
        status_counts[status] = status_counts.get(status, 0) + 1
        cleanup_status_counts[cleanup_status] = cleanup_status_counts.get(cleanup_status, 0) + 1
        if created_at and created_at > latest_created_at:
            latest_created_at = created_at

        if cleanup_status != "pending":
            continue
        created_dt = _parse_created_at(created_at)
        if oldest_pending_item is None:
            oldest_pending_item = dict(item)
            oldest_pending_item["_created_dt"] = created_dt
            continue
        previous_dt = oldest_pending_item.get("_created_dt")
        if previous_dt is None and created_dt is not None:
            oldest_pending_item = dict(item)
            oldest_pending_item["_created_dt"] = created_dt
            continue
        if created_dt is not None and previous_dt is not None and created_dt < previous_dt:
            oldest_pending_item = dict(item)
            oldest_pending_item["_created_dt"] = created_dt

    oldest_pending_request_id = ""
    oldest_pending_created_at = ""
    if isinstance(oldest_pending_item, dict):
        oldest_pending_request_id = str(oldest_pending_item.get("request_id", "")).strip()
        oldest_pending_created_at = str(oldest_pending_item.get("created_at", "")).strip()

    return {
        "registry_path": str(registry_path),
        "total_entries": len(items),
        "pending_cleanup_count": int(cleanup_status_counts.get("pending", 0) or 0),
        "cleaned_count": int(cleanup_status_counts.get("cleaned", 0) or 0),
        "generated_with_errors_count": int(status_counts.get("generated_with_errors", 0) or 0),
        "project_counts": dict(sorted(project_counts.items())),
        "environment_counts": dict(sorted(environment_counts.items())),
        "status_counts": dict(sorted(status_counts.items())),
        "cleanup_status_counts": dict(sorted(cleanup_status_counts.items())),
        "latest_created_at": latest_created_at,
        "oldest_pending_request_id": oldest_pending_request_id,
        "oldest_pending_created_at": oldest_pending_created_at,
    }


def list_pending_cleanup_entries(registry_path: Path, *, limit: int = 20) -> dict[str, Any]:
    summary = summarize_registry_entries(registry_path)
    items = load_registry_entries(registry_path)
    pending_items = [
        dict(item)
        for item in items
        if str(item.get("cleanup_status", "pending")).strip().lower() == "pending"
    ]
    pending_items.sort(
        key=lambda item: (
            _parse_created_at(item.get("created_at")) or datetime.min.replace(tzinfo=UTC),
            str(item.get("request_id", "")),
        )
    )
    entries: list[dict[str, Any]] = []
    for item in pending_items[: max(1, min(limit, 100))]:
        created_at = str(item.get("created_at", "")).strip()
        created_dt = _parse_created_at(created_at)
        age_seconds = None
        if created_dt is not None:
            age_seconds = max(0, int((datetime.now(UTC) - created_dt).total_seconds()))
        entries.append(
            {
                "request_id": str(item.get("request_id", "")).strip(),
                "project": str(item.get("project", "default")).strip() or "default",
                "environment": str(item.get("environment", "test")).strip() or "test",
                "status": str(item.get("status", "unknown")).strip() or "unknown",
                "cleanup_status": str(item.get("cleanup_status", "pending")).strip() or "pending",
                "created_at": created_at,
                "age_seconds": age_seconds,
                "total_records": int(item.get("total_records", 0) or 0),
                "requirement_ids": list(item.get("requirement_ids", [])) if isinstance(item.get("requirement_ids"), list) else [],
            }
        )
    return {
        **summary,
        "pending_items": entries,
        "pending_items_count": len(entries),
        "pending_cleanup_ratio": round(len(entries) / max(1, int(summary.get("total_entries", 0) or 0)), 3),
        "oldest_pending_item": entries[0] if entries else {},
    }


def summarize_cleanup_retention(
    registry_path: Path,
    *,
    pending_retention_days: int = DEFAULT_PENDING_RETENTION_DAYS,
    cleaned_archive_days: int = DEFAULT_CLEANED_ARCHIVE_DAYS,
    limit: int = 20,
    now: datetime | None = None,
) -> dict[str, Any]:
    summary = summarize_registry_entries(registry_path)
    items = load_registry_entries(registry_path)
    effective_now = now.astimezone(UTC) if now is not None else datetime.now(UTC)
    normalized_pending_days = max(1, int(pending_retention_days))
    normalized_cleaned_days = max(1, int(cleaned_archive_days))
    pending_deadline = effective_now - timedelta(days=normalized_pending_days)
    cleaned_deadline = effective_now - timedelta(days=normalized_cleaned_days)

    overdue_pending_items: list[tuple[datetime, dict[str, Any]]] = []
    archive_candidate_items: list[tuple[datetime, dict[str, Any]]] = []

    for item in items:
        cleanup_status = str(item.get("cleanup_status", "unknown")).strip().lower() or "unknown"
        created_at = str(item.get("created_at", "")).strip()
        created_dt = _parse_created_at(created_at)
        cleaned_at = str(item.get("cleaned_at", "")).strip()
        cleaned_dt = _parse_created_at(cleaned_at)

        if cleanup_status == "pending" and created_dt is not None and created_dt <= pending_deadline:
            overdue_pending_items.append(
                (
                    created_dt,
                    _build_retention_item(
                        item,
                        effective_now=effective_now,
                        age_anchor="created_at",
                        anchor_value=created_at,
                        anchor_dt=created_dt,
                    ),
                )
            )
            continue

        if cleanup_status != "cleaned":
            continue
        archive_anchor = cleaned_dt or created_dt
        archive_anchor_name = "cleaned_at" if cleaned_dt is not None else "created_at"
        archive_anchor_value = cleaned_at if cleaned_dt is not None else created_at
        if archive_anchor is None or archive_anchor > cleaned_deadline:
            continue
        archive_candidate_items.append(
            (
                archive_anchor,
                _build_retention_item(
                    item,
                    effective_now=effective_now,
                    age_anchor=archive_anchor_name,
                    anchor_value=archive_anchor_value,
                    anchor_dt=archive_anchor,
                ),
            )
        )

    overdue_pending_items.sort(key=lambda item: (item[0], item[1]["request_id"]))
    archive_candidate_items.sort(key=lambda item: (item[0], item[1]["request_id"]))
    limited_overdue_items = [item for _, item in overdue_pending_items[: max(1, min(limit, 100))]]
    limited_archive_items = [item for _, item in archive_candidate_items[: max(1, min(limit, 100))]]
    pending_cleanup_count = int(summary.get("pending_cleanup_count", 0) or 0)
    cleaned_count = int(summary.get("cleaned_count", 0) or 0)

    return {
        **summary,
        "generated_at": effective_now.isoformat(),
        "retention_policy": {
            "pending_retention_days": normalized_pending_days,
            "cleaned_archive_days": normalized_cleaned_days,
            "pending_age_anchor": "created_at",
            "cleaned_age_anchor": "cleaned_at|created_at",
        },
        "overdue_pending_count": len(overdue_pending_items),
        "archive_candidate_count": len(archive_candidate_items),
        "overdue_pending_ratio": round(len(overdue_pending_items) / max(1, pending_cleanup_count), 3),
        "archive_candidate_ratio": round(len(archive_candidate_items) / max(1, cleaned_count), 3),
        "overdue_pending_items": limited_overdue_items,
        "archive_candidate_items": limited_archive_items,
        "oldest_overdue_pending_item": limited_overdue_items[0] if limited_overdue_items else {},
        "oldest_archive_candidate_item": limited_archive_items[0] if limited_archive_items else {},
    }
