from __future__ import annotations

import ast
import importlib.util
import sqlite3
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from migrations.baselines import authorized_retirements
from migrations.baselines.authorized_retirements import (
    AuthorizedSchemaRetirement,
    require_table,
)
from migrations.baselines.fingerprint import assert_frozen_schema
from sqlalchemy import create_engine, text

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

    assert revision == "20260713_121000"
    engine = create_engine(_database_url(database_path), future=True)
    try:
        with engine.connect() as connection:
            assert_frozen_schema(connection)
    finally:
        engine.dispose()


def test_empty_bootstrap_validates_schema_after_upgrade(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(
        bootstrap_database,
        "_classify_database",
        lambda _config, _database_url: bootstrap_database.BootstrapDatabaseState.EMPTY,
    )
    monkeypatch.setattr(
        bootstrap_database,
        "_install_frozen_baseline",
        lambda _config, _database_url: calls.append("install"),
    )
    monkeypatch.setattr(
        bootstrap_database.command,
        "upgrade",
        lambda _config, _revision: calls.append("upgrade"),
    )
    monkeypatch.setattr(
        bootstrap_database,
        "_assert_managed_database_health",
        lambda _config, _database_url: calls.append("health"),
    )

    bootstrap_database._bootstrap_database(object(), "sqlite://")

    assert calls == ["install", "upgrade", "health"]


def test_managed_bootstrap_validates_schema_before_and_after_upgrade(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(
        bootstrap_database,
        "_classify_database",
        lambda _config, _database_url: bootstrap_database.BootstrapDatabaseState.MANAGED,
    )
    monkeypatch.setattr(
        bootstrap_database,
        "_assert_managed_database_health",
        lambda _config, _database_url: calls.append("health"),
    )
    monkeypatch.setattr(
        bootstrap_database.command,
        "upgrade",
        lambda _config, _revision: calls.append("upgrade"),
    )

    bootstrap_database._bootstrap_database(object(), "sqlite://")

    assert calls == ["health", "upgrade", "health"]


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
                text("INSERT INTO alembic_version (version_num) VALUES ('20260713_121000')")
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


def test_managed_database_after_baseline_allows_additive_schema_changes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_path = tmp_path / "future-managed.db"
    config = _alembic_config(database_path)
    database_url = _database_url(database_path)
    bootstrap_database._bootstrap_database(config, database_url)

    engine = create_engine(database_url, future=True)
    try:
        with engine.begin() as connection:
            connection.execute(
                text("ALTER TABLE test_assets ADD COLUMN future_note TEXT")
            )
            connection.execute(
                text(
                    "CREATE INDEX ix_test_assets_future_note "
                    "ON test_assets (future_note)"
                )
            )
            connection.execute(
                text("CREATE TABLE future_asset_metadata (id INTEGER PRIMARY KEY)")
            )
    finally:
        engine.dispose()

    monkeypatch.setattr(
        bootstrap_database,
        "_read_alembic_revisions",
        lambda _database_url: ["future_revision"],
    )
    monkeypatch.setattr(
        bootstrap_database,
        "_revision_relationship_to_baseline",
        lambda _config, _revision: (
            bootstrap_database.BaselineRevisionRelationship.DESCENDANT
        ),
    )

    bootstrap_database._assert_managed_database_health(config, database_url)


def test_revision_relationship_uses_alembic_graph(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frozen_revision = bootstrap_database.FROZEN_REVISION
    ancestor_revision = "ancestor_revision"
    descendant_revision = "descendant_revision"
    unrelated_revision = "unrelated_revision"

    class RevisionNode:
        def __init__(self, revision: str) -> None:
            self.revision = revision

    class FakeScriptDirectory:
        lineages = {
            frozen_revision: [frozen_revision, ancestor_revision],
            ancestor_revision: [ancestor_revision],
            descendant_revision: [descendant_revision, frozen_revision, ancestor_revision],
            unrelated_revision: [unrelated_revision],
        }

        def iterate_revisions(self, revision: str, _lower: str):
            return [RevisionNode(item) for item in self.lineages[revision]]

    monkeypatch.setattr(
        ScriptDirectory,
        "from_config",
        lambda _config: FakeScriptDirectory(),
    )

    relationship = bootstrap_database.BaselineRevisionRelationship
    assert bootstrap_database._revision_relationship_to_baseline(
        object(), frozen_revision
    ) is relationship.EXACT
    assert bootstrap_database._revision_relationship_to_baseline(
        object(), descendant_revision
    ) is relationship.DESCENDANT
    assert bootstrap_database._revision_relationship_to_baseline(
        object(), ancestor_revision
    ) is relationship.ANCESTOR
    assert bootstrap_database._revision_relationship_to_baseline(
        object(), unrelated_revision
    ) is relationship.UNRELATED


def test_retirement_authorization_uses_alembic_revision_lineage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frozen_revision = bootstrap_database.FROZEN_REVISION
    retirement_revision = "retirement_revision"
    later_revision = "later_revision"
    authorization = AuthorizedSchemaRetirement(
        revision=retirement_revision,
        retired_objects=frozenset(),
        replacement_objects=frozenset({require_table("replacement_table")}),
    )

    class RevisionNode:
        def __init__(self, revision: str) -> None:
            self.revision = revision

    class FakeScriptDirectory:
        lineages = {
            frozen_revision: [frozen_revision],
            retirement_revision: [retirement_revision, frozen_revision],
            later_revision: [later_revision, retirement_revision, frozen_revision],
        }

        def iterate_revisions(self, revision: str, _lower: str):
            return [RevisionNode(item) for item in self.lineages[revision]]

    monkeypatch.setattr(
        ScriptDirectory,
        "from_config",
        lambda _config: FakeScriptDirectory(),
    )
    monkeypatch.setattr(
        authorized_retirements,
        "AUTHORIZED_SCHEMA_RETIREMENTS",
        (authorization,),
    )

    assert bootstrap_database._authorized_retirements_for_revision(
        object(),
        frozen_revision,
    ) == ()
    assert bootstrap_database._authorized_retirements_for_revision(
        object(),
        retirement_revision,
    ) == (authorization,)
    assert bootstrap_database._authorized_retirements_for_revision(
        object(),
        later_revision,
    ) == (authorization,)


def test_descendant_health_check_passes_lineage_authorization_to_fingerprint(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_path = tmp_path / "authorized-descendant.db"
    config = _alembic_config(database_path)
    database_url = _database_url(database_path)
    bootstrap_database._bootstrap_database(config, database_url)
    authorization = AuthorizedSchemaRetirement(
        revision="retirement_revision",
        retired_objects=frozenset(),
        replacement_objects=frozenset({require_table("replacement_table")}),
    )
    received: list[tuple[AuthorizedSchemaRetirement, ...]] = []

    monkeypatch.setattr(
        bootstrap_database,
        "_read_alembic_revisions",
        lambda _database_url: ["later_revision"],
    )
    monkeypatch.setattr(
        bootstrap_database,
        "_revision_relationship_to_baseline",
        lambda _config, _revision: (
            bootstrap_database.BaselineRevisionRelationship.DESCENDANT
        ),
    )
    monkeypatch.setattr(
        bootstrap_database,
        "_authorized_retirements_for_revision",
        lambda _config, _revision: (authorization,),
    )
    monkeypatch.setattr(
        bootstrap_database,
        "assert_frozen_schema_compatible",
        lambda _connection, *, authorized_retirements: received.append(
            authorized_retirements
        ),
    )

    bootstrap_database._assert_managed_database_health(config, database_url)

    assert received == [(authorization,)]


def test_unrelated_managed_revision_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_path = tmp_path / "unrelated-managed.db"
    config = _alembic_config(database_path)
    database_url = _database_url(database_path)
    bootstrap_database._bootstrap_database(config, database_url)

    monkeypatch.setattr(
        bootstrap_database,
        "_read_alembic_revisions",
        lambda _database_url: ["unrelated_revision"],
    )
    monkeypatch.setattr(
        bootstrap_database,
        "_revision_relationship_to_baseline",
        lambda _config, _revision: (
            bootstrap_database.BaselineRevisionRelationship.UNRELATED
        ),
    )

    with pytest.raises(
        bootstrap_database.BootstrapDatabaseError,
        match="is unrelated to frozen baseline",
    ):
        bootstrap_database._assert_managed_database_health(config, database_url)


def test_database_at_frozen_revision_still_requires_exact_schema(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "frozen-with-extra-table.db"
    config = _alembic_config(database_path)
    database_url = _database_url(database_path)
    bootstrap_database._bootstrap_database(config, database_url)

    engine = create_engine(database_url, future=True)
    try:
        with engine.begin() as connection:
            connection.execute(
                text("CREATE TABLE unexpected_at_frozen_revision (id INTEGER PRIMARY KEY)")
            )
    finally:
        engine.dispose()

    with pytest.raises(
        bootstrap_database.BootstrapDatabaseError,
        match=r"\[versioned_empty_or_inconsistent\]",
    ):
        bootstrap_database._assert_managed_database_health(config, database_url)


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
