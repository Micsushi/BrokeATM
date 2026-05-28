from __future__ import annotations

import pytest
from sqlalchemy import create_engine, inspect, text

from app.core import database
from app.core.config import settings


def test_startup_adds_user_scope_columns_to_existing_local_sqlite_db(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    with engine.begin() as connection:
        connection.execute(
            text("CREATE TABLE accounts (id INTEGER PRIMARY KEY, name VARCHAR(100))")
        )
        connection.execute(
            text("CREATE TABLE categories (id INTEGER PRIMARY KEY, name VARCHAR(100))")
        )
        connection.execute(text("INSERT INTO accounts (name) VALUES ('Checking')"))

    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(settings, "database_backend", "sqlite")

    database.ensure_local_user_scope_columns(("accounts", "categories"))

    inspector = inspect(engine)
    assert "user_id" in {column["name"] for column in inspector.get_columns("accounts")}
    assert "user_id" in {column["name"] for column in inspector.get_columns("categories")}

    with engine.connect() as connection:
        row = connection.execute(text("SELECT name, user_id FROM accounts")).one()
    assert row.name == "Checking"
    assert row.user_id is None
