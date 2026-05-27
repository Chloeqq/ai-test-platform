"""add test data pool tables

Revision ID: 20260525_120000_add_test_data_pool_tables
Revises: 20260501_090000_default_page_object_project_mall
Create Date: 2026-05-25 12:00:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine import Connection

# revision identifiers, used by Alembic.
revision = "20260525_120000_add_test_data_pool_tables"
down_revision = "20260501_090000_default_page_object_project_mall"
branch_labels = None
depends_on = None


def _has_table(conn: Connection, table_name: str) -> bool:
    return bool(sa.inspect(conn).has_table(table_name))


def _safe_create_index(index_name: str, table_name: str, columns: list[str], *, unique: bool = False) -> None:
    conn = op.get_bind()
    if not _has_table(conn, table_name):
        return
    existing = {str(item.get("name", "")) for item in sa.inspect(conn).get_indexes(table_name)}
    if index_name in existing:
        return
    op.create_index(index_name, table_name, columns, unique=unique)


def _drop_index_if_exists(index_name: str, table_name: str) -> None:
    conn = op.get_bind()
    if not _has_table(conn, table_name):
        return
    existing = {str(item.get("name", "")) for item in sa.inspect(conn).get_indexes(table_name)}
    if index_name in existing:
        op.drop_index(index_name, table_name=table_name)


def upgrade() -> None:
    conn = op.get_bind()
    if not _has_table(conn, "test_data_pools"):
        op.create_table(
            "test_data_pools",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("pool_name", sa.String(length=120), nullable=False),
            sa.Column("description", sa.Text(), nullable=False, server_default=""),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
            sa.Column("created_by", sa.String(length=120), nullable=False, server_default="system"),
            sa.Column("updated_by", sa.String(length=120), nullable=False, server_default="system"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("pool_name", name="uq_test_data_pools_pool_name"),
        )

    if not _has_table(conn, "test_data_pool_items"):
        op.create_table(
            "test_data_pool_items",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("pool_id", sa.Integer(), sa.ForeignKey("test_data_pools.id", ondelete="CASCADE"), nullable=False),
            sa.Column("item_key", sa.String(length=160), nullable=False),
            sa.Column("item_value", sa.Text(), nullable=False, server_default=""),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
            sa.Column("created_by", sa.String(length=120), nullable=False, server_default="system"),
            sa.Column("updated_by", sa.String(length=120), nullable=False, server_default="system"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("pool_id", "item_key", name="uq_test_data_pool_item_key"),
        )

    if not _has_table(conn, "test_data_pool_audit_logs"):
        op.create_table(
            "test_data_pool_audit_logs",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("pool_name", sa.String(length=120), nullable=False, server_default=""),
            sa.Column("item_key", sa.String(length=160), nullable=False, server_default=""),
            sa.Column("operation", sa.String(length=40), nullable=False, server_default=""),
            sa.Column("changed_by", sa.String(length=120), nullable=False, server_default="system"),
            sa.Column("note", sa.Text(), nullable=False, server_default=""),
            sa.Column("before_value", sa.Text(), nullable=False, server_default=""),
            sa.Column("after_value", sa.Text(), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )

    _safe_create_index("ix_test_data_pools_pool_name", "test_data_pools", ["pool_name"])
    _safe_create_index("ix_test_data_pools_status", "test_data_pools", ["status"])
    _safe_create_index("ix_test_data_pool_items_pool_id", "test_data_pool_items", ["pool_id"])
    _safe_create_index("ix_test_data_pool_items_item_key", "test_data_pool_items", ["item_key"])
    _safe_create_index("ix_test_data_pool_items_status", "test_data_pool_items", ["status"])
    _safe_create_index("ix_test_data_pool_audit_logs_pool_name", "test_data_pool_audit_logs", ["pool_name"])
    _safe_create_index("ix_test_data_pool_audit_logs_item_key", "test_data_pool_audit_logs", ["item_key"])
    _safe_create_index("ix_test_data_pool_audit_logs_operation", "test_data_pool_audit_logs", ["operation"])
    _safe_create_index("ix_test_data_pool_audit_logs_created_at", "test_data_pool_audit_logs", ["created_at"])


def downgrade() -> None:
    for index_name, table_name in [
        ("ix_test_data_pool_audit_logs_created_at", "test_data_pool_audit_logs"),
        ("ix_test_data_pool_audit_logs_operation", "test_data_pool_audit_logs"),
        ("ix_test_data_pool_audit_logs_item_key", "test_data_pool_audit_logs"),
        ("ix_test_data_pool_audit_logs_pool_name", "test_data_pool_audit_logs"),
        ("ix_test_data_pool_items_status", "test_data_pool_items"),
        ("ix_test_data_pool_items_item_key", "test_data_pool_items"),
        ("ix_test_data_pool_items_pool_id", "test_data_pool_items"),
        ("ix_test_data_pools_status", "test_data_pools"),
        ("ix_test_data_pools_pool_name", "test_data_pools"),
    ]:
        _drop_index_if_exists(index_name, table_name)

    conn = op.get_bind()
    if _has_table(conn, "test_data_pool_audit_logs"):
        op.drop_table("test_data_pool_audit_logs")
    if _has_table(conn, "test_data_pool_items"):
        op.drop_table("test_data_pool_items")
    if _has_table(conn, "test_data_pools"):
        op.drop_table("test_data_pools")
