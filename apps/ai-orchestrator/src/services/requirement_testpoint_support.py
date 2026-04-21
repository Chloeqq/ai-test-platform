# mypy: ignore-errors

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

_logger = logging.getLogger(__name__)


def _fetch_page_element_codes(page: str, project: str = "atp", client: str = "web") -> list[str] | None:
    """Fetch element codes from DB for PO Store validation. Returns None on failure."""
    try:
        from sqlalchemy import select

        from app.core.database import SessionLocal
        from app.models.page_object import PageElement, PageObject

        db = SessionLocal()
        try:
            page_obj = db.execute(
                select(PageObject).where(
                    PageObject.project_code == project,
                    PageObject.client == client,
                    PageObject.page_code == page,
                )
            ).scalar_one_or_none()
            if page_obj is None:
                return None
            elements = db.execute(
                select(PageElement.element_code).where(PageElement.page_object_id == page_obj.id)
            ).scalars().all()
            return list(elements)
        finally:
            db.close()
    except Exception:
        _logger.debug("PO Store lookup failed for %s", page, exc_info=True)
        return None


def _validate_raw_points_against_contract(points: list[dict[str, Any]]) -> None:
    """Validate freshly built point dicts against the shared TestPointV1 model.

    Logs warnings for any points that don't conform but does not raise,
    to avoid blocking the pipeline for non-critical schema mismatches.
    """
    try:
        from shared_backend.schemas.models import TestPointV1
    except ImportError:
        return
    for idx, raw in enumerate(points):
        try:
            TestPointV1.model_validate(raw)
        except Exception as exc:
            _logger.warning("point[%d] does not conform to TestPointV1: %s", idx, exc)


class RequirementTestPointSupport:
    def __init__(
        self,
        *,
        now,
        normalize_test_point_plan,
        build_test_point_traceability_summary,
        agent_root: Path,
        requirement_quality_gate_enabled: bool,
        requirement_min_parse_confidence: float,
        requirement_min_test_intents: int,
        requirement_block_high_ambiguity: bool,
        requirement_max_coverage_gap_ratio: float,
        blocker_catalog: dict[str, dict[str, str]],
    ) -> None:
        self._now = now
        self._normalize_test_point_plan = normalize_test_point_plan
        self._build_test_point_traceability_summary = build_test_point_traceability_summary
        self._agent_root = agent_root
        self._requirement_quality_gate_enabled = requirement_quality_gate_enabled
        self._requirement_min_parse_confidence = requirement_min_parse_confidence
        self._requirement_min_test_intents = requirement_min_test_intents
        self._requirement_block_high_ambiguity = requirement_block_high_ambiguity
        self._requirement_max_coverage_gap_ratio = requirement_max_coverage_gap_ratio
        self._blocker_catalog = blocker_catalog

    _SOURCE_TYPE_THRESHOLDS: dict[str, dict[str, float]] = {
        "prd_text": {"min_test_intents": 3, "min_parse_confidence": 0.6, "max_coverage_gap_ratio": 0.5},
        "openapi_spec": {"min_test_intents": 1, "min_parse_confidence": 0.4, "max_coverage_gap_ratio": 0.8},
        "git_diff": {"min_test_intents": 1, "min_parse_confidence": 0.3, "max_coverage_gap_ratio": 0.8},
        "user_story": {"min_test_intents": 2, "min_parse_confidence": 0.5, "max_coverage_gap_ratio": 0.6},
        "defect_ticket": {"min_test_intents": 1, "min_parse_confidence": 0.4, "max_coverage_gap_ratio": 0.8},
        "mixed": {"min_test_intents": 2, "min_parse_confidence": 0.5, "max_coverage_gap_ratio": 0.6},
    }

    def _resolve_gate_thresholds(self, source_type: str) -> dict[str, float]:
        overrides = self._SOURCE_TYPE_THRESHOLDS.get(source_type, {})
        return {
            "min_test_intents": overrides.get("min_test_intents", self._requirement_min_test_intents),
            "min_parse_confidence": overrides.get("min_parse_confidence", self._requirement_min_parse_confidence),
            "max_coverage_gap_ratio": overrides.get("max_coverage_gap_ratio", self._requirement_max_coverage_gap_ratio),
        }

    def build_requirement_quality_gate(self, requirement_spec: dict[str, Any], *, stage: str) -> dict[str, Any]:
        intents = requirement_spec.get("test_intents")
        intent_list = intents if isinstance(intents, list) else []
        ambiguities = requirement_spec.get("ambiguities")
        ambiguity_list = ambiguities if isinstance(ambiguities, list) else []
        coverage_matrix = requirement_spec.get("coverage_matrix")
        coverage_list = coverage_matrix if isinstance(coverage_matrix, list) else []

        source_type = str(requirement_spec.get("source_type", "manual")).strip().lower()
        thresholds = self._resolve_gate_thresholds(source_type)
        effective_min_intents = max(1, int(thresholds["min_test_intents"]))
        effective_min_confidence = float(thresholds["min_parse_confidence"])
        effective_max_gap_ratio = float(thresholds["max_coverage_gap_ratio"])

        high_ambiguity_count = 0
        medium_ambiguity_count = 0
        for item in ambiguity_list:
            if not isinstance(item, dict):
                continue
            severity = str(item.get("severity", "medium")).strip().lower()
            if severity in {"high", "critical"}:
                high_ambiguity_count += 1
            elif severity == "medium":
                medium_ambiguity_count += 1

        coverage_gap_count = 0
        for row in coverage_list:
            if not isinstance(row, dict):
                continue
            intent_ids = row.get("intent_ids")
            traceability = str(row.get("traceability_status", "")).strip().lower()
            has_links = isinstance(intent_ids, list) and bool(intent_ids)
            if traceability == "gap" or not has_links:
                coverage_gap_count += 1
        coverage_gap_ratio = (
            round(coverage_gap_count / max(1, len(coverage_list)), 2)
            if coverage_list
            else (1.0 if not intent_list else 0.0)
        )

        parse_confidence = requirement_spec.get("parse_confidence", 0.0)
        try:
            parse_confidence_value = float(parse_confidence)
        except Exception:
            parse_confidence_value = 0.0

        has_design_input = bool(str(requirement_spec.get("design_input", "")).strip())
        has_page = bool(str(requirement_spec.get("page", "")).strip())

        blockers: list[dict[str, Any]] = []
        min_test_intents = effective_min_intents
        if len(intent_list) < min_test_intents:
            blockers.append(
                self.build_requirement_quality_blocker(
                    code="insufficient_test_intents",
                    message=f"test_intents below threshold: {len(intent_list)} < {min_test_intents}",
                    value=len(intent_list),
                    threshold=min_test_intents,
                )
            )
        if parse_confidence_value < effective_min_confidence:
            blockers.append(
                self.build_requirement_quality_blocker(
                    code="low_parse_confidence",
                    message=f"parse_confidence below threshold: {round(parse_confidence_value, 2)} < {effective_min_confidence}",
                    value=round(parse_confidence_value, 2),
                    threshold=effective_min_confidence,
                )
            )
        if self._requirement_block_high_ambiguity and high_ambiguity_count > 0:
            blockers.append(
                self.build_requirement_quality_blocker(
                    code="high_ambiguity_present",
                    message=f"high ambiguity present: {high_ambiguity_count}",
                    value=high_ambiguity_count,
                    threshold=0,
                )
            )
        if coverage_gap_ratio > effective_max_gap_ratio:
            blockers.append(
                self.build_requirement_quality_blocker(
                    code="coverage_gap_ratio_high",
                    message=f"coverage_gap_ratio above threshold: {coverage_gap_ratio} > {effective_max_gap_ratio}",
                    value=coverage_gap_ratio,
                    threshold=effective_max_gap_ratio,
                )
            )
        if not has_design_input:
            blockers.append(
                self.build_requirement_quality_blocker(
                    code="missing_design_input",
                    message="design_input is empty",
                    value=has_design_input,
                    threshold=True,
                )
            )
        if not has_page:
            blockers.append(
                self.build_requirement_quality_blocker(
                    code="missing_page_resolution",
                    message="page is empty",
                    value=has_page,
                    threshold=True,
                )
            )

        return {
            "version": "RequirementQualityGateV1",
            "stage": stage,
            "gate_enabled": bool(self._requirement_quality_gate_enabled),
            "decision": "block" if blockers else "allow",
            "explanation": (
                "blocked because blockers were detected"
                if blockers
                else "allow because parse confidence and traceability satisfy the current thresholds"
            ),
            "blockers": blockers,
            "metrics": {
                "parse_confidence": round(parse_confidence_value, 2),
                "intent_count": len(intent_list),
                "high_ambiguity_count": high_ambiguity_count,
                "medium_ambiguity_count": medium_ambiguity_count,
                "coverage_row_count": len(coverage_list),
                "coverage_gap_count": coverage_gap_count,
                "coverage_gap_ratio": coverage_gap_ratio,
                "has_design_input": has_design_input,
                "has_page": has_page,
                "blocker_codes": [str(item.get("code", "")).strip() for item in blockers if isinstance(item, dict)],
            },
            "thresholds": {
                "min_parse_confidence": effective_min_confidence,
                "min_test_intents": min_test_intents,
                "block_high_ambiguity": bool(self._requirement_block_high_ambiguity),
                "max_coverage_gap_ratio": effective_max_gap_ratio,
                "source_type": source_type,
            },
        }

    def attach_requirement_quality_gate(self, requirement_spec: dict[str, Any], *, stage: str) -> dict[str, Any]:
        gate = self.build_requirement_quality_gate(requirement_spec, stage=stage)
        requirement_spec["quality_gate"] = gate
        return gate

    def build_requirement_quality_blocker(
        self,
        *,
        code: str,
        message: str,
        value: Any = None,
        threshold: Any = None,
    ) -> dict[str, Any]:
        catalog = self._blocker_catalog.get(code, {})
        blocker: dict[str, Any] = {
            "code": code,
            "message": message,
            "category": str(catalog.get("category", "unknown")),
            "severity": str(catalog.get("severity", "medium")),
            "alert_code": str(catalog.get("alert_code", f"REQQG_{code.upper()}")),
            "metric_key": str(catalog.get("metric_key", "")),
        }
        if value is not None:
            blocker["value"] = value
        if threshold is not None:
            blocker["threshold"] = threshold
        return blocker

    def enforce_requirement_quality_gate(self, requirement_spec: dict[str, Any], *, stage: str) -> dict[str, Any]:
        gate = self.attach_requirement_quality_gate(requirement_spec, stage=stage)
        return gate

    @staticmethod
    def merge_case_requirements(raw_requirement: str, requirement_spec: dict[str, Any]) -> list[str]:
        items: list[str] = []
        normalized_raw = str(raw_requirement).strip()
        if normalized_raw:
            items.append(normalized_raw)

        intents = requirement_spec.get("test_intents") or []
        if isinstance(intents, list):
            for intent in intents[:5]:
                if not isinstance(intent, dict):
                    continue
                title = str(intent.get("title", "")).strip()
                priority = str(intent.get("priority", "")).strip()
                if title:
                    items.append(f"[{priority or 'P1'}] {title}" if priority else title)

        normalized_design_input = str(requirement_spec.get("design_input", "")).strip()
        if normalized_design_input and normalized_design_input not in items:
            items.append(normalized_design_input)

        deduped: list[str] = []
        seen: set[str] = set()
        for item in items:
            normalized = str(item).strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            deduped.append(normalized)
        return deduped or ([normalized_raw] if normalized_raw else [])

    def build_test_points_preview(
        self,
        *,
        case: dict[str, Any],
        requirement_spec: dict[str, Any],
    ) -> dict[str, Any]:
        intent_based = self.build_test_points_from_requirement_spec(
            case=case,
            requirement_spec=requirement_spec,
        )
        return self.apply_constraint_summary_to_test_points(intent_based, requirement_spec=requirement_spec)

    def build_test_points_from_requirement_spec(
        self,
        *,
        case: dict[str, Any],
        requirement_spec: dict[str, Any],
    ) -> dict[str, Any]:
        execution = case.get("execution") if isinstance(case.get("execution"), dict) else {}
        page = str(execution.get("page", "")).strip() or str(requirement_spec.get("page", "")).strip() or "product"
        case_id = str(case.get("id", "")).strip()
        requirement = case.get("requirement")
        if isinstance(requirement, str):
            requirement_rows = [requirement]
        elif isinstance(requirement, list):
            requirement_rows = [str(item).strip() for item in requirement if str(item).strip()]
        else:
            requirement_rows = []
        if not requirement_rows:
            requirement_rows = [
                str(requirement_spec.get("raw_requirement", "")).strip()
                or str(requirement_spec.get("design_input", "")).strip()
            ]
            requirement_rows = [row for row in requirement_rows if row]

        intents = requirement_spec.get("test_intents") if isinstance(requirement_spec.get("test_intents"), list) else []
        precondition_id = f"{page}-00"
        points: list[dict[str, Any]] = [
            {
                "key": precondition_id,
                "intent_id": precondition_id,
                "point_type": "precondition",
                "action": "login",
                "description": "Use shared login precondition.",
                "priority": "P0",
                "dependencies": [],
                "source_ids": [],
                "steps": [{"action": "login", "raw_text": "Use shared login precondition."}],
                "involved_elements": [],
                "metadata": {
                    "traceability": {
                        "intent_ids": [precondition_id],
                        "source_ids": [],
                        "origin": "precondition",
                    }
                },
            }
        ]
        page_elements = _fetch_page_element_codes(page)
        if not page_elements:
            raise ValueError(f"page object element_codes not found for page '{page}'")
        for index, intent in enumerate(intents[:80], start=1):
            if not isinstance(intent, dict):
                continue
            title = str(intent.get("title", "")).strip() or f"intent-{index:02d}"
            intent_type = str(intent.get("intent_type", "functional")).strip().lower() or "functional"
            priority = str(intent.get("priority", "P1")).strip() or "P1"
            dependencies = intent.get("dependencies") if isinstance(intent.get("dependencies"), list) else []
            source_ids = intent.get("source_ids") if isinstance(intent.get("source_ids"), list) else []
            action, target, value = self.map_intent_to_step(
                page=page,
                intent_type=intent_type,
                title=title,
                steps_hint=intent.get("steps_hint"),
                page_elements=page_elements,
            )
            intent_id_value = str(intent.get("intent_id", "")).strip()
            if not intent_id_value:
                raise ValueError(f"requirement_spec.test_intents[{index - 1}] missing intent_id")
            if action != "login" and (target is None or not str(target).strip()):
                raise ValueError(
                    f"requirement_spec.test_intents[{index - 1}] unresolved target for action '{action}' on page '{page}'"
                )
            step_entry: dict[str, Any] = {"action": action, "raw_text": title[:200]}
            if target:
                step_entry["target"] = target
            if value is not None:
                step_entry["value"] = value
            involved = [target] if target else []
            point = {
                "key": intent_id_value,
                "intent_id": intent_id_value,
                "point_type": self.map_intent_type_to_point_type(intent_type),
                "action": action,
                "description": title[:200],
                "priority": priority,
                "dependencies": [str(item).strip() for item in dependencies if str(item).strip()],
                "source_ids": [str(item).strip() for item in source_ids if str(item).strip()],
                "steps": [step_entry],
                "involved_elements": involved,
                "metadata": {
                    "traceability": {
                        "intent_ids": [intent_id_value],
                        "source_ids": [str(item).strip() for item in source_ids if str(item).strip()],
                        "origin": "requirement_intent",
                    }
                },
            }
            if target:
                point["target"] = target
            if value is not None:
                point["value"] = value
            points.append(point)

        _validate_raw_points_against_contract(points)

        payload = {
            "version": "TestPointPlanV1",
            "project": "default",
            "case_id": case_id,
            "page": page,
            "source_type": "requirement_intents",
            "requirement": requirement_rows,
            "generated_at": self._now(),
            "points": points,
            "metadata": {
                "build_source": "requirement_spec.test_intents",
                "intent_count": len(intents),
                "point_count": len(points),
                "coverage_matrix": requirement_spec.get("coverage_matrix", []) if isinstance(requirement_spec.get("coverage_matrix"), list) else [],
                "traceability_summary": self._build_test_point_traceability_summary(
                    requirement_spec=requirement_spec,
                    test_points={"points": points},
                ),
            },
        }
        return self._normalize_test_point_plan(payload)

    def apply_constraint_summary_to_test_points(
        self,
        test_points: dict[str, Any],
        *,
        requirement_spec: dict[str, Any],
    ) -> dict[str, Any]:
        normalized = dict(test_points) if isinstance(test_points, dict) else {}
        metadata = normalized.get("metadata") if isinstance(normalized.get("metadata"), dict) else {}
        metadata = dict(metadata)
        review_summary = normalized.get("review_summary") if isinstance(normalized.get("review_summary"), dict) else {}
        review_summary = dict(review_summary)
        points = normalized.get("points") if isinstance(normalized.get("points"), list) else []
        summary = self.build_constraint_technique_summary(requirement_spec=requirement_spec, current_points=points)
        metadata["technique_summary"] = summary
        metadata["field_definition_count"] = int(summary.get("field_definition_count", 0) or 0)
        metadata["parameter_constraint_count"] = int(summary.get("parameter_constraint_count", 0) or 0)
        metadata["coverage_matrix"] = (
            requirement_spec.get("coverage_matrix")
            if isinstance(requirement_spec.get("coverage_matrix"), list)
            else (
                metadata.get("coverage_matrix")
                if isinstance(metadata.get("coverage_matrix"), list)
                else []
            )
        )
        metadata["traceability_summary"] = self._build_test_point_traceability_summary(
            requirement_spec=requirement_spec,
            test_points=normalized,
        )
        review_summary.setdefault("mainline_point_count", len([point for point in points if isinstance(point, dict)]))
        normalized["metadata"] = metadata
        normalized["review_summary"] = review_summary
        return normalized

    def build_constraint_technique_summary(
        self,
        *,
        requirement_spec: dict[str, Any],
        current_points: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        field_definitions = (
            requirement_spec.get("field_definitions")
            if isinstance(requirement_spec.get("field_definitions"), list)
            else []
        )
        parameter_constraints = (
            requirement_spec.get("parameter_constraints")
            if isinstance(requirement_spec.get("parameter_constraints"), list)
            else []
        )
        normalized_items = [item for item in [*field_definitions, *parameter_constraints] if isinstance(item, dict)]
        technique_distribution: dict[str, int] = {}
        api_parameter_count = 0
        field_definition_count = 0
        parameter_constraint_count = 0
        design_only_point_count = 0

        for item in normalized_items[:60]:
            field_type = str(item.get("field_type", "")).strip().lower() or str(item.get("type", "")).strip().lower() or "string"
            constraints = item.get("constraints") if isinstance(item.get("constraints"), dict) else {}
            format_hint = str(item.get("format", constraints.get("format", ""))).strip().lower()
            if field_type == "string" and format_hint in {"date", "date-time", "datetime", "timestamp"}:
                field_type = "datetime" if format_hint in {"date-time", "datetime", "timestamp"} else "date"
            is_parameter = bool(str(item.get("location", "")).strip() or str(item.get("in", "")).strip())
            if is_parameter:
                parameter_constraint_count += 1
                api_parameter_count += 1
            else:
                field_definition_count += 1

            equivalence_count = 0
            boundary_count = 0
            enum_values = (
                item.get("enum")
                if isinstance(item.get("enum"), list)
                else constraints.get("enum")
                if isinstance(constraints.get("enum"), list)
                else []
            )
            if bool(item.get("required", False)):
                equivalence_count += 1
            if enum_values:
                equivalence_count += 2
            if field_type in {"string", "text", "keyword", "search"}:
                if self.safe_int(item.get("min_length", constraints.get("min_length", constraints.get("minLength")))) not in (None, 0):
                    boundary_count += 1
                if self.safe_int(item.get("max_length", constraints.get("max_length", constraints.get("maxLength")))) not in (None, 0):
                    boundary_count += 1
            elif field_type in {"integer", "number", "decimal", "float", "amount", "price", "currency_amount"}:
                if self.safe_float(item.get("min", constraints.get("min", constraints.get("minimum")))) is not None:
                    boundary_count += 1
                if self.safe_float(item.get("max", constraints.get("max", constraints.get("maximum")))) is not None:
                    boundary_count += 1
                if field_type in {"decimal", "float", "amount", "price", "currency_amount"}:
                    equivalence_count += 1
            elif field_type in {"date", "datetime", "timestamp"}:
                boundary_count += 2
                equivalence_count += 1

            if boundary_count:
                technique_distribution["boundary"] = technique_distribution.get("boundary", 0) + boundary_count
                design_only_point_count += boundary_count
            if equivalence_count:
                technique_distribution["equivalence"] = technique_distribution.get("equivalence", 0) + equivalence_count
                design_only_point_count += equivalence_count

        current_mainline_point_count = len([point for point in (current_points or []) if isinstance(point, dict)])
        return {
            "field_definition_count": int(field_definition_count),
            "parameter_constraint_count": int(parameter_constraint_count),
            "api_parameter_count": int(api_parameter_count),
            "mainline_point_count": int(current_mainline_point_count),
            "design_only_point_count": int(design_only_point_count),
            "technique_distribution": dict(sorted(technique_distribution.items())),
            "has_structured_constraints": bool(field_definition_count or parameter_constraint_count),
            "source": "requirement_spec.constraints",
        }

    @staticmethod
    def map_intent_type_to_point_type(intent_type: str) -> str:
        mapping = {
            "functional": "action",
            "negative": "assertion",
            "security": "assertion",
            "compatibility": "assertion",
            "performance": "assertion",
            "regression": "action",
            "api": "api",
        }
        return mapping.get(intent_type, "action")

    @staticmethod
    def safe_int(value: Any) -> int | None:
        try:
            if value in (None, ""):
                return None
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def safe_float(value: Any) -> float | None:
        try:
            if value in (None, ""):
                return None
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _validate_target_against_po(
        target: str | None,
        page_elements: list[str] | None,
    ) -> str | None:
        """Validate a target against the current PO element list."""
        if target is None or page_elements is None or not page_elements:
            return target
        if target in page_elements:
            return target
        raise ValueError(f"target '{target}' not found in PO Store element_codes")

    @staticmethod
    def map_intent_to_step(
        *,
        page: str,
        intent_type: str,
        title: str,
        steps_hint: Any,
        page_elements: list[str] | None = None,
    ) -> tuple[str, str | None, Any]:
        hints = [str(item).strip().lower() for item in (steps_hint if isinstance(steps_hint, list) else []) if str(item).strip()]
        lowered_title = title.lower()
        if any(item == "login" or item == "auth_check" for item in hints) or any(token in lowered_title for token in ["登录", "鉴权", "auth"]):
            return "login", None, None
        if any(item.startswith("open:") for item in hints):
            target = f"{page}_menu"
            target = RequirementTestPointSupport._validate_target_against_po(target, page_elements)
            return "click", target, None
        if any(item.startswith("api:") or item == "api" for item in hints) or intent_type == "api":
            target = f"{page}_list_title"
            target = RequirementTestPointSupport._validate_target_against_po(target, page_elements)
            return "assert_visible", target, None
        if any(item in {"search", "query"} for item in hints) or any(token in lowered_title for token in ["搜索", "查询", "筛选"]):
            target = "search_input"
            target = RequirementTestPointSupport._validate_target_against_po(target, page_elements)
            return "fill", target, "3"
        if any(item in {"create", "update", "delete", "submit", "approve"} for item in hints):
            target = f"{page}_menu"
            target = RequirementTestPointSupport._validate_target_against_po(target, page_elements)
            return "click", target, None
        if any(item in {"assert", "negative", "regression", "smoke"} for item in hints):
            target = f"{page}_list_title"
            target = RequirementTestPointSupport._validate_target_against_po(target, page_elements)
            return "assert_visible", target, None
        target = f"{page}_list_title"
        target = RequirementTestPointSupport._validate_target_against_po(target, page_elements)
        return "wait_for", target, None

    @staticmethod
    def render_requirement_spec_markdown(requirement_spec: dict[str, Any]) -> str:
        spec = requirement_spec if isinstance(requirement_spec, dict) else {}
        page = str(spec.get("page", "")).strip() or "-"
        priority = str(spec.get("priority", "")).strip() or "P1"
        parse_confidence = spec.get("parse_confidence", 0)
        source_type = str(spec.get("source_type", "")).strip() or "manual"
        test_intents = spec.get("test_intents") if isinstance(spec.get("test_intents"), list) else []
        ambiguities = spec.get("ambiguities") if isinstance(spec.get("ambiguities"), list) else []
        business_rules = spec.get("business_rules") if isinstance(spec.get("business_rules"), list) else []
        quality_gate = spec.get("quality_gate") if isinstance(spec.get("quality_gate"), dict) else {}
        parser_runtime = spec.get("parser_runtime") if isinstance(spec.get("parser_runtime"), dict) else {}
        change_impact = spec.get("change_impact") if isinstance(spec.get("change_impact"), dict) else {}
        source_inputs = spec.get("source_inputs") if isinstance(spec.get("source_inputs"), list) else []

        lines = [
            "# 需求测试点分析",
            "",
            "## 概览",
            f"- 来源: `{source_type}`",
            f"- 页面: `{page}`",
            f"- 优先级: `{priority}`",
            f"- 解析置信度: `{parse_confidence}`",
            f"- 测试点数量: `{len(test_intents)}`",
            f"- 规则数量: `{len(business_rules)}`",
            f"- 消歧数量: `{len(ambiguities)}`",
            f"- 输入源数量: `{len(source_inputs)}`",
        ]

        if source_inputs:
            lines.extend(["", "## 输入源"])
            for index, item in enumerate(source_inputs[:20], start=1):
                if not isinstance(item, dict):
                    continue
                source_id = str(item.get("source_id", "")).strip() or "-"
                source_type_item = str(item.get("source_type", "")).strip() or "input_source"
                summary = str(item.get("summary", "")).strip() or "-"
                reference_ids = item.get("reference_ids") if isinstance(item.get("reference_ids"), list) else []
                refs = ",".join(str(value).strip() for value in reference_ids if str(value).strip())
                lines.append(
                    f"{index}. [{source_type_item}] `{source_id}` {summary}" + (f" refs={refs}" if refs else "")
                )

        if quality_gate:
            blockers = quality_gate.get("blockers") if isinstance(quality_gate.get("blockers"), list) else []
            lines.extend(
                [
                    "",
                    "## 质量门禁",
                    f"- 决策: `{str(quality_gate.get('decision', '')).strip() or '-'}`",
                    f"- 阶段: `{str(quality_gate.get('stage', '')).strip() or '-'}`",
                    f"- 阻断项数量: `{len(blockers)}`",
                ]
            )
            for index, blocker in enumerate(blockers[:10], start=1):
                if not isinstance(blocker, dict):
                    continue
                code = str(blocker.get("code", "")).strip() or "unknown"
                message = str(blocker.get("message", "")).strip() or "-"
                lines.append(f"- blocker-{index}: `{code}` {message}")

        if test_intents:
            lines.extend(["", "## 测试点"])
            for index, intent in enumerate(test_intents[:30], start=1):
                if not isinstance(intent, dict):
                    continue
                title = str(intent.get("title", "")).strip() or f"intent-{index:02d}"
                intent_type = str(intent.get("intent_type", "")).strip() or "functional"
                intent_priority = str(intent.get("priority", "")).strip() or "P1"
                lines.append(f"{index}. [{intent_priority}/{intent_type}] {title}")

        if business_rules:
            lines.extend(["", "## 业务规则"])
            for index, rule in enumerate(business_rules[:20], start=1):
                if isinstance(rule, dict):
                    text = str(rule.get("rule_text", "")).strip() or str(rule.get("text", "")).strip()
                    source_ids = rule.get("source_ids") if isinstance(rule.get("source_ids"), list) else []
                else:
                    text = str(rule).strip()
                    source_ids = []
                if text:
                    suffix = f" ({','.join(str(value).strip() for value in source_ids if str(value).strip())})" if source_ids else ""
                    lines.append(f"{index}. {text}{suffix}")

        if change_impact:
            lines.extend(
                [
                    "",
                    "## Change Impact",
                    f"- impact_score: `{change_impact.get('impact_score', '-')}`",
                    f"- changed_files: `{len(change_impact.get('changed_files', [])) if isinstance(change_impact.get('changed_files'), list) else 0}`",
                    f"- changed_areas: `{','.join(change_impact.get('changed_areas', [])) if isinstance(change_impact.get('changed_areas'), list) else '-'}`",
                    f"- affected_intents: `{','.join(change_impact.get('affected_intent_ids', [])) if isinstance(change_impact.get('affected_intent_ids'), list) else '-'}`",
                    f"- top_factor: `{(change_impact.get('top_factor') or {}).get('factor', '-') if isinstance(change_impact.get('top_factor'), dict) else '-'}`",
                    f"- regression_scope: `{','.join(change_impact.get('recommended_regression_scope', [])) if isinstance(change_impact.get('recommended_regression_scope'), list) else '-'}`",
                ]
            )

        if ambiguities:
            lines.extend(["", "## 待消歧"])
            for index, item in enumerate(ambiguities[:20], start=1):
                if not isinstance(item, dict):
                    text = str(item).strip()
                    if text:
                        lines.append(f"{index}. {text}")
                    continue
                text = str(item.get("text", "")).strip() or str(item.get("title", "")).strip() or "未命名歧义"
                suggestion = str(item.get("suggestion", "")).strip()
                if suggestion:
                    lines.append(f"{index}. {text} -> 建议: {suggestion}")
                else:
                    lines.append(f"{index}. {text}")

        if parser_runtime:
            lines.extend(
                [
                    "",
                    "## 解析运行信息",
                    f"- mode: `{str(parser_runtime.get('mode', '')).strip() or '-'}`",
                    f"- model: `{str(parser_runtime.get('model', '')).strip() or '-'}`",
                    f"- prompt_version: `{str(parser_runtime.get('prompt_version', '')).strip() or '-'}`",
                    f"- instructions_version: `{str(parser_runtime.get('instructions_version', '')).strip() or '-'}`",
                ]
            )
        return "\n".join(lines).strip() + "\n"
