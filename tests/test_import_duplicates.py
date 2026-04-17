from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import Base
from app.models.models import Account, Transaction
from app.services.import_service import check_duplicates, commit_import


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


def make_row(**overrides):
    row = {
        "transaction_date": date(2026, 2, 3),
        "posted_date": None,
        "reference_number": None,
        "merchant_name": "Amazon Marketplace",
        "merchant_city": None,
        "merchant_state": None,
        "merchant_country": None,
        "mcc_description": None,
        "amount": 14.99,
        "currency": "CAD",
        "transaction_type": "expense",
        "suggested_category": "shopping",
        "category_name": "shopping",
        "card_number_masked": None,
        "cardholder": "Import User",
        "exclude": False,
        "notes": None,
        "source_file": "statement.pdf",
        "import_month": 2,
        "import_year": 2026,
    }
    row.update(overrides)
    return row


def test_check_duplicates_marks_refless_rows_within_upload(db_session: Session):
    rows = [make_row(), make_row()]

    result = check_duplicates(db_session, rows)

    assert result[0]["duplicate"] is False
    assert result[1]["duplicate"] is True
    assert result[1]["duplicate_in_import"] is True
    assert result[1]["duplicate_in_database"] is False


def test_check_duplicates_marks_refless_rows_against_database(db_session: Session):
    account = Account(name="Imported PDF", card_number_masked="")
    db_session.add(account)
    db_session.flush()
    db_session.add(
        Transaction(
            transaction_date=date(2026, 2, 3),
            posted_date=None,
            reference_number=None,
            merchant_name="Amazon   Marketplace",
            merchant_city=None,
            merchant_state=None,
            merchant_country=None,
            mcc_description=None,
            amount=14.99,
            currency="CAD",
            transaction_type="expense",
            account_id=account.id,
            category_id=None,
            notes=None,
            import_batch_id="existing-batch",
            is_excluded=False,
        )
    )
    db_session.commit()

    result = check_duplicates(db_session, [make_row()])

    assert result[0]["duplicate"] is True
    assert result[0]["duplicate_in_import"] is False
    assert result[0]["duplicate_in_database"] is True


def test_commit_import_skips_refless_duplicate_rows_within_upload(db_session: Session):
    _, imported, skipped = commit_import(
        db_session,
        rows=[make_row(), make_row()],
        filename="statement.pdf",
        month=2,
        year=2026,
    )

    assert imported == 1
    assert skipped == 1
    assert db_session.query(Transaction).count() == 1


def test_commit_import_skips_refless_duplicate_rows_against_database(db_session: Session):
    account = Account(name="Imported PDF", card_number_masked="")
    db_session.add(account)
    db_session.flush()
    db_session.add(
        Transaction(
            transaction_date=date(2026, 2, 3),
            posted_date=None,
            reference_number=None,
            merchant_name="Amazon Marketplace",
            merchant_city=None,
            merchant_state=None,
            merchant_country=None,
            mcc_description=None,
            amount=14.99,
            currency="CAD",
            transaction_type="expense",
            account_id=account.id,
            category_id=None,
            notes=None,
            import_batch_id="existing-batch",
            is_excluded=False,
        )
    )
    db_session.commit()

    _, imported, skipped = commit_import(
        db_session,
        rows=[make_row()],
        filename="statement.pdf",
        month=2,
        year=2026,
    )

    assert imported == 0
    assert skipped == 1
    assert db_session.query(Transaction).count() == 1
