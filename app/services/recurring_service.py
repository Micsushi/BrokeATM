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
    """Return all dates that are due but not yet created for this rule."""
    ceiling = min(today, rule.end_date) if rule.end_date else today

    if rule.last_created_date is None:
        # First run — start from start_date
        cursor = rule.start_date
    else:
        cursor = _next_date(rule.last_created_date, rule.frequency)

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
            )
            db.add(tx)
            total_created += 1

        rule.last_created_date = dates[-1]

    db.commit()
    return {"created": total_created, "rules_triggered": rules_triggered}
