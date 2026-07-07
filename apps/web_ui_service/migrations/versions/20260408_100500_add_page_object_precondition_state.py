"""add page object precondition state

Revision ID: 20260408_100500_add_page_object_precondition_state
Revises: 20260406_181500_wp01_page_objects_schema
Create Date: 2026-04-08 10:05:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260408_100500_add_page_object_precondition_state"
down_revision = "20260406_181500_wp01_page_objects_schema"
branch_labels = None
depends_on = None


def _has_column(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table(table_name):
        return False
    return any(str(item.get("name", "")) == column_name for item in inspector.get_columns(table_name))


def upgrade() -> None:
    if not _has_column("page_objects", "precondition_state"):
        op.add_column(
            "page_objects",
            sa.Column("precondition_state", sa.Text(), nullable=False, server_default=""),
        )


def downgrade() -> None:
    if _has_column("page_objects", "precondition_state"):
        op.drop_column("page_objects", "precondition_state")
