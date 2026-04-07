from __future__ import annotations

from pathlib import Path
import sys

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

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


def _has_alembic_version_table(database_url: str) -> bool:
    engine = create_engine(database_url, future=True)
    with engine.connect() as conn:
        return bool(inspect(conn).has_table("alembic_version"))


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


def main() -> None:
    config = _alembic_config()
    database_url = _database_url(config)

    if _has_alembic_version_table(database_url):
        command.upgrade(config, "head")
        print("database bootstrap: alembic_version exists, upgraded to head")
        return

    if not _has_any_user_table(database_url):
        command.upgrade(config, "head")
        print("database bootstrap: empty database, upgraded to head")
        return

    _create_current_metadata(database_url)
    command.stamp(config, "head")
    print("database bootstrap: legacy database stamped to head after metadata sync")


if __name__ == "__main__":
    main()
