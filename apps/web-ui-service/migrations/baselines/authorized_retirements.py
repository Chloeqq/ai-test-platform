"""Static authorizations for retiring objects from the frozen schema baseline.

This module is intentionally independent from runtime ORM metadata and settings.
Each published authorization is bound to an Alembic revision and remains immutable.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Literal

SchemaObjectKind = Literal[
    "table",
    "column",
    "primary_key",
    "foreign_key",
    "unique_constraint",
    "check_constraint",
    "index",
]


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


@dataclass(frozen=True, order=True)
class SchemaObjectRef:
    """Stable identity of one normalized schema object."""

    kind: SchemaObjectKind
    table_name: str
    object_key: str


@dataclass(frozen=True, order=True)
class RequiredSchemaObject:
    """A replacement object that must exist with the declared logical shape."""

    ref: SchemaObjectRef
    expected_payload: str | None = None


@dataclass(frozen=True)
class AuthorizedSchemaRetirement:
    """Frozen objects one revision may retire and their required replacements."""

    revision: str
    retired_objects: frozenset[SchemaObjectRef]
    replacement_objects: frozenset[RequiredSchemaObject]


def table_ref(table_name: str) -> SchemaObjectRef:
    return SchemaObjectRef("table", table_name, table_name)


def column_ref(table_name: str, column_name: str) -> SchemaObjectRef:
    return SchemaObjectRef("column", table_name, column_name)


def primary_key_ref(table_name: str, columns: tuple[str, ...]) -> SchemaObjectRef:
    return SchemaObjectRef("primary_key", table_name, _canonical(list(columns)))


def foreign_key_ref(
    table_name: str,
    columns: tuple[str, ...],
    referred_table: str,
    referred_columns: tuple[str, ...],
) -> SchemaObjectRef:
    return SchemaObjectRef(
        "foreign_key",
        table_name,
        _canonical(
            {
                "columns": list(columns),
                "referred_columns": list(referred_columns),
                "referred_table": referred_table,
            }
        ),
    )


def unique_constraint_ref(
    table_name: str,
    columns: tuple[str, ...],
) -> SchemaObjectRef:
    return SchemaObjectRef(
        "unique_constraint",
        table_name,
        _canonical(sorted(columns)),
    )


def check_constraint_ref(table_name: str, expression: str) -> SchemaObjectRef:
    return SchemaObjectRef("check_constraint", table_name, _canonical(expression))


def index_ref(
    table_name: str,
    columns: tuple[str, ...],
    *,
    unique: bool,
) -> SchemaObjectRef:
    return SchemaObjectRef(
        "index",
        table_name,
        _canonical({"columns": list(columns), "unique": unique}),
    )


def require_table(table_name: str) -> RequiredSchemaObject:
    return RequiredSchemaObject(table_ref(table_name))


def require_column(
    table_name: str,
    column_name: str,
    *,
    logical_type: str,
    nullable: bool,
    primary_key: bool = False,
    server_default: str | None = None,
) -> RequiredSchemaObject:
    return RequiredSchemaObject(
        column_ref(table_name, column_name),
        _canonical(
            {
                "name": column_name,
                "nullable": nullable,
                "primary_key": primary_key,
                "server_default": server_default,
                "type": logical_type,
            }
        ),
    )


def require_primary_key(
    table_name: str,
    columns: tuple[str, ...],
) -> RequiredSchemaObject:
    return RequiredSchemaObject(primary_key_ref(table_name, columns))


def require_foreign_key(
    table_name: str,
    columns: tuple[str, ...],
    referred_table: str,
    referred_columns: tuple[str, ...],
) -> RequiredSchemaObject:
    return RequiredSchemaObject(
        foreign_key_ref(table_name, columns, referred_table, referred_columns)
    )


def require_unique_constraint(
    table_name: str,
    columns: tuple[str, ...],
) -> RequiredSchemaObject:
    return RequiredSchemaObject(unique_constraint_ref(table_name, columns))


def require_check_constraint(
    table_name: str,
    expression: str,
) -> RequiredSchemaObject:
    return RequiredSchemaObject(check_constraint_ref(table_name, expression))


def require_index(
    table_name: str,
    columns: tuple[str, ...],
    *,
    unique: bool,
) -> RequiredSchemaObject:
    return RequiredSchemaObject(index_ref(table_name, columns, unique=unique))


AUTHORIZED_SCHEMA_RETIREMENTS: tuple[AuthorizedSchemaRetirement, ...] = (
    AuthorizedSchemaRetirement(
        revision="20260715_100000",
        retired_objects=frozenset(
            {
                column_ref("test_asset_sources", "requirement_pk"),
                column_ref("test_asset_sources", "requirement_version_pk"),
                foreign_key_ref(
                    "test_asset_sources",
                    ("requirement_pk",),
                    "requirements",
                    ("id",),
                ),
                foreign_key_ref(
                    "test_asset_sources",
                    ("requirement_version_pk",),
                    "requirement_versions",
                    ("id",),
                ),
                index_ref(
                    "test_asset_sources",
                    ("requirement_pk",),
                    unique=False,
                ),
                index_ref(
                    "test_asset_sources",
                    ("requirement_version_pk",),
                    unique=False,
                ),
            }
        ),
        replacement_objects=frozenset(
            {
                require_column(
                    "test_asset_sources",
                    "source_type",
                    logical_type="string(20)",
                    nullable=False,
                ),
                require_check_constraint(
                    "test_asset_sources",
                    "source_type IN ('requirement', 'manual')",
                ),
                require_index(
                    "test_asset_sources",
                    ("source_type",),
                    unique=False,
                ),
                require_table("test_asset_requirement_sources"),
                require_column(
                    "test_asset_requirement_sources",
                    "id",
                    logical_type="integer-auto-pk",
                    nullable=False,
                    primary_key=True,
                ),
                require_column(
                    "test_asset_requirement_sources",
                    "test_asset_source_pk",
                    logical_type="integer",
                    nullable=False,
                ),
                require_column(
                    "test_asset_requirement_sources",
                    "requirement_pk",
                    logical_type="integer",
                    nullable=False,
                ),
                require_column(
                    "test_asset_requirement_sources",
                    "requirement_version_pk",
                    logical_type="integer",
                    nullable=False,
                ),
                require_primary_key(
                    "test_asset_requirement_sources",
                    ("id",),
                ),
                require_foreign_key(
                    "test_asset_requirement_sources",
                    ("test_asset_source_pk",),
                    "test_asset_sources",
                    ("id",),
                ),
                require_foreign_key(
                    "test_asset_requirement_sources",
                    ("requirement_pk",),
                    "requirements",
                    ("id",),
                ),
                require_foreign_key(
                    "test_asset_requirement_sources",
                    ("requirement_version_pk",),
                    "requirement_versions",
                    ("id",),
                ),
                require_unique_constraint(
                    "test_asset_requirement_sources",
                    ("test_asset_source_pk",),
                ),
                require_index(
                    "test_asset_requirement_sources",
                    ("requirement_pk",),
                    unique=False,
                ),
                require_index(
                    "test_asset_requirement_sources",
                    ("requirement_version_pk",),
                    unique=False,
                ),
            }
        ),
    ),
)


def authorized_retirements_for_lineage(
    revision_lineage: frozenset[str],
) -> tuple[AuthorizedSchemaRetirement, ...]:
    """Return only authorizations introduced by revisions in this lineage."""
    return tuple(
        authorization
        for authorization in AUTHORIZED_SCHEMA_RETIREMENTS
        if authorization.revision in revision_lineage
    )
