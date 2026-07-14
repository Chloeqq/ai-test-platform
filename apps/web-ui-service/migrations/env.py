from __future__ import annotations

from logging.config import fileConfig
import os

from alembic import context
from sqlalchemy import engine_from_config, inspect, pool

from app.core.config import get_settings
from app.core.database import Base
import app.models  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = get_settings()
database_url = str(config.attributes.get("database_url") or settings.database_url)
config.set_main_option("sqlalchemy.url", database_url)

target_metadata = Base.metadata


def _legacy_empty_database_upgrade_allowed() -> bool:
    value = os.getenv("ALLOW_LEGACY_EMPTY_DB_ALEMBIC_UPGRADE", "")
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _has_migration_destination() -> bool:
    try:
        return context.get_revision_argument() is not None
    except (KeyError, TypeError):
        return False


def _assert_empty_database_uses_deterministic_bootstrap(connection) -> None:
    """Block raw migration commands from invoking the dynamic legacy root."""
    if _legacy_empty_database_upgrade_allowed() or not _has_migration_destination():
        return

    table_names = set(inspect(connection).get_table_names())
    if not table_names:
        raise RuntimeError(
            "empty database migrations are blocked; use "
            "scripts/bootstrap_database.py for the deterministic baseline. "
            "Set ALLOW_LEGACY_EMPTY_DB_ALEMBIC_UPGRADE=1 only for an "
            "explicit legacy maintenance operation."
        )


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        _assert_empty_database_uses_deterministic_bootstrap(connection)
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()
        if connection.in_transaction():
            connection.commit()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
