from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class UserOwnedMixin:
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)


class TransactionType(StrEnum):
    expense = "expense"
    income = "income"
    refund = "refund"
    transfer = "transfer"


class Account(UserOwnedMixin, Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    card_number_masked: Mapped[str | None] = mapped_column(String(20), nullable=True)
    institution: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    transactions: Mapped[list["Transaction"]] = relationship(
        "Transaction", back_populates="account"
    )


class Category(UserOwnedMixin, Base):
    __tablename__ = "categories"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_categories_user_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    color: Mapped[str | None] = mapped_column(String(7), nullable=True)
    keywords: Mapped[str | None] = mapped_column("mcc_descriptions", Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    transactions: Mapped[list["Transaction"]] = relationship(
        "Transaction", back_populates="category"
    )


class Transaction(UserOwnedMixin, Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    transaction_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    posted_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    reference_number: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)

    merchant_name: Mapped[str] = mapped_column(String(200), nullable=False)
    merchant_city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    merchant_state: Mapped[str | None] = mapped_column(String(50), nullable=True)
    merchant_country: Mapped[str | None] = mapped_column(String(10), nullable=True)
    mcc_description: Mapped[str | None] = mapped_column(String(300), nullable=True)

    amount: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="CAD", nullable=False)

    transaction_type: Mapped[str] = mapped_column(
        String(20), default=TransactionType.expense, nullable=False
    )

    account_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("accounts.id"), nullable=True, index=True
    )
    category_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("categories.id"), nullable=True, index=True
    )

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    import_batch_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    is_excluded: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    recurring_rule_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("recurring_rules.id", ondelete="SET NULL"), nullable=True, index=True
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    account: Mapped["Account | None"] = relationship("Account", back_populates="transactions")
    category: Mapped["Category | None"] = relationship("Category", back_populates="transactions")


class BudgetRule(UserOwnedMixin, Base):
    __tablename__ = "budget_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    category_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("categories.id", ondelete="CASCADE"), nullable=True
    )
    limit_amount: Mapped[float] = mapped_column(Float, nullable=False)
    is_total: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
    )


class BudgetHiddenCategory(UserOwnedMixin, Base):
    __tablename__ = "budget_hidden_categories"
    __table_args__ = (
        UniqueConstraint("user_id", "category_key", name="uq_budget_hidden_categories_user_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    category_key: Mapped[str] = mapped_column(String(64), nullable=False)
    category_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("categories.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class RecurringRule(UserOwnedMixin, Base):
    __tablename__ = "recurring_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    merchant_name: Mapped[str] = mapped_column(String(200), nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    transaction_type: Mapped[str] = mapped_column(String(20), default="expense", nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="CAD", nullable=False)
    category_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("categories.id"), nullable=True
    )
    account_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("accounts.id"), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    frequency: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # monthly, weekly, biweekly, yearly
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)  # null = forever
    last_created_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ImportBatch(UserOwnedMixin, Base):
    __tablename__ = "import_batches"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    total_rows: Mapped[int] = mapped_column(Integer, default=0)
    imported_rows: Mapped[int] = mapped_column(Integer, default=0)
    skipped_rows: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class AppSetting(UserOwnedMixin, Base):
    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    default_currency: Mapped[str] = mapped_column(String(3), default="CAD", nullable=False)
