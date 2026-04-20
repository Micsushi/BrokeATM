from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.core.utils import add_months
from app.models.models import RecurringRule, Transaction

RULE_TX_FIELDS = (
    "merchant_name",
    "amount",
    "transaction_type",
    "currency",
    "category_id",
    "account_id",
    "notes",
)


def _next_date(current: date, frequency: str) -> date:
    if frequency == "monthly":
        return add_months(current, 1)
    if frequency == "weekly":
        return current + timedelta(weeks=1)
    if frequency == "biweekly":
        return current + timedelta(weeks=2)
    if frequency == "yearly":
        return add_months(current, 12)
    raise ValueError(f"Unknown frequency: {frequency}")


def _due_dates(rule: RecurringRule, today: date) -> list[date]:
    ceiling = min(today, rule.end_date) if rule.end_date else today

    cursor = (
        _next_date(rule.last_created_date, rule.frequency)
        if rule.last_created_date
        else rule.start_date
    )

    dates = []
    while cursor <= ceiling:
        dates.append(cursor)
        cursor = _next_date(cursor, rule.frequency)
    return dates


def schedule_dates(
    start_date: date,
    frequency: str,
    end_date: date | None,
    today: date | None = None,
) -> list[date]:
    current_day = today or date.today()
    ceiling = min(current_day, end_date) if end_date else current_day
    if start_date > ceiling:
        return []

    dates = []
    cursor = start_date
    while cursor <= ceiling:
        dates.append(cursor)
        cursor = _next_date(cursor, frequency)
    return dates


def schedule_horizon(
    start_date: date,
    frequency: str,
    end_date: date | None,
    today: date | None = None,
) -> date | None:
    dates = schedule_dates(start_date, frequency, end_date, today=today)
    return dates[-1] if dates else None


def _build_transaction(rule: RecurringRule, tx_date: date) -> Transaction:
    return Transaction(
        transaction_date=tx_date,
        merchant_name=rule.merchant_name,
        amount=rule.amount,
        transaction_type=rule.transaction_type,
        currency=rule.currency,
        category_id=rule.category_id,
        account_id=rule.account_id,
        notes=rule.notes,
        recurring_rule_id=rule.id,
    )


def preview_rule_update(
    db: Session,
    rule: RecurringRule,
    fields: dict,
    *,
    today: date | None = None,
) -> dict:
    current_day = today or date.today()
    next_start = fields.get("start_date", rule.start_date)
    next_frequency = fields.get("frequency", rule.frequency)
    next_end = fields.get("end_date", rule.end_date)

    schedule_changed = (
        next_start != rule.start_date
        or next_frequency != rule.frequency
        or next_end != rule.end_date
    )

    expected_dates = set(
        schedule_dates(next_start, next_frequency, next_end, today=current_day)
    )
    existing_txs = (
        db.query(Transaction)
        .filter(Transaction.recurring_rule_id == rule.id)
        .order_by(Transaction.transaction_date.asc(), Transaction.id.asc())
        .all()
    )
    existing_dates = {tx.transaction_date for tx in existing_txs}
    overlap_ids = [tx.id for tx in existing_txs if tx.transaction_date not in expected_dates]
    missing_dates = sorted(expected_dates - existing_dates)

    return {
        "schedule_changed": schedule_changed,
        "overlap_ids": overlap_ids,
        "overlap_count": len(overlap_ids),
        "missing_dates": missing_dates,
        "missing_count": len(missing_dates),
        "horizon": schedule_horizon(next_start, next_frequency, next_end, today=current_day),
    }


def process_due_rules(db: Session) -> dict:
    today = date.today()
    rules = db.query(RecurringRule).all()

    total_created = 0
    rules_triggered = 0

    for rule in rules:
        dates = _due_dates(rule, today)
        if not dates:
            continue

        rules_triggered += 1
        for d in dates:
            db.add(_build_transaction(rule, d))
            total_created += 1

        rule.last_created_date = dates[-1]

    db.commit()
    return {"created": total_created, "rules_triggered": rules_triggered}


def apply_rule_update(
    db: Session,
    rule: RecurringRule,
    fields: dict,
    *,
    remove_overlap: bool = False,
    backfill_missing: bool = False,
    today: date | None = None,
) -> dict:
    impact = preview_rule_update(db, rule, fields, today=today)
    tx_fields = {k: v for k, v in fields.items() if k in RULE_TX_FIELDS}

    for key, val in fields.items():
        setattr(rule, key, val)

    if remove_overlap and impact["overlap_ids"]:
        db.query(Transaction).filter(
            Transaction.id.in_(impact["overlap_ids"])
        ).delete(synchronize_session=False)

    if tx_fields:
        db.query(Transaction).filter(
            Transaction.recurring_rule_id == rule.id
        ).update(tx_fields, synchronize_session=False)

    if backfill_missing:
        for tx_date in impact["missing_dates"]:
            db.add(_build_transaction(rule, tx_date))

    if impact["schedule_changed"]:
        rule.last_created_date = impact["horizon"]

    db.commit()
    db.refresh(rule)
    return impact


def delete_rule_transactions_from(db: Session, rule: RecurringRule, from_date: date) -> int:
    deleted = db.query(Transaction).filter(
        Transaction.recurring_rule_id == rule.id,
        Transaction.transaction_date >= from_date,
    ).delete(synchronize_session=False)

    prev_last = None
    if rule.last_created_date and rule.last_created_date >= from_date:
        prev_date = from_date - timedelta(days=1)
        remaining = db.query(Transaction).filter(
            Transaction.recurring_rule_id == rule.id,
            Transaction.transaction_date <= prev_date,
        ).order_by(Transaction.transaction_date.desc()).first()
        prev_last = remaining.transaction_date if remaining else None
        rule.last_created_date = prev_last

    new_end = from_date - timedelta(days=1)
    if rule.start_date > new_end:
        db.delete(rule)
    else:
        rule.end_date = new_end

    db.commit()
    return deleted


def delete_rule_and_all_transactions(db: Session, rule: RecurringRule) -> int:
    deleted = db.query(Transaction).filter(
        Transaction.recurring_rule_id == rule.id
    ).delete(synchronize_session=False)
    db.delete(rule)
    db.commit()
    return deleted
