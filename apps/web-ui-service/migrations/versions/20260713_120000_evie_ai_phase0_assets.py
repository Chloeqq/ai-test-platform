"""Add EvieAi Phase 0 natural-language asset tables.

Revision ID: 20260713_120000
Revises: 20260713_110000_add_parsed_blocks_to_requirement_documents
Create Date: 2026-07-13 12:59:12.110700
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "20260713_120000"
down_revision = "20260713_110000_add_parsed_blocks_to_requirement_documents"
branch_labels = None
depends_on = None


_EXPECTED_COLUMNS = {
    "requirements": {
        "id",
        "requirement_id",
        "project_code",
        "requirement_code",
        "external_requirement_key",
        "status",
        "current_version_pk",
        "row_version",
        "created_at",
        "updated_at",
        "deleted_at",
        "created_by",
        "updated_by",
    },
    "requirement_versions": {
        "id",
        "requirement_version_id",
        "requirement_pk",
        "version_no",
        "title",
        "content",
        "content_checksum",
        "version_status",
        "created_at",
        "created_by",
    },
    "test_assets": {
        "id",
        "test_asset_id",
        "project_code",
        "asset_code",
        "review_status",
        "conversion_status",
        "current_version_pk",
        "row_version",
        "created_at",
        "updated_at",
        "deleted_at",
        "created_by",
        "updated_by",
    },
    "test_asset_versions": {
        "id",
        "test_asset_version_id",
        "test_asset_pk",
        "version_no",
        "title",
        "precondition",
        "natural_steps",
        "expected_result",
        "priority",
        "tags",
        "content_checksum",
        "created_at",
        "created_by",
    },
    "test_asset_sources": {
        "id",
        "test_asset_source_id",
        "test_asset_pk",
        "requirement_pk",
        "requirement_version_pk",
        "source_identity_hash",
        "created_at",
        "created_by",
    },
}

_EXPECTED_PRIMARY_KEYS = {
    table_name: f"pk_{table_name}" for table_name in _EXPECTED_COLUMNS
}

_EXPECTED_UNIQUE_CONSTRAINTS = {
    "requirements": {
        "uq_requirements_requirement_id",
        "uq_requirements_project_code_requirement_code",
    },
    "requirement_versions": {
        "uq_requirement_versions_requirement_version_id",
        "uq_requirement_versions_requirement_pk_version_no",
    },
    "test_assets": {
        "uq_test_assets_test_asset_id",
        "uq_test_assets_project_code_asset_code",
    },
    "test_asset_versions": {
        "uq_test_asset_versions_test_asset_version_id",
        "uq_test_asset_versions_test_asset_pk_version_no",
    },
    "test_asset_sources": {
        "uq_test_asset_sources_test_asset_source_id",
        "uq_test_asset_sources_test_asset_pk_source_identity_hash",
    },
}

_EXPECTED_FOREIGN_KEYS = {
    "requirements": set(),
    "requirement_versions": {
        "fk_requirement_versions_requirement_pk_requirements",
    },
    "test_assets": set(),
    "test_asset_versions": {
        "fk_test_asset_versions_test_asset_pk_test_assets",
    },
    "test_asset_sources": {
        "fk_test_asset_sources_test_asset_pk_test_assets",
        "fk_test_asset_sources_requirement_pk_requirements",
        "fk_test_asset_sources_requirement_version_pk_requirement_versions",
    },
}

_EXPECTED_CHECK_CONSTRAINTS = {
    "requirements": {
        "ck_requirements_status",
        "ck_requirements_row_version_positive",
    },
    "requirement_versions": {
        "ck_requirement_versions_version_no_positive",
        "ck_requirement_versions_version_status",
    },
    "test_assets": {
        "ck_test_assets_review_status",
        "ck_test_assets_conversion_status",
        "ck_test_assets_row_version_positive",
    },
    "test_asset_versions": {
        "ck_test_asset_versions_version_no_positive",
    },
    "test_asset_sources": set(),
}

_EXPECTED_INDEXES = {
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


def _constraint_names(items: list[dict[str, object]]) -> set[str]:
    return {str(item["name"]) for item in items if item.get("name")}


def _assert_existing_phase0_schema(inspector: sa.Inspector) -> None:
    for table_name, expected_columns in _EXPECTED_COLUMNS.items():
        actual_columns = {
            str(column["name"]) for column in inspector.get_columns(table_name)
        }
        if actual_columns != expected_columns:
            raise RuntimeError(
                f"existing {table_name} columns do not match EvieAi Phase 0"
            )

        primary_key_name = inspector.get_pk_constraint(table_name).get("name")
        if primary_key_name != _EXPECTED_PRIMARY_KEYS[table_name]:
            raise RuntimeError(
                f"existing {table_name} primary key does not match EvieAi Phase 0"
            )

        actual_unique_constraints = _constraint_names(
            inspector.get_unique_constraints(table_name)
        )
        if actual_unique_constraints != _EXPECTED_UNIQUE_CONSTRAINTS[table_name]:
            raise RuntimeError(
                f"existing {table_name} unique constraints do not match EvieAi Phase 0"
            )

        actual_foreign_keys = _constraint_names(inspector.get_foreign_keys(table_name))
        if actual_foreign_keys != _EXPECTED_FOREIGN_KEYS[table_name]:
            raise RuntimeError(
                f"existing {table_name} foreign keys do not match EvieAi Phase 0"
            )

        actual_check_constraints = _constraint_names(
            inspector.get_check_constraints(table_name)
        )
        if actual_check_constraints != _EXPECTED_CHECK_CONSTRAINTS[table_name]:
            raise RuntimeError(
                f"existing {table_name} check constraints do not match EvieAi Phase 0"
            )

        actual_indexes = _constraint_names(inspector.get_indexes(table_name))
        if not _EXPECTED_INDEXES[table_name].issubset(actual_indexes):
            raise RuntimeError(
                f"existing {table_name} indexes do not match EvieAi Phase 0"
            )


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    target_tables = set(_EXPECTED_COLUMNS)
    existing_target_tables = {
        table_name for table_name in target_tables if inspector.has_table(table_name)
    }
    if existing_target_tables:
        if existing_target_tables != target_tables:
            raise RuntimeError("partial EvieAi Phase 0 schema already exists")
        _assert_existing_phase0_schema(inspector)
        return

    op.create_table(
        "requirements",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("requirement_id", sa.String(length=64), nullable=False),
        sa.Column("project_code", sa.String(length=20), nullable=False),
        sa.Column("requirement_code", sa.String(length=120), nullable=False),
        sa.Column("external_requirement_key", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("current_version_pk", sa.Integer(), nullable=True),
        sa.Column(
            "row_version",
            sa.Integer(),
            server_default=sa.text("1"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(length=120), nullable=False),
        sa.Column("updated_by", sa.String(length=120), nullable=False),
        sa.CheckConstraint(
            "status IN ('draft', 'active', 'closed', 'archived')",
            name="ck_requirements_status",
        ),
        sa.CheckConstraint(
            "row_version >= 1",
            name="ck_requirements_row_version_positive",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_requirements"),
        sa.UniqueConstraint(
            "project_code",
            "requirement_code",
            name="uq_requirements_project_code_requirement_code",
        ),
        sa.UniqueConstraint(
            "requirement_id",
            name="uq_requirements_requirement_id",
        ),
    )
    op.create_index(
        "ix_requirements_deleted_at",
        "requirements",
        ["deleted_at"],
        unique=False,
    )
    op.create_index(
        "ix_requirements_project_code",
        "requirements",
        ["project_code"],
        unique=False,
    )
    op.create_index(
        "ix_requirements_project_code_external_requirement_key",
        "requirements",
        ["project_code", "external_requirement_key"],
        unique=False,
    )
    op.create_index(
        "ix_requirements_status",
        "requirements",
        ["status"],
        unique=False,
    )

    op.create_table(
        "requirement_versions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("requirement_version_id", sa.String(length=64), nullable=False),
        sa.Column("requirement_pk", sa.Integer(), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_checksum", sa.String(length=64), nullable=False),
        sa.Column("version_status", sa.String(length=20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("created_by", sa.String(length=120), nullable=False),
        sa.CheckConstraint(
            "version_status IN ('draft', 'effective', 'superseded', 'removed')",
            name="ck_requirement_versions_version_status",
        ),
        sa.CheckConstraint(
            "version_no >= 1",
            name="ck_requirement_versions_version_no_positive",
        ),
        sa.ForeignKeyConstraint(
            ["requirement_pk"],
            ["requirements.id"],
            name="fk_requirement_versions_requirement_pk_requirements",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_requirement_versions"),
        sa.UniqueConstraint(
            "requirement_pk",
            "version_no",
            name="uq_requirement_versions_requirement_pk_version_no",
        ),
        sa.UniqueConstraint(
            "requirement_version_id",
            name="uq_requirement_versions_requirement_version_id",
        ),
    )
    op.create_index(
        "ix_requirement_versions_content_checksum",
        "requirement_versions",
        ["content_checksum"],
        unique=False,
    )
    op.create_index(
        "ix_requirement_versions_requirement_pk",
        "requirement_versions",
        ["requirement_pk"],
        unique=False,
    )
    op.create_index(
        "ix_requirement_versions_version_status",
        "requirement_versions",
        ["version_status"],
        unique=False,
    )

    op.create_table(
        "test_assets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("test_asset_id", sa.String(length=64), nullable=False),
        sa.Column("project_code", sa.String(length=20), nullable=False),
        sa.Column("asset_code", sa.String(length=120), nullable=False),
        sa.Column("review_status", sa.String(length=20), nullable=False),
        sa.Column("conversion_status", sa.String(length=20), nullable=False),
        sa.Column("current_version_pk", sa.Integer(), nullable=True),
        sa.Column(
            "row_version",
            sa.Integer(),
            server_default=sa.text("1"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(length=120), nullable=False),
        sa.Column("updated_by", sa.String(length=120), nullable=False),
        sa.CheckConstraint(
            "conversion_status IN "
            "('not_started', 'processing', 'blocked', 'succeeded', 'stale')",
            name="ck_test_assets_conversion_status",
        ),
        sa.CheckConstraint(
            "review_status IN ('pending', 'approved', 'rejected')",
            name="ck_test_assets_review_status",
        ),
        sa.CheckConstraint(
            "row_version >= 1",
            name="ck_test_assets_row_version_positive",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_test_assets"),
        sa.UniqueConstraint(
            "project_code",
            "asset_code",
            name="uq_test_assets_project_code_asset_code",
        ),
        sa.UniqueConstraint("test_asset_id", name="uq_test_assets_test_asset_id"),
    )
    op.create_index(
        "ix_test_assets_conversion_status",
        "test_assets",
        ["conversion_status"],
        unique=False,
    )
    op.create_index(
        "ix_test_assets_deleted_at",
        "test_assets",
        ["deleted_at"],
        unique=False,
    )
    op.create_index(
        "ix_test_assets_project_code",
        "test_assets",
        ["project_code"],
        unique=False,
    )
    op.create_index(
        "ix_test_assets_review_status",
        "test_assets",
        ["review_status"],
        unique=False,
    )

    op.create_table(
        "test_asset_versions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("test_asset_version_id", sa.String(length=64), nullable=False),
        sa.Column("test_asset_pk", sa.Integer(), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("precondition", sa.Text(), nullable=True),
        sa.Column("natural_steps", sa.JSON(), nullable=False),
        sa.Column("expected_result", sa.Text(), nullable=False),
        sa.Column("priority", sa.String(length=20), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("content_checksum", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("created_by", sa.String(length=120), nullable=False),
        sa.CheckConstraint(
            "version_no >= 1",
            name="ck_test_asset_versions_version_no_positive",
        ),
        sa.ForeignKeyConstraint(
            ["test_asset_pk"],
            ["test_assets.id"],
            name="fk_test_asset_versions_test_asset_pk_test_assets",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_test_asset_versions"),
        sa.UniqueConstraint(
            "test_asset_pk",
            "version_no",
            name="uq_test_asset_versions_test_asset_pk_version_no",
        ),
        sa.UniqueConstraint(
            "test_asset_version_id",
            name="uq_test_asset_versions_test_asset_version_id",
        ),
    )
    op.create_index(
        "ix_test_asset_versions_content_checksum",
        "test_asset_versions",
        ["content_checksum"],
        unique=False,
    )
    op.create_index(
        "ix_test_asset_versions_test_asset_pk",
        "test_asset_versions",
        ["test_asset_pk"],
        unique=False,
    )

    op.create_table(
        "test_asset_sources",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("test_asset_source_id", sa.String(length=64), nullable=False),
        sa.Column("test_asset_pk", sa.Integer(), nullable=False),
        sa.Column("requirement_pk", sa.Integer(), nullable=False),
        sa.Column("requirement_version_pk", sa.Integer(), nullable=False),
        sa.Column("source_identity_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("created_by", sa.String(length=120), nullable=False),
        sa.ForeignKeyConstraint(
            ["requirement_pk"],
            ["requirements.id"],
            name="fk_test_asset_sources_requirement_pk_requirements",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["requirement_version_pk"],
            ["requirement_versions.id"],
            name="fk_test_asset_sources_requirement_version_pk_requirement_versions",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["test_asset_pk"],
            ["test_assets.id"],
            name="fk_test_asset_sources_test_asset_pk_test_assets",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_test_asset_sources"),
        sa.UniqueConstraint(
            "test_asset_pk",
            "source_identity_hash",
            name="uq_test_asset_sources_test_asset_pk_source_identity_hash",
        ),
        sa.UniqueConstraint(
            "test_asset_source_id",
            name="uq_test_asset_sources_test_asset_source_id",
        ),
    )
    op.create_index(
        "ix_test_asset_sources_requirement_pk",
        "test_asset_sources",
        ["requirement_pk"],
        unique=False,
    )
    op.create_index(
        "ix_test_asset_sources_requirement_version_pk",
        "test_asset_sources",
        ["requirement_version_pk"],
        unique=False,
    )
    op.create_index(
        "ix_test_asset_sources_source_identity_hash",
        "test_asset_sources",
        ["source_identity_hash"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_test_asset_sources_source_identity_hash",
        table_name="test_asset_sources",
    )
    op.drop_index(
        "ix_test_asset_sources_requirement_version_pk",
        table_name="test_asset_sources",
    )
    op.drop_index(
        "ix_test_asset_sources_requirement_pk",
        table_name="test_asset_sources",
    )
    op.drop_table("test_asset_sources")

    op.drop_index(
        "ix_test_asset_versions_test_asset_pk",
        table_name="test_asset_versions",
    )
    op.drop_index(
        "ix_test_asset_versions_content_checksum",
        table_name="test_asset_versions",
    )
    op.drop_table("test_asset_versions")

    op.drop_index("ix_test_assets_review_status", table_name="test_assets")
    op.drop_index("ix_test_assets_project_code", table_name="test_assets")
    op.drop_index("ix_test_assets_deleted_at", table_name="test_assets")
    op.drop_index("ix_test_assets_conversion_status", table_name="test_assets")
    op.drop_table("test_assets")

    op.drop_index(
        "ix_requirement_versions_version_status",
        table_name="requirement_versions",
    )
    op.drop_index(
        "ix_requirement_versions_requirement_pk",
        table_name="requirement_versions",
    )
    op.drop_index(
        "ix_requirement_versions_content_checksum",
        table_name="requirement_versions",
    )
    op.drop_table("requirement_versions")

    op.drop_index("ix_requirements_status", table_name="requirements")
    op.drop_index(
        "ix_requirements_project_code_external_requirement_key",
        table_name="requirements",
    )
    op.drop_index("ix_requirements_project_code", table_name="requirements")
    op.drop_index("ix_requirements_deleted_at", table_name="requirements")
    op.drop_table("requirements")
