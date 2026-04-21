from __future__ import annotations

import logging
import re
from typing import Any

_LOGGER = logging.getLogger(__name__)


_DSL_ACTIONS = {"input", "click", "assert", "navigate", "wait", "login"}
_ASSERTION_TYPES = {"url", "visible", "text"}
_DSL_TO_RUNNER_ACTION = {
    "input": "fill",
    "click": "click",
    "wait": "wait_for",
    "navigate": "goto",
    "login": "login",
}
_LIST_PREFIX_RE = re.compile(r"^\s*(?:[-*•·]+\s*|\d+\s*[.)、]\s*)")
_SPACE_RE = re.compile(r"\s+")


class ExecutionCompilerError(ValueError):
    def __init__(self, *, code: str, message: str, reason: str = "", stage: str = "execution_compiler") -> None:
        super().__init__(message)
        self.code = str(code).strip() or "execution_compiler_failed"
        self.message = str(message).strip() or "execution compiler failed"
        self.reason = str(reason).strip()
        self.stage = str(stage).strip() or "execution_compiler"

    def to_detail(self) -> dict[str, str]:
        return {
            "code": self.code,
            "message": self.message,
            "reason": self.reason,
            "stage": self.stage,
        }


def _normalized_text(value: Any) -> str:
    text = str(value or "").replace("\r", "\n").strip()
    text = _LIST_PREFIX_RE.sub("", text)
    return _SPACE_RE.sub(" ", text).strip()


def _compact(value: Any) -> str:
    return _SPACE_RE.sub("", str(value or "").strip().lower())


def _extract_intent_id(point: dict[str, Any], point_index: int) -> str:
    _ = point_index
    return _normalized_text(point.get("intent_id"))


def _normalize_involved_elements(point: dict[str, Any]) -> list[str]:
    raw_involved = point.get("involved_elements")
    if not isinstance(raw_involved, list):
        return []
    normalized: list[str] = []
    for item in raw_involved:
        value = _normalized_text(item)
        if value:
            normalized.append(value)
    return normalized


def _resolve_explicit_target(point: dict[str, Any], step: dict[str, Any]) -> tuple[str, str]:
    for source in (
        step.get("target"),
        point.get("target"),
        point.get("element_code"),
        point.get("element"),
    ):
        value = _normalized_text(source)
        if value:
            return value, ""

    involved = _normalize_involved_elements(point)
    if len(involved) == 1:
        return involved[0], ""
    if len(involved) > 1:
        return "", "ambiguous explicit target"
    return "", "missing explicit target"


def _clamp_confidence(value: Any, *, default: float = 0.0) -> float:
    if isinstance(value, (int, float)):
        return max(0.0, min(1.0, float(value)))
    return max(0.0, min(1.0, float(default)))


def _build_traceability(
    *,
    point_index: int,
    step_index: int,
    raw_text: str,
) -> dict[str, Any]:
    return {
        "status": "resolved",
        "compiler_status": "resolved",
        "execution_status": "ready",
        "reason": "",
        "confidence": 1.0,
        "source_point_index": int(point_index),
        "source_step_index": int(step_index),
        "raw_text": _normalized_text(raw_text),
    }


def _extract_steps(point: dict[str, Any]) -> list[dict[str, Any]]:
    raw_steps = point.get("steps")
    result: list[dict[str, Any]] = []
    if isinstance(raw_steps, list):
        for step in raw_steps:
            if isinstance(step, dict):
                result.append(step)
            else:
                text = _normalized_text(step)
                if text:
                    result.append({"raw_text": text})
    elif isinstance(raw_steps, dict):
        result.append(raw_steps)
    elif raw_steps is not None:
        text = _normalized_text(raw_steps)
        if text:
            result.append({"raw_text": text})

    return result


def normalize_test_points(points: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not isinstance(points, list):
        raise ExecutionCompilerError(
            code="execution_compiler_missing_test_points",
            message="test_points.points must be a list",
            reason="invalid points payload",
            stage="normalize_test_points",
        )
    if not points:
        raise ExecutionCompilerError(
            code="execution_compiler_empty_test_points",
            message="test_points.points must not be empty",
            reason="empty points",
            stage="normalize_test_points",
        )

    normalized: list[dict[str, Any]] = []
    for point_index, raw_point in enumerate(points):
        if not isinstance(raw_point, dict):
            raise ExecutionCompilerError(
                code="execution_compiler_invalid_point",
                message="point must be an object",
                reason=f"invalid point at index {point_index}",
                stage="normalize_test_points",
            )
        intent_id = _extract_intent_id(raw_point, point_index)
        if not intent_id:
            raise ExecutionCompilerError(
                code="execution_compiler_missing_intent_id",
                message="point must include intent_id",
                reason=f"point {point_index} missing intent_id",
                stage="normalize_test_points",
            )
        steps = _extract_steps(raw_point)
        if not steps:
            raise ExecutionCompilerError(
                code="execution_compiler_invalid_point",
                message="point must include executable steps",
                reason=f"point {point_index} has no executable step",
                stage="normalize_test_points",
            )
        normalized.append(
            {
                "intent_id": intent_id,
                "point_index": point_index,
                "steps": steps,
                "involved_elements": _normalize_involved_elements(raw_point),
            }
        )
    return normalized


def _extract_route_from_text(text: str) -> str:
    matched = re.search(r"(https?://[^\s]+|#/[A-Za-z0-9_./-]+|/[A-Za-z0-9_./-]+)", str(text or ""))
    if matched:
        route = _normalized_text(matched.group(1))
        if route:
            return route
    return "/"


def _parse_input_value(text: str) -> str | None:
    if any(token in text for token in ["留空", "为空", "空值"]):
        return ""
    if "空格" in text:
        return " "
    quoted = re.search(r"[\"“'‘](.*?)[\"”'’]", text)
    if quoted and _normalized_text(quoted.group(1)):
        return _normalized_text(quoted.group(1))
    suffix = re.search(r"(?:输入|填写)\s+([A-Za-z0-9_@.\-]+)$", text)
    if suffix and _normalized_text(suffix.group(1)):
        return _normalized_text(suffix.group(1))
    return None


def normalize_test_points_to_actions(points: list[dict[str, Any]]) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    for point in points:
        if not isinstance(point, dict):
            raise ExecutionCompilerError(
                code="execution_compiler_invalid_point",
                message="point must be object",
                reason="invalid point while normalizing actions",
                stage="normalize_test_points_to_actions",
            )
        intent_id = _normalized_text(point.get("intent_id"))
        if not intent_id:
            raise ExecutionCompilerError(
                code="execution_compiler_missing_intent_id",
                message="point must include intent_id",
                reason="missing intent_id while normalizing actions",
                stage="normalize_test_points_to_actions",
            )
        point_index = int(point.get("point_index", -1))
        step_rows = point.get("steps") if isinstance(point.get("steps"), list) else []
        if not step_rows:
            raise ExecutionCompilerError(
                code="execution_compiler_missing_test_points",
                message="point must include explicit steps",
                reason=f"point `{intent_id}` has no explicit steps",
                stage="normalize_test_points_to_actions",
            )
        for step_index, raw_step in enumerate(step_rows):
            if not isinstance(raw_step, dict):
                raise ExecutionCompilerError(
                    code="execution_compiler_invalid_dsl_action",
                    message="step must be object",
                    reason=f"invalid step at point `{intent_id}` index {step_index}",
                    stage="normalize_test_points_to_actions",
                )
            step = raw_step
            raw_text = _normalized_text(step.get("raw_text") or step.get("description") or step.get("summary") or "")
            action = _normalized_text(step.get("action")).lower()
            raw_assertion = _normalized_text(step.get("assertion")).lower()
            target = _normalized_text(step.get("target"))
            effective_target = target or _normalized_text(point.get("target"))
            value = step.get("value")
            if not action:
                raise ExecutionCompilerError(
                    code="execution_compiler_invalid_dsl_action",
                    message="step action is required",
                    reason=f"point `{intent_id}` step {step_index} missing action",
                    stage="normalize_test_points_to_actions",
                )
            mapped_action = action
            assertion = raw_assertion or None
            if action in {"fill", "input"}:
                mapped_action = "input"
            elif action == "click":
                mapped_action = "click"
            elif action in {"wait", "wait_for"}:
                mapped_action = "wait"
            elif action in {"goto", "navigate"}:
                mapped_action = "navigate"
            elif action in {"assert_visible", "assert_text", "assert_url"}:
                mapped_action = "assert"
                assertion = {
                    "assert_visible": "visible",
                    "assert_text": "text",
                    "assert_url": "url",
                }[action]
            elif action == "assert":
                mapped_action = "assert"
                if assertion not in {"visible", "text", "url"}:
                    assertion = "visible"
            elif action == "login":
                mapped_action = "login"
                assertion = None
            else:
                raise ExecutionCompilerError(
                    code="execution_compiler_invalid_dsl_action",
                    message="step action is not allowed",
                    reason=f"point `{intent_id}` step {step_index} action `{action}` not allowed",
                    stage="normalize_test_points_to_actions",
                )

            requires_target = mapped_action in {"input", "click", "wait", "assert"} and assertion != "url"
            if requires_target and not effective_target:
                raise ExecutionCompilerError(
                    code="execution_compiler_invalid_dsl_action",
                    message="step target is required",
                    reason=f"point `{intent_id}` step {step_index} missing target",
                    stage="normalize_test_points_to_actions",
                )
            if mapped_action == "input" and value is None:
                raise ExecutionCompilerError(
                    code="execution_compiler_invalid_dsl_action",
                    message="input step requires value",
                    reason=f"point `{intent_id}` step {step_index} missing value",
                    stage="normalize_test_points_to_actions",
                )
            if mapped_action == "assert" and assertion not in {"visible", "text", "url"}:
                raise ExecutionCompilerError(
                    code="execution_compiler_invalid_dsl_action",
                    message="assert step has invalid assertion",
                    reason=f"point `{intent_id}` step {step_index} invalid assertion `{assertion}`",
                    stage="normalize_test_points_to_actions",
                )
            normalized_action = {
                "type": mapped_action,
                "target": effective_target or None,
                "value": value,
                "assertion": assertion,
                "intent_id": intent_id,
                "meta": {
                    "raw_text": raw_text or action,
                    "source_point_index": point_index,
                    "source_step_index": step_index,
                    "compiler_status": "resolved",
                    "compiler_reason": "",
                    "confidence": 1.0,
                },
            }
            actions.append(normalized_action)
    if not actions:
        raise ExecutionCompilerError(
            code="execution_ir_empty_steps",
            message="no actions produced",
            reason="point list produced no actions",
            stage="normalize_test_points_to_actions",
        )
    return actions


def build_execution_ir(actions: list[dict[str, Any]]) -> dict[str, Any]:
    if not isinstance(actions, list) or not actions:
        raise ExecutionCompilerError(
            code="execution_ir_empty_steps",
            message="actions must not be empty",
            reason="invalid action list",
            stage="build_execution_ir",
        )
    steps: list[dict[str, Any]] = []
    for index, raw in enumerate(actions):
        if not isinstance(raw, dict):
            raise ExecutionCompilerError(
                code="execution_compiler_invalid_dsl_action",
                message="action must be object",
                reason=f"invalid action at index {index}",
                stage="build_execution_ir",
            )
        action_type = _normalized_text(raw.get("type")).lower()
        if action_type not in _DSL_ACTIONS and action_type != "unknown":
            raise ExecutionCompilerError(
                code="execution_compiler_invalid_dsl_action",
                message="action type is not allowed",
                reason=f"type `{action_type}` not allowed",
                stage="build_execution_ir",
            )
        intent_id = _normalized_text(raw.get("intent_id"))
        target = _normalized_text(raw.get("target"))
        assertion = _normalized_text(raw.get("assertion")).lower() if raw.get("assertion") is not None else ""
        meta = raw.get("meta") if isinstance(raw.get("meta"), dict) else {}
        raw_text = _normalized_text(meta.get("raw_text"))
        if not raw_text:
            raw_text = action_type or "compiled-step"
        compiler_status = _normalized_text(meta.get("compiler_status")) or "resolved"
        compiler_reason = _normalized_text(meta.get("compiler_reason"))
        confidence = meta.get("confidence")
        if not intent_id:
            raise ExecutionCompilerError(
                code="execution_compiler_missing_intent_id",
                message="action missing intent_id",
                reason=f"action {index} missing intent_id",
                stage="build_execution_ir",
            )
        if action_type == "unknown":
            raise ExecutionCompilerError(
                code="execution_compiler_unrecognized_step",
                message="action type is unknown",
                reason=f"action {index} is unknown",
                stage="build_execution_ir",
            )
        if action_type in {"input", "click", "wait", "assert"} and not target and assertion != "url":
            raise ExecutionCompilerError(
                code="execution_compiler_invalid_dsl_action",
                message="action requires target",
                reason=f"{action_type} action {index} missing explicit target",
                stage="build_execution_ir",
            )
        if action_type == "input" and raw.get("value") is None:
            raise ExecutionCompilerError(
                code="execution_compiler_invalid_dsl_action",
                message="input action requires value",
                reason=f"input action {index} missing value",
                stage="build_execution_ir",
            )
        if action_type == "assert" and assertion and assertion not in _ASSERTION_TYPES:
            raise ExecutionCompilerError(
                code="execution_compiler_invalid_dsl_action",
                message="assert action has invalid assertion",
                reason=f"assert action {index} invalid assertion `{assertion}`",
                stage="build_execution_ir",
            )
        steps.append(
            {
                "type": action_type,
                "target": target,
                "value": raw.get("value"),
                "assertion": assertion or None,
                "selector": "",
                "locator_type": "",
                "intent_id": intent_id,
                "meta": {
                    "raw_text": raw_text,
                    "source_point_index": int(meta.get("source_point_index", -1)),
                    "source_step_index": int(meta.get("source_step_index", -1)),
                    "compiler_status": compiler_status,
                    "compiler_reason": compiler_reason,
                    "confidence": _clamp_confidence(confidence, default=1.0),
                },
            }
        )
    return {"version": "execution-ir/v1", "steps": steps}


def bind_targets(ir: dict[str, Any], page_object: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(ir, dict) or not isinstance(ir.get("steps"), list):
        raise ExecutionCompilerError(
            code="execution_ir_empty_steps",
            message="execution ir is invalid",
            reason="ir.steps missing",
            stage="bind_targets",
        )
    normalized_elements: dict[str, dict[str, str]] = {}
    elements = page_object.get("elements") if isinstance(page_object, dict) else None
    if isinstance(elements, dict):
        for raw_code, raw_meta in elements.items():
            code = _normalized_text(raw_code)
            meta = raw_meta if isinstance(raw_meta, dict) else {}
            selector = _normalized_text(meta.get("selector"))
            locator_type = _normalized_text(meta.get("type"))
            role = _normalized_text(meta.get("role"))
            if code and selector:
                normalized_elements[code] = {
                    "selector": selector,
                    "locator_type": locator_type or "css",
                    "role": role,
                }

    bound_steps: list[dict[str, Any]] = []
    for index, raw_step in enumerate(ir["steps"]):
        step = dict(raw_step) if isinstance(raw_step, dict) else {}
        action_type = _normalized_text(step.get("type")).lower()
        target = _normalized_text(step.get("target"))
        meta = step.get("meta") if isinstance(step.get("meta"), dict) else {}
        meta_status = _normalized_text(meta.get("compiler_status")) or "resolved"
        meta_reason = _normalized_text(meta.get("compiler_reason"))
        meta_confidence = meta.get("confidence")
        raw_text = _normalized_text(meta.get("raw_text")) or action_type or "compiled-step"
        intent_id = _normalized_text(step.get("intent_id"))
        assertion = _normalized_text(step.get("assertion")).lower() if step.get("assertion") is not None else ""
        if action_type == "unknown" or meta_status != "resolved":
            raise ExecutionCompilerError(
                code="execution_render_failed",
                message="compiled step is not resolved",
                reason=meta_reason or "compiler marked step as unresolved",
                stage="bind_targets",
            )
        if action_type == "login":
            step["target"] = None
            step["selector"] = None
            step["locator_type"] = None
            step["role"] = None
            step["meta"] = {
                "raw_text": raw_text,
                "source_point_index": int(meta.get("source_point_index", -1)),
                "source_step_index": int(meta.get("source_step_index", -1)),
                "compiler_status": "resolved",
                "compiler_reason": meta_reason,
                "confidence": _clamp_confidence(meta_confidence, default=1.0),
            }
            bound_steps.append(step)
            continue
        if action_type == "navigate" or (action_type == "assert" and assertion == "url"):
            step["selector"] = None
            step["locator_type"] = None
            step["role"] = None
            step["target"] = None
            step["meta"] = {
                "raw_text": raw_text,
                "source_point_index": int(meta.get("source_point_index", -1)),
                "source_step_index": int(meta.get("source_step_index", -1)),
                "compiler_status": "resolved",
                "compiler_reason": meta_reason,
                "confidence": _clamp_confidence(meta_confidence, default=1.0),
            }
            bound_steps.append(step)
            continue

        element = normalized_elements.get(target) if target else None
        if element is None:
            raise ExecutionCompilerError(
                code="page_object_not_found",
                message="target not found in page object",
                reason=meta_reason or (f"target `{target}` not found in page object" if target else "missing explicit target"),
                stage="bind_targets",
            )

        step["selector"] = element["selector"]
        step["locator_type"] = element["locator_type"]
        step["role"] = element.get("role") or None
        step["meta"] = {
            "raw_text": raw_text,
            "source_point_index": int(meta.get("source_point_index", -1)),
            "source_step_index": int(meta.get("source_step_index", -1)),
            "compiler_status": "resolved",
            "compiler_reason": meta_reason,
            "confidence": _clamp_confidence(meta_confidence, default=1.0),
        }
        bound_steps.append(step)
    return {"version": _normalized_text(ir.get("version")) or "execution-ir/v1", "steps": bound_steps}


def render_execution_steps(ir: dict[str, Any]) -> list[dict[str, Any]]:
    steps = ir.get("steps") if isinstance(ir, dict) else None
    if not isinstance(steps, list) or not steps:
        raise ExecutionCompilerError(
            code="execution_render_failed",
            message="execution ir steps must not be empty",
            reason="empty ir steps",
            stage="render_execution_steps",
        )
    rendered: list[dict[str, Any]] = []
    for index, raw_step in enumerate(steps):
        step = raw_step if isinstance(raw_step, dict) else {}
        action_type = _normalized_text(step.get("type")).lower()
        target = _normalized_text(step.get("target"))
        selector = _normalized_text(step.get("selector"))
        locator_type = _normalized_text(step.get("locator_type"))
        role = _normalized_text(step.get("role"))
        intent_id = _normalized_text(step.get("intent_id"))
        assertion = _normalized_text(step.get("assertion")).lower()
        meta = step.get("meta") if isinstance(step.get("meta"), dict) else {}
        compiler_status = _normalized_text(meta.get("compiler_status")) or "resolved"
        compiler_reason = _normalized_text(meta.get("compiler_reason"))
        confidence_value = meta.get("confidence")
        if not isinstance(confidence_value, (int, float)):
            confidence_value = 1.0 if compiler_status == "resolved" else 0.0
        confidence = max(0.0, min(1.0, float(confidence_value)))

        if compiler_status != "resolved" or action_type == "unknown":
            raise ExecutionCompilerError(
                code="execution_render_failed",
                message="compiled step is not resolved",
                reason=compiler_reason or f"step {index} is unresolved",
                stage="render_execution_steps",
            )

        runner_action = _DSL_TO_RUNNER_ACTION.get(action_type)
        if action_type == "login":
            runner_action = "login"
        if action_type == "assert":
            if assertion == "url":
                runner_action = "assert_url"
            elif assertion == "text":
                runner_action = "assert_text"
            else:
                runner_action = "assert_visible"
        if action_type in {"input", "click", "wait"} and (not target or not selector or not locator_type):
            raise ExecutionCompilerError(
                code="execution_render_failed",
                message="compiled step missing selector binding",
                reason=f"step {index} missing target/selector/locator_type",
                stage="render_execution_steps",
            )
        if not runner_action:
            raise ExecutionCompilerError(
                code="execution_render_failed",
                message="unsupported action",
                reason=f"unsupported action `{action_type}`",
                stage="render_execution_steps",
            )

        output: dict[str, Any] = {
            "action": runner_action,
            "target": target if runner_action not in {"goto", "assert_url", "login"} else (target or ""),
            "selector": selector if runner_action not in {"goto", "assert_url", "login"} else (selector or ""),
            "locator_type": locator_type if runner_action not in {"goto", "assert_url", "login"} else (locator_type or ""),
            "role": role if runner_action not in {"goto", "assert_url", "login"} else (role or ""),
            "intent_id": intent_id,
            "confidence": confidence,
            "traceability": {
                "status": "resolved",
                "compiler_status": "resolved",
                "execution_status": "ready",
                "confidence": confidence,
                "reason": compiler_reason,
                "source_point_index": int(meta.get("source_point_index", -1)),
                "source_step_index": int(meta.get("source_step_index", -1)),
                "raw_text": _normalized_text(meta.get("raw_text")),
            },
        }
        if runner_action == "fill":
            if step.get("value") is None:
                raise ExecutionCompilerError(
                    code="execution_render_failed",
                    message="fill step missing value",
                    reason=f"step {index} missing fill value",
                    stage="render_execution_steps",
                )
            output["value"] = step.get("value")
        elif runner_action == "goto":
            output["target"] = ""
            output["selector"] = ""
            output["locator_type"] = ""
            output["role"] = ""
            if step.get("value") in {"", None}:
                raise ExecutionCompilerError(
                    code="execution_render_failed",
                    message="navigation step missing route",
                    reason=f"step {index} missing navigation route",
                    stage="render_execution_steps",
                )
            output["value"] = step.get("value")
        elif runner_action == "assert_url":
            output["target"] = ""
            output["selector"] = ""
            output["locator_type"] = ""
            output["role"] = ""
            if step.get("value") in {"", None}:
                raise ExecutionCompilerError(
                    code="execution_render_failed",
                    message="assert url step missing value",
                    reason=f"step {index} missing assert url",
                    stage="render_execution_steps",
                )
            output["value"] = step.get("value")
        elif runner_action == "assert_text":
            output["value"] = step.get("value") if step.get("value") is not None else ""
        elif runner_action == "assert_visible":
            output["value"] = step.get("value") if step.get("value") not in {"", None} else None
        elif runner_action == "login":
            output["target"] = ""
            output["selector"] = ""
            output["locator_type"] = ""
            output["role"] = ""

        output["confidence"] = float(output["traceability"]["confidence"])
        rendered.append(output)
    return rendered


def compile_execution_steps(
    test_points: list[dict[str, Any]],
    page_object: dict[str, Any],
) -> list[dict[str, Any]]:
    """Compile test points into executable steps."""
    normalized_points = normalize_test_points(test_points)
    actions = normalize_test_points_to_actions(normalized_points)
    ir = build_execution_ir(actions)
    bound_ir = bind_targets(ir, page_object)
    rendered = render_execution_steps(bound_ir)
    if not rendered:
        raise ExecutionCompilerError(
            code="execution_render_failed",
            message="rendered steps must not be empty",
            reason="rendered steps empty",
            stage="compile_execution_steps",
        )
    return rendered


# Deprecated: use ExecutionCompilerError directly. Kept for backward compatibility.
ExecutionCompileError = ExecutionCompilerError


_PAGE_ALIAS_MAP = {
    "addprouct": "addproduct",
    "add-product": "addproduct",
}
_PAGE_FRIENDLY_NAME = {
    "product": "商品列表",
    "addproduct": "添加商品",
    "order": "订单列表",
    "returnapply": "退货申请",
}


def _dedup_keep_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered


def _normalize_page_slug(value: str) -> str:
    normalized = "".join(ch for ch in str(value).strip().lower() if ch.isalnum() or ch in {"-", "_"})
    normalized = _PAGE_ALIAS_MAP.get(normalized, normalized)
    return normalized or "product"


def _dict_value(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list_value(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _has_multisource_inputs(
    *,
    input_sources: list[dict[str, Any]],
    openapi_spec: dict[str, Any],
    prd_text: str,
    prd_url: str,
    user_story: str,
    git_diff: str,
    git_diff_path: str,
    openapi_url: str,
    defect_ticket: str,
    runtime_logs: str,
) -> bool:
    return any(
        [
            bool(input_sources),
            bool(openapi_spec),
            bool(str(prd_text).strip()),
            bool(str(prd_url).strip()),
            bool(str(user_story).strip()),
            bool(str(git_diff).strip()),
            bool(str(git_diff_path).strip()),
            bool(str(openapi_url).strip()),
            bool(str(defect_ticket).strip()),
            bool(str(runtime_logs).strip()),
        ]
    )


def _build_system_requirement(*, page: str, page_url: str = "", has_multisource_inputs: bool = False) -> str:
    normalized_page = _normalize_page_slug(page) if str(page).strip() else ""
    if has_multisource_inputs:
        return "多输入源需求驱动的页面核心流程验证"
    page_label = _PAGE_FRIENDLY_NAME.get(normalized_page, normalized_page or "目标页面")
    route_label = str(page_url or "").strip()
    if route_label:
        return f"自动生成的页面测试目标：验证 {page_label} 页面可访问、关键区域可见、核心基础交互可执行。目标 URL：{route_label}"
    return f"自动生成的页面测试目标：验证 {page_label} 页面可访问、关键区域可见、核心基础交互可执行。"


def _extract_quality_gate(payload: Any) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    direct = payload.get("quality_gate")
    if isinstance(direct, dict):
        return direct
    details = payload.get("details")
    if isinstance(details, dict):
        nested = details.get("quality_gate")
        if isinstance(nested, dict):
            return nested
    error = payload.get("error")
    if isinstance(error, dict):
        nested = _extract_quality_gate(error)
        if isinstance(nested, dict):
            return nested
    return None


def _is_quality_gate_blocked(payload: Any) -> tuple[bool, dict[str, Any] | None]:
    gate = _extract_quality_gate(payload)
    if not isinstance(gate, dict):
        return False, None
    decision = str(gate.get("decision", "")).strip().lower()
    if decision == "block":
        return True, gate
    blockers = gate.get("blockers")
    if isinstance(blockers, list) and len(blockers) > 0:
        return True, gate
    return False, gate


def _render_requirement_spec_markdown(requirement_spec: dict[str, Any]) -> str:
    spec = requirement_spec if isinstance(requirement_spec, dict) else {}
    page = str(spec.get("page", "")).strip() or "-"
    priority = str(spec.get("priority", "")).strip() or "P1"
    parse_confidence = spec.get("parse_confidence", 0)
    test_intents: list[Any] = _list_value(spec.get("test_intents"))
    ambiguities: list[Any] = _list_value(spec.get("ambiguities"))
    business_rules: list[Any] = _list_value(spec.get("business_rules"))
    quality_gate = _dict_value(spec.get("quality_gate"))
    lines = [
        "# 需求测试点分析",
        "",
        f"- 页面: `{page}`",
        f"- 优先级: `{priority}`",
        f"- 解析置信度: `{parse_confidence}`",
        f"- 测试点数量: `{len(test_intents)}`",
        f"- 规则数量: `{len(business_rules)}`",
        f"- 消歧数量: `{len(ambiguities)}`",
    ]
    if quality_gate:
        blockers = _list_value(quality_gate.get("blockers"))
        lines.extend(
            [
                "",
                "## 质量门禁",
                f"- 决策: `{str(quality_gate.get('decision', '')).strip() or '-'}`",
                f"- 阶段: `{str(quality_gate.get('stage', '')).strip() or '-'}`",
                f"- 阻断项数量: `{len(blockers)}`",
            ]
        )
    if test_intents:
        lines.extend(["", "## 测试点"])
        for index, intent in enumerate(test_intents[:20], start=1):
            if not isinstance(intent, dict):
                continue
            lines.append(
                f"{index}. [{str(intent.get('priority', 'P1')).strip() or 'P1'}/{str(intent.get('intent_type', 'functional')).strip() or 'functional'}] {str(intent.get('title', '')).strip() or f'intent-{index:02d}'}"
            )
    return "\n".join(lines).strip() + "\n"


class PreviewTestPointsCompiler:
    """DEPRECATED: Use run_preview_pipeline from preview_pipeline.py instead.

    This class is kept for backward compatibility. New code should use
    the canonical preview path: build_preview_response -> run_preview_pipeline.
    """

    def __init__(self, *, orchestrator_client: Any) -> None:
        import warnings
        warnings.warn(
            "PreviewTestPointsCompiler is deprecated; use run_preview_pipeline instead",
            DeprecationWarning,
            stacklevel=2,
        )
        self._orchestrator_client = orchestrator_client

    def _resolve_effective_requirement(self, *, requirement_text: str, normalized_page: str, multisource_enabled: bool) -> str:
        requirement = str(requirement_text or "").strip()
        if requirement:
            return requirement
        return _build_system_requirement(page=normalized_page, has_multisource_inputs=multisource_enabled)

    def compile_preview(self, payload: Any) -> dict[str, Any]:
        from shared_backend.mapping_engine import build_preview_payload

        request = build_preview_payload(payload)
        requirement_text = str(request.get("requirement", "")).strip()
        page = str(request.get("page", "")).strip()
        normalized_page = _normalize_page_slug(page) if page else ""
        if not normalized_page:
            raise ExecutionCompilerError(
                code="preview_missing_page",
                message="page must not be empty",
                reason="page is empty after normalization",
                stage="compile_preview",
            )

        input_sources = [item for item in _list_value(request.get("input_sources")) if isinstance(item, dict)]
        openapi_spec = _dict_value(request.get("openapi_spec"))
        multisource_enabled = _has_multisource_inputs(
            input_sources=input_sources,
            openapi_spec=openapi_spec,
            prd_text=request.get("prd_text", ""),
            prd_url=request.get("prd_url", ""),
            user_story=request.get("user_story", ""),
            git_diff=request.get("git_diff", ""),
            git_diff_path=request.get("git_diff_path", ""),
            openapi_url=request.get("openapi_url", ""),
            defect_ticket=request.get("defect_ticket", ""),
            runtime_logs=request.get("runtime_logs", ""),
        )
        effective_requirement = self._resolve_effective_requirement(
            requirement_text=requirement_text,
            normalized_page=normalized_page,
            multisource_enabled=multisource_enabled,
        )
        if not effective_requirement and not multisource_enabled and not normalized_page:
            raise ExecutionCompilerError(
                code="preview_missing_requirement",
                message="requirement must not be empty when no page or additional input sources are provided",
                reason="missing requirement without multisource inputs",
                stage="compile_preview",
            )

        parse_result = self._orchestrator_client.parse(
            requirement=effective_requirement,
            page=normalized_page,
            source=str(request.get("source", "")).strip() or "manual",
            input_sources=input_sources,
            openapi_spec=openapi_spec,
            prd_text=request.get("prd_text", ""),
            prd_url=request.get("prd_url", ""),
            user_story=request.get("user_story", ""),
            git_diff=request.get("git_diff", ""),
            git_diff_path=request.get("git_diff_path", ""),
            openapi_url=request.get("openapi_url", ""),
            defect_ticket=request.get("defect_ticket", ""),
            runtime_logs=request.get("runtime_logs", ""),
        )
        if not isinstance(parse_result, dict):
            parse_result = {}

        requirement_spec = parse_result.get("requirement_spec")
        if not isinstance(requirement_spec, dict):
            requirement_spec = parse_result
        if not isinstance(requirement_spec, dict):
            requirement_spec = {}

        requirement_analysis_markdown = str(parse_result.get("requirement_analysis_markdown", "")).strip()
        if not requirement_analysis_markdown:
            requirement_analysis_markdown = _render_requirement_spec_markdown(requirement_spec)

        quality_gate = _extract_quality_gate(requirement_spec)
        test_intents = _list_value(requirement_spec.get("test_intents"))
        ambiguities = _list_value(requirement_spec.get("ambiguities"))
        business_rules = _list_value(requirement_spec.get("business_rules"))
        parser_runtime = _dict_value(requirement_spec.get("parser_runtime"))
        source_summary = _dict_value(parser_runtime.get("source_summary"))
        source_inputs = _list_value(requirement_spec.get("source_inputs"))
        source_count = int(
            source_summary.get(
                "source_count",
                parser_runtime.get("source_count", len(source_inputs)),
            )
            or 0
        )
        source_types = _list_value(source_summary.get("source_types"))
        if not source_types:
            source_types = [
                str(item.get("source_type", "")).strip()
                for item in source_inputs
                if isinstance(item, dict) and str(item.get("source_type", "")).strip()
            ]
        deduped_source_types = _dedup_keep_order([str(item).strip() for item in source_types if str(item).strip()])
        change_impact = _dict_value(requirement_spec.get("change_impact"))

        intent_type_distribution: dict[str, int] = {}
        for item in test_intents:
            if not isinstance(item, dict):
                continue
            intent_type = str(item.get("intent_type", "unknown")).strip() or "unknown"
            intent_type_distribution[intent_type] = intent_type_distribution.get(intent_type, 0) + 1

        item = {
            "page": str(requirement_spec.get("page", "")).strip() or normalized_page,
            "priority": str(requirement_spec.get("priority", "")).strip() or "P1",
            "parse_confidence": requirement_spec.get("parse_confidence", 0),
            "intent_count": len(test_intents),
            "intent_type_distribution": intent_type_distribution,
            "ambiguity_count": len(ambiguities),
            "rule_count": len(business_rules),
            "source_count": source_count,
            "source_types": deduped_source_types,
            "change_impact": {
                "impact_score": change_impact.get("impact_score", 0),
                "changed_areas": _list_value(change_impact.get("changed_areas")),
                "risk_signal_count": len(_list_value(change_impact.get("risk_signals"))),
                "top_factor": _dict_value(change_impact.get("top_factor")),
                "recommended_regression_scope": _list_value(change_impact.get("recommended_regression_scope")),
            },
            "quality_gate": quality_gate,
            "requirement_spec": requirement_spec,
            "requirement_analysis_markdown": requirement_analysis_markdown,
            "output_contract": {
                "machine_schema": "RequirementSpecV1",
                "human_render": "RequirementAnalysisMarkdownV1",
                "rendered_by": "web-ui-service",
            },
        }
        return {"item": item}


def compile_playwright_python(ir: dict[str, Any], page_object: dict[str, Any]) -> str:
    from shared_backend.mapping_engine import map_ir_to_selectors

    mapped = map_ir_to_selectors(ir, page_object, preserve_target=True)
    steps = mapped.get("steps")
    if not isinstance(steps, list):
        raise ExecutionCompileError(
            code="execution_compile_invalid_steps",
            message="mapped ir steps is invalid",
            reason="mapped ir does not contain valid steps array",
            stage="compile_playwright_python",
        )
    lines = [
        "from playwright.sync_api import Page, expect",
        "",
        "def run_case(page: Page) -> None:",
    ]
    if not steps:
        lines.append("    return")
        return "\n".join(lines) + "\n"

    for step in steps:
        if not isinstance(step, dict):
            continue
        action = str(step.get("action", "")).strip()
        selector = str(step.get("selector", "")).strip()
        value = step.get("value")
        if not action or not selector:
            raise ExecutionCompileError(
                code="execution_compile_missing_action_or_selector",
                message="mapped step requires action and selector",
                reason="action/selector missing in mapped step",
                stage="compile_playwright_python",
            )
        escaped_selector = selector.replace("\\", "\\\\").replace("'", "\\'")
        if action == "fill":
            escaped_value = str(value if value is not None else "").replace("\\", "\\\\").replace("'", "\\'")
            lines.append(f"    page.locator('{escaped_selector}').fill('{escaped_value}')")
        elif action == "click":
            lines.append(f"    page.locator('{escaped_selector}').click()")
        elif action == "wait_for":
            lines.append(f"    expect(page.locator('{escaped_selector}')).to_be_visible()")
        elif action == "assert_visible":
            lines.append(f"    expect(page.locator('{escaped_selector}')).to_be_visible()")
        elif action == "assert_text":
            escaped_value = str(value if value is not None else "").replace("\\", "\\\\").replace("'", "\\'")
            lines.append(f"    expect(page.locator('{escaped_selector}')).to_have_text('{escaped_value}')")
        else:
            raise ExecutionCompileError(
                code="execution_compile_unsupported_action",
                message="unsupported action for playwright compiler",
                reason=f"unsupported action: {action}",
                stage="compile_playwright_python",
            )
    return "\n".join(lines) + "\n"
