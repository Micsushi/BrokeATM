from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.core.utils import add_months
from app.models.models import RecurringRule, Transaction


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

    cursor = _next_date(rule.last_created_date, rule.frequency) if rule.last_created_date else rule.start_date

    dates = []
    while cursor <= ceiling:
        dates.append(cursor)
        cursor = _next_date(cursor, rule.frequency)
    return dates


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
            tx = Transaction(
                transaction_date=d,
                merchant_name=rule.merchant_name,
                amount=rule.amount,
                transaction_type=rule.transaction_type,
                currency=rule.currency,
                category_id=rule.category_id,
                account_id=rule.account_id,
                notes=rule.notes,
                recurring_rule_id=rule.id,
            )
            db.add(tx)
            total_created += 1

        rule.last_created_date = dates[-1]

    db.commit()
    return {"created": total_created, "rules_triggered": rules_triggered}


def update_rule_and_transactions(db: Session, rule: RecurringRule, fields: dict) -> None:
    tx_fields = {k: v for k, v in fields.items() if k in (
        "merchant_name", "amount", "transaction_type", "currency",
        "category_id", "account_id", "notes",
    )}

    for key, val in fields.items():
        setattr(rule, key, val)

    if tx_fields:
        db.query(Transaction).filter(
            Transaction.recurring_rule_id == rule.id
        ).update(tx_fields, synchronize_session=False)

    db.commit()
    db.refresh(rule)


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


def count_transactions_after(db: Session, rule_id: int, after_date: date) -> int:
    return db.query(Transaction).filter(
        Transaction.recurring_rule_id == rule_id,
        Transaction.transaction_date > after_date,
    ).count()


def remove_transactions_after(db: Session, rule_id: int, after_date: date) -> int:
    return db.query(Transaction).filter(
        Transaction.recurring_rule_id == rule_id,
        Transaction.transaction_date > after_date,
    ).delete(synchronize_session=False)
