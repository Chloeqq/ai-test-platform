from __future__ import annotations

import re
from typing import Any

from .schema import TestPoint, TestPointPlan


def build_test_point_plan(
    page: str,
    requirement: list[str],
    steps: list[dict],
    *,
    source_type: str | None = "yaml_case",
    source_name: str | None = None,
    source_ref: str | None = None,
    priority: str | None = None,
) -> TestPointPlan:
    points: list[TestPoint] = []

    for index, step in enumerate(steps, start=1):
        action = step["action"]
        target = step.get("target")
        value = step.get("value")

        if action == "login":
            point_type = "precondition"
            description = "Use the shared login entry step."
        elif action == "click":
            point_type = "navigation"
            description = f"Navigate with target '{target}'."
        elif action == "fill":
            point_type = "input"
            description = f"Fill target '{target}' with test data."
        elif action in {"wait_for", "assert_visible"}:
            point_type = "assertion"
            description = f"Verify target '{target}' is ready or visible."
        elif action == "assert_url":
            point_type = "assertion"
            description = "Verify the current URL."
        else:
            point_type = "action"
            description = f"Execute action '{action}'."

        points.append(
            TestPoint(
                key=f"{page}-{index:02d}",
                point_type=point_type,
                description=description,
                action=action,
                target=target,
                value=value,
            )
        )

    return TestPointPlan(
        page=page,
        requirement=requirement,
        source_type=source_type,
        source_name=source_name,
        source_ref=source_ref,
        priority=priority,
        points=points,
    )


def build_test_point_plan_from_openapi(
    openapi_spec: dict[str, Any],
    *,
    page: str = "api",
    source_name: str | None = None,
    source_ref: str | None = "inline_openapi",
    priority: str | None = "P1",
) -> TestPointPlan:
    requirement: list[str] = []
    if openapi_spec.get("info", {}).get("title"):
        requirement.append(str(openapi_spec["info"]["title"]))
    if openapi_spec.get("info", {}).get("description"):
        requirement.append(str(openapi_spec["info"]["description"]))

    points: list[TestPoint] = []
    index = 1
    for path_name, path_item in (openapi_spec.get("paths") or {}).items():
        if not isinstance(path_item, dict):
            continue
        for method, operation in path_item.items():
            if method.lower() not in {"get", "post", "put", "patch", "delete"}:
                continue
            if not isinstance(operation, dict):
                operation = {}
            operation_id = operation.get("operationId") or f"{method}_{path_name}"
            sanitized_operation = re.sub(r"[^a-zA-Z0-9]+", "_", str(operation_id)).strip("_").lower()
            summary = operation.get("summary") or operation.get("description") or f"{method.upper()} {path_name}"
            points.append(
                TestPoint(
                    key=f"{page}-{index:02d}",
                    point_type="action",
                    description=f"Validate API operation: {summary}",
                    action="api_request",
                    target=sanitized_operation or method.lower(),
                    value=f"{method.upper()} {path_name}",
                )
            )
            index += 1

    return TestPointPlan(
        page=page,
        requirement=requirement,
        source_type="openapi",
        source_name=source_name or openapi_spec.get("info", {}).get("title") or "openapi",
        source_ref=source_ref,
        priority=priority,
        points=points,
    )


def render_steps_from_test_point_plan(plan: dict) -> list[dict]:
    steps: list[dict] = []

    for point in plan.get("points", []):
        step = {"action": point["action"]}

        if point.get("target") is not None:
            step["target"] = point["target"]

        if point.get("value") is not None:
            step["value"] = point["value"]

        steps.append(step)

    return steps
