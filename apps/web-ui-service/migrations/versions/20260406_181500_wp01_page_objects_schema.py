"""wp01 page objects schema

Revision ID: 20260406_181500_wp01_page_objects_schema
Revises:
Create Date: 2026-04-06 18:15:00
"""
from __future__ import annotations

from collections.abc import Iterable

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine import Connection
from sqlalchemy.engine.reflection import Inspector

# revision identifiers, used by Alembic.
revision = "20260406_181500_wp01_page_objects_schema"
down_revision = None
branch_labels = None
depends_on = None


def _inspector(conn: Connection) -> Inspector:
    return sa.inspect(conn)


def _has_table(conn: Connection, table_name: str) -> bool:
    return bool(_inspector(conn).has_table(table_name))


def _has_column(conn: Connection, table_name: str, column_name: str) -> bool:
    if not _has_table(conn, table_name):
        return False
    columns = _inspector(conn).get_columns(table_name)
    return any(str(col.get("name", "")) == column_name for col in columns)


def _safe_create_index(index_name: str, table_name: str, columns: list[str], *, unique: bool = False) -> None:
    conn = op.get_bind()
    inspector = _inspector(conn)
    existing = {str(item.get("name", "")) for item in inspector.get_indexes(table_name)}
    if index_name in existing:
        return
    op.create_index(index_name, table_name, columns, unique=unique)


def _add_missing_columns(conn: Connection, table_name: str, columns: Iterable[sa.Column]) -> None:
    for column in columns:
        if _has_column(conn, table_name, str(column.name)):
            continue
        op.add_column(table_name, column)


def _create_page_objects_table() -> None:
    op.create_table(
        "page_objects",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("project_code", sa.String(length=20), nullable=False, server_default="atp"),
        sa.Column("client", sa.String(length=10), nullable=False, server_default="web"),
        sa.Column("page_code", sa.String(length=40), nullable=False),
        sa.Column("page_name", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("page_url", sa.String(length=256), nullable=False, server_default=""),
        sa.Column("module_id", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("element_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("health_status", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("created_by", sa.String(length=60), nullable=False, server_default="system"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("project_code", "client", "page_code", name="uq_page_objects_identity"),
    )
    _safe_create_index("ix_page_objects_project_code", "page_objects", ["project_code"])
    _safe_create_index("ix_page_objects_client", "page_objects", ["client"])
    _safe_create_index("ix_page_objects_page_code", "page_objects", ["page_code"])
    _safe_create_index("ix_page_objects_module_id", "page_objects", ["module_id"])
    _safe_create_index("ix_page_objects_status", "page_objects", ["status"])
    _safe_create_index("ix_page_objects_health_status", "page_objects", ["health_status"])
    _safe_create_index("ix_page_objects_created_at", "page_objects", ["created_at"])
    _safe_create_index("ix_page_objects_updated_at", "page_objects", ["updated_at"])


def _create_page_elements_table() -> None:
    op.create_table(
        "page_elements",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("page_object_id", sa.Integer(), sa.ForeignKey("page_objects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("element_code", sa.String(length=80), nullable=False),
        sa.Column("element_name", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("locator_type", sa.String(length=30), nullable=False, server_default="css"),
        sa.Column("locator_value", sa.Text(), nullable=False, server_default=""),
        sa.Column("backup_locator", sa.String(length=512), nullable=False, server_default=""),
        sa.Column("health_status", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("role", sa.String(length=60), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("owner", sa.String(length=60), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("page_object_id", "element_code", name="uq_page_elements_identity"),
    )
    _safe_create_index("ix_page_elements_page_object_id", "page_elements", ["page_object_id"])
    _safe_create_index("ix_page_elements_element_code", "page_elements", ["element_code"])
    _safe_create_index("ix_page_elements_status", "page_elements", ["status"])
    _safe_create_index("ix_page_elements_health_status", "page_elements", ["health_status"])
    _safe_create_index("ix_page_elements_version", "page_elements", ["version"])
    _safe_create_index("ix_page_elements_created_at", "page_elements", ["created_at"])
    _safe_create_index("ix_page_elements_updated_at", "page_elements", ["updated_at"])


def _create_page_element_versions_table() -> None:
    op.create_table(
        "page_element_versions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("page_element_id", sa.Integer(), sa.ForeignKey("page_elements.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("locator_type", sa.String(length=30), nullable=False, server_default="css"),
        sa.Column("locator_value", sa.Text(), nullable=False, server_default=""),
        sa.Column("role", sa.String(length=60), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("changed_by", sa.String(length=60), nullable=False, server_default="system"),
        sa.Column("change_summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("page_element_id", "version_no", name="uq_page_element_versions_identity"),
    )
    _safe_create_index("ix_page_element_versions_page_element_id", "page_element_versions", ["page_element_id"])
    _safe_create_index("ix_page_element_versions_version_no", "page_element_versions", ["version_no"])
    _safe_create_index("ix_page_element_versions_created_at", "page_element_versions", ["created_at"])


def _create_page_object_refs_table() -> None:
    op.create_table(
        "page_object_refs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("page_element_id", sa.Integer(), sa.ForeignKey("page_elements.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reference_type", sa.String(length=30), nullable=False, server_default="test_case"),
        sa.Column("reference_key", sa.String(length=120), nullable=False),
        sa.Column("source", sa.String(length=40), nullable=False, server_default="manual"),
        sa.Column("created_by", sa.String(length=60), nullable=False, server_default="system"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint(
            "page_element_id",
            "reference_type",
            "reference_key",
            name="uq_page_object_refs_identity",
        ),
    )
    _safe_create_index("ix_page_object_refs_page_element_id", "page_object_refs", ["page_element_id"])
    _safe_create_index("ix_page_object_refs_reference_type", "page_object_refs", ["reference_type"])
    _safe_create_index("ix_page_object_refs_reference_key", "page_object_refs", ["reference_key"])
    _safe_create_index("ix_page_object_refs_created_at", "page_object_refs", ["created_at"])


def _create_page_element_health_checks_table() -> None:
    op.create_table(
        "page_element_health_checks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("page_element_id", sa.Integer(), sa.ForeignKey("page_elements.id", ondelete="CASCADE"), nullable=False),
        sa.Column("check_status", sa.String(length=20), nullable=False, server_default="unknown"),
        sa.Column("detail", sa.Text(), nullable=False, server_default=""),
        sa.Column("checked_by", sa.String(length=60), nullable=False, server_default="system"),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    _safe_create_index("ix_page_element_health_checks_page_element_id", "page_element_health_checks", ["page_element_id"])
    _safe_create_index("ix_page_element_health_checks_check_status", "page_element_health_checks", ["check_status"])
    _safe_create_index("ix_page_element_health_checks_checked_at", "page_element_health_checks", ["checked_at"])


def upgrade() -> None:
    conn = op.get_bind()

    if not _has_table(conn, "page_objects"):
        _create_page_objects_table()
    else:
        _add_missing_columns(
            conn,
            "page_objects",
            [
                sa.Column("page_url", sa.String(length=256), nullable=False, server_default=""),
                sa.Column("module_id", sa.Integer(), nullable=False, server_default="0"),
                sa.Column("element_count", sa.Integer(), nullable=False, server_default="0"),
                sa.Column("health_status", sa.Integer(), nullable=False, server_default="1"),
            ],
        )

    if not _has_table(conn, "page_elements"):
        _create_page_elements_table()
    else:
        _add_missing_columns(
            conn,
            "page_elements",
            [
                sa.Column("backup_locator", sa.String(length=512), nullable=False, server_default=""),
                sa.Column("health_status", sa.Integer(), nullable=False, server_default="1"),
                sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            ],
        )

    if not _has_table(conn, "page_element_versions"):
        _create_page_element_versions_table()
    if not _has_table(conn, "page_object_refs"):
        _create_page_object_refs_table()
    if not _has_table(conn, "page_element_health_checks"):
        _create_page_element_health_checks_table()


def downgrade() -> None:
    conn = op.get_bind()

    if _has_table(conn, "page_element_health_checks"):
        op.drop_table("page_element_health_checks")
    if _has_table(conn, "page_object_refs"):
        op.drop_table("page_object_refs")
    if _has_table(conn, "page_element_versions"):
        op.drop_table("page_element_versions")
    if _has_table(conn, "page_elements"):
        op.drop_table("page_elements")
    if _has_table(conn, "page_objects"):
        op.drop_table("page_objects")
