from __future__ import annotations

import ast
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text

from migrations.baselines.fingerprint import (
    BaselineSchemaMismatch,
    assert_frozen_schema,
    frozen_schema_fingerprint,
    schema_fingerprint,
)
from migrations.baselines.schema_20260713_120000 import (
    FROZEN_REVISION,
    SCHEMA_SNAPSHOT_VERSION,
    create_frozen_schema,
)


def _create_frozen_sqlite_schema():
    engine = create_engine("sqlite://", future=True)
    connection = engine.connect()
    transaction = connection.begin()
    create_frozen_schema(Operations(MigrationContext.configure(connection)))
    return engine, connection, transaction


def test_frozen_baseline_creates_the_approved_sqlite_schema() -> None:
    engine, connection, transaction = _create_frozen_sqlite_schema()
    try:
        assert FROZEN_REVISION == "20260713_120000"
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


def test_frozen_baseline_has_no_runtime_orm_imports() -> None:
    baseline_path = (
        Path(__file__).resolve().parents[2]
        / "migrations"
        / "baselines"
        / "schema_20260713_120000.py"
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
