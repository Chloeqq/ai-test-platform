from __future__ import annotations

import re
from typing import Any

from sqlalchemy.orm import Session

from app.models.test_point import TestPoint
from app.repositories.test_point_repository import TestPointRepository


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


def _normalize_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    items: list[str] = []
    for raw in value:
        item = _normalize_text(raw)
        if item and item not in items:
            items.append(item)
    return items


def _safe_point_prefix(page_code: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9]+", "_", _normalize_text(page_code).upper()).strip("_")
    return normalized or "COMMON"


def _resolve_point_id(*, raw_point_id: str, page_code: str, index: int) -> str:
    direct = _normalize_text(raw_point_id)
    if direct:
        return direct
    return f"TP_{_safe_point_prefix(page_code)}_{index:03d}"


def sync_requirement_test_points(
    db: Session,
    *,
    project_code: str,
    page_code: str,
    requirement_spec: dict[str, Any],
    source: str = "full-chain",
) -> dict[str, Any]:
    TestPoint.__table__.create(bind=db.get_bind(), checkfirst=True)
    project = _normalize_text(project_code).lower() or "mall"
    page = _normalize_text(page_code) or _normalize_text(requirement_spec.get("page")) or "common"
    intents = requirement_spec.get("test_intents") if isinstance(requirement_spec.get("test_intents"), list) else []

    inserted = 0
    updated = 0
    ignored = 0
    scene_type_counts: dict[str, int] = {}
    for index, raw in enumerate(intents, start=1):
        if not isinstance(raw, dict):
            ignored += 1
            continue
        point_name = _normalize_text(raw.get("summary")) or _normalize_text(raw.get("title"))
        if not point_name:
            ignored += 1
            continue
        scene_type = _normalize_text(raw.get("scene_type"))
        scene_type_counts[scene_type or "unknown"] = int(scene_type_counts.get(scene_type or "unknown", 0)) + 1
        point_id = _resolve_point_id(raw_point_id=_normalize_text(raw.get("point_id")), page_code=page, index=index)
        involved_elements = _normalize_list(raw.get("involved_elements"))
        priority = _normalize_text(raw.get("priority")) or "P1"
        test_data_type = _normalize_text(raw.get("test_data_type"))
        expect_result = _normalize_text(raw.get("expect_result"))
        existing = TestPointRepository(db).get_by_point_id(project, page, point_id)
        if existing is None:
            db.add(
                TestPoint(
                    project_code=project,
                    page_code=page,
                    point_id=point_id,
                    point_name=point_name,
                    scene_type=scene_type,
                    priority=priority,
                    test_data_type=test_data_type,
                    involved_elements=involved_elements,
                    expect_result=expect_result,
                    source=source,
                    status="active",
                    raw_payload=raw,
                )
            )
            inserted += 1
            continue

        changed = False
        for attr, value in (
            ("point_name", point_name),
            ("scene_type", scene_type),
            ("priority", priority),
            ("test_data_type", test_data_type),
            ("involved_elements", involved_elements),
            ("expect_result", expect_result),
            ("source", source),
            ("status", "active"),
            ("raw_payload", raw),
        ):
            if getattr(existing, attr) != value:
                setattr(existing, attr, value)
                changed = True
        if changed:
            updated += 1

    db.commit()
    return {
        "project_code": project,
        "page_code": page,
        "inserted_count": inserted,
        "updated_count": updated,
        "ignored_count": ignored,
        "total_count": inserted + updated,
        "scene_type_counts": scene_type_counts,
    }
