"""add recurring_rule_id to transactions

Revision ID: a1b2c3d4e5f7
Revises: 7b1d2e3f4a5b
Create Date: 2026-04-18

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1b2c3d4e5f7"
down_revision: Union[str, Sequence[str], None] = "7b1d2e3f4a5b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "transactions",
        sa.Column("recurring_rule_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        "ix_transactions_recurring_rule_id",
        "transactions",
        ["recurring_rule_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_transactions_recurring_rule_id", table_name="transactions")
    op.drop_column("transactions", "recurring_rule_id")
