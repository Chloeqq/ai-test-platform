from __future__ import annotations

import re
from typing import Any

from .schema import TestPoint, TestPointPlan


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


def _point_confidence(action: str, point_type: str, target: str | None, value: Any) -> tuple[float, list[str], str, str]:
    warnings: list[str] = []
    normalized_action = _normalize_text(action)
    normalized_type = _normalize_text(point_type)
    normalized_target = _normalize_text(target)
    has_value = value not in (None, "")

    if normalized_action == "login":
        return 0.96, warnings, "execute", "共享登录预条件稳定，可直接执行。"

    if normalized_action in {"click", "wait_for", "assert_visible"}:
        confidence = 0.9 if normalized_target else 0.6
        if not normalized_target:
            warnings.append(f"{normalized_action} 步骤缺少 target")
        if normalized_type == "assertion":
            confidence -= 0.03
        return round(max(0.0, min(1.0, confidence)), 2), warnings, "execute" if confidence >= 0.85 else "review", (
            "目标明确且可执行。" if normalized_target else "依赖目标缺失，需要人工确认。"
        )

    if normalized_action == "fill":
        confidence = 0.88 if normalized_target and has_value else 0.62
        if not normalized_target:
            warnings.append("fill 步骤缺少 target")
        if not has_value:
            warnings.append("fill 步骤缺少 value")
        return round(max(0.0, min(1.0, confidence)), 2), warnings, "execute" if confidence >= 0.85 else "review", (
            "输入目标和测试数据完整。" if normalized_target and has_value else "输入信息不完整，需要确认。"
        )

    if normalized_action == "assert_url":
        confidence = 0.93 if has_value else 0.58
        if not has_value:
            warnings.append("assert_url 步骤缺少 value")
        return round(max(0.0, min(1.0, confidence)), 2), warnings, "execute" if confidence >= 0.85 else "review", (
            "URL 断言稳定。" if has_value else "URL 断言缺少期望值。"
        )

    if normalized_action == "goto":
        confidence = 0.84 if has_value else 0.55
        if not has_value:
            warnings.append("goto 步骤缺少 value")
        return round(max(0.0, min(1.0, confidence)), 2), warnings, "review", "导航步骤通常依赖环境，建议确认。"

    if normalized_action == "api_request":
        confidence = 0.86 if normalized_target and has_value else 0.66
        if not normalized_target:
            warnings.append("api_request 步骤缺少 target")
        if not has_value:
            warnings.append("api_request 步骤缺少 value")
        return round(max(0.0, min(1.0, confidence)), 2), warnings, "execute" if confidence >= 0.85 else "review", (
            "API 目标明确。" if normalized_target and has_value else "API 目标或请求描述不完整。"
        )

    confidence = 0.65
    warnings.append(f"未识别的 action: {normalized_action or 'unknown'}")
    return confidence, warnings, "review", "当前步骤需要人工复核。"


def _build_point_fields(action: str, point_type: str, target: str | None, value: Any) -> dict[str, Any]:
    confidence, warnings, suggestion, review_reason = _point_confidence(action, point_type, target, value)
    dependent_elements = [_normalize_text(target)] if _normalize_text(target) else []
    requires_review = confidence < 0.75 or bool(warnings) or suggestion == "review"
    return {
        "confidence": confidence,
        "warnings": warnings,
        "requires_review": requires_review,
        "suggestion": suggestion,
        "review_reason": review_reason,
        "dependent_elements": dependent_elements,
        "source_ids": [],
        "technique_type": "normal",
        "technique_source": "step_action",
        "technique_confidence": confidence,
        "execution_scope": "mainline",
    }


def _build_technique_distribution(points: list[TestPoint]) -> dict[str, int]:
    distribution: dict[str, int] = {}
    for point in points:
        technique_type = _normalize_text(point.technique_type or "normal").lower() or "normal"
        distribution[technique_type] = distribution.get(technique_type, 0) + 1
    return dict(sorted(distribution.items()))


def _build_plan_summary(points: list[TestPoint]) -> dict[str, Any]:
    confidences = [float(point.confidence) for point in points if isinstance(point.confidence, (int, float))]
    warnings = [warning for point in points for warning in (point.warnings or [])]
    low_confidence_count = sum(1 for point in points if isinstance(point.confidence, (int, float)) and float(point.confidence) < 0.75)
    pending_review_count = sum(1 for point in points if bool(point.requires_review) and _normalize_text(point.suggestion).lower() != "skip")
    skip_suggestion_count = sum(1 for point in points if _normalize_text(point.suggestion).lower() == "skip")
    review_suggestion_count = sum(1 for point in points if _normalize_text(point.suggestion).lower() == "review")
    execute_suggestion_count = sum(1 for point in points if _normalize_text(point.suggestion).lower() == "execute")
    dependent_elements = []
    seen: set[str] = set()
    for point in points:
        for item in point.dependent_elements or []:
            normalized = _normalize_text(item)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            dependent_elements.append(normalized)

    confidence = round(sum(confidences) / len(confidences), 2) if confidences else 0.0
    technique_distribution = _build_technique_distribution(points)
    return {
        "confidence": confidence,
        "warnings": list(dict.fromkeys([item for item in warnings if _normalize_text(item)])),
        "requires_review": bool(pending_review_count > 0 or low_confidence_count > 0 or confidence < 0.75),
        "review_summary": {
            "pending_review_count": pending_review_count,
            "skip_suggestion_count": skip_suggestion_count,
            "review_suggestion_count": review_suggestion_count,
            "execute_suggestion_count": execute_suggestion_count,
            "low_confidence_point_count": low_confidence_count,
            "total_points": len(points),
            "dependent_element_count": len(dependent_elements),
            "technique_distribution": technique_distribution,
        },
        "dependent_elements": dependent_elements,
    }


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

        point_fields = _build_point_fields(action=action, point_type=point_type, target=target, value=value)

        points.append(
            TestPoint(
                key=f"{page}-{index:02d}",
                point_type=point_type,
                description=description,
                action=action,
                target=target,
                value=value,
                confidence=point_fields["confidence"],
                warnings=point_fields["warnings"],
                requires_review=point_fields["requires_review"],
                suggestion=point_fields["suggestion"],
                review_reason=point_fields["review_reason"],
                dependent_elements=point_fields["dependent_elements"],
                source_ids=point_fields["source_ids"],
                technique_type=point_fields["technique_type"],
                technique_source=point_fields["technique_source"],
                technique_confidence=point_fields["technique_confidence"],
                execution_scope=point_fields["execution_scope"],
            )
        )

    summary = _build_plan_summary(points)

    return TestPointPlan(
        page=page,
        requirement=requirement,
        source_type=source_type,
        source_name=source_name,
        source_ref=source_ref,
        priority=priority,
        points=points,
        confidence=summary["confidence"],
        warnings=summary["warnings"],
        requires_review=summary["requires_review"],
        review_summary=summary["review_summary"],
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
            point_fields = _build_point_fields(
                action="api_request",
                point_type="action",
                target=sanitized_operation or method.lower(),
                value=f"{method.upper()} {path_name}",
            )
            points.append(
                TestPoint(
                    key=f"{page}-{index:02d}",
                    point_type="action",
                    description=f"Validate API operation: {summary}",
                    action="api_request",
                    target=sanitized_operation or method.lower(),
                    value=f"{method.upper()} {path_name}",
                    confidence=point_fields["confidence"],
                    warnings=point_fields["warnings"],
                    requires_review=point_fields["requires_review"],
                    suggestion=point_fields["suggestion"],
                    review_reason=point_fields["review_reason"],
                    dependent_elements=point_fields["dependent_elements"],
                    source_ids=point_fields["source_ids"],
                    technique_type=point_fields["technique_type"],
                    technique_source=point_fields["technique_source"],
                    technique_confidence=point_fields["technique_confidence"],
                    execution_scope=point_fields["execution_scope"],
                )
            )
            index += 1

    summary = _build_plan_summary(points)

    return TestPointPlan(
        page=page,
        requirement=requirement,
        source_type="openapi",
        source_name=source_name or openapi_spec.get("info", {}).get("title") or "openapi",
        source_ref=source_ref,
        priority=priority,
        points=points,
        confidence=summary["confidence"],
        warnings=summary["warnings"],
        requires_review=summary["requires_review"],
        review_summary=summary["review_summary"],
    )


def render_steps_from_test_point_plan(plan: dict) -> list[dict]:
    steps: list[dict] = []

    for point in plan.get("points", []):
        if str(point.get("execution_scope", "mainline")).strip().lower() == "design_only":
            continue
        step = {"action": point["action"]}

        if point.get("target") is not None:
            step["target"] = point["target"]

        if point.get("value") is not None:
            step["value"] = point["value"]

        steps.append(step)

    return steps
