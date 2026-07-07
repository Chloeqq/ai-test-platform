"""add project source semantics config

Revision ID: 20260430_100000_add_project_source_semantics_config
Revises: 20260424_160000_page_object_governance_models
Create Date: 2026-04-30 10:00:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine import Connection

# revision identifiers, used by Alembic.
revision = "20260430_100000_add_project_source_semantics_config"
down_revision = "20260424_160000_page_object_governance_models"
branch_labels = None
depends_on = None


def _has_table(conn: Connection, table_name: str) -> bool:
    return bool(sa.inspect(conn).has_table(table_name))


def _has_column(conn: Connection, table_name: str, column_name: str) -> bool:
    if not _has_table(conn, table_name):
        return False
    return any(str(item.get("name", "")) == column_name for item in sa.inspect(conn).get_columns(table_name))


def _drop_column_if_exists(conn: Connection, table_name: str, column_name: str) -> None:
    if _has_column(conn, table_name, column_name):
        op.drop_column(table_name, column_name)


def upgrade() -> None:
    conn = op.get_bind()
    if not _has_table(conn, "test_projects"):
        return
    if not _has_column(conn, "test_projects", "source_roots_json"):
        op.add_column("test_projects", sa.Column("source_roots_json", sa.JSON(), nullable=True))
    if not _has_column(conn, "test_projects", "source_terms_json"):
        op.add_column("test_projects", sa.Column("source_terms_json", sa.JSON(), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    _drop_column_if_exists(conn, "test_projects", "source_terms_json")
    _drop_column_if_exists(conn, "test_projects", "source_roots_json")
