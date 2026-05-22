"""ContractValidator — inter-layer schema and field consistency checks.

This module implements verification points V1, V3, V4, and V5 from the rectification plan:
- V1: RequirementSpec structure validation (L2 exit)
- V3: ExecutionDraft structure + element_code validation (L3 exit)
- V4: Field completeness validation after normalization
- V5: Cross-layer contract consistency (intent coverage, element resolution, dedup)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from .models import ALLOWED_ACTIONS

_LOGGER = logging.getLogger(__name__)

ACTIONS_REQUIRING_TARGET: frozenset[str] = frozenset({
    "click", "fill", "select", "check", "uncheck",
    "hover", "scroll", "upload", "drag", "focus", "blur", "clear",
    "assert_visible", "assert_text", "assert_value",
    "assert_hidden", "assert_enabled", "assert_disabled",
    "assert_count", "assert_metric",
})


@dataclass
class ValidationResult:
    """契约校验结果，可合并多条 errors/warnings。"""
    valid: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def add_error(self, msg: str) -> None:
        self.errors.append(msg)
        self.valid = False

    def add_warning(self, msg: str) -> None:
        self.warnings.append(msg)

    def merge(self, other: "ValidationResult") -> None:
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)
        if not other.valid:
            self.valid = False


class ContractValidator:
    """Validates contracts between pipeline layers."""

    # ------------------------------------------------------------------
    # V1: RequirementSpec structure validation (L2 exit)
    # ------------------------------------------------------------------

    def validate_requirement_spec(
        self,
        spec: dict[str, Any],
    ) -> ValidationResult:
        """V1: Validate RequirementSpec structure at the L2 parser exit."""
        result = ValidationResult()
        if not isinstance(spec, dict):
            result.add_error("requirement_spec must be a dict")
            return result

        page = str(spec.get("page", "")).strip()
        if not page:
            result.add_error("requirement_spec.page is empty")

        intents = spec.get("test_intents")
        if not isinstance(intents, list):
            result.add_error("requirement_spec.test_intents must be a list")
        else:
            if not intents:
                result.add_error("requirement_spec.test_intents is empty")
            seen_ids: set[str] = set()
            for idx, intent in enumerate(intents):
                if not isinstance(intent, dict):
                    result.add_error(f"test_intents[{idx}] is not a dict")
                    continue
                iid = str(intent.get("intent_id", "")).strip()
                if not iid:
                    result.add_error(f"test_intents[{idx}] missing intent_id")
                elif iid in seen_ids:
                    result.add_error(f"test_intents[{idx}] duplicate intent_id '{iid}'")
                else:
                    seen_ids.add(iid)
                title = str(intent.get("title", "")).strip()
                if not title:
                    result.add_error(f"test_intents[{idx}] missing title")

        confidence = spec.get("parse_confidence")
        if confidence is not None:
            try:
                conf_val = float(confidence)
                if conf_val < 0.0 or conf_val > 1.0:
                    result.add_warning("parse_confidence outside [0.0, 1.0]; will be clamped")
            except (TypeError, ValueError):
                result.add_warning("parse_confidence is not a number")

        from .models import VALID_SOURCE_TYPES
        source_type = str(spec.get("source_type", "")).strip().lower()
        if source_type and source_type not in VALID_SOURCE_TYPES:
            result.add_warning(f"source_type '{source_type}' not in recognized set; defaulting to manual")

        return result

    # ------------------------------------------------------------------
    # V3: ExecutionDraft structure validation (L3 exit)
    # ------------------------------------------------------------------

    def validate_execution_draft(
        self,
        draft: dict[str, Any],
        *,
        element_codes: set[str] | None = None,
    ) -> ValidationResult:
        """V3: Validate ExecutionDraft structure and element_code resolvability at the L3 exit."""
        result = ValidationResult()
        if not isinstance(draft, dict):
            result.add_error("execution draft must be a dict")
            return result

        case = draft.get("case") if isinstance(draft.get("case"), dict) else draft
        execution = case.get("execution") if isinstance(case.get("execution"), dict) else {}

        steps = execution.get("steps")
        if not isinstance(steps, list) or not steps:
            result.add_error("execution.steps is empty or missing")
            return result

        for idx, step in enumerate(steps):
            if not isinstance(step, dict):
                result.add_error(f"steps[{idx}] is not a dict")
                continue
            action = str(step.get("action", "")).strip()
            if not action:
                result.add_error(f"steps[{idx}] missing action")
            elif action not in ALLOWED_ACTIONS:
                result.add_warning(f"steps[{idx}] action '{action}' not in allowed set")

            target = str(step.get("target", "")).strip()
            if action in ACTIONS_REQUIRING_TARGET and not target:
                result.add_warning(f"steps[{idx}] action '{action}' has no target")

            if target and element_codes is not None and target not in element_codes:
                result.add_error(f"steps[{idx}] target '{target}' not resolvable in page object")

        return result

    # ------------------------------------------------------------------
    # V4: Field completeness validation (L4 Normalizer exit)
    # ------------------------------------------------------------------

    def validate_normalized_test_points(
        self,
        points: list[dict[str, Any]],
        *,
        strict: bool = False,
    ) -> ValidationResult:
        """V4: Field completeness validation on normalized test point list."""
        result = ValidationResult()
        if not isinstance(points, list):
            result.add_error("points must be a list")
            return result

        seen_intent_step_pairs: set[tuple[str, int]] = set()

        for idx, point in enumerate(points):
            if not isinstance(point, dict):
                result.add_error(f"points[{idx}] is not a dict")
                continue

            intent_id = str(point.get("intent_id") or "").strip()
            if not intent_id:
                if strict:
                    result.add_error(f"points[{idx}] missing intent_id")
                else:
                    result.add_warning(f"points[{idx}] missing intent_id")

            action = str(point.get("action", "")).strip().lower()
            point_type = str(point.get("point_type", "")).strip().lower()
            steps = point.get("steps")
            has_steps = isinstance(steps, list) and bool(steps)
            if not action and not has_steps:
                if strict:
                    result.add_error(f"points[{idx}] has neither action nor steps")
                else:
                    result.add_warning(f"points[{idx}] has neither action nor steps")

            involved = point.get("involved_elements")
            involved_list = involved if isinstance(involved, list) else []
            if not involved_list:
                if strict and action not in {"login", "goto", "assert_url"}:
                    result.add_error(f"points[{idx}] has no involved_elements")
                else:
                    result.add_warning(f"points[{idx}] has no involved_elements")

            expected_result = str(point.get("expected_result") or "").strip()
            expected_required = point_type != "precondition" and action not in {"login"}
            if expected_required and not expected_result:
                if strict:
                    result.add_error(f"points[{idx}] missing expected_result")
                else:
                    result.add_warning(f"points[{idx}] missing expected_result")

            if action and action in ACTIONS_REQUIRING_TARGET:
                target = str(point.get("target", "")).strip()
                if not target and not has_steps:
                    if strict:
                        result.add_error(f"points[{idx}] action '{action}' requires target or steps")
                    else:
                        result.add_warning(f"points[{idx}] action '{action}' usually requires a target")

            if action == "noop":
                result.add_warning(f"points[{idx}] has noop action")

            step_index = point.get("step_index", idx)
            pair = (intent_id, step_index)
            if pair in seen_intent_step_pairs and intent_id:
                result.add_error(f"points[{idx}] duplicate intent_id+step_index: {pair}")
            seen_intent_step_pairs.add(pair)

        return result

    def validate_intent_coverage(
        self,
        requirement_spec: dict[str, Any],
        normalized_points: list[dict[str, Any]],
        *,
        strict: bool = False,
    ) -> ValidationResult:
        """V5a: Check that all test_intents have corresponding points and vice versa."""
        result = ValidationResult()

        intents = requirement_spec.get("test_intents")
        if not isinstance(intents, list):
            result.add_warning("requirement_spec has no test_intents list")
            return result

        spec_intent_ids: set[str] = set()
        for intent in intents:
            if isinstance(intent, dict):
                iid = str(intent.get("intent_id", "")).strip()
                if iid:
                    spec_intent_ids.add(iid)

        point_intent_ids: set[str] = set()
        for point in normalized_points:
            if isinstance(point, dict):
                point_type = str(point.get("point_type", "")).strip().lower()
                action = str(point.get("action", "")).strip().lower()
                if point_type == "precondition" or action == "login":
                    continue
                iid = str(point.get("intent_id") or "").strip()
                if iid:
                    point_intent_ids.add(iid)

        orphan_points = point_intent_ids - spec_intent_ids
        for oid in sorted(orphan_points):
            message = f"point intent_id '{oid}' not found in requirement_spec.test_intents"
            if strict:
                result.add_error(message)
            else:
                result.add_warning(message)

        uncovered_intents = spec_intent_ids - point_intent_ids
        for uid in sorted(uncovered_intents):
            message = f"requirement_spec intent '{uid}' has no corresponding test point"
            if strict:
                result.add_error(message)
            else:
                result.add_warning(message)

        return result

    def validate_element_resolution(
        self,
        normalized_points: list[dict[str, Any]],
        page_object: dict[str, Any],
        *,
        strict: bool = False,
    ) -> ValidationResult:
        """V5b: Check that targets referenced in points exist in the page object."""
        result = ValidationResult()
        elements = page_object.get("elements") if isinstance(page_object, dict) else {}
        if not isinstance(elements, dict):
            elements = {}
        known_codes = set(elements.keys())

        for idx, point in enumerate(normalized_points):
            if not isinstance(point, dict):
                continue
            action = str(point.get("action", "")).strip().lower()
            target = str(point.get("target", "")).strip()
            if target and target not in known_codes:
                msg = f"points[{idx}] target '{target}' not in page object elements"
                if strict:
                    result.add_error(msg)
                else:
                    result.add_warning(msg)

            involved = point.get("involved_elements") or []
            for elem in involved:
                if elem and elem not in known_codes:
                    msg = f"points[{idx}] involved element '{elem}' not in page object"
                    if strict and action not in {"login", "goto", "assert_url"}:
                        result.add_error(msg)
                    else:
                        result.add_warning(msg)

        return result

    def validate_full(
        self,
        requirement_spec: dict[str, Any] | None,
        normalized_points: list[dict[str, Any]],
        page_object: dict[str, Any] | None = None,
        *,
        strict: bool = False,
    ) -> ValidationResult:
        """Run all validation checks and return combined result."""
        result = self.validate_normalized_test_points(normalized_points, strict=strict)

        if requirement_spec is not None:
            intent_result = self.validate_intent_coverage(requirement_spec, normalized_points, strict=strict)
            result.merge(intent_result)

        if page_object is not None:
            element_result = self.validate_element_resolution(
                normalized_points, page_object, strict=strict
            )
            result.merge(element_result)

        return result
