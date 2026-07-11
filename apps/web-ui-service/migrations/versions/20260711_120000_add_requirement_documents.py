"""add requirement_documents table

Revision ID: 20260711_120000_add_requirement_documents
Revises: 52d25ca7de2e
Create Date: 2026-07-11 12:00:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine import Connection

# revision identifiers, used by Alembic.
revision = "20260711_120000_add_requirement_documents"
down_revision = "52d25ca7de2e"
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
    if not _has_table(conn, "requirement_documents"):
        op.create_table(
            "requirement_documents",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("project_code", sa.String(length=64), nullable=False),
            sa.Column("filename", sa.String(length=512), nullable=False, server_default=""),
            sa.Column("source_type", sa.String(length=20), nullable=False, server_default=""),
            sa.Column("object_key", sa.String(length=1024), nullable=False, server_default=""),
            sa.Column("file_size", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("parse_status", sa.String(length=20), nullable=False, server_default="pending"),
            sa.Column("parse_error", sa.Text(), nullable=True),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_by", sa.String(length=120), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )

    _safe_create_index("ix_requirement_documents_project_code", "requirement_documents", ["project_code"])
    _safe_create_index("ix_requirement_documents_parse_status", "requirement_documents", ["parse_status"])
    _safe_create_index("ix_requirement_documents_created_at", "requirement_documents", ["created_at"])


def downgrade() -> None:
    for index_name in [
        "ix_requirement_documents_created_at",
        "ix_requirement_documents_parse_status",
        "ix_requirement_documents_project_code",
    ]:
        _drop_index_if_exists(index_name, "requirement_documents")

    conn = op.get_bind()
    if _has_table(conn, "requirement_documents"):
        op.drop_table("requirement_documents")