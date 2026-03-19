from __future__ import annotations

from collections import defaultdict
from datetime_compat import UTC
from datetime import datetime
from pathlib import Path
import re
from typing import Any

try:
    from .schema import (
        CleanupInstruction,
        DataGenerationRequest,
        DataGenerationResponse,
        DataRequirement,
        GeneratedRecord,
        RegistryEntrySummary,
        ValidationResult,
    )
    from .registry import append_registry_entry
    from .templates import DEFAULT_TEMPLATE_BY_DATA_TYPE, TEMPLATE_LIBRARY, normalize_tags, summarize_template_library
    from .utils.parser import load_generation_request
except ImportError:  # pragma: no cover
    from schema import CleanupInstruction, DataGenerationRequest, DataGenerationResponse, DataRequirement, GeneratedRecord, RegistryEntrySummary, ValidationResult  # type: ignore
    from registry import append_registry_entry  # type: ignore
    from templates import DEFAULT_TEMPLATE_BY_DATA_TYPE, TEMPLATE_LIBRARY, normalize_tags, summarize_template_library  # type: ignore
    from utils.parser import load_generation_request  # type: ignore


class DataGenerationAgent:
    """
    Deterministic minimal generator.

    This is intentionally rule-first:
    - no LLM dependency
    - repeatable outputs
    - validation before returning
    """

    def __init__(self, *, registry_path: str | Path | None = None) -> None:
        self.repo_root = Path(__file__).resolve().parents[3]
        self.registry_path = Path(registry_path) if registry_path else self.repo_root / "reports" / "data-generation" / "registry.json"

    def generate(self, payload: dict[str, Any] | DataGenerationRequest) -> dict[str, Any]:
        request = load_generation_request(payload)
        generated: dict[str, list[GeneratedRecord]] = defaultdict(list)
        requirement_records: dict[str, list[GeneratedRecord]] = {}
        validations: list[ValidationResult] = []
        cleanup_instructions: list[CleanupInstruction] = []
        response_warnings: list[str] = []
        template_usage_keys: list[str] = []
        resolved_template_keys: list[str] = []

        for raw_requirement in request.requirements:
            requirement, resolution_warnings = self._resolve_requirement(raw_requirement)
            if requirement.template_key:
                template_usage_keys.append(requirement.template_key)
                resolved_template_keys.append(requirement.template_key)
            records = self._generate_requirement_records(requirement, request.request_id)
            self._attach_relationships(records, requirement, requirement_records)
            validation = self._validate_requirement(
                requirement,
                records,
                available_relationships=requirement_records,
            )
            generated[requirement.requirement_id] = records
            requirement_records[requirement.requirement_id] = records
            validations.append(validation)
            cleanup_instructions.append(
                CleanupInstruction(
                    requirement_id=requirement.requirement_id,
                    record_ids=[record.record_id for record in records],
                )
            )
            if validation.warnings:
                response_warnings.extend(validation.warnings)
            response_warnings.extend(resolution_warnings)

        confidence = 0.95 if all(item.passed for item in validations) else 0.75
        registry_entry = self._persist_registry_entry(
            request=request,
            generated=dict(generated),
            validations=validations,
        )
        template_summary = self._build_template_summary(
            request=request,
            template_usage_keys=template_usage_keys,
            resolved_template_keys=resolved_template_keys,
        )
        response = DataGenerationResponse(
            request_id=request.request_id,
            project=request.project,
            environment=request.environment,
            generated=dict(generated),
            validations=validations,
            cleanup_instructions=cleanup_instructions,
            registry_entry=registry_entry,
            template_summary=template_summary,
            generation_confidence=confidence,
            warnings=response_warnings[:20],
        )
        return response.model_dump()

    def _persist_registry_entry(
        self,
        *,
        request: DataGenerationRequest,
        generated: dict[str, list[GeneratedRecord]],
        validations: list[ValidationResult],
    ) -> RegistryEntrySummary:
        created_at = datetime.now(UTC).isoformat()
        total_records = sum(len(items) for items in generated.values())
        status = "generated" if all(item.passed for item in validations) else "generated_with_errors"
        entry = RegistryEntrySummary(
            request_id=request.request_id,
            project=request.project,
            environment=request.environment,
            status=status,
            cleanup_status="pending",
            created_at=created_at,
            cleaned_at="",
            total_records=total_records,
            requirement_ids=list(generated.keys()),
            registry_path=str(self.registry_path),
        )
        append_registry_entry(self.registry_path, entry.model_dump())
        return entry

    def _build_template_summary(
        self,
        *,
        request: DataGenerationRequest,
        template_usage_keys: list[str],
        resolved_template_keys: list[str],
    ) -> dict[str, Any]:
        catalog_summary = summarize_template_library()
        used_counts: dict[str, int] = {}
        for key in template_usage_keys:
            used_counts[key] = used_counts.get(key, 0) + 1
        resolved_counts: dict[str, int] = {}
        for key in resolved_template_keys:
            resolved_counts[key] = resolved_counts.get(key, 0) + 1
        requested_tags_raw: list[str] = []
        for requirement in request.requirements:
            requested_tags_raw.extend(list(requirement.tags))
        _, request_tag_warnings, requested_tags = normalize_tags(
            requested_tags_raw,
            scope=f"request:{request.request_id}",
        )
        default_template_count = sum(
            1
            for requirement in request.requirements
            if not requirement.template_key and not requirement.fields
        )
        return {
            **catalog_summary,
            "request_template_usage_counts": dict(sorted(used_counts.items())),
            "request_resolved_template_counts": dict(sorted(resolved_counts.items())),
            "request_tag_counts": dict(sorted(requested_tags.items())),
            "request_tag_warnings": request_tag_warnings,
            "request_unique_tag_count": len(requested_tags),
            "default_template_request_count": default_template_count,
            "used_template_count": len(used_counts),
            "resolved_template_count": len(resolved_counts),
            "request_requirement_count": len(request.requirements),
            "request_id": request.request_id,
        }

    def _resolve_requirement(self, requirement: DataRequirement) -> tuple[DataRequirement, list[str]]:
        warnings: list[str] = []
        template_key = str(requirement.template_key or "").strip()
        resolved_template_key = template_key
        if not resolved_template_key and not requirement.fields:
            resolved_template_key = DEFAULT_TEMPLATE_BY_DATA_TYPE.get(str(requirement.data_type).strip().lower(), "")
        if not resolved_template_key:
            return requirement, warnings

        template = TEMPLATE_LIBRARY.get(resolved_template_key)
        if not isinstance(template, dict):
            raise ValueError(f"Unknown template_key: {resolved_template_key}")

        merged_fields = self._merge_template_fields(
            template_fields=template.get("fields") if isinstance(template.get("fields"), list) else [],
            requirement_fields=[field.model_dump() for field in requirement.fields],
        )
        merged_tags = self._merge_string_lists(
            list(template.get("tags") if isinstance(template.get("tags"), list) else []),
            list(requirement.tags),
        )
        normalized_tags, tag_warnings, _ = normalize_tags(
            merged_tags,
            scope=f"requirement:{requirement.requirement_id}",
        )
        resolved = DataRequirement.model_validate(
            {
                **requirement.model_dump(),
                "template_key": resolved_template_key,
                "fields": merged_fields,
                "tags": normalized_tags,
            }
        )
        warnings.append(f"{requirement.requirement_id} resolved template {resolved_template_key}")
        warnings.extend(tag_warnings)
        return resolved, warnings

    def _merge_template_fields(
        self,
        *,
        template_fields: list[dict[str, Any]],
        requirement_fields: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        by_name: dict[str, dict[str, Any]] = {}
        order: list[str] = []
        for field in template_fields:
            name = str(field.get("name", "")).strip()
            if not name:
                continue
            by_name[name] = dict(field)
            order.append(name)
        for field in requirement_fields:
            name = str(field.get("name", "")).strip()
            if not name:
                continue
            if name not in by_name:
                order.append(name)
                by_name[name] = {}
            by_name[name].update(dict(field))
        return [by_name[name] for name in order if name in by_name]

    def _merge_string_lists(self, left: list[str], right: list[str]) -> list[str]:
        output: list[str] = []
        seen: set[str] = set()
        for item in [*left, *right]:
            value = str(item).strip()
            if not value or value in seen:
                continue
            seen.add(value)
            output.append(value)
        return output

    def _generate_requirement_records(self, requirement: DataRequirement, request_id: str) -> list[GeneratedRecord]:
        records: list[GeneratedRecord] = []
        for index in range(requirement.quantity):
            values: dict[str, Any] = {}
            warnings: list[str] = []
            for field in requirement.fields:
                value = self._generate_field_value(
                    requirement_id=requirement.requirement_id,
                    request_id=request_id,
                    field=field.model_dump(),
                    index=index,
                )
                values[field.name] = value
                if value is None and field.required and not field.nullable:
                    warnings.append(f"{field.name} generated as null")
            records.append(
                GeneratedRecord(
                    record_id=f"{requirement.requirement_id}-{index + 1:03d}",
                    requirement_id=requirement.requirement_id,
                    data_type=requirement.data_type,
                    values=values,
                    warnings=warnings,
                )
            )
        return records

    def _generate_field_value(self, *, requirement_id: str, request_id: str, field: dict[str, Any], index: int) -> Any:
        field_type = str(field.get("type", "string")).strip().lower()
        prefix = str(field.get("prefix", "")).strip() or requirement_id
        min_value = field.get("min_value")
        max_value = field.get("max_value")
        options = field.get("options") if isinstance(field.get("options"), list) else []
        unique = bool(field.get("unique", False))
        min_length = int(field.get("min_length", 4) or 4) if field.get("min_length") is not None else 4

        if field_type == "integer":
            base = int(min_value if min_value is not None else 1)
            candidate = base + index
            if max_value is not None:
                candidate = min(candidate, int(max_value))
            return candidate
        if field_type == "float":
            base = float(min_value if min_value is not None else 1.0)
            candidate = base + float(index)
            if max_value is not None:
                candidate = min(candidate, float(max_value))
            return round(candidate, 2)
        if field_type == "boolean":
            return index % 2 == 0
        if field_type == "email":
            local = f"{prefix}-{request_id.lower()}-{index + 1}" if unique else f"{prefix}-{index + 1}"
            return f"{local}@example.test"
        if field_type == "enum":
            normalized_options = [str(item).strip() for item in options if str(item).strip()]
            return normalized_options[index % len(normalized_options)] if normalized_options else "unknown"

        suffix = f"{index + 1}" if unique or field_type == "string" else ""
        base = f"{prefix}-{request_id.lower()}-{suffix}".strip("-")
        if len(base) < min_length:
            base = base + ("x" * (min_length - len(base)))
        max_length = field.get("max_length")
        if max_length is not None:
            return base[: int(max_length)]
        return base

    def _attach_relationships(
        self,
        records: list[GeneratedRecord],
        requirement: DataRequirement,
        requirement_records: dict[str, list[GeneratedRecord]],
    ) -> None:
        for ref_id in requirement.relationships:
            upstream = requirement_records.get(ref_id, [])
            if not upstream:
                continue
            for index, record in enumerate(records):
                linked = upstream[index % len(upstream)]
                record.relationships[ref_id] = linked.record_id

    def _validate_requirement(
        self,
        requirement: DataRequirement,
        records: list[GeneratedRecord],
        *,
        available_relationships: dict[str, list[GeneratedRecord]],
    ) -> ValidationResult:
        errors: list[str] = []
        warnings: list[str] = []
        if not requirement.fields:
            errors.append(f"{requirement.requirement_id} has no fields or resolved template")
        seen_unique: dict[str, set[Any]] = {
            field.name: set()
            for field in requirement.fields
            if field.unique
        }
        missing_relationship_sources = [
            ref_id
            for ref_id in requirement.relationships
            if ref_id not in available_relationships
        ]
        for ref_id in missing_relationship_sources:
            errors.append(f"{requirement.requirement_id} missing relationship source {ref_id}")
        for record in records:
            for field in requirement.fields:
                value = record.values.get(field.name)
                if field.required and value is None and not field.nullable:
                    errors.append(f"{requirement.requirement_id}.{field.name} is required")
                    continue
                if value is None:
                    continue
                field_errors, field_warnings = self._validate_field_value(
                    requirement=requirement,
                    field=field,
                    value=value,
                )
                errors.extend(field_errors)
                warnings.extend(field_warnings)
                if field.unique:
                    bucket = seen_unique[field.name]
                    if value in bucket:
                        errors.append(f"{requirement.requirement_id}.{field.name} duplicate value")
                    bucket.add(value)
            if requirement.relationships and not record.relationships:
                warnings.append(f"{record.record_id} has unresolved relationships")
        return ValidationResult(
            requirement_id=requirement.requirement_id,
            passed=len(errors) == 0,
            errors=errors[:20],
            warnings=warnings[:20],
        )

    def _validate_field_value(
        self,
        *,
        requirement: DataRequirement,
        field: Any,
        value: Any,
    ) -> tuple[list[str], list[str]]:
        errors: list[str] = []
        warnings: list[str] = []
        field_name = str(field.name)
        field_prefix = f"{requirement.requirement_id}.{field_name}"

        if field.type in {"string", "email", "enum"}:
            value_text = str(value)
            if field.min_length is not None and len(value_text) < field.min_length:
                errors.append(f"{field_prefix} below min_length")
            if field.max_length is not None and len(value_text) > field.max_length:
                errors.append(f"{field_prefix} above max_length")
            if field.pattern:
                try:
                    if re.fullmatch(field.pattern, value_text) is None:
                        errors.append(f"{field_prefix} does not match pattern")
                except re.error:
                    warnings.append(f"{field_prefix} pattern is invalid")

        if field.type == "email":
            if re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", str(value)) is None:
                errors.append(f"{field_prefix} invalid email")

        if field.type == "enum":
            normalized_options = [str(item).strip() for item in field.options if str(item).strip()]
            if not normalized_options:
                warnings.append(f"{field_prefix} enum options are empty")
            elif str(value) not in normalized_options:
                errors.append(f"{field_prefix} not in enum options")

        if field.type in {"integer", "float"}:
            numeric = float(value)
            if field.min_value is not None and numeric < float(field.min_value):
                errors.append(f"{field_prefix} below min_value")
            if field.max_value is not None and numeric > float(field.max_value):
                errors.append(f"{field_prefix} above max_value")

        return errors, warnings
