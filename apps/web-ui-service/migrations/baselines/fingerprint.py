"""Dialect-normalized schema fingerprinting for frozen installation baselines."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any

from sqlalchemy import Connection, inspect


FROZEN_REVISION = "20260713_120000"
SCHEMA_SNAPSHOT_VERSION = 1
_MANIFEST_PATH = Path(__file__).with_name("schema_manifest_20260713_120000.json")


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
                    "server_default": (
                        "server-default" if column.get("default") is not None else None
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
            "unique_constraints": sorted(
                sorted(str(column) for column in constraint["column_names"])
                for constraint in inspector.get_unique_constraints(table_name)
                if constraint.get("column_names")
            ),
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
                ),
                key=lambda item: (item["columns"], item["unique"]),
            ),
        }
    return {
        "frozen_revision": FROZEN_REVISION,
        "schema_snapshot_version": SCHEMA_SNAPSHOT_VERSION,
        "tables": tables,
    }


def _fingerprint(value: dict[str, Any]) -> str:
    canonical = json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


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
    if type_name in {"float", "numeric", "decimal"}:
        return "number"
    return type_name


def _normalize_check_expression(value: str) -> str:
    without_identifier_quotes = value.replace('"', "")
    return re.sub(r"\s+", " ", without_identifier_quotes).strip()
