"""default page object project to mall

Revision ID: 20260501_090000_default_page_object_project_mall
Revises: 20260430_100000_add_project_source_semantics_config
Create Date: 2026-05-01 09:00:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine import Connection

# revision identifiers, used by Alembic.
revision = "20260501_090000_default_page_object_project_mall"
down_revision = "20260430_100000_add_project_source_semantics_config"
branch_labels = None
depends_on = None


PAGE_OBJECT_PROJECT_TABLES = (
    "page_objects",
    "page_object_recorder_sessions",
    "page_object_candidate_groups",
    "page_object_candidate_elements",
    "page_object_governance_logs",
)


def _has_table(conn: Connection, table_name: str) -> bool:
    return bool(sa.inspect(conn).has_table(table_name))


def _has_column(conn: Connection, table_name: str, column_name: str) -> bool:
    if not _has_table(conn, table_name):
        return False
    return any(str(item.get("name", "")) == column_name for item in sa.inspect(conn).get_columns(table_name))


def _set_project_code_default(default_value: str) -> None:
    conn = op.get_bind()
    # SQLite cannot reliably alter column defaults in place. The application
    # layer now always supplies project_code, so skipping keeps local test
    # databases migratable while PostgreSQL/MySQL production defaults converge.
    if conn.dialect.name == "sqlite":
        return
    for table_name in PAGE_OBJECT_PROJECT_TABLES:
        if _has_column(conn, table_name, "project_code"):
            op.alter_column(
                table_name,
                "project_code",
                existing_type=sa.String(length=20),
                existing_nullable=False,
                server_default=default_value,
            )


def upgrade() -> None:
    _set_project_code_default("mall")


def downgrade() -> None:
    _set_project_code_default("atp")
