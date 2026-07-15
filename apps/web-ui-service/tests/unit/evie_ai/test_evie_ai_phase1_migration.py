from __future__ import annotations

import ast
import importlib.util
import json
import os
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

from app.policies.evie_ai.content_fingerprint import (
    TestAssetContent as AssetContent,
)
from app.policies.evie_ai.content_fingerprint import (
    build_content_fingerprint,
)

SERVICE_ROOT = Path(__file__).resolve().parents[3]
MIGRATION_PATH = (
    SERVICE_ROOT
    / "migrations/versions/20260715_100000_evie_ai_phase1_asset_lifecycle.py"
)
PHASE0_REVISION = "20260713_121000"
PHASE1_REVISION = "20260715_100000"
PHASE1_TABLES = {
    "test_asset_requirement_sources",
    "test_asset_idempotency_records",
    "test_asset_content_claims",
    "test_asset_review_records",
    "test_asset_audit_events",
}
CONTENT = AssetContent(
    title="  Cafe\u0301  ",
    precondition=" ready \r\nnext  \r",
    natural_steps=(" first  \r\n  second  ", " keep  internal "),
    expected_result=" result  ",
    priority=" P1 ",
    tags=(" smoke ", "", "回归", "smoke", "  回归 "),
)


def _run_alembic(
    database_path: Path,
    *arguments: str,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["DATABASE_URL"] = f"sqlite:///{database_path}"
    return subprocess.run(
        [sys.executable, "-m", "alembic", *arguments],
        cwd=SERVICE_ROOT,
        env=environment,
        check=check,
        capture_output=True,
        text=True,
        timeout=120,
    )


def _run_bootstrap(database_path: Path) -> None:
    environment = os.environ.copy()
    environment["DATABASE_URL"] = f"sqlite:///{database_path}"
    subprocess.run(
        [sys.executable, "scripts/bootstrap_database.py"],
        cwd=SERVICE_ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
        timeout=120,
    )


def _prepare_phase0_database(database_path: Path) -> None:
    _run_bootstrap(database_path)
    _run_alembic(database_path, "downgrade", PHASE0_REVISION)


def _revision(connection: sqlite3.Connection) -> str:
    return str(
        connection.execute("SELECT version_num FROM alembic_version").fetchone()[0]
    )


def _table_names(connection: sqlite3.Connection) -> set[str]:
    return {
        str(row[0])
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }


def _column_names(connection: sqlite3.Connection, table_name: str) -> set[str]:
    return {
        str(row[1])
        for row in connection.execute(f'PRAGMA table_info("{table_name}")')
    }


def _seed_phase0_data(
    database_path: Path,
    *,
    duplicate_asset: bool = False,
    invalid_current_version: bool = False,
    invalid_source_ownership: bool = False,
) -> None:
    now = "2026-07-15T10:00:00+08:00"
    connection = sqlite3.connect(database_path)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(
            """
            INSERT INTO users (
                id, username, hashed_password, role, is_active, created_at, updated_at
            ) VALUES (1, 'phase1-admin', 'hash', 'admin', 1, ?, ?)
            """,
            (now, now),
        )
        connection.execute(
            """
            INSERT INTO requirements (
                id, requirement_id, project_code, requirement_code, status,
                current_version_pk, row_version, created_at, updated_at,
                created_by, updated_by
            ) VALUES (1, 'req_00000000000000000000000000000001', 'mall',
                'REQ-1', 'active', 1, 1, ?, ?, 'seed', 'seed')
            """,
            (now, now),
        )
        if invalid_source_ownership:
            connection.execute(
                """
                INSERT INTO requirements (
                    id, requirement_id, project_code, requirement_code, status,
                    current_version_pk, row_version, created_at, updated_at,
                    created_by, updated_by
                ) VALUES (2, 'req_00000000000000000000000000000002', 'mall',
                    'REQ-2', 'active', 1, 1, ?, ?, 'seed', 'seed')
                """,
                (now, now),
            )
        requirement_pk = 2 if invalid_source_ownership else 1
        connection.execute(
            """
            INSERT INTO requirement_versions (
                id, requirement_version_id, requirement_pk, version_no, title,
                content, content_checksum, version_status, created_at, created_by
            ) VALUES (1, 'reqv_00000000000000000000000000000001', ?, 1,
                'Requirement', 'Body', ?, 'effective', ?, 'seed')
            """,
            (requirement_pk, "1" * 64, now),
        )
        asset_count = 2 if duplicate_asset else 1
        for asset_pk in range(1, asset_count + 1):
            asset_id = f"ta_{asset_pk:032x}"
            version_id = f"tav_{asset_pk:032x}"
            source_id = f"tas_{asset_pk:032x}"
            current_version_pk = 999 if invalid_current_version else asset_pk
            connection.execute(
                """
                INSERT INTO test_assets (
                    id, test_asset_id, project_code, asset_code, review_status,
                    conversion_status, current_version_pk, row_version,
                    created_at, updated_at, created_by, updated_by
                ) VALUES (?, ?, 'mall', ?, 'pending', 'not_started', ?, 1,
                    ?, ?, 'seed', 'seed')
                """,
                (
                    asset_pk,
                    asset_id,
                    asset_id,
                    current_version_pk,
                    now,
                    now,
                ),
            )
            connection.execute(
                """
                INSERT INTO test_asset_versions (
                    id, test_asset_version_id, test_asset_pk, version_no, title,
                    precondition, natural_steps, expected_result, priority, tags,
                    content_checksum, created_at, created_by
                ) VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, 'seed')
                """,
                (
                    asset_pk,
                    version_id,
                    asset_pk,
                    CONTENT.title,
                    CONTENT.precondition,
                    json.dumps(list(CONTENT.natural_steps), ensure_ascii=False),
                    CONTENT.expected_result,
                    CONTENT.priority,
                    json.dumps(list(CONTENT.tags), ensure_ascii=False),
                    str(asset_pk) * 64,
                    now,
                ),
            )
            connection.execute(
                """
                INSERT INTO test_asset_sources (
                    id, test_asset_source_id, test_asset_pk, requirement_pk,
                    requirement_version_pk, source_identity_hash, created_at,
                    created_by
                ) VALUES (?, ?, ?, 1, 1, ?, ?, 'seed')
                """,
                (asset_pk, source_id, asset_pk, str(asset_pk) * 64, now),
            )
        connection.commit()
    finally:
        connection.close()


def _assert_phase0_shape_unchanged_after_failed_upgrade(database_path: Path) -> None:
    connection = sqlite3.connect(database_path)
    try:
        assert _revision(connection) == PHASE0_REVISION
        assert "user_public_id" not in _column_names(connection, "users")
        assert PHASE1_TABLES.isdisjoint(_table_names(connection))
        assert {
            "requirement_pk",
            "requirement_version_pk",
        }.issubset(_column_names(connection, "test_asset_sources"))
        assert "source_type" not in _column_names(
            connection,
            "test_asset_sources",
        )
    finally:
        connection.close()


def _load_migration_module():
    spec = importlib.util.spec_from_file_location(
        "evie_ai_phase1_migration",
        MIGRATION_PATH,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_fresh_bootstrap_reaches_phase1_head_with_authorized_retirement(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "fresh-phase1.db"

    _run_bootstrap(database_path)

    connection = sqlite3.connect(database_path)
    try:
        assert _revision(connection) == PHASE1_REVISION
        assert PHASE1_TABLES.issubset(_table_names(connection))
        assert "user_public_id" in _column_names(connection, "users")
        assert {
            "source_type",
            "source_identity_hash",
        }.issubset(_column_names(connection, "test_asset_sources"))
        assert "requirement_pk" not in _column_names(
            connection,
            "test_asset_sources",
        )
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        connection.close()


def test_phase0_data_is_backfilled_without_losing_requirement_source(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "phase0-data.db"
    _prepare_phase0_database(database_path)
    _seed_phase0_data(database_path)

    _run_bootstrap(database_path)

    connection = sqlite3.connect(database_path)
    try:
        user_public_id = connection.execute(
            "SELECT user_public_id FROM users WHERE id = 1"
        ).fetchone()[0]
        source = connection.execute(
            """
            SELECT source.test_asset_source_id, source.source_type,
                   source.source_identity_hash, child.requirement_pk,
                   child.requirement_version_pk
            FROM test_asset_sources AS source
            JOIN test_asset_requirement_sources AS child
              ON child.test_asset_source_pk = source.id
            """
        ).fetchone()
        claim = connection.execute(
            "SELECT test_asset_pk, project_code, content_fingerprint "
            "FROM test_asset_content_claims"
        ).fetchone()

        assert re.fullmatch(r"usr_[0-9a-f]{32}", user_public_id)
        assert source == (
            "tas_00000000000000000000000000000001",
            "requirement",
            "1" * 64,
            1,
            1,
        )
        assert claim == (1, "mall", build_content_fingerprint(CONTENT))
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        connection.close()


def test_duplicate_active_assets_fail_closed_before_schema_changes(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "duplicate-assets.db"
    _prepare_phase0_database(database_path)
    _seed_phase0_data(database_path, duplicate_asset=True)

    result = _run_alembic(database_path, "upgrade", "head", check=False)

    assert result.returncode != 0
    assert "exact duplicate active assets exist" in result.stderr
    assert "ta_00000000000000000000000000000001" in result.stderr
    assert CONTENT.expected_result not in result.stderr
    _assert_phase0_shape_unchanged_after_failed_upgrade(database_path)


def test_invalid_current_version_fails_closed_before_schema_changes(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "invalid-current-version.db"
    _prepare_phase0_database(database_path)
    _seed_phase0_data(database_path, invalid_current_version=True)

    result = _run_alembic(database_path, "upgrade", "head", check=False)

    assert result.returncode != 0
    assert "invalid current version" in result.stderr
    _assert_phase0_shape_unchanged_after_failed_upgrade(database_path)


def test_requirement_source_scope_mismatch_fails_closed_before_schema_changes(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "invalid-source.db"
    _prepare_phase0_database(database_path)
    _seed_phase0_data(database_path, invalid_source_ownership=True)

    result = _run_alembic(database_path, "upgrade", "head", check=False)

    assert result.returncode != 0
    assert "Requirement source ownership is invalid" in result.stderr
    _assert_phase0_shape_unchanged_after_failed_upgrade(database_path)


def test_empty_database_can_downgrade_and_upgrade_again(tmp_path: Path) -> None:
    database_path = tmp_path / "roundtrip.db"
    _run_bootstrap(database_path)

    _run_alembic(database_path, "downgrade", PHASE0_REVISION)
    connection = sqlite3.connect(database_path)
    try:
        assert _revision(connection) == PHASE0_REVISION
        assert PHASE1_TABLES.isdisjoint(_table_names(connection))
        assert "user_public_id" not in _column_names(connection, "users")
        assert "requirement_pk" in _column_names(
            connection,
            "test_asset_sources",
        )
    finally:
        connection.close()

    _run_bootstrap(database_path)
    connection = sqlite3.connect(database_path)
    try:
        assert _revision(connection) == PHASE1_REVISION
        assert PHASE1_TABLES.issubset(_table_names(connection))
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        connection.close()


def test_downgrade_with_public_user_identity_fails_without_schema_change(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "downgrade-blocked.db"
    _prepare_phase0_database(database_path)
    _seed_phase0_data(database_path)
    _run_alembic(database_path, "upgrade", "head")

    result = _run_alembic(
        database_path,
        "downgrade",
        PHASE0_REVISION,
        check=False,
    )

    assert result.returncode != 0
    assert "users contain stable public identities" in result.stderr
    connection = sqlite3.connect(database_path)
    try:
        assert _revision(connection) == PHASE1_REVISION
        assert PHASE1_TABLES.issubset(_table_names(connection))
        assert "user_public_id" in _column_names(connection, "users")
        assert connection.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1
    finally:
        connection.close()


def test_migration_fingerprint_is_frozen_and_matches_application_vector() -> None:
    module = _load_migration_module()
    migration_row = {
        "title": CONTENT.title,
        "precondition": CONTENT.precondition,
        "natural_steps": list(CONTENT.natural_steps),
        "expected_result": CONTENT.expected_result,
        "priority": CONTENT.priority,
        "tags": list(CONTENT.tags),
    }

    assert module._content_fingerprint(migration_row) == (
        build_content_fingerprint(CONTENT)
    )
    assert module._content_fingerprint(migration_row) == (
        "4d9c36eda49d4b99c63a4ef88b7f28ce1e008df972346621c37ea808fc0aaebb"
    )

    tree = ast.parse(MIGRATION_PATH.read_text(encoding="utf-8"))
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
    assert not any(module_name.startswith("app.") for module_name in imported_modules)
    assert not any(module_name.startswith("app.") for module_name in imported_names)
    assert "Base.metadata" not in MIGRATION_PATH.read_text(encoding="utf-8")
