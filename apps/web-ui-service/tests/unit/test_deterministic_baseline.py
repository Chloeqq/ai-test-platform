from __future__ import annotations

import ast
from copy import deepcopy
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from migrations.baselines import fingerprint
from migrations.baselines.authorized_retirements import (
    AuthorizedSchemaRetirement,
    column_ref,
    foreign_key_ref,
    index_ref,
    require_column,
    require_foreign_key,
    require_table,
    require_unique_constraint,
)
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


def _phase1_source_retirement() -> AuthorizedSchemaRetirement:
    source_table = "test_asset_sources"
    replacement_table = "test_asset_requirement_sources"
    return AuthorizedSchemaRetirement(
        revision="phase1_revision",
        retired_objects=frozenset(
            {
                column_ref(source_table, "requirement_pk"),
                column_ref(source_table, "requirement_version_pk"),
                foreign_key_ref(
                    source_table,
                    ("requirement_pk",),
                    "requirements",
                    ("id",),
                ),
                foreign_key_ref(
                    source_table,
                    ("requirement_version_pk",),
                    "requirement_versions",
                    ("id",),
                ),
                index_ref(source_table, ("requirement_pk",), unique=False),
                index_ref(
                    source_table,
                    ("requirement_version_pk",),
                    unique=False,
                ),
            }
        ),
        replacement_objects=frozenset(
            {
                require_table(replacement_table),
                require_column(
                    replacement_table,
                    "test_asset_source_pk",
                    logical_type="integer",
                    nullable=False,
                ),
                require_column(
                    replacement_table,
                    "requirement_pk",
                    logical_type="integer",
                    nullable=False,
                ),
                require_column(
                    replacement_table,
                    "requirement_version_pk",
                    logical_type="integer",
                    nullable=False,
                ),
                require_foreign_key(
                    replacement_table,
                    ("test_asset_source_pk",),
                    source_table,
                    ("id",),
                ),
                require_foreign_key(
                    replacement_table,
                    ("requirement_pk",),
                    "requirements",
                    ("id",),
                ),
                require_foreign_key(
                    replacement_table,
                    ("requirement_version_pk",),
                    "requirement_versions",
                    ("id",),
                ),
                require_unique_constraint(
                    replacement_table,
                    ("test_asset_source_pk",),
                ),
            }
        ),
    )


def _apply_phase1_source_shape(connection) -> None:
    operations = Operations(MigrationContext.configure(connection))
    with operations.batch_alter_table(
        "test_asset_sources",
        recreate="always",
    ) as batch:
        batch.drop_index("ix_test_asset_sources_requirement_pk")
        batch.drop_index("ix_test_asset_sources_requirement_version_pk")
        batch.drop_constraint(
            "fk_test_asset_sources_requirement_pk_requirements",
            type_="foreignkey",
        )
        batch.drop_constraint(
            "fk_test_asset_sources_req_version_pk_requirement_versions",
            type_="foreignkey",
        )
        batch.drop_column("requirement_pk")
        batch.drop_column("requirement_version_pk")
    operations.create_table(
        "test_asset_requirement_sources",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("test_asset_source_pk", sa.Integer(), nullable=False),
        sa.Column("requirement_pk", sa.Integer(), nullable=False),
        sa.Column("requirement_version_pk", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["test_asset_source_pk"],
            ["test_asset_sources.id"],
            name="fk_req_sources_source_pk_sources",
        ),
        sa.ForeignKeyConstraint(
            ["requirement_pk"],
            ["requirements.id"],
            name="fk_req_sources_requirement_pk_requirements",
        ),
        sa.ForeignKeyConstraint(
            ["requirement_version_pk"],
            ["requirement_versions.id"],
            name="fk_req_sources_req_version_pk_versions",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_test_asset_requirement_sources"),
        sa.UniqueConstraint(
            "test_asset_source_pk",
            name="uq_req_sources_test_asset_source_pk",
        ),
    )


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


def test_sqlite_authorized_retirement_requires_its_replacement_shape() -> None:
    engine, connection, transaction = _create_frozen_sqlite_schema()
    try:
        _apply_phase1_source_shape(connection)
        authorization = _phase1_source_retirement()

        assert_frozen_schema_compatible(
            connection,
            authorized_retirements=(authorization,),
        )
        with pytest.raises(BaselineSchemaMismatch, match="missing column"):
            assert_frozen_schema_compatible(connection)

        connection.execute(text("DROP TABLE test_asset_requirement_sources"))
        with pytest.raises(BaselineSchemaMismatch, match="missing replacement table"):
            assert_frozen_schema_compatible(
                connection,
                authorized_retirements=(authorization,),
            )
    finally:
        transaction.rollback()
        connection.close()
        engine.dispose()


def test_authorized_retirement_does_not_hide_other_frozen_drift() -> None:
    engine, connection, transaction = _create_frozen_sqlite_schema()
    try:
        _apply_phase1_source_shape(connection)
        connection.execute(text("DROP TABLE users"))

        with pytest.raises(BaselineSchemaMismatch, match="missing table users"):
            assert_frozen_schema_compatible(
                connection,
                authorized_retirements=(_phase1_source_retirement(),),
            )
    finally:
        transaction.rollback()
        connection.close()
        engine.dispose()


def test_retirement_authorization_must_reference_frozen_objects() -> None:
    authorization = AuthorizedSchemaRetirement(
        revision="invalid_revision",
        retired_objects=frozenset({column_ref("test_assets", "not_frozen")}),
        replacement_objects=frozenset({require_table("test_assets")}),
    )

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(
            fingerprint,
            "normalize_schema",
            lambda _connection: deepcopy(load_frozen_manifest()),
        )
        with pytest.raises(BaselineSchemaMismatch, match="references non-frozen object"):
            assert_frozen_schema_compatible(
                object(),  # type: ignore[arg-type]
                authorized_retirements=(authorization,),
            )


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


def test_authorized_retirement_manifest_has_no_runtime_dependencies() -> None:
    manifest_path = (
        Path(__file__).resolve().parents[2]
        / "migrations"
        / "baselines"
        / "authorized_retirements.py"
    )
    tree = ast.parse(manifest_path.read_text(encoding="utf-8"))
    imported_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }

    assert not any(module.startswith("app.") for module in imported_modules)
    source = manifest_path.read_text(encoding="utf-8")
    assert "from app" not in source
    assert "import app" not in source
    assert "Base.metadata" not in source
