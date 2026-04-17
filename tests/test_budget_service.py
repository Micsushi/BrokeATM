from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import Base
from app.models.models import Category, Transaction
from app.services.budget_service import (
    budget_category_key,
    get_settings_with_averages,
    save_budget_rules,
)


@pytest.fixture()
def db_session() -> Session:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def make_expense(category_id: int | None, merchant_name: str, amount: float) -> Transaction:
    return Transaction(
        transaction_date=date.today(),
        posted_date=None,
        reference_number=None,
        merchant_name=merchant_name,
        merchant_city=None,
        merchant_state=None,
        merchant_country=None,
        mcc_description=None,
        amount=amount,
        currency="CAD",
        transaction_type="expense",
        account_id=None,
        category_id=category_id,
        notes=None,
        import_batch_id=None,
        is_excluded=False,
    )


def test_hidden_budget_categories_persist_in_settings(db_session: Session):
    groceries = Category(name="Groceries", color="#10b981")
    transfers = Category(name="Transfers", color="#64748b")
    db_session.add_all([groceries, transfers])
    db_session.flush()
    db_session.add_all([
        make_expense(groceries.id, "Trader Joe's", 82.5),
        make_expense(transfers.id, "Savings Transfer", 200.0),
    ])
    db_session.commit()

    save_budget_rules(
        db_session,
        total=400,
        rules=[{"category_id": groceries.id, "limit_amount": 150}],
        hidden_category_keys=[budget_category_key(transfers.id)],
    )

    settings = get_settings_with_averages(db_session)
    categories = {row["category_key"]: row for row in settings["categories"]}

    assert settings["hidden_category_keys"] == [budget_category_key(transfers.id)]
    assert categories[budget_category_key(groceries.id)]["limit_amount"] == 150
    assert categories[budget_category_key(transfers.id)]["avg_6m"] > 0
    assert categories[budget_category_key(transfers.id)]["limit_amount"] is None


def test_budgeted_categories_are_not_saved_as_hidden(db_session: Session):
    groceries = Category(name="Groceries", color="#10b981")
    db_session.add(groceries)
    db_session.flush()
    db_session.add(make_expense(groceries.id, "Costco", 120.0))
    db_session.commit()

    save_budget_rules(
        db_session,
        total=300,
        rules=[{"category_id": groceries.id, "limit_amount": 200}],
        hidden_category_keys=[budget_category_key(groceries.id)],
    )

    settings = get_settings_with_averages(db_session)

    assert settings["hidden_category_keys"] == []
