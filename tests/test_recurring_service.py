from __future__ import annotations

from collections.abc import Generator
from datetime import date

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.api import recurring_router
from app.core.database import Base, get_db
from app.models.models import RecurringRule, Transaction
from app.services.recurring_service import apply_rule_update, preview_rule_update, schedule_dates


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


@pytest.fixture()
def recurring_client(db_session: Session) -> TestClient:
    app = FastAPI()
    app.include_router(recurring_router.router)

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        yield client


def make_rule(
    db_session: Session,
    *,
    merchant_name: str = "Gym",
    start_date: date = date(2020, 1, 1),
    end_date: date | None = date(2020, 4, 1),
    frequency: str = "monthly",
    last_created_date: date | None = date(2020, 4, 1),
) -> RecurringRule:
    rule = RecurringRule(
        merchant_name=merchant_name,
        amount=50.0,
        transaction_type="expense",
        currency="CAD",
        category_id=None,
        account_id=None,
        notes="Membership",
        frequency=frequency,
        start_date=start_date,
        end_date=end_date,
        last_created_date=last_created_date,
    )
    db_session.add(rule)
    db_session.commit()
    db_session.refresh(rule)
    return rule


def add_linked_transaction(db_session: Session, rule: RecurringRule, tx_date: date) -> Transaction:
    tx = Transaction(
        transaction_date=tx_date,
        merchant_name=rule.merchant_name,
        amount=rule.amount,
        transaction_type=rule.transaction_type,
        currency=rule.currency,
        category_id=rule.category_id,
        account_id=rule.account_id,
        notes=rule.notes,
        recurring_rule_id=rule.id,
        is_excluded=False,
    )
    db_session.add(tx)
    db_session.commit()
    db_session.refresh(tx)
    return tx


def linked_dates(db_session: Session, rule_id: int) -> list[date]:
    rows = (
        db_session.query(Transaction)
        .filter(Transaction.recurring_rule_id == rule_id)
        .order_by(Transaction.transaction_date.asc())
        .all()
    )
    return [row.transaction_date for row in rows]


def test_schedule_dates_monthly_preserves_anchor_day_after_short_month() -> None:
    assert schedule_dates(
        date(2025, 8, 31),
        "monthly",
        date(2026, 3, 31),
        today=date(2026, 4, 1),
    ) == [
        date(2025, 8, 31),
        date(2025, 9, 30),
        date(2025, 10, 31),
        date(2025, 11, 30),
        date(2025, 12, 31),
        date(2026, 1, 31),
        date(2026, 2, 28),
        date(2026, 3, 31),
    ]


def test_schedule_dates_monthly_returns_to_original_day_after_february() -> None:
    assert schedule_dates(
        date(2025, 1, 29),
        "monthly",
        date(2025, 4, 30),
        today=date(2025, 5, 1),
    ) == [
        date(2025, 1, 29),
        date(2025, 2, 28),
        date(2025, 3, 29),
        date(2025, 4, 29),
    ]


def test_preview_rule_update_reports_overlap_and_missing_entries(db_session: Session) -> None:
    rule = make_rule(db_session)
    for tx_date in [date(2020, 1, 1), date(2020, 2, 1), date(2020, 3, 1), date(2020, 4, 1)]:
        add_linked_transaction(db_session, rule, tx_date)

    impact = preview_rule_update(
        db_session,
        rule,
        {"start_date": date(2020, 2, 1), "end_date": date(2020, 5, 1)},
        today=date(2020, 5, 20),
    )

    assert impact["schedule_changed"] is True
    assert impact["overlap_count"] == 1
    assert impact["missing_count"] == 1
    assert impact["missing_dates"] == [date(2020, 5, 1)]
    assert impact["horizon"] == date(2020, 5, 1)


def test_apply_rule_update_backfills_full_schedule_window(db_session: Session) -> None:
    rule = make_rule(
        db_session,
        start_date=date(2020, 1, 1),
        end_date=date(2020, 4, 1),
        last_created_date=date(2020, 4, 1),
    )
    for tx_date in [date(2020, 1, 1), date(2020, 3, 1), date(2020, 4, 1)]:
        add_linked_transaction(db_session, rule, tx_date)

    apply_rule_update(
        db_session,
        rule,
        {"start_date": date(2019, 12, 1)},
        backfill_missing=True,
        today=date(2020, 4, 20),
    )

    assert linked_dates(db_session, rule.id) == [
        date(2019, 12, 1),
        date(2020, 1, 1),
        date(2020, 2, 1),
        date(2020, 3, 1),
        date(2020, 4, 1),
    ]
    db_session.refresh(rule)
    assert rule.start_date == date(2019, 12, 1)
    assert rule.last_created_date == date(2020, 4, 1)


def test_apply_rule_update_removes_entries_outside_new_schedule(db_session: Session) -> None:
    rule = make_rule(
        db_session,
        start_date=date(2020, 1, 1),
        end_date=date(2020, 5, 1),
        last_created_date=date(2020, 5, 1),
    )
    for tx_date in [
        date(2020, 1, 1),
        date(2020, 2, 1),
        date(2020, 3, 1),
        date(2020, 4, 1),
        date(2020, 5, 1),
    ]:
        add_linked_transaction(db_session, rule, tx_date)

    apply_rule_update(
        db_session,
        rule,
        {"start_date": date(2020, 3, 1), "end_date": date(2020, 4, 1)},
        remove_overlap=True,
        today=date(2020, 5, 20),
    )

    assert linked_dates(db_session, rule.id) == [date(2020, 3, 1), date(2020, 4, 1)]
    db_session.refresh(rule)
    assert rule.start_date == date(2020, 3, 1)
    assert rule.end_date == date(2020, 4, 1)
    assert rule.last_created_date == date(2020, 4, 1)


def test_update_rule_returns_confirmation_preview_when_schedule_change_has_impact(
    db_session: Session,
    recurring_client: TestClient,
) -> None:
    rule = make_rule(
        db_session,
        start_date=date(2020, 1, 1),
        end_date=date(2020, 4, 1),
        last_created_date=date(2020, 4, 1),
    )
    for tx_date in [date(2020, 1, 1), date(2020, 2, 1), date(2020, 3, 1), date(2020, 4, 1)]:
        add_linked_transaction(db_session, rule, tx_date)

    response = recurring_client.patch(
        f"/api/recurring/{rule.id}",
        json={
            "merchant_name": rule.merchant_name,
            "amount": rule.amount,
            "transaction_type": rule.transaction_type,
            "currency": rule.currency,
            "category_id": rule.category_id,
            "account_id": rule.account_id,
            "notes": rule.notes,
            "frequency": rule.frequency,
            "start_date": "2020-02-01",
            "end_date": "2020-05-01",
        },
    )

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["needs_confirmation"] is True
    assert detail["overlap_count"] == 1
    assert detail["missing_count"] == 1
