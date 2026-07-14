from __future__ import annotations

import os
from pathlib import Path
import sqlite3
import subprocess
import sys


SERVICE_ROOT = Path(__file__).resolve().parents[2]


def _run_alembic(database_path: Path, *arguments: str, allow_legacy: bool = False) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["DATABASE_URL"] = f"sqlite:///{database_path}"
    if allow_legacy:
        environment["ALLOW_LEGACY_EMPTY_DB_ALEMBIC_UPGRADE"] = "1"
    else:
        environment.pop("ALLOW_LEGACY_EMPTY_DB_ALEMBIC_UPGRADE", None)
    return subprocess.run(
        [sys.executable, "-m", "alembic", *arguments],
        cwd=SERVICE_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_raw_alembic_upgrade_rejects_an_empty_database(tmp_path: Path) -> None:
    database_path = tmp_path / "empty.db"
    result = _run_alembic(database_path, "upgrade", "head")

    assert result.returncode != 0
    assert "empty database migrations are blocked" in result.stderr
    assert "bootstrap_database.py" in result.stderr

    connection = sqlite3.connect(database_path)
    try:
        tables = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    finally:
        connection.close()
    assert tables == []


def test_alembic_current_remains_read_only_for_an_empty_database(tmp_path: Path) -> None:
    database_path = tmp_path / "empty-current.db"

    result = _run_alembic(database_path, "current")

    assert result.returncode == 0
    if database_path.exists():
        assert _sqlite_table_names(database_path) == set()


def test_explicit_legacy_override_is_required_to_upgrade_an_empty_database(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "legacy-override.db"

    result = _run_alembic(
        database_path,
        "upgrade",
        "head",
        allow_legacy=True,
    )

    assert result.returncode == 0
    connection = sqlite3.connect(database_path)
    try:
        revision = connection.execute(
            "SELECT version_num FROM alembic_version"
        ).fetchone()[0]
    finally:
        connection.close()
    assert revision == "20260713_121000"


def _sqlite_table_names(database_path: Path) -> set[str]:
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
