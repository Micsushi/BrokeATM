from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.models import AppSetting, RecurringRule, Transaction

DEFAULT_CURRENCY = "CAD"
SETTINGS_ROW_ID = 1


def normalize_currency_code(code: str | None) -> str:
    value = (code or DEFAULT_CURRENCY).strip().upper()
    if len(value) != 3 or not value.isalpha():
        raise ValueError("Currency must be a 3-letter ISO code.")
    return value


def get_or_create_app_settings(db: Session) -> AppSetting:
    settings = db.get(AppSetting, SETTINGS_ROW_ID)
    if settings is None:
        settings = AppSetting(id=SETTINGS_ROW_ID, default_currency=DEFAULT_CURRENCY)
        db.add(settings)
        db.flush()
    return settings


def ensure_app_settings(db: Session) -> AppSetting:
    settings = get_or_create_app_settings(db)
    db.commit()
    db.refresh(settings)
    return settings


def get_default_currency(db: Session) -> str:
    return get_or_create_app_settings(db).default_currency


def update_default_currency(db: Session, currency_code: str) -> AppSetting:
    currency = normalize_currency_code(currency_code)
    settings = get_or_create_app_settings(db)
    if settings.default_currency != currency:
        settings.default_currency = currency
        db.query(Transaction).update({Transaction.currency: currency}, synchronize_session=False)
        db.query(RecurringRule).update(
            {RecurringRule.currency: currency},
            synchronize_session=False,
        )
    db.commit()
    db.refresh(settings)
    return settings
