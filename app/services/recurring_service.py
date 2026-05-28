from datetime import date, timedelta
from typing import Any

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


def _scheduled_date(start_date: date, frequency: str, step: int) -> date:
    if frequency == "monthly":
        return add_months(start_date, step, anchor_day=start_date.day)
    if frequency == "weekly":
        return start_date + timedelta(weeks=step)
    if frequency == "biweekly":
        return start_date + timedelta(weeks=2 * step)
    if frequency == "yearly":
        return add_months(start_date, 12 * step, anchor_day=start_date.day)
    raise ValueError(f"Unknown frequency: {frequency}")


def _due_dates(rule: RecurringRule, today: date) -> list[date]:
    dates = schedule_dates(
        rule.start_date,
        rule.frequency,
        rule.end_date,
        today=today,
    )
    if not rule.last_created_date:
        return dates
    return [tx_date for tx_date in dates if tx_date > rule.last_created_date]


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
    step = 0
    while True:
        cursor = _scheduled_date(start_date, frequency, step)
        if cursor > ceiling:
            break
        dates.append(cursor)
        step += 1
    return dates


def schedule_horizon(
    start_date: date,
    frequency: str,
    end_date: date | None,
    today: date | None = None,
) -> date | None:
    dates = schedule_dates(start_date, frequency, end_date, today=today)
    return dates[-1] if dates else None


def _scope(q: Any, model: Any, user_id: str | None) -> Any:
    if user_id is not None:
        return q.filter(model.user_id == user_id)
    return q.filter(model.user_id.is_(None))


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
        user_id=rule.user_id,
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
        .filter(
            Transaction.recurring_rule_id == rule.id,
            Transaction.user_id == rule.user_id
            if rule.user_id is not None
            else Transaction.user_id.is_(None),
        )
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


def process_due_rules(db: Session, user_id: str | None = None) -> dict:
    today = date.today()
    rules = _scope(db.query(RecurringRule), RecurringRule, user_id).all()

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

    owner_filter = (
        Transaction.user_id == rule.user_id
        if rule.user_id is not None
        else Transaction.user_id.is_(None)
    )

    if remove_overlap and impact["overlap_ids"]:
        db.query(Transaction).filter(
            Transaction.id.in_(impact["overlap_ids"]),
            owner_filter,
        ).delete(synchronize_session=False)

    if tx_fields:
        db.query(Transaction).filter(
            Transaction.recurring_rule_id == rule.id,
            owner_filter,
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
    owner_filter = (
        Transaction.user_id == rule.user_id
        if rule.user_id is not None
        else Transaction.user_id.is_(None)
    )
    deleted = db.query(Transaction).filter(
        Transaction.recurring_rule_id == rule.id,
        Transaction.transaction_date >= from_date,
        owner_filter,
    ).delete(synchronize_session=False)

    prev_last = None
    if rule.last_created_date and rule.last_created_date >= from_date:
        prev_date = from_date - timedelta(days=1)
        remaining = db.query(Transaction).filter(
            Transaction.recurring_rule_id == rule.id,
            Transaction.transaction_date <= prev_date,
            owner_filter,
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
    owner_filter = (
        Transaction.user_id == rule.user_id
        if rule.user_id is not None
        else Transaction.user_id.is_(None)
    )
    deleted = db.query(Transaction).filter(
        Transaction.recurring_rule_id == rule.id,
        owner_filter,
    ).delete(synchronize_session=False)
    db.delete(rule)
    db.commit()
    return deleted
