"""merge dual heads

Revision ID: 52d25ca7de2e
Revises: 20260328_110000, 20260525_120000_add_test_data_pool_tables
Create Date: 2026-06-09 18:02:24.660663
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '52d25ca7de2e'
down_revision = ('20260328_110000', '20260525_120000_add_test_data_pool_tables')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
