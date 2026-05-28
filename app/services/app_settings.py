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


def get_or_create_app_settings(db: Session, user_id: str | None = None) -> AppSetting:
    if user_id is None:
        settings = db.query(AppSetting).filter(AppSetting.user_id.is_(None)).first()
    else:
        settings = db.query(AppSetting).filter(AppSetting.user_id == user_id).first()
    if settings is None:
        settings = AppSetting(default_currency=DEFAULT_CURRENCY, user_id=user_id)
        if user_id is None:
            settings.id = SETTINGS_ROW_ID
        db.add(settings)
        db.flush()
    return settings


def ensure_app_settings(db: Session, user_id: str | None = None) -> AppSetting:
    settings = get_or_create_app_settings(db, user_id=user_id)
    db.commit()
    db.refresh(settings)
    return settings


def get_default_currency(db: Session, user_id: str | None = None) -> str:
    return get_or_create_app_settings(db, user_id=user_id).default_currency


def update_default_currency(
    db: Session,
    currency_code: str,
    user_id: str | None = None,
) -> AppSetting:
    currency = normalize_currency_code(currency_code)
    settings = get_or_create_app_settings(db, user_id=user_id)
    if settings.default_currency != currency:
        settings.default_currency = currency
        tx_q = db.query(Transaction)
        rule_q = db.query(RecurringRule)
        if user_id is None:
            tx_q = tx_q.filter(Transaction.user_id.is_(None))
            rule_q = rule_q.filter(RecurringRule.user_id.is_(None))
        else:
            tx_q = tx_q.filter(Transaction.user_id == user_id)
            rule_q = rule_q.filter(RecurringRule.user_id == user_id)
        tx_q.update({Transaction.currency: currency}, synchronize_session=False)
        rule_q.update(
            {RecurringRule.currency: currency},
            synchronize_session=False,
        )
    db.commit()
    db.refresh(settings)
    return settings
