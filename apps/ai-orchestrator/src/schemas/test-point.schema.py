from __future__ import annotations

from typing import Any


TEST_POINT_PLAN_SCHEMA_V1: dict[str, Any] = {
    "type": "object",
    "required": ["version", "project", "case_id", "page", "points"],
    "properties": {
        "version": {"const": "TestPointPlanV1"},
        "project": {"type": "string"},
        "case_id": {"type": "string"},
        "page": {"type": "string"},
        "source_type": {"type": "string"},
        "requirement": {"type": "array", "items": {"type": "string"}},
        "points": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["key", "point_type", "action", "description", "priority"],
                "properties": {
                    "key": {"type": "string"},
                    "point_type": {"type": "string"},
                    "action": {"type": "string"},
                    "description": {"type": "string"},
                    "priority": {"type": "string"},
                    "dependencies": {"type": "array", "items": {"type": "string"}},
                    "source_ids": {"type": "array", "items": {"type": "string"}},
                    "target": {"type": "string"},
                    "value": {},
                },
            },
        },
        "metadata": {"type": "object"},
        "review_summary": {"type": "object"},
    },
}


def normalize_test_point_plan(payload: dict[str, Any] | None, *, strict: bool = False) -> tuple[dict[str, Any], list[str]]:
    from shared_backend.schemas import normalize_test_point_plan_v1

    return normalize_test_point_plan_v1(payload, strict=strict)


def validate_test_point_plan(payload: dict[str, Any] | None, *, strict: bool = False) -> list[str]:
    _normalized, warnings = normalize_test_point_plan(payload, strict=strict)
    return warnings


def get_test_point_plan_schema() -> dict[str, Any]:
    return TEST_POINT_PLAN_SCHEMA_V1
