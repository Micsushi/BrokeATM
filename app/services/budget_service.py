import calendar
from datetime import date

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.models import BudgetRule, Category, Transaction


def _add_months(d: date, n: int) -> date:
    month = d.month - 1 + n
    year = d.year + month // 12
    month = month % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _ym(d: date) -> str:
    return f"{d.year}-{str(d.month).zfill(2)}"


def get_budget_rules(db: Session) -> dict:
    rules = db.query(BudgetRule).all()
    return {
        "total": next((r.limit_amount for r in rules if r.is_total), None),
        "rules": [
            {"category_id": r.category_id, "limit_amount": r.limit_amount}
            for r in rules if not r.is_total
        ],
    }


def save_budget_rules(db: Session, total: float | None, rules: list[dict]) -> None:
    cat_sum = sum(r["limit_amount"] for r in rules)
    if total is not None and total < cat_sum:
        raise ValueError(
            f"Total budget ({total:.2f}) must be ≥ sum of category budgets ({cat_sum:.2f})"
        )
    db.query(BudgetRule).delete()
    if total is not None:
        db.add(BudgetRule(category_id=None, limit_amount=total, is_total=True))
    for rule in rules:
        db.add(BudgetRule(
            category_id=rule["category_id"],
            limit_amount=rule["limit_amount"],
            is_total=False,
        ))
    db.commit()


def get_settings_with_averages(db: Session, avg_months: int = 3) -> dict:
    today = date.today()
    start = _add_months(today, -avg_months)
    start_str = f"{_ym(start)}-01"

    rows = (
        db.query(
            Transaction.category_id,
            Category.name.label("cat_name"),
            Category.color.label("cat_color"),
            func.sum(Transaction.amount).label("total"),
        )
        .outerjoin(Category, Transaction.category_id == Category.id)
        .filter(
            Transaction.transaction_type == "expense",
            Transaction.transaction_date >= start_str,
        )
        .group_by(Transaction.category_id, Category.name, Category.color)
        .all()
    )

    rules = db.query(BudgetRule).all()
    total_budget = next((r.limit_amount for r in rules if r.is_total), None)
    cat_limits = {r.category_id: r.limit_amount for r in rules if not r.is_total}

    categories = []
    for r in rows:
        categories.append({
            "category_id": r.category_id,
            "category_name": r.cat_name or "Uncategorized",
            "category_color": r.cat_color,
            "avg_monthly": round(r.total / avg_months, 2),
            "limit_amount": cat_limits.get(r.category_id),
        })

    # Also include categories that have a budget but no spending in this period
    for cat_id, limit in cat_limits.items():
        if not any(c["category_id"] == cat_id for c in categories):
            cat = db.get(Category, cat_id)
            categories.append({
                "category_id": cat_id,
                "category_name": cat.name if cat else "Unknown",
                "category_color": cat.color if cat else None,
                "avg_monthly": 0.0,
                "limit_amount": limit,
            })

    categories.sort(key=lambda c: c["avg_monthly"], reverse=True)
    return {"total": total_budget, "avg_months": avg_months, "categories": categories}


def get_monthly_summary(db: Session, months: int = 6) -> dict:
    today = date.today()

    month_list = []
    for i in range(months - 1, -1, -1):
        d = _add_months(today, -i)
        month_list.append({
            "ym": _ym(d),
            "label": d.strftime("%b %Y"),
        })

    start_ym = month_list[0]["ym"]
    end_ym = month_list[-1]["ym"]

    rules = db.query(BudgetRule).all()
    total_budget = next((r.limit_amount for r in rules if r.is_total), None)
    cat_budgets = {r.category_id: r.limit_amount for r in rules if not r.is_total}
    budgeted_ids = set(cat_budgets.keys())

    rows = (
        db.query(
            func.strftime("%Y-%m", Transaction.transaction_date).label("ym"),
            Transaction.category_id,
            Category.name.label("cat_name"),
            func.sum(Transaction.amount).label("total"),
        )
        .outerjoin(Category, Transaction.category_id == Category.id)
        .filter(
            Transaction.transaction_type == "expense",
            func.strftime("%Y-%m", Transaction.transaction_date) >= start_ym,
            func.strftime("%Y-%m", Transaction.transaction_date) <= end_ym,
        )
        .group_by("ym", Transaction.category_id, Category.name)
        .all()
    )

    # Index: (ym, category_id) -> {name, spent}
    spending: dict[tuple, dict] = {}
    for r in rows:
        spending[(r.ym, r.category_id)] = {"cat_name": r.cat_name, "spent": r.total}

    # Resolve category names for budgeted cats not in spending
    cat_name_cache: dict[int, str] = {}
    for cat_id in budgeted_ids:
        if cat_id is not None:
            cat = db.get(Category, cat_id)
            cat_name_cache[cat_id] = cat.name if cat else "Unknown"

    monthly = []
    for mo in month_list:
        ym = mo["ym"]

        items = []
        for cat_id, budget_limit in cat_budgets.items():
            key = (ym, cat_id)
            spent = spending.get(key, {}).get("spent", 0.0)
            name = spending.get(key, {}).get("cat_name") or cat_name_cache.get(cat_id, "Unknown")
            items.append({
                "category_id": cat_id,
                "category_name": name,
                "budget": budget_limit,
                "spent": round(spent, 2),
                "over": spent > budget_limit,
            })

        others_spent = sum(
            info["spent"]
            for (m, cat_id), info in spending.items()
            if m == ym and cat_id not in budgeted_ids
        )
        total_spent = sum(
            info["spent"]
            for (m, _), info in spending.items()
            if m == ym
        )

        monthly.append({
            "ym": ym,
            "label": mo["label"],
            "total_budget": total_budget,
            "total_spent": round(total_spent, 2),
            "others_spent": round(others_spent, 2),
            "items": items,
        })

    return {"months": months, "total_budget": total_budget, "monthly": monthly}
