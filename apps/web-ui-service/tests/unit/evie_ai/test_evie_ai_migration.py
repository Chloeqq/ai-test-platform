from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path


SERVICE_ROOT = Path(__file__).resolve().parents[3]
PARENT_REVISION = "20260713_110000_add_parsed_blocks_to_requirement_documents"
PHASE0_REVISION = "20260713_120000"
EVIE_AI_TABLES = {
    "requirements",
    "requirement_versions",
    "test_assets",
    "test_asset_versions",
    "test_asset_sources",
}
EXPECTED_INDEXES = {
    "requirements": {
        "ix_requirements_deleted_at",
        "ix_requirements_project_code",
        "ix_requirements_project_code_external_requirement_key",
        "ix_requirements_status",
    },
    "requirement_versions": {
        "ix_requirement_versions_content_checksum",
        "ix_requirement_versions_requirement_pk",
        "ix_requirement_versions_version_status",
    },
    "test_assets": {
        "ix_test_assets_conversion_status",
        "ix_test_assets_deleted_at",
        "ix_test_assets_project_code",
        "ix_test_assets_review_status",
    },
    "test_asset_versions": {
        "ix_test_asset_versions_content_checksum",
        "ix_test_asset_versions_test_asset_pk",
    },
    "test_asset_sources": {
        "ix_test_asset_sources_requirement_pk",
        "ix_test_asset_sources_requirement_version_pk",
        "ix_test_asset_sources_source_identity_hash",
    },
}
EXPECTED_NAMED_CONSTRAINTS = {
    "requirements": {
        "pk_requirements",
        "uq_requirements_requirement_id",
        "uq_requirements_project_code_requirement_code",
        "ck_requirements_status",
        "ck_requirements_row_version_positive",
    },
    "requirement_versions": {
        "pk_requirement_versions",
        "uq_requirement_versions_requirement_version_id",
        "uq_requirement_versions_requirement_pk_version_no",
        "fk_requirement_versions_requirement_pk_requirements",
        "ck_requirement_versions_version_no_positive",
        "ck_requirement_versions_version_status",
    },
    "test_assets": {
        "pk_test_assets",
        "uq_test_assets_test_asset_id",
        "uq_test_assets_project_code_asset_code",
        "ck_test_assets_review_status",
        "ck_test_assets_conversion_status",
        "ck_test_assets_row_version_positive",
    },
    "test_asset_versions": {
        "pk_test_asset_versions",
        "uq_test_asset_versions_test_asset_version_id",
        "uq_test_asset_versions_test_asset_pk_version_no",
        "fk_test_asset_versions_test_asset_pk_test_assets",
        "ck_test_asset_versions_version_no_positive",
    },
    "test_asset_sources": {
        "pk_test_asset_sources",
        "uq_test_asset_sources_test_asset_source_id",
        "uq_test_asset_sources_test_asset_pk_source_identity_hash",
        "fk_test_asset_sources_test_asset_pk_test_assets",
        "fk_test_asset_sources_requirement_pk_requirements",
        "fk_test_asset_sources_requirement_version_pk_requirement_versions",
    },
}


def _run_alembic(database_path: Path, *arguments: str) -> None:
    environment = os.environ.copy()
    environment["DATABASE_URL"] = f"sqlite:///{database_path}"
    subprocess.run(
        [sys.executable, "-m", "alembic", *arguments],
        cwd=SERVICE_ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
        timeout=120,
    )


def _database_state(database_path: Path) -> tuple[str, set[str], str]:
    connection = sqlite3.connect(database_path)
    try:
        revision = connection.execute(
            "SELECT version_num FROM alembic_version"
        ).fetchone()[0]
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        return revision, tables, integrity
    finally:
        connection.close()


def _assert_phase0_schema(database_path: Path) -> None:
    connection = sqlite3.connect(database_path)
    try:
        for table_name in EVIE_AI_TABLES:
            table_sql = connection.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
                (table_name,),
            ).fetchone()[0]
            for constraint_name in EXPECTED_NAMED_CONSTRAINTS[table_name]:
                assert constraint_name in table_sql

            index_names = {
                row[1]
                for row in connection.execute(
                    f'PRAGMA index_list("{table_name}")'
                )
            }
            assert EXPECTED_INDEXES[table_name].issubset(index_names)

        requirement_fks = connection.execute(
            'PRAGMA foreign_key_list("requirements")'
        ).fetchall()
        asset_fks = connection.execute(
            'PRAGMA foreign_key_list("test_assets")'
        ).fetchall()
        assert requirement_fks == []
        assert asset_fks == []
    finally:
        connection.close()


def test_phase0_migration_upgrade_downgrade_upgrade(tmp_path: Path) -> None:
    database_path = tmp_path / "evie-ai-phase0.db"

    _run_alembic(database_path, "upgrade", "head")
    revision, tables, integrity = _database_state(database_path)
    assert revision == PHASE0_REVISION
    assert EVIE_AI_TABLES.issubset(tables)
    assert "requirement_documents" in tables
    assert integrity == "ok"
    _assert_phase0_schema(database_path)

    _run_alembic(database_path, "downgrade", PARENT_REVISION)
    revision, tables, integrity = _database_state(database_path)
    assert revision == PARENT_REVISION
    assert EVIE_AI_TABLES.isdisjoint(tables)
    assert "requirement_documents" in tables
    assert "prompt_templates" in tables
    assert integrity == "ok"

    _run_alembic(database_path, "upgrade", "head")
    revision, tables, integrity = _database_state(database_path)
    assert revision == PHASE0_REVISION
    assert EVIE_AI_TABLES.issubset(tables)
    assert integrity == "ok"
    _assert_phase0_schema(database_path)
