"""add parsed_blocks column to requirement_documents

Revision ID: 20260713_110000_add_parsed_blocks_to_requirement_documents
Revises: 20260713_100000_prompt_templates_description
Create Date: 2026-07-13 11:00:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine import Connection

revision = "20260713_110000_add_parsed_blocks_to_requirement_documents"
down_revision = "20260713_100000_prompt_templates_description"
branch_labels = None
depends_on = None


def _has_table(conn: Connection, table_name: str) -> bool:
    return bool(sa.inspect(conn).has_table(table_name))


def _has_column(conn: Connection, table_name: str, column_name: str) -> bool:
    if not _has_table(conn, table_name):
        return False
    return column_name in {str(c["name"]) for c in sa.inspect(conn).get_columns(table_name)}


def upgrade() -> None:
    conn = op.get_bind()
    if _has_table(conn, "requirement_documents") and not _has_column(conn, "requirement_documents", "parsed_blocks"):
        op.add_column("requirement_documents", sa.Column("parsed_blocks", sa.JSON(), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    if _has_column(conn, "requirement_documents", "parsed_blocks"):
        op.drop_column("requirement_documents", "parsed_blocks")
