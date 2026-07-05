"""add asset fields to test_cases

Revision ID: 20260328_110000
Revises: 20260327_181500
Create Date: 2026-03-28 11:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260328_110000"
down_revision = "20260327_181500"
branch_labels = None
depends_on = None


def _column_names(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {str(col.get("name", "")).strip() for col in inspector.get_columns(table_name)}


def upgrade() -> None:
    columns = _column_names("test_cases")
    if "test_type" not in columns:
        op.add_column("test_cases", sa.Column("test_type", sa.String(length=50), nullable=True))
        op.execute(sa.text("UPDATE test_cases SET test_type = 'ui' WHERE test_type IS NULL OR test_type = ''"))
        op.alter_column("test_cases", "test_type", existing_type=sa.String(length=50), nullable=False)
    if "markers" not in columns:
        op.add_column("test_cases", sa.Column("markers", sa.JSON(), nullable=True))
        op.execute(sa.text("UPDATE test_cases SET markers = '[]' WHERE markers IS NULL"))
        op.alter_column("test_cases", "markers", existing_type=sa.JSON(), nullable=False)
    if "pytest_path" not in columns:
        op.add_column("test_cases", sa.Column("pytest_path", sa.String(length=500), nullable=True))
        op.execute(sa.text("UPDATE test_cases SET pytest_path = '' WHERE pytest_path IS NULL"))
        op.alter_column("test_cases", "pytest_path", existing_type=sa.String(length=500), nullable=False)
    if "status" not in columns:
        op.add_column("test_cases", sa.Column("status", sa.String(length=20), nullable=True))
        op.execute(sa.text("UPDATE test_cases SET status = 'active' WHERE status IS NULL OR status = ''"))
        op.alter_column("test_cases", "status", existing_type=sa.String(length=20), nullable=False)

    columns = _column_names("test_cases")
    for index_name, column_name in (
        ("ix_test_cases_test_type", "test_type"),
        ("ix_test_cases_pytest_path", "pytest_path"),
        ("ix_test_cases_status", "status"),
    ):
        if column_name in columns:
            existing_indexes = {str(idx.get("name", "")).strip() for idx in sa.inspect(op.get_bind()).get_indexes("test_cases")}
            if index_name not in existing_indexes:
                op.create_index(index_name, "test_cases", [column_name], unique=False)


def downgrade() -> None:
    existing_indexes = {str(idx.get("name", "")).strip() for idx in sa.inspect(op.get_bind()).get_indexes("test_cases")}
    for index_name in ("ix_test_cases_status", "ix_test_cases_pytest_path", "ix_test_cases_test_type"):
        if index_name in existing_indexes:
            op.drop_index(index_name, table_name="test_cases")

    columns = _column_names("test_cases")
    for column_name in ("status", "pytest_path", "markers", "test_type"):
        if column_name in columns:
            op.drop_column("test_cases", column_name)

