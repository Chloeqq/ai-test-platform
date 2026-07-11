"""Behavior Registry API — CRUD for behaviors + assertion templates (Phase 3)."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.repositories.behavior_registry_repository import BehaviorRegistryRepository

router = APIRouter(tags=["behavior-registry"], prefix="/api/behavior-registry")


# ---------------------------------------------------------------------------
# List behaviors for a page
# ---------------------------------------------------------------------------

@router.get("/behaviors")
def list_behaviors(
    page_code: str = Query(default=""),
    scope: str = Query(default=""),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """List behavior entries, optionally filtered by page_code or scope."""
    repo = BehaviorRegistryRepository(db)
    items = repo.list_active(page_code=page_code)
    if scope:
        items = [b for b in items if b.scope == scope]
    return {
        "items": [
            {
                "id": b.id,
                "behavior_code": b.behavior_code,
                "intent_type": b.intent_type,
                "scenario": b.scenario,
                "scope": b.scope,
                "page_code": b.page_code,
                "domain": b.domain,
                "version": b.version,
                "status": b.status,
                "priority": b.priority,
                "label": b.label,
                "capabilities": b.capabilities,
            }
            for b in items
        ]
    }


# ---------------------------------------------------------------------------
# Get single behavior with templates
# ---------------------------------------------------------------------------

@router.get("/behaviors/{behavior_id}")
def get_behavior(behavior_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    repo = BehaviorRegistryRepository(db)
    b = repo.find_by_code(str(behavior_id))  # fallback: try code
    if not b:
        # Try by id
        from app.models.behavior_registry import BehaviorRegistry
        b = db.get(BehaviorRegistry, behavior_id)
    if not b:
        raise HTTPException(status_code=404, detail="behavior not found")

    templates = repo.list_templates_by_behavior(b.id)
    return {
        "id": b.id,
        "behavior_code": b.behavior_code,
        "intent_type": b.intent_type,
        "scenario": b.scenario,
        "scope": b.scope,
        "page_code": b.page_code,
        "domain": b.domain,
        "version": b.version,
        "status": b.status,
        "priority": b.priority,
        "label": b.label,
        "capabilities": b.capabilities,
        "templates": [
            {
                "id": t.id,
                "capability": t.capability,
                "execution_layer": t.execution_layer,
                "action": t.action,
                "target": t.target,
                "operator": t.operator,
                "value": t.value,
                "description": t.description,
            }
            for t in templates
        ],
    }


# ---------------------------------------------------------------------------
# Upsert behavior
# ---------------------------------------------------------------------------

@router.post("/behaviors")
def upsert_behavior(payload: dict[str, Any], db: Session = Depends(get_db)) -> dict[str, Any]:
    repo = BehaviorRegistryRepository(db)
    b = repo.upsert_behavior(**payload)
    db.commit()
    return {"id": b.id, "behavior_code": b.behavior_code}


# ---------------------------------------------------------------------------
# Add assertion template
# ---------------------------------------------------------------------------

@router.post("/behaviors/{behavior_id}/templates")
def add_template(behavior_id: int, payload: dict[str, Any], db: Session = Depends(get_db)) -> dict[str, Any]:
    repo = BehaviorRegistryRepository(db)
    t = repo.add_template(behavior_id=behavior_id, **payload)
    return {"id": t.id, "action": t.action, "target": t.target}


# ---------------------------------------------------------------------------
# Delete assertion template
# ---------------------------------------------------------------------------

@router.delete("/templates/{template_id}")
def delete_template(template_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    from app.models.behavior_registry import AssertionTemplate
    t = db.get(AssertionTemplate, template_id)
    if not t:
        raise HTTPException(status_code=404, detail="template not found")
    db.delete(t)
    db.commit()
    return {"deleted": template_id}
