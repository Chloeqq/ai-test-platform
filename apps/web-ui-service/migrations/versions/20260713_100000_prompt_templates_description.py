"""prompt_templates: add description column, drop stale boolean index

Revision ID: 20260713_100000_prompt_templates_description
Revises: 20260712_120000_add_prompt_templates
Create Date: 2026-07-13 10:00:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine import Connection

revision = "20260713_100000_prompt_templates_description"
down_revision = "20260712_120000_add_prompt_templates"
branch_labels = None
depends_on = None


def _has_table(conn: Connection, table_name: str) -> bool:
    return bool(sa.inspect(conn).has_table(table_name))


def _has_column(conn: Connection, table_name: str, column_name: str) -> bool:
    if not _has_table(conn, table_name):
        return False
    return column_name in {str(c["name"]) for c in sa.inspect(conn).get_columns(table_name)}


def _has_index(conn: Connection, table_name: str, index_name: str) -> bool:
    if not _has_table(conn, table_name):
        return False
    return index_name in {str(i.get("name", "")) for i in sa.inspect(conn).get_indexes(table_name)}


def upgrade() -> None:
    conn = op.get_bind()
    if _has_table(conn, "prompt_templates") and not _has_column(conn, "prompt_templates", "description"):
        op.add_column("prompt_templates", sa.Column("description", sa.Text(), nullable=True))
    if _has_index(conn, "prompt_templates", "ix_prompt_templates_is_enabled"):
        op.drop_index("ix_prompt_templates_is_enabled", table_name="prompt_templates")


def downgrade() -> None:
    conn = op.get_bind()
    if _has_column(conn, "prompt_templates", "description"):
        op.drop_column("prompt_templates", "description")
    if not _has_index(conn, "prompt_templates", "ix_prompt_templates_is_enabled"):
        op.create_index("ix_prompt_templates_is_enabled", "prompt_templates", ["is_enabled"])
