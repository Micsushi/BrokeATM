"""drop unique constraint on transaction ref + account

Revision ID: b2f8a1c0d4e1
Revises: 48c2758e1859
Create Date: 2026-04-13

Each transaction row is uniquely identified by primary key ``id``.
Duplicate detection for imports is handled in application logic.
"""

from typing import Sequence, Union

from alembic import op


revision: str = "b2f8a1c0d4e1"
down_revision: Union[str, Sequence[str], None] = "48c2758e1859"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("transactions", schema=None) as batch_op:
        batch_op.drop_constraint("uq_ref_account", type_="unique")


def downgrade() -> None:
    with op.batch_alter_table("transactions", schema=None) as batch_op:
        batch_op.create_unique_constraint(
            "uq_ref_account",
            ["reference_number", "account_id"],
        )
