from __future__ import annotations

from pathlib import Path
import sys

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _alembic_config() -> Config:
    repo_root = Path(__file__).resolve().parents[1]
    from app.core.config import get_settings

    config = Config(str(repo_root / "alembic.ini"))
    config.set_main_option("script_location", str(repo_root / "migrations"))
    config.set_main_option("sqlalchemy.url", get_settings().database_url)
    return config


def _database_url(config: Config) -> str:
    return str(config.get_main_option("sqlalchemy.url"))


def _read_alembic_revisions(database_url: str) -> list[str]:
    engine = create_engine(database_url, future=True)
    with engine.connect() as conn:
        if not inspect(conn).has_table("alembic_version"):
            return []
        rows = conn.execute(text("SELECT version_num FROM alembic_version")).fetchall()
    return [str(row[0]).strip() for row in rows if row and str(row[0]).strip()]


def _has_any_user_table(database_url: str) -> bool:
    engine = create_engine(database_url, future=True)
    with engine.connect() as conn:
        tables = [name for name in inspect(conn).get_table_names() if str(name).strip() and name != "alembic_version"]
    return bool(tables)


def _create_current_metadata(database_url: str) -> None:
    from app.core.database import Base
    import app.models  # noqa: F401

    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(bind=engine)


def _revision_exists(config: Config, revision: str) -> bool:
    script_directory = ScriptDirectory.from_config(config)
    try:
        return script_directory.get_revision(revision) is not None
    except Exception:
        return False


def _current_head_revision(config: Config) -> str:
    script_directory = ScriptDirectory.from_config(config)
    head_revision = script_directory.get_current_head()
    if not head_revision:
        raise RuntimeError("No Alembic head revision found")
    return str(head_revision).strip()


def _stamp_database_head(database_url: str, revision: str) -> None:
    engine = create_engine(database_url, future=True)
    with engine.begin() as conn:
        if not inspect(conn).has_table("alembic_version"):
            conn.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(255) NOT NULL)"))
        conn.execute(text("DELETE FROM alembic_version"))
        conn.execute(
            text("INSERT INTO alembic_version (version_num) VALUES (:version_num)"),
            {"version_num": revision},
        )


def _ensure_alembic_version_capacity(database_url: str) -> None:
    engine = create_engine(database_url, future=True)
    with engine.begin() as conn:
        inspector = inspect(conn)
        if not inspector.has_table("alembic_version"):
            conn.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(255) NOT NULL)"))
            return
        if engine.dialect.name == "postgresql":
            conn.execute(text("ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(255)"))


def _sync_current_metadata(config: Config, database_url: str, reason: str) -> None:
    _ensure_alembic_version_capacity(database_url)
    _create_current_metadata(database_url)
    _stamp_database_head(database_url, _current_head_revision(config))
    print(f"database bootstrap: {reason}, synced current metadata and stamped head")


def _bootstrap_database(config: Config, database_url: str) -> None:
    _ensure_alembic_version_capacity(database_url)
    current_revisions = _read_alembic_revisions(database_url)
    if current_revisions:
        missing_revisions = [revision for revision in current_revisions if not _revision_exists(config, revision)]
        if missing_revisions:
            _sync_current_metadata(
                config,
                database_url,
                f"alembic_version has missing revisions: {', '.join(missing_revisions)}",
            )
            return
        command.upgrade(config, "head")
        print("database bootstrap: alembic_version exists, upgraded to head")
        return

    if not _has_any_user_table(database_url):
        command.upgrade(config, "head")
        print("database bootstrap: empty database, upgraded to head")
        return

    _sync_current_metadata(config, database_url, "legacy database detected without alembic version")


def main() -> None:
    config = _alembic_config()
    database_url = _database_url(config)
    _bootstrap_database(config, database_url)


if __name__ == "__main__":
    main()
