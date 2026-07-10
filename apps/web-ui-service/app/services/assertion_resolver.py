"""Phase 1: Assertion Resolver + Compiler + Audit Log.

Deterministic pipeline from intent_type + scenario to executable DSL.
AI only provides intent classification; everything else is system-resolved.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.behavior_registry import (
    AssertionExecutionLog,
    resolve_behavior_code,
)
from app.repositories.behavior_registry_repository import BehaviorRegistryRepository
from shared_backend.type_utils import str_value


# ---------------------------------------------------------------------------
# Variable Resolver
# ---------------------------------------------------------------------------

def resolve_variables(value: str, context: dict[str, Any]) -> str:
    """Replace {{variable}} placeholders with context values.

    Sources:
      - Environment: {{VAR_NAME}} → os.getenv("ATP_"+VAR_NAME)
      - DataPool: {{test_user.username}} → context.get("test_data", {}).get("username")
      - Runtime: {{user_id}} → context.get("runtime", {}).get("user_id")
    """
    result = value
    import re
    for match in re.finditer(r"\{\{(\w+(?:\.\w+)*)\}\}", value):
        var = match.group(1)
        replacement = ""

        # Try runtime context first
        if var in context.get("runtime", {}):
            replacement = str(context["runtime"][var])
        # Try test data
        elif "." in var:
            parts = var.split(".", 1)
            if parts[0] in context.get("test_data", {}):
                nested = context["test_data"][parts[0]]
                replacement = str(nested.get(parts[1], "")) if isinstance(nested, dict) else ""
        # Try environment
        else:
            replacement = os.getenv(f"ATP_{var.upper()}", "")

        if replacement:
            result = result.replace("{{" + var + "}}", replacement)

    return result


# ---------------------------------------------------------------------------
# Assertion Compiler
# ---------------------------------------------------------------------------

def compile_assertions(
    behavior_id: int,
    db: Session,
    *,
    context: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Compile assertion templates into executable DSL.

    Args:
        behavior_id: ID of the behavior in behavior_registry.
        db: Database session.
        context: Variable context dict {runtime: {...}, test_data: {...}}.

    Returns:
        List of compiled assertion dicts with action/target/value/layer.
    """
    ctx = context or {}
    repo = BehaviorRegistryRepository(db)
    templates = repo.list_templates_by_behavior(behavior_id)

    compiled: list[dict[str, Any]] = []
    for t in templates:
        value = resolve_variables(str_value(t.value), ctx)
        compiled.append({
            "action": str_value(t.action),
            "target": str_value(t.target),
            "value": value,
            "operator": str_value(t.operator),
            "execution_layer": str_value(t.execution_layer),
            "capability": str_value(t.capability),
            "description": str_value(t.description),
        })

    return compiled


# ---------------------------------------------------------------------------
# Assertion Resolver (main entry point)
# ---------------------------------------------------------------------------

def resolve_and_compile(
    intent_type: str,
    scenario: str,
    page_code: str,
    db: Session,
    *,
    context: dict[str, Any] | None = None,
    context_filter: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Resolve intent to behavior, compile assertions, and log the result.

    This is the main public API for Phase 1.

    Args:
        intent_type: AI-classified intent (e.g. "AUTH_LOGIN").
        scenario: "positive" | "negative" | "boundary".
        page_code: Page identifier (e.g. "login").
        db: Database session.
        context: Variable context for template resolution.
        context_filter: Additional filter for behavior matching ({role: "admin"}).

    Returns:
        {
            "behavior_code": "AUTH_LOGIN_SUCCESS",
            "source": "page_level",
            "assertions": [{action, target, value, operator, ...}, ...],
            "status": "resolved" | "not_configured"
        }
    """
    ctx = context or {}

    # Step 1: Determine behavior_code from intent_type + scenario
    behavior_code = resolve_behavior_code(intent_type, scenario)

    if not behavior_code:
        # Unknown intent/scenario combo
        _log_result(db, "", intent_type, scenario, "unknown", 0, "not_configured")
        return {
            "behavior_code": "",
            "source": "not_configured",
            "assertions": [],
            "status": "not_configured",
            "reason": f"No behavior mapping for {intent_type}+{scenario}",
        }

    # Step 2: Look up in Behavior Registry by behavior_code (not intent+scenario)
    repo = BehaviorRegistryRepository(db)
    registry_entry = repo.find_by_code(behavior_code)
    if not registry_entry or registry_entry.page_code != page_code:
        # Try domain-level lookup
        registry_entry = repo.find_by_intent(
            intent_type=intent_type,
            scenario=scenario,
            page_code=page_code,
            context_filter=context_filter,
        )

    if not registry_entry:
        _log_result(db, behavior_code, intent_type, scenario, 0, "not_configured")
        return {
            "behavior_code": behavior_code,
            "source": "not_configured",
            "assertions": [],
            "status": "not_configured",
            "reason": f"No assertion template for {behavior_code} on page {page_code}",
        }

    # Step 3: Compile assertions from templates
    assertions = compile_assertions(registry_entry.id, db, context=ctx)

    # Step 4: Determine source
    source = f"{registry_entry.scope}_level"

    # Step 5: Log
    _log_result(
        db, behavior_code, intent_type, scenario,
        registry_entry.version, source, assertions,
        test_case_id=str_value(ctx.get("test_case_id", "")),
    )

    return {
        "behavior_code": behavior_code,
        "source": source,
        "assertions": assertions,
        "status": "resolved",
        "version": registry_entry.version,
    }


# ---------------------------------------------------------------------------
# Audit Log
# ---------------------------------------------------------------------------

def _log_result(
    db: Session,
    behavior_code: str,
    intent_type: str,
    scenario: str,
    version: int,
    source: str,
    assertions: list[dict[str, Any]] | str = "",
    test_case_id: str = "",
) -> None:
    """Record assertion generation in audit log."""
    try:
        log_entry = AssertionExecutionLog(
            test_case_id=test_case_id,
            intent_type=intent_type,
            scenario=scenario,
            behavior_code=behavior_code,
            behavior_version=version,
            source=source,
            compiled_assertions=assertions if isinstance(assertions, list) else [],
            executed_at=datetime.now(timezone.utc),
        )
        db.add(log_entry)
        db.commit()
    except Exception:
        pass  # Log failure should not block assertion generation
