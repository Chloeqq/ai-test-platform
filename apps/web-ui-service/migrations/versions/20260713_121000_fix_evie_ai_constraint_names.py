"""Normalize the Phase 0 RequirementVersion foreign-key constraint name.

Revision ID: 20260713_121000
Revises: 20260713_120000
Create Date: 2026-07-13 15:00:00.000000

``20260713_120000`` originally used a 65-byte PostgreSQL-incompatible name.
SQLite accepted that legacy name, so this revision conditionally rebuilds only
SQLite databases that already contain it.  New PostgreSQL installations receive
the corrected name directly from ``20260713_120000`` and take the validation
path without a DDL change.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "20260713_121000"
down_revision = "20260713_120000"
branch_labels = None
depends_on = None

_TABLE_NAME = "test_asset_sources"
_CANONICAL_REQUIREMENT_VERSION_FK = (
    "fk_test_asset_sources_req_version_pk_requirement_versions"
)
# Historical input only.  It is never created by this migration.
_LEGACY_REQUIREMENT_VERSION_FK = (
    "fk_test_asset_sources_requirement_version_pk_" "requirement_versions"
)
_EXPECTED_COLUMNS = ["requirement_version_pk"]
_EXPECTED_REFERRED_TABLE = "requirement_versions"
_EXPECTED_REFERRED_COLUMNS = ["id"]


def _named_foreign_keys(bind: sa.Connection) -> dict[str, dict[str, object]]:
    return {
        str(foreign_key["name"]): foreign_key
        for foreign_key in sa.inspect(bind).get_foreign_keys(_TABLE_NAME)
        if foreign_key.get("name")
    }


def _has_expected_definition(foreign_key: dict[str, object]) -> bool:
    return (
        list(foreign_key.get("constrained_columns") or []) == _EXPECTED_COLUMNS
        and foreign_key.get("referred_table") == _EXPECTED_REFERRED_TABLE
        and list(foreign_key.get("referred_columns") or [])
        == _EXPECTED_REFERRED_COLUMNS
    )


def _assert_canonical_constraint(bind: sa.Connection) -> None:
    foreign_key = _named_foreign_keys(bind).get(_CANONICAL_REQUIREMENT_VERSION_FK)
    if foreign_key is None or not _has_expected_definition(foreign_key):
        raise RuntimeError(
            "test_asset_sources does not contain the canonical RequirementVersion "
            "foreign key"
        )


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table(_TABLE_NAME):
        raise RuntimeError("test_asset_sources is missing at the Phase 0 boundary")

    foreign_keys = _named_foreign_keys(bind)
    canonical_foreign_key = foreign_keys.get(_CANONICAL_REQUIREMENT_VERSION_FK)
    if canonical_foreign_key is not None:
        if not _has_expected_definition(canonical_foreign_key):
            raise RuntimeError(
                "canonical RequirementVersion foreign key has an unexpected definition"
            )
        return

    legacy_foreign_key = foreign_keys.get(_LEGACY_REQUIREMENT_VERSION_FK)
    if legacy_foreign_key is None or not _has_expected_definition(legacy_foreign_key):
        raise RuntimeError(
            "test_asset_sources does not contain a recognized RequirementVersion "
            "foreign key"
        )
    if bind.dialect.name != "sqlite":
        raise RuntimeError(
            "legacy RequirementVersion foreign-key name is only supported for "
            "previously executed SQLite Phase 0 databases"
        )

    with op.batch_alter_table(_TABLE_NAME, recreate="always") as batch:
        batch.drop_constraint(_LEGACY_REQUIREMENT_VERSION_FK, type_="foreignkey")
        batch.create_foreign_key(
            _CANONICAL_REQUIREMENT_VERSION_FK,
            _EXPECTED_REFERRED_TABLE,
            _EXPECTED_COLUMNS,
            _EXPECTED_REFERRED_COLUMNS,
            ondelete="RESTRICT",
        )
    _assert_canonical_constraint(bind)


def downgrade() -> None:
    """Keep the canonical safe name when returning to the corrected 120000 schema.

    Reintroducing the historical 65-byte name would make a subsequent
    PostgreSQL upgrade impossible and would no longer match corrected
    ``20260713_120000``.
    """
