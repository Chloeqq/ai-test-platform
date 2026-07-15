"""Dialect-normalized schema fingerprinting for frozen installation baselines."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from migrations.baselines.authorized_retirements import (
    AuthorizedSchemaRetirement,
    RequiredSchemaObject,
    SchemaObjectRef,
    column_ref,
    foreign_key_ref,
    index_ref,
    primary_key_ref,
    table_ref,
)
from sqlalchemy import Connection, inspect

FROZEN_REVISION = "20260713_121000"
SCHEMA_SNAPSHOT_VERSION = 1
_MANIFEST_PATH = Path(__file__).with_name("schema_manifest_20260713_121000.json")


class BaselineSchemaMismatch(RuntimeError):
    """Raised when a database does not match the approved frozen schema."""


def load_frozen_manifest() -> dict[str, Any]:
    """Load the checked-in logical schema manifest without importing ORM metadata."""
    with _MANIFEST_PATH.open(encoding="utf-8") as manifest_file:
        manifest = json.load(manifest_file)
    if manifest.get("frozen_revision") != FROZEN_REVISION:
        raise BaselineSchemaMismatch("frozen schema manifest revision is invalid")
    if manifest.get("schema_snapshot_version") != SCHEMA_SNAPSHOT_VERSION:
        raise BaselineSchemaMismatch("frozen schema manifest version is invalid")
    return manifest


def frozen_schema_fingerprint() -> str:
    """Return the stable digest of the checked-in logical schema manifest."""
    return _fingerprint(load_frozen_manifest())


def schema_fingerprint(connection: Connection) -> str:
    """Return a stable logical fingerprint of the schema visible to ``connection``."""
    return _fingerprint(normalize_schema(connection))


def assert_frozen_schema(connection: Connection) -> None:
    """Fail closed unless the reflected schema equals the frozen logical manifest."""
    expected = frozen_schema_fingerprint()
    actual = schema_fingerprint(connection)
    if actual != expected:
        raise BaselineSchemaMismatch(
            "database schema does not match frozen baseline "
            f"{FROZEN_REVISION}: expected={expected}, actual={actual}"
        )


def assert_frozen_schema_compatible(
    connection: Connection,
    *,
    authorized_retirements: tuple[AuthorizedSchemaRetirement, ...] = (),
) -> None:
    """Require frozen objects except revision-authorized deterministic retirements."""
    expected = load_frozen_manifest()
    actual = normalize_schema(connection)
    retired_objects = frozenset(
        schema_object
        for authorization in authorized_retirements
        for schema_object in authorization.retired_objects
    )
    issues = _retirement_authorization_issues(expected, authorized_retirements)
    issues.extend(
        _frozen_schema_compatibility_issues(
            expected,
            actual,
            retired_objects=retired_objects,
        )
    )
    for authorization in authorized_retirements:
        issues.extend(
            _replacement_schema_issues(
                actual,
                authorization.replacement_objects,
                revision=authorization.revision,
            )
        )
    if issues:
        raise BaselineSchemaMismatch(
            "database schema does not contain the required frozen baseline "
            f"{FROZEN_REVISION}: {'; '.join(issues)}"
        )


def normalize_schema(connection: Connection) -> dict[str, Any]:
    """Normalize SQLAlchemy reflection into a cross-dialect logical schema shape."""
    inspector = inspect(connection)
    tables: dict[str, Any] = {}
    for table_name in sorted(inspector.get_table_names()):
        if table_name == "alembic_version":
            continue
        columns = inspector.get_columns(table_name)
        primary_key = inspector.get_pk_constraint(table_name).get("constrained_columns") or []
        primary_key_set = set(primary_key)
        unique_constraints = sorted(
            sorted(str(column) for column in constraint["column_names"])
            for constraint in inspector.get_unique_constraints(table_name)
            if constraint.get("column_names")
        )
        unique_constraint_columns = {
            tuple(constraint) for constraint in unique_constraints
        }
        tables[table_name] = {
            "columns": [
                {
                    "name": str(column["name"]),
                    "type": _normalize_logical_type(
                        column["type"],
                        is_primary_key=str(column["name"]) in primary_key_set,
                    ),
                    "nullable": bool(column.get("nullable", True)),
                    "primary_key": str(column["name"]) in primary_key_set,
                    # PostgreSQL reflects SERIAL/IDENTITY primary keys as a
                    # server default while SQLite does not.  Both represent
                    # the same logical integer auto primary key.
                    "server_default": (
                        "server-default"
                        if column.get("default") is not None
                        and str(column["name"]) not in primary_key_set
                        else None
                    ),
                }
                for column in columns
            ],
            "primary_key": [str(column) for column in primary_key],
            "foreign_keys": sorted(
                (
                    {
                        "columns": [str(column) for column in foreign_key["constrained_columns"]],
                        "referred_table": str(foreign_key["referred_table"]),
                        "referred_columns": [
                            str(column) for column in foreign_key["referred_columns"]
                        ],
                    }
                    for foreign_key in inspector.get_foreign_keys(table_name)
                ),
                key=lambda item: (item["columns"], item["referred_table"]),
            ),
            "unique_constraints": unique_constraints,
            "check_constraints": sorted(
                _normalize_check_expression(str(constraint.get("sqltext") or ""))
                for constraint in inspector.get_check_constraints(table_name)
            ),
            "indexes": sorted(
                (
                    {
                        "columns": [str(column) for column in index["column_names"]],
                        "unique": bool(index.get("unique", False)),
                    }
                    for index in inspector.get_indexes(table_name)
                    if index.get("column_names")
                    # PostgreSQL exposes an implicit unique index for each
                    # unique constraint; SQLite does not.  The constraint is
                    # already represented above, so do not count it twice.
                    and not (
                        bool(index.get("unique", False))
                        and tuple(sorted(str(column) for column in index["column_names"]))
                        in unique_constraint_columns
                    )
                ),
                key=lambda item: (item["columns"], item["unique"]),
            ),
        }
    return {
        "frozen_revision": FROZEN_REVISION,
        "schema_snapshot_version": SCHEMA_SNAPSHOT_VERSION,
        "tables": tables,
    }


def _frozen_schema_compatibility_issues(
    expected: dict[str, Any],
    actual: dict[str, Any],
    *,
    retired_objects: frozenset[SchemaObjectRef] = frozenset(),
) -> list[str]:
    """Return frozen objects missing or changed in a later normalized schema."""
    issues: list[str] = []
    expected_tables = expected.get("tables", {})
    actual_tables = actual.get("tables", {})

    for table_name, expected_table in expected_tables.items():
        actual_table = actual_tables.get(table_name)
        if actual_table is None:
            if table_ref(table_name) not in retired_objects:
                issues.append(f"missing table {table_name}")
            continue

        expected_columns = {
            column["name"]: column for column in expected_table.get("columns", [])
        }
        actual_columns = {
            column["name"]: column for column in actual_table.get("columns", [])
        }
        for column_name, expected_column in expected_columns.items():
            actual_column = actual_columns.get(column_name)
            if actual_column is None:
                if column_ref(table_name, column_name) not in retired_objects:
                    issues.append(f"missing column {table_name}.{column_name}")
            elif actual_column != expected_column:
                issues.append(f"changed column {table_name}.{column_name}")

        expected_primary_key = expected_table.get("primary_key", [])
        if actual_table.get("primary_key", []) != expected_primary_key:
            primary_key = primary_key_ref(table_name, tuple(expected_primary_key))
            if primary_key not in retired_objects:
                issues.append(f"changed primary key {table_name}")

        for object_type in ("foreign_keys", "unique_constraints", "check_constraints", "indexes"):
            expected_objects = expected_table.get(object_type, [])
            actual_objects = actual_table.get(object_type, [])
            for expected_object in expected_objects:
                if expected_object not in actual_objects:
                    schema_object = _collection_object_ref(
                        object_type,
                        table_name,
                        expected_object,
                    )
                    if schema_object not in retired_objects:
                        issues.append(
                            f"missing {object_type} on {table_name}: {expected_object}"
                        )

    return issues


def _retirement_authorization_issues(
    expected: dict[str, Any],
    authorizations: tuple[AuthorizedSchemaRetirement, ...],
) -> list[str]:
    issues: list[str] = []
    seen_revisions: set[str] = set()
    for authorization in authorizations:
        if authorization.revision in seen_revisions:
            issues.append(f"duplicate retirement authorization {authorization.revision}")
        seen_revisions.add(authorization.revision)
        if not authorization.replacement_objects:
            issues.append(
                f"retirement authorization {authorization.revision} has no replacements"
            )
        for schema_object in authorization.retired_objects:
            if _schema_object_payload(expected, schema_object) is _MISSING:
                issues.append(
                    "retirement authorization "
                    f"{authorization.revision} references non-frozen object "
                    f"{_schema_object_label(schema_object)}"
                )
    return issues


def _replacement_schema_issues(
    actual: dict[str, Any],
    requirements: frozenset[RequiredSchemaObject],
    *,
    revision: str,
) -> list[str]:
    issues: list[str] = []
    for requirement in sorted(requirements):
        payload = _schema_object_payload(actual, requirement.ref)
        label = _schema_object_label(requirement.ref)
        if payload is _MISSING:
            issues.append(f"missing replacement {label} for {revision}")
        elif (
            requirement.expected_payload is not None
            and _canonical(payload) != requirement.expected_payload
        ):
            issues.append(f"changed replacement {label} for {revision}")
    return issues


_MISSING = object()


def _schema_object_payload(
    schema: dict[str, Any],
    schema_object: SchemaObjectRef,
) -> Any:
    table = schema.get("tables", {}).get(schema_object.table_name)
    if table is None:
        return _MISSING
    if schema_object.kind == "table":
        return schema_object.table_name
    if schema_object.kind == "column":
        return next(
            (
                column
                for column in table.get("columns", [])
                if column.get("name") == schema_object.object_key
            ),
            _MISSING,
        )
    if schema_object.kind == "primary_key":
        primary_key = table.get("primary_key", [])
        return primary_key if _canonical(primary_key) == schema_object.object_key else _MISSING

    field_name = {
        "foreign_key": "foreign_keys",
        "unique_constraint": "unique_constraints",
        "check_constraint": "check_constraints",
        "index": "indexes",
    }[schema_object.kind]
    return next(
        (
            value
            for value in table.get(field_name, [])
            if _canonical(value) == schema_object.object_key
        ),
        _MISSING,
    )


def _collection_object_ref(
    object_type: str,
    table_name: str,
    value: Any,
) -> SchemaObjectRef:
    if object_type == "foreign_keys":
        return foreign_key_ref(
            table_name,
            tuple(value["columns"]),
            str(value["referred_table"]),
            tuple(value["referred_columns"]),
        )
    if object_type == "unique_constraints":
        return SchemaObjectRef("unique_constraint", table_name, _canonical(value))
    if object_type == "check_constraints":
        return SchemaObjectRef("check_constraint", table_name, _canonical(value))
    if object_type == "indexes":
        return index_ref(table_name, tuple(value["columns"]), unique=bool(value["unique"]))
    raise ValueError(f"unsupported normalized schema object type: {object_type}")


def _schema_object_label(schema_object: SchemaObjectRef) -> str:
    if schema_object.kind == "table":
        return f"table {schema_object.table_name}"
    if schema_object.kind == "column":
        return f"column {schema_object.table_name}.{schema_object.object_key}"
    return (
        f"{schema_object.kind} on {schema_object.table_name}: "
        f"{schema_object.object_key}"
    )


def _fingerprint(value: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _normalize_logical_type(column_type: Any, *, is_primary_key: bool) -> str:
    type_name = column_type.__class__.__name__.lower()
    if is_primary_key and type_name in {"integer", "biginteger", "smallinteger"}:
        return "integer-auto-pk"
    if "json" in type_name:
        return "json"
    if type_name in {"integer", "biginteger", "smallinteger"}:
        return "integer"
    if type_name in {"string", "varchar", "char"}:
        length = getattr(column_type, "length", None)
        return f"string({length})" if length is not None else "string"
    if type_name in {"text", "unicode_text"}:
        return "text"
    if type_name in {"datetime", "timestamp"}:
        return "datetime"
    if type_name in {"boolean", "bool"}:
        return "boolean"
    if type_name in {"float", "numeric", "decimal", "double_precision"}:
        return "number"
    return type_name


def _normalize_check_expression(value: str) -> str:
    without_identifier_quotes = value.replace('"', "")
    without_postgresql_casts = re.sub(
        r"::(?:character varying|text)(?:\[\])?",
        "",
        without_identifier_quotes,
    )
    normalized_any_array = re.sub(
        r"\b([A-Za-z_][A-Za-z0-9_]*)\s*=\s*ANY\s*\(ARRAY\[([^\]]*)\]\)",
        r"\1 IN (\2)",
        without_postgresql_casts,
    )
    return re.sub(r"\s+", " ", normalized_any_array).strip()
