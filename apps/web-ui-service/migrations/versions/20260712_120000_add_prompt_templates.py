"""add prompt_templates table

Revision ID: 20260712_120000_add_prompt_templates
Revises: 20260711_120000_add_requirement_documents
Create Date: 2026-07-12 12:00:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine import Connection

revision = "20260712_120000_add_prompt_templates"
down_revision = "20260711_120000_add_requirement_documents"
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
    if not _has_table(conn, "prompt_templates"):
        op.create_table(
            "prompt_templates",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("code", sa.String(length=80), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False, server_default=""),
            sa.Column("scene_type", sa.String(length=40), nullable=False, server_default=""),
            sa.Column("system_prompt", sa.Text(), nullable=False, server_default=""),
            sa.Column("user_prompt_template", sa.Text(), nullable=False, server_default=""),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("variables", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("created_by", sa.String(length=120), nullable=True),
            sa.Column("updated_by", sa.String(length=120), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("code", name="uq_prompt_templates_code"),
        )
    _safe_create_index("ix_prompt_templates_scene_type", "prompt_templates", ["scene_type"])


def downgrade() -> None:
    for index_name in ["ix_prompt_templates_scene_type"]:
        _drop_index_if_exists(index_name, "prompt_templates")
    conn = op.get_bind()
    if _has_table(conn, "prompt_templates"):
        op.drop_table("prompt_templates")
