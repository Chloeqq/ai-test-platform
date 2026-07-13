from __future__ import annotations

import ast
import importlib.util
from pathlib import Path
import sqlite3

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, text

from migrations.baselines.fingerprint import assert_frozen_schema


SERVICE_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = SERVICE_ROOT / "scripts" / "bootstrap_database.py"
SPEC = importlib.util.spec_from_file_location("bootstrap_database", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
bootstrap_database = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bootstrap_database)


def _alembic_config(database_path: Path) -> Config:
    config = Config(str(SERVICE_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(SERVICE_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database_path}")
    config.attributes["database_url"] = f"sqlite:///{database_path}"
    return config


def _database_url(database_path: Path) -> str:
    return f"sqlite:///{database_path}"


def _table_names(database_path: Path) -> set[str]:
    connection = sqlite3.connect(database_path)
    try:
        return {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
    finally:
        connection.close()


def test_empty_database_uses_frozen_baseline_then_stamps_revision(tmp_path: Path) -> None:
    database_path = tmp_path / "empty.db"
    config = _alembic_config(database_path)

    bootstrap_database._bootstrap_database(config, _database_url(database_path))

    connection = sqlite3.connect(database_path)
    try:
        revision = connection.execute(
            "SELECT version_num FROM alembic_version"
        ).fetchone()[0]
    finally:
        connection.close()

    assert revision == "20260713_120000"
    engine = create_engine(_database_url(database_path), future=True)
    try:
        with engine.connect() as connection:
            assert_frozen_schema(connection)
    finally:
        engine.dispose()


def test_unversioned_database_fails_without_creating_a_version_record(tmp_path: Path) -> None:
    database_path = tmp_path / "unversioned.db"
    engine = create_engine(_database_url(database_path), future=True)
    try:
        with engine.begin() as connection:
            connection.execute(text("CREATE TABLE legacy_data (id INTEGER PRIMARY KEY)"))
    finally:
        engine.dispose()

    with pytest.raises(
        bootstrap_database.BootstrapDatabaseError,
        match=r"\[unversioned\]",
    ):
        bootstrap_database._bootstrap_database(
            _alembic_config(database_path),
            _database_url(database_path),
        )

    assert _table_names(database_path) == {"legacy_data"}


def test_unknown_revision_database_fails_without_schema_repair(tmp_path: Path) -> None:
    database_path = tmp_path / "unknown-revision.db"
    engine = create_engine(_database_url(database_path), future=True)
    try:
        with engine.begin() as connection:
            connection.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY)"))
            connection.execute(
                text("CREATE TABLE test_projects (id INTEGER PRIMARY KEY)")
            )
            connection.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(255))"))
            connection.execute(
                text("INSERT INTO alembic_version (version_num) VALUES ('missing_revision')")
            )
    finally:
        engine.dispose()

    with pytest.raises(
        bootstrap_database.BootstrapDatabaseError,
        match=r"\[unknown_revision\]",
    ):
        bootstrap_database._bootstrap_database(
            _alembic_config(database_path),
            _database_url(database_path),
        )

    assert _table_names(database_path) == {"alembic_version", "test_projects", "users"}


def test_versioned_database_with_baseline_revision_and_missing_schema_fails_closed(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "inconsistent.db"
    engine = create_engine(_database_url(database_path), future=True)
    try:
        with engine.begin() as connection:
            connection.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY)"))
            connection.execute(
                text("CREATE TABLE test_projects (id INTEGER PRIMARY KEY)")
            )
            connection.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(255))"))
            connection.execute(
                text("INSERT INTO alembic_version (version_num) VALUES ('20260713_120000')")
            )
    finally:
        engine.dispose()

    with pytest.raises(
        bootstrap_database.BootstrapDatabaseError,
        match=r"\[versioned_empty_or_inconsistent\]",
    ):
        bootstrap_database._bootstrap_database(
            _alembic_config(database_path),
            _database_url(database_path),
        )

    assert _table_names(database_path) == {"alembic_version", "test_projects", "users"}


def test_bootstrap_has_no_runtime_metadata_repair_path() -> None:
    tree = ast.parse(SCRIPT_PATH.read_text(encoding="utf-8"))
    imported_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    source = SCRIPT_PATH.read_text(encoding="utf-8")

    assert "app.models" not in imported_modules
    assert "app.core.database" not in imported_modules
    assert "metadata.create_all" not in source
