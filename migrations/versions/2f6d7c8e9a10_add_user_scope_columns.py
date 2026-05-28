"""add user scope columns

Revision ID: 2f6d7c8e9a10
Revises: a1b2c3d4e5f7
Create Date: 2026-05-05 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "2f6d7c8e9a10"
down_revision: str | None = "a1b2c3d4e5f7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_USER_TABLES = (
    "accounts",
    "categories",
    "transactions",
    "budget_rules",
    "budget_hidden_categories",
    "recurring_rules",
    "import_batches",
    "app_settings",
)


def _upgrade_category_name_constraint() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("ALTER TABLE categories DROP CONSTRAINT IF EXISTS categories_name_key")
    op.create_unique_constraint(
        "uq_categories_user_name",
        "categories",
        ["user_id", "name"],
    )


def _downgrade_category_name_constraint() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("ALTER TABLE categories DROP CONSTRAINT IF EXISTS uq_categories_user_name")
    op.create_unique_constraint("categories_name_key", "categories", ["name"])


def upgrade() -> None:
    for table in _USER_TABLES:
        op.add_column(table, sa.Column("user_id", sa.String(length=36), nullable=True))
        if table != "budget_hidden_categories":
            op.create_index(f"ix_{table}_user_id", table, ["user_id"])

    _upgrade_category_name_constraint()

    # budget_hidden_categories used category_key as sole PK, which conflicts when two
    # users hide the same category key. Restructure to a surrogate id PK.
    op.execute("ALTER TABLE budget_hidden_categories RENAME TO budget_hidden_categories_old")
    op.create_table(
        "budget_hidden_categories",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(36), nullable=True),
        sa.Column("category_key", sa.String(64), nullable=False),
        sa.Column(
            "category_id",
            sa.Integer(),
            sa.ForeignKey("categories.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint(
            "user_id",
            "category_key",
            name="uq_budget_hidden_categories_user_key",
        ),
    )
    op.execute("""
        INSERT INTO budget_hidden_categories (user_id, category_key, category_id, created_at)
        SELECT user_id, category_key, category_id, created_at
        FROM budget_hidden_categories_old
    """)
    op.drop_table("budget_hidden_categories_old")
    op.create_index(
        "ix_budget_hidden_categories_category_id",
        "budget_hidden_categories",
        ["category_id"],
    )
    op.create_index("ix_budget_hidden_categories_user_id", "budget_hidden_categories", ["user_id"])


def downgrade() -> None:
    _downgrade_category_name_constraint()

    op.execute("ALTER TABLE budget_hidden_categories RENAME TO budget_hidden_categories_new")
    op.create_table(
        "budget_hidden_categories",
        sa.Column("category_key", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(36), nullable=True),
        sa.Column(
            "category_id",
            sa.Integer(),
            sa.ForeignKey("categories.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.execute("""
        INSERT INTO budget_hidden_categories (category_key, user_id, category_id, created_at)
        SELECT category_key, user_id, category_id, created_at
        FROM budget_hidden_categories_new
    """)
    op.drop_table("budget_hidden_categories_new")
    op.create_index(
        "ix_budget_hidden_categories_category_id",
        "budget_hidden_categories",
        ["category_id"],
    )

    for table in reversed(_USER_TABLES):
        if table != "budget_hidden_categories":
            op.drop_index(f"ix_{table}_user_id", table_name=table)
        op.drop_column(table, "user_id")
