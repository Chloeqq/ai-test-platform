from __future__ import annotations

import ast
from copy import deepcopy
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from migrations.baselines import fingerprint
from migrations.baselines.fingerprint import (
    BaselineSchemaMismatch,
    _normalize_check_expression,
    _normalize_logical_type,
    assert_frozen_schema,
    assert_frozen_schema_compatible,
    frozen_schema_fingerprint,
    load_frozen_manifest,
    schema_fingerprint,
)
from migrations.baselines.schema_20260713_121000 import (
    FROZEN_REVISION,
    SCHEMA_SNAPSHOT_VERSION,
    create_frozen_schema,
)
from sqlalchemy import create_engine, create_mock_engine, text
from sqlalchemy.dialects import postgresql


def _create_frozen_sqlite_schema():
    engine = create_engine("sqlite://", future=True)
    connection = engine.connect()
    transaction = connection.begin()
    create_frozen_schema(Operations(MigrationContext.configure(connection)))
    return engine, connection, transaction


def test_frozen_baseline_creates_the_approved_sqlite_schema() -> None:
    engine, connection, transaction = _create_frozen_sqlite_schema()
    try:
        assert FROZEN_REVISION == "20260713_121000"
        assert SCHEMA_SNAPSHOT_VERSION == 1
        assert_frozen_schema(connection)
        assert schema_fingerprint(connection) == frozen_schema_fingerprint()
    finally:
        transaction.rollback()
        connection.close()
        engine.dispose()


def test_frozen_baseline_detects_schema_drift() -> None:
    engine, connection, transaction = _create_frozen_sqlite_schema()
    try:
        connection.execute(text("DROP TABLE users"))

        with pytest.raises(BaselineSchemaMismatch, match="does not match frozen baseline"):
            assert_frozen_schema(connection)
    finally:
        transaction.rollback()
        connection.close()
        engine.dispose()


def test_sqlite_schema_after_frozen_revision_allows_additive_changes() -> None:
    engine, connection, transaction = _create_frozen_sqlite_schema()
    try:
        connection.execute(text("ALTER TABLE test_assets ADD COLUMN future_note TEXT"))
        connection.execute(
            text("CREATE INDEX ix_test_assets_future_note ON test_assets (future_note)")
        )
        connection.execute(
            text("CREATE TABLE future_asset_metadata (id INTEGER PRIMARY KEY)")
        )

        assert_frozen_schema_compatible(connection)
        with pytest.raises(BaselineSchemaMismatch, match="does not match frozen baseline"):
            assert_frozen_schema(connection)
    finally:
        transaction.rollback()
        connection.close()
        engine.dispose()


def test_compatible_schema_still_rejects_changed_frozen_column() -> None:
    expected = load_frozen_manifest()
    actual = deepcopy(expected)
    actual["tables"]["test_assets"]["columns"][0]["nullable"] = True

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(fingerprint, "normalize_schema", lambda _connection: actual)
        with pytest.raises(BaselineSchemaMismatch, match="changed column test_assets.id"):
            assert_frozen_schema_compatible(object())  # type: ignore[arg-type]


def test_postgresql_normalized_schema_allows_future_tables_columns_and_indexes() -> None:
    actual = deepcopy(load_frozen_manifest())
    test_assets = actual["tables"]["test_assets"]
    test_assets["columns"].append(
        {
            "name": "future_metadata",
            "type": _normalize_logical_type(
                postgresql.JSONB(),
                is_primary_key=False,
            ),
            "nullable": True,
            "primary_key": False,
            "server_default": None,
        }
    )
    test_assets["indexes"].append(
        {"columns": ["future_metadata"], "unique": False}
    )
    actual["tables"]["future_asset_events"] = {
        "columns": [],
        "primary_key": [],
        "foreign_keys": [],
        "unique_constraints": [],
        "check_constraints": [],
        "indexes": [],
    }

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(fingerprint, "normalize_schema", lambda _connection: actual)
        assert_frozen_schema_compatible(object())  # type: ignore[arg-type]


def test_frozen_baseline_compiles_for_postgresql() -> None:
    statements: list[str] = []

    def _capture(statement, *_args, **_kwargs) -> None:
        statements.append(str(statement.compile(dialect=postgresql.dialect())))

    engine = create_mock_engine("postgresql+psycopg2://", _capture)
    connection = engine.connect()
    create_frozen_schema(Operations(MigrationContext.configure(connection)))

    assert any("CREATE TABLE requirements" in statement for statement in statements)
    assert any("CREATE TABLE test_assets" in statement for statement in statements)


def test_postgresql_reflection_is_normalized_to_baseline_semantics() -> None:
    assert _normalize_logical_type(
        postgresql.DOUBLE_PRECISION(),
        is_primary_key=False,
    ) == "number"
    assert _normalize_check_expression(
        "status::text = ANY (ARRAY['draft'::character varying, 'active'::character varying]::text[])"
    ) == "status IN ('draft', 'active')"


def test_frozen_baseline_has_no_runtime_orm_imports() -> None:
    baseline_path = (
        Path(__file__).resolve().parents[2]
        / "migrations"
        / "baselines"
        / "schema_20260713_121000.py"
    )
    tree = ast.parse(baseline_path.read_text(encoding="utf-8"))
    imported_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    imported_names = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }

    assert "app.models" not in imported_modules
    assert "app.core.database" not in imported_modules
    assert "app.models" not in imported_names
    assert "app.core.database" not in imported_names

    source = baseline_path.read_text(encoding="utf-8")
    assert "metadata.create_all" not in source
