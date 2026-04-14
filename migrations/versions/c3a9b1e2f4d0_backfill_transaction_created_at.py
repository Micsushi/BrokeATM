"""Backfill transaction created_at to migration time

Revision ID: c3a9b1e2f4d0
Revises: b2f8a1c0d4e1
Create Date: 2026-04-13

Sets ``created_at`` on every existing transaction to the time this migration runs
so the Records ``Added`` column has a consistent baseline for older databases.
"""

from typing import Sequence, Union

from alembic import op


revision: str = "c3a9b1e2f4d0"
down_revision: Union[str, Sequence[str], None] = "b2f8a1c0d4e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("UPDATE transactions SET created_at = CURRENT_TIMESTAMP")


def downgrade() -> None:
    pass
