from __future__ import annotations

import logging
import sys
from enum import Enum
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from migrations.baselines.authorized_retirements import (  # noqa: E402
    AuthorizedSchemaRetirement,
    authorized_retirements_for_lineage,
)
from migrations.baselines.fingerprint import (  # noqa: E402
    FROZEN_REVISION,
    BaselineSchemaMismatch,
    assert_frozen_schema,
    assert_frozen_schema_compatible,
)
from migrations.baselines.schema_20260713_121000 import (
    create_frozen_schema,  # noqa: E402
)

LOGGER = logging.getLogger(__name__)
_MINIMUM_MANAGED_TABLES = frozenset({"test_projects", "users"})


class BootstrapDatabaseState(str, Enum):
    EMPTY = "empty"
    MANAGED = "managed"
    UNVERSIONED = "unversioned"
    UNKNOWN_REVISION = "unknown_revision"
    VERSIONED_EMPTY_OR_INCONSISTENT = "versioned_empty_or_inconsistent"


class BaselineRevisionRelationship(str, Enum):
    EXACT = "exact"
    DESCENDANT = "descendant"
    ANCESTOR = "ancestor"
    UNRELATED = "unrelated"


class BootstrapDatabaseError(RuntimeError):
    """A database state that requires explicit operator remediation."""

    def __init__(self, state: BootstrapDatabaseState, detail: str) -> None:
        self.state = state
        super().__init__(f"database bootstrap blocked [{state.value}]: {detail}")


def _alembic_config() -> Config:
    from app.core.config import get_settings

    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(PROJECT_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", get_settings().database_url)
    config.attributes["database_url"] = get_settings().database_url
    return config


def _database_url(config: Config) -> str:
    return str(config.get_main_option("sqlalchemy.url"))


def _read_alembic_revisions(database_url: str) -> list[str]:
    engine = create_engine(database_url, future=True)
    try:
        with engine.connect() as connection:
            inspector = inspect(connection)
            if not inspector.has_table("alembic_version"):
                return []
            rows = connection.execute(text("SELECT version_num FROM alembic_version")).fetchall()
        return [str(row[0]).strip() for row in rows if row and str(row[0]).strip()]
    finally:
        engine.dispose()


def _database_tables(database_url: str) -> set[str]:
    engine = create_engine(database_url, future=True)
    try:
        with engine.connect() as connection:
            return set(inspect(connection).get_table_names())
    finally:
        engine.dispose()


def _revision_exists(config: Config, revision: str) -> bool:
    script_directory = ScriptDirectory.from_config(config)
    try:
        return script_directory.get_revision(revision) is not None
    except Exception:
        return False


def _classify_database(config: Config, database_url: str) -> BootstrapDatabaseState:
    tables = _database_tables(database_url)
    has_version_table = "alembic_version" in tables
    user_tables = tables - {"alembic_version"}
    revisions = _read_alembic_revisions(database_url)

    if not user_tables and not has_version_table:
        return BootstrapDatabaseState.EMPTY
    if user_tables and not has_version_table:
        return BootstrapDatabaseState.UNVERSIONED
    if not revisions or len(revisions) != 1 or not user_tables:
        return BootstrapDatabaseState.VERSIONED_EMPTY_OR_INCONSISTENT
    if not _revision_exists(config, revisions[0]):
        return BootstrapDatabaseState.UNKNOWN_REVISION
    return BootstrapDatabaseState.MANAGED


def _revision_relationship_to_baseline(
    config: Config,
    revision: str,
) -> BaselineRevisionRelationship:
    if revision == FROZEN_REVISION:
        return BaselineRevisionRelationship.EXACT
    revision_lineage = _revision_lineage(config, revision)
    baseline_lineage = _revision_lineage(config, FROZEN_REVISION)
    if revision_lineage is None or baseline_lineage is None:
        return BaselineRevisionRelationship.UNRELATED
    if FROZEN_REVISION in revision_lineage:
        return BaselineRevisionRelationship.DESCENDANT
    if revision in baseline_lineage:
        return BaselineRevisionRelationship.ANCESTOR
    return BaselineRevisionRelationship.UNRELATED


def _revision_lineage(config: Config, revision: str) -> frozenset[str] | None:
    script_directory = ScriptDirectory.from_config(config)
    try:
        return frozenset(
            item.revision
            for item in script_directory.iterate_revisions(revision, "base")
            if item.revision
        )
    except Exception:
        return None


def _authorized_retirements_for_revision(
    config: Config,
    revision: str,
) -> tuple[AuthorizedSchemaRetirement, ...]:
    revision_lineage = _revision_lineage(config, revision)
    if revision_lineage is None:
        return ()
    return authorized_retirements_for_lineage(revision_lineage)


def _assert_managed_database_health(config: Config, database_url: str) -> None:
    revisions = _read_alembic_revisions(database_url)
    if len(revisions) != 1:
        raise BootstrapDatabaseError(
            BootstrapDatabaseState.VERSIONED_EMPTY_OR_INCONSISTENT,
            "alembic_version must contain exactly one revision",
        )

    tables = _database_tables(database_url)
    missing_minimum_tables = _MINIMUM_MANAGED_TABLES - tables
    if missing_minimum_tables:
        raise BootstrapDatabaseError(
            BootstrapDatabaseState.VERSIONED_EMPTY_OR_INCONSISTENT,
            "managed database is missing required tables: "
            f"{', '.join(sorted(missing_minimum_tables))}",
        )

    revision = revisions[0]
    relationship = _revision_relationship_to_baseline(config, revision)
    if relationship is BaselineRevisionRelationship.ANCESTOR:
        return
    if relationship is BaselineRevisionRelationship.UNRELATED:
        raise BootstrapDatabaseError(
            BootstrapDatabaseState.VERSIONED_EMPTY_OR_INCONSISTENT,
            f"managed revision {revision} is unrelated to frozen baseline "
            f"{FROZEN_REVISION}",
        )

    engine = create_engine(database_url, future=True)
    try:
        with engine.connect() as connection:
            if relationship is BaselineRevisionRelationship.EXACT:
                assert_frozen_schema(connection)
            else:
                assert_frozen_schema_compatible(
                    connection,
                    authorized_retirements=_authorized_retirements_for_revision(
                        config,
                        revision,
                    ),
                )
    except BaselineSchemaMismatch as exc:
        raise BootstrapDatabaseError(
            BootstrapDatabaseState.VERSIONED_EMPTY_OR_INCONSISTENT,
            str(exc),
        ) from exc
    finally:
        engine.dispose()


def _install_frozen_baseline(config: Config, database_url: str) -> None:
    engine = create_engine(database_url, future=True)
    try:
        with engine.begin() as connection:
            operations = Operations(MigrationContext.configure(connection))
            create_frozen_schema(operations)
            assert_frozen_schema(connection)
    except BaselineSchemaMismatch as exc:
        raise BootstrapDatabaseError(
            BootstrapDatabaseState.VERSIONED_EMPTY_OR_INCONSISTENT,
            str(exc),
        ) from exc
    finally:
        engine.dispose()

    command.stamp(config, FROZEN_REVISION)


def _bootstrap_database(config: Config, database_url: str) -> None:
    state = _classify_database(config, database_url)
    if state is BootstrapDatabaseState.EMPTY:
        _install_frozen_baseline(config, database_url)
        command.upgrade(config, "head")
        _assert_managed_database_health(config, database_url)
        LOGGER.info("database bootstrap completed from frozen revision %s", FROZEN_REVISION)
        return

    if state is BootstrapDatabaseState.MANAGED:
        _assert_managed_database_health(config, database_url)
        command.upgrade(config, "head")
        _assert_managed_database_health(config, database_url)
        LOGGER.info("managed database upgraded through Alembic")
        return

    if state is BootstrapDatabaseState.UNVERSIONED:
        raise BootstrapDatabaseError(
            state,
            "user tables exist without alembic_version; manual database adoption is required",
        )
    if state is BootstrapDatabaseState.UNKNOWN_REVISION:
        raise BootstrapDatabaseError(
            state,
            "alembic_version references a revision absent from this repository",
        )
    raise BootstrapDatabaseError(
        state,
        "alembic_version exists but the database schema is empty or inconsistent",
    )


def main() -> None:
    config = _alembic_config()
    _bootstrap_database(config, _database_url(config))


if __name__ == "__main__":
    main()
