# mypy: ignore-errors

from __future__ import annotations

import re


TEMPLATE_CATALOG_VERSION = "data-generation-template-catalog.v1"

TEMPLATE_LIBRARY: dict[str, dict[str, object]] = {
    "user_basic": {
        "version": "1.0.0",
        "data_type": "user",
        "tags": ["template", "user", "basic"],
        "fields": [
            {"name": "username", "type": "string", "prefix": "user", "unique": True, "min_length": 6},
            {"name": "email", "type": "email", "prefix": "buyer", "unique": True},
            {"name": "age", "type": "integer", "min_value": 18, "max_value": 60},
            {"name": "enabled", "type": "boolean"},
        ],
    },
    "product_basic": {
        "version": "1.0.0",
        "data_type": "product",
        "tags": ["template", "product", "basic"],
        "fields": [
            {"name": "product_name", "type": "string", "prefix": "product", "unique": True, "min_length": 8},
            {"name": "sku", "type": "string", "prefix": "sku", "unique": True, "min_length": 6},
            {"name": "price", "type": "float", "min_value": 10.0, "max_value": 999.0},
            {"name": "status", "type": "enum", "options": ["draft", "published"]},
        ],
    },
    "order_basic": {
        "version": "1.0.0",
        "data_type": "order",
        "tags": ["template", "order", "basic"],
        "fields": [
            {"name": "order_no", "type": "string", "prefix": "ord", "unique": True, "min_length": 8},
            {"name": "amount", "type": "float", "min_value": 10.0, "max_value": 5000.0},
            {"name": "status", "type": "enum", "options": ["draft", "paid", "cancelled"]},
        ],
    },
}


DEFAULT_TEMPLATE_BY_DATA_TYPE = {
    "user": "user_basic",
    "product": "product_basic",
    "order": "order_basic",
}


def normalize_tags(tags: list[object], *, scope: str) -> tuple[list[str], list[str], dict[str, int]]:
    normalized_tags: list[str] = []
    warnings: list[str] = []
    counts: dict[str, int] = {}
    seen: set[str] = set()
    for item in tags:
        raw_value = str(item).strip()
        if not raw_value:
            continue
        normalized = re.sub(r"[-\s_]+", "-", raw_value.strip().lower())
        counts[normalized] = counts.get(normalized, 0) + 1
        if normalized != raw_value:
            warnings.append(f"{scope} tag normalized: {raw_value} -> {normalized}")
        if normalized in seen:
            warnings.append(f"{scope} duplicate tag collapsed: {normalized}")
            continue
        seen.add(normalized)
        normalized_tags.append(normalized)
    return normalized_tags, warnings[:20], dict(sorted(counts.items()))


def _parse_version_parts(value: object) -> tuple[int, ...] | None:
    text = str(value or "").strip()
    if not text or not re.fullmatch(r"\d+(?:\.\d+)*", text):
        return None
    return tuple(int(part) for part in text.split("."))


def summarize_template_library() -> dict[str, object]:
    templates: list[dict[str, object]] = []
    tag_counts: dict[str, int] = {}
    data_type_counts: dict[str, int] = {}
    version_counts: dict[str, int] = {}
    tag_warnings: list[str] = []
    for template_key, template in TEMPLATE_LIBRARY.items():
        data_type = str(template.get("data_type", "")).strip() or "unknown"
        version = str(template.get("version", "")).strip() or "unknown"
        tags, normalized_warnings, _ = normalize_tags(
            template.get("tags", []) if isinstance(template.get("tags"), list) else [],
            scope=f"template:{template_key}",
        )
        field_count = len(template.get("fields", [])) if isinstance(template.get("fields"), list) else 0
        templates.append(
            {
                "template_key": template_key,
                "data_type": data_type,
                "version": version,
                "tags": tags,
                "field_count": field_count,
            }
        )
        data_type_counts[data_type] = data_type_counts.get(data_type, 0) + 1
        version_counts[version] = version_counts.get(version, 0) + 1
        for tag in tags:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
        tag_warnings.extend(normalized_warnings)

    return {
        "catalog_version": TEMPLATE_CATALOG_VERSION,
        "tag_rule": "trim + lowercase + spaces/underscores to hyphen + dedup",
        "total_templates": len(TEMPLATE_LIBRARY),
        "default_template_by_data_type": dict(sorted(DEFAULT_TEMPLATE_BY_DATA_TYPE.items())),
        "data_type_counts": dict(sorted(data_type_counts.items())),
        "version_counts": dict(sorted(version_counts.items())),
        "tag_counts": dict(sorted(tag_counts.items())),
        "tag_warnings": tag_warnings[:20],
        "templates": sorted(templates, key=lambda item: str(item.get("template_key", ""))),
    }


def summarize_template_migration(
    template_library: dict[str, dict[str, object]] | None = None,
    default_template_by_data_type: dict[str, str] | None = None,
) -> dict[str, object]:
    library = template_library or TEMPLATE_LIBRARY
    default_mapping = default_template_by_data_type or DEFAULT_TEMPLATE_BY_DATA_TYPE
    templates_by_data_type: dict[str, list[dict[str, object]]] = {}
    invalid_version_items: list[dict[str, object]] = []

    for template_key, template in library.items():
        data_type = str(template.get("data_type", "")).strip() or "unknown"
        version = str(template.get("version", "")).strip() or "unknown"
        parsed_version = _parse_version_parts(version)
        template_entry = {
            "template_key": template_key,
            "data_type": data_type,
            "version": version,
            "parsed_version": parsed_version,
        }
        templates_by_data_type.setdefault(data_type, []).append(template_entry)
        if parsed_version is None:
            invalid_version_items.append(
                {
                    "template_key": template_key,
                    "data_type": data_type,
                    "version": version,
                    "warning": f"invalid semantic version: {version}",
                }
            )

    migration_candidates: list[dict[str, object]] = []
    default_template_drift_items: list[dict[str, object]] = []
    data_type_latest_versions: dict[str, str] = {}
    data_type_recommended_templates: dict[str, str] = {}

    for data_type, items in sorted(templates_by_data_type.items()):
        valid_items = [item for item in items if item.get("parsed_version") is not None]
        if not valid_items:
            data_type_latest_versions[data_type] = "unknown"
            data_type_recommended_templates[data_type] = ""
            continue

        valid_items.sort(
            key=lambda item: (
                item.get("parsed_version"),
                str(item.get("template_key", "")),
            ),
            reverse=True,
        )
        latest_item = valid_items[0]
        latest_version = str(latest_item.get("version", "")).strip() or "unknown"
        latest_template_key = str(latest_item.get("template_key", "")).strip()
        data_type_latest_versions[data_type] = latest_version
        data_type_recommended_templates[data_type] = latest_template_key

        for item in items:
            parsed_version = item.get("parsed_version")
            template_key = str(item.get("template_key", "")).strip()
            version = str(item.get("version", "")).strip() or "unknown"
            if parsed_version is None or parsed_version >= latest_item["parsed_version"]:
                continue
            migration_candidates.append(
                {
                    "template_key": template_key,
                    "data_type": data_type,
                    "current_version": version,
                    "target_version": latest_version,
                    "recommended_template_key": latest_template_key,
                }
            )

        default_template_key = str(default_mapping.get(data_type, "")).strip()
        default_template = next(
            (item for item in items if str(item.get("template_key", "")).strip() == default_template_key),
            None,
        )
        if default_template is None:
            continue
        default_version = str(default_template.get("version", "")).strip() or "unknown"
        default_parsed = default_template.get("parsed_version")
        if default_parsed is None or default_parsed >= latest_item["parsed_version"]:
            continue
        default_template_drift_items.append(
            {
                "data_type": data_type,
                "default_template_key": default_template_key,
                "default_version": default_version,
                "recommended_template_key": latest_template_key,
                "target_version": latest_version,
            }
        )

    version_warnings = [str(item.get("warning", "")).strip() for item in invalid_version_items if str(item.get("warning", "")).strip()]
    return {
        "catalog_version": TEMPLATE_CATALOG_VERSION,
        "version_rule": "semantic-version string; latest version wins within each data_type",
        "total_templates": len(library),
        "data_type_latest_versions": dict(sorted(data_type_latest_versions.items())),
        "data_type_recommended_templates": dict(sorted(data_type_recommended_templates.items())),
        "migration_candidate_count": len(migration_candidates),
        "migration_candidates": sorted(
            migration_candidates,
            key=lambda item: (
                str(item.get("data_type", "")),
                str(item.get("template_key", "")),
            ),
        )[:50],
        "default_template_drift_count": len(default_template_drift_items),
        "default_template_drift_items": sorted(
            default_template_drift_items,
            key=lambda item: str(item.get("data_type", "")),
        )[:50],
        "invalid_version_template_count": len(invalid_version_items),
        "invalid_version_items": sorted(
            invalid_version_items,
            key=lambda item: (
                str(item.get("data_type", "")),
                str(item.get("template_key", "")),
            ),
        )[:50],
        "up_to_date_template_count": max(0, len(library) - len(migration_candidates) - len(invalid_version_items)),
        "version_warnings": version_warnings[:20],
    }
