from __future__ import annotations

from typing import Any, Mapping


class IRSchemaValidationError(ValueError):
    def __init__(self, code: str, message: str, *, detail: Mapping[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = str(code).strip() or "ir_schema_validation_error"
        self.detail = dict(detail or {})

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"code": self.code, "message": str(self)}
        if self.detail:
            payload["detail"] = self.detail
        return payload


class IRSchemaValidator:
    def __init__(self, *, allowed_actions: set[str] | None = None) -> None:
        default_actions = {"fill", "click", "wait_for", "assert_visible", "assert_text", "assert_metric"}
        self.allowed_actions = set(allowed_actions) if isinstance(allowed_actions, set) and allowed_actions else default_actions

    def validate_ir(self, ir: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(ir, Mapping):
            raise IRSchemaValidationError("invalid_ir", "ir must be an object")
        raw_steps = ir.get("steps")
        if not isinstance(raw_steps, list):
            raise IRSchemaValidationError("steps_missing", "ir.steps must be an array")
        validated_steps = [self.validate_step(step, index=index) for index, step in enumerate(raw_steps)]
        normalized = dict(ir)
        normalized["steps"] = validated_steps
        return normalized

    def validate_step(self, step: Mapping[str, Any], *, index: int | None = None) -> dict[str, Any]:
        if not isinstance(step, Mapping):
            raise IRSchemaValidationError("invalid_step", "step must be an object", detail={"index": index})
        action = str(step.get("action", "") or "").strip()
        target = str(step.get("target", "") or "").strip()
        missing_fields: list[str] = []
        if not action:
            missing_fields.append("action")
        if not target:
            missing_fields.append("target")
        if missing_fields:
            raise IRSchemaValidationError(
                "step_missing_fields",
                f"step missing required fields: {', '.join(missing_fields)}",
                detail={"index": index, "missing_fields": missing_fields},
            )
        if action not in self.allowed_actions:
            raise IRSchemaValidationError(
                "unsupported_action",
                f"action `{action}` is not allowed",
                detail={"index": index, "action": action, "allowed_actions": sorted(self.allowed_actions)},
            )
        normalized = dict(step)
        normalized["action"] = action
        normalized["target"] = target
        return normalized
