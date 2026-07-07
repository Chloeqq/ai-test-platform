"""initial enterprise schema (reconstructed)

Revision ID: 20260323_143500
Revises:
Create Date: 2026-03-23 14:35:00
"""
from __future__ import annotations

from alembic import op

revision = "20260323_143500"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Reconstructed baseline: use current metadata to materialize core tables
    # for legacy environments that historically relied on Base.metadata.create_all.
    from app.core.database import Base
    import app.models  # noqa: F401

    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    # Keep downgrade non-destructive for reconstructed legacy baseline.
    pass
