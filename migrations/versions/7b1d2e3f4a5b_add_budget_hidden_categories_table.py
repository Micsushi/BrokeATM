"""add budget_hidden_categories table

Revision ID: 7b1d2e3f4a5b
Revises: f1a2b3c4d5e6
Create Date: 2026-04-17
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "7b1d2e3f4a5b"
down_revision: Union[str, Sequence[str], None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "budget_hidden_categories",
        sa.Column("category_key", sa.String(length=64), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("category_key"),
    )
    op.create_index(
        op.f("ix_budget_hidden_categories_category_id"),
        "budget_hidden_categories",
        ["category_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_budget_hidden_categories_category_id"),
        table_name="budget_hidden_categories",
    )
    op.drop_table("budget_hidden_categories")
