"""add app_settings table

Revision ID: f1a2b3c4d5e6
Revises: 9ace07cc10a9
Create Date: 2026-04-14
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, Sequence[str], None] = "9ace07cc10a9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "app_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("default_currency", sa.String(length=3), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute("INSERT INTO app_settings (id, default_currency) VALUES (1, 'CAD')")


def downgrade() -> None:
    op.drop_table("app_settings")
