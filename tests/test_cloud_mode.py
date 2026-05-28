from __future__ import annotations

from collections.abc import Generator
from datetime import date

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import (
    accounts_router,
    budget_router,
    import_router,
    recurring_router,
    settings_router,
    transactions_router,
)
from app.core.config import settings
from app.core.database import Base, get_db
from app.core.user_context import _bootstrapped_users
from app.models.models import Account, AppSetting, Category, Transaction

MOCK_USER_ID = "00000000-0000-4000-8000-000000000001"
OTHER_USER_ID = "00000000-0000-4000-8000-000000000999"


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = session_local()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture()
def cloud_client(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[TestClient, None, None]:
    monkeypatch.setattr(settings, "deployment_mode", "cloud")
    monkeypatch.setattr(settings, "auth_mode", "mock")
    _bootstrapped_users.clear()

    app = FastAPI()
    app.include_router(accounts_router.router)
    app.include_router(budget_router.router)
    app.include_router(import_router.router)
    app.include_router(recurring_router.router)
    app.include_router(settings_router.router)
    app.include_router(transactions_router.router)

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client


@pytest.fixture()
def local_client(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[TestClient, None, None]:
    monkeypatch.setattr(settings, "deployment_mode", "local")
    monkeypatch.setattr(settings, "auth_mode", "none")
    _bootstrapped_users.clear()

    app = FastAPI()
    app.include_router(accounts_router.router)
    app.include_router(budget_router.router)
    app.include_router(import_router.router)
    app.include_router(recurring_router.router)
    app.include_router(settings_router.router)
    app.include_router(transactions_router.router)

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client


def test_cloud_accounts_are_scoped_to_mock_user(
    cloud_client: TestClient,
    db_session: Session,
) -> None:
    db_session.add(Account(name="Local only", user_id=None))
    db_session.add(Account(name="Someone else", user_id=OTHER_USER_ID))
    db_session.commit()

    response = cloud_client.post("/api/accounts", json={"name": "Mine"})
    assert response.status_code == 201

    listed = cloud_client.get("/api/accounts")
    assert listed.status_code == 200
    assert [row["name"] for row in listed.json()] == ["Mine"]


def test_local_mode_does_not_require_auth_and_uses_unowned_rows(
    local_client: TestClient,
    db_session: Session,
) -> None:
    db_session.add(Account(name="Local checking", user_id=None))
    db_session.add(Account(name="Cloud account", user_id=MOCK_USER_ID))
    db_session.commit()

    response = local_client.get("/api/accounts")

    assert response.status_code == 200
    assert [row["name"] for row in response.json()] == ["Local checking"]


def test_cloud_transactions_are_scoped_for_list_summary_and_delete_all(
    cloud_client: TestClient,
    db_session: Session,
) -> None:
    db_session.add(
        Transaction(
            transaction_date=date(2026, 5, 1),
            merchant_name="Mine",
            amount=12.0,
            transaction_type="expense",
            currency="CAD",
            is_excluded=False,
            user_id=MOCK_USER_ID,
        )
    )
    db_session.add(
        Transaction(
            transaction_date=date(2026, 5, 2),
            merchant_name="Other",
            amount=99.0,
            transaction_type="expense",
            currency="CAD",
            is_excluded=False,
            user_id=OTHER_USER_ID,
        )
    )
    db_session.add(
        Transaction(
            transaction_date=date(2026, 5, 3),
            merchant_name="Local",
            amount=50.0,
            transaction_type="expense",
            currency="CAD",
            is_excluded=False,
            user_id=None,
        )
    )
    db_session.commit()

    listed = cloud_client.get("/api/transactions")
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["merchant_name"] == "Mine"

    summary = cloud_client.get("/api/transactions/summary")
    assert summary.status_code == 200
    assert summary.json()["expense"] == 12.0

    deleted = cloud_client.post("/api/transactions/delete-all")
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] == 1
    assert db_session.query(Transaction).count() == 2


def test_cloud_transaction_mutations_cannot_touch_other_user_rows(
    cloud_client: TestClient,
    db_session: Session,
) -> None:
    other = Transaction(
        transaction_date=date(2026, 5, 2),
        merchant_name="Other",
        amount=99.0,
        transaction_type="expense",
        currency="CAD",
        is_excluded=False,
        user_id=OTHER_USER_ID,
    )
    db_session.add(other)
    db_session.commit()
    db_session.refresh(other)

    get_response = cloud_client.get(f"/api/transactions/{other.id}")
    patch_response = cloud_client.patch(
        f"/api/transactions/{other.id}",
        json={"merchant_name": "Changed"},
    )
    delete_response = cloud_client.delete(f"/api/transactions/{other.id}")

    assert get_response.status_code == 404
    assert patch_response.status_code == 404
    assert delete_response.status_code == 404
    db_session.refresh(other)
    assert other.merchant_name == "Other"


def test_cloud_transaction_create_rejects_other_user_foreign_ids(
    cloud_client: TestClient,
    db_session: Session,
) -> None:
    other_category = Category(name="other food", user_id=OTHER_USER_ID)
    other_account = Account(name="Other checking", user_id=OTHER_USER_ID)
    db_session.add_all([other_category, other_account])
    db_session.commit()
    db_session.refresh(other_category)
    db_session.refresh(other_account)

    response = cloud_client.post(
        "/api/transactions",
        json={
            "transaction_date": "2026-05-04",
            "merchant_name": "Cafe",
            "amount": 12.5,
            "category_id": other_category.id,
            "account_id": other_account.id,
        },
    )

    assert response.status_code == 404
    assert db_session.query(Transaction).count() == 0


def test_cloud_transaction_update_rejects_other_user_category(
    cloud_client: TestClient,
    db_session: Session,
) -> None:
    tx = Transaction(
        transaction_date=date(2026, 5, 4),
        merchant_name="Mine",
        amount=12.5,
        transaction_type="expense",
        currency="CAD",
        is_excluded=False,
        user_id=MOCK_USER_ID,
    )
    other_category = Category(name="other food", user_id=OTHER_USER_ID)
    db_session.add_all([tx, other_category])
    db_session.commit()
    db_session.refresh(tx)
    db_session.refresh(other_category)

    response = cloud_client.patch(
        f"/api/transactions/{tx.id}",
        json={"category_id": other_category.id},
    )

    assert response.status_code == 404
    db_session.refresh(tx)
    assert tx.category_id is None


def test_cloud_recurring_create_rejects_other_user_account(
    cloud_client: TestClient,
    db_session: Session,
) -> None:
    other_account = Account(name="Other checking", user_id=OTHER_USER_ID)
    db_session.add(other_account)
    db_session.commit()
    db_session.refresh(other_account)

    response = cloud_client.post(
        "/api/recurring",
        json={
            "merchant_name": "Rent",
            "amount": 1000.0,
            "frequency": "monthly",
            "start_date": "2026-05-01",
            "account_id": other_account.id,
        },
    )

    assert response.status_code == 404


def test_cloud_budget_save_rejects_other_user_category(
    cloud_client: TestClient,
    db_session: Session,
) -> None:
    other_category = Category(name="other food", user_id=OTHER_USER_ID)
    db_session.add(other_category)
    db_session.commit()
    db_session.refresh(other_category)

    response = cloud_client.put(
        "/api/budget/settings",
        json={
            "total": 100.0,
            "rules": [{"category_id": other_category.id, "limit_amount": 50.0}],
            "hidden_category_keys": [f"cat:{other_category.id}"],
        },
    )

    assert response.status_code == 404


def test_cloud_settings_are_per_user(
    cloud_client: TestClient,
    db_session: Session,
) -> None:
    db_session.add(AppSetting(default_currency="USD", user_id=OTHER_USER_ID))
    db_session.add(AppSetting(default_currency="EUR", user_id=None))
    db_session.commit()

    initial = cloud_client.get("/api/settings")
    assert initial.status_code == 200
    assert initial.json()["default_currency"] == "CAD"

    updated = cloud_client.put("/api/settings", json={"default_currency": "JPY"})
    assert updated.status_code == 200
    assert updated.json()["default_currency"] == "JPY"

    values = {
        row.user_id: row.default_currency
        for row in db_session.query(AppSetting).order_by(AppSetting.id).all()
    }
    assert values[MOCK_USER_ID] == "JPY"
    assert values[OTHER_USER_ID] == "USD"
    assert values[None] == "EUR"


def test_cloud_parse_all_rejects_non_csv_endpoint(cloud_client: TestClient) -> None:
    response = cloud_client.post(
        "/api/import/parse-all",
        files={"file": ("statement.pdf", b"%PDF-1.4", "application/pdf")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Online mode supports CSV import only."


def test_local_parse_all_keeps_non_csv_endpoint_enabled(local_client: TestClient) -> None:
    response = local_client.post(
        "/api/import/parse-all",
        files={"file": ("statement.pdf", b"not actually a pdf", "application/pdf")},
    )

    assert response.status_code == 200
    assert isinstance(response.json(), list)
