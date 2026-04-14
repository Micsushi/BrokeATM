from datetime import date

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.utils import add_months
from app.models.models import BudgetRule, Category, Transaction


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


def get_settings_with_averages(db: Session, avg_months: int = 6) -> dict:
    """Always computes 1, 3, and 6 month averages in one query. avg_months kept for compat."""
    today = date.today()
    start_6m = add_months(today, -6)
    start_str = f"{_ym(start_6m)}-01"

    # Compute cutoff YM strings for 1m and 3m windows
    ym_1m = _ym(add_months(today, -1))
    ym_3m = _ym(add_months(today, -3))

    rows = (
        db.query(
            func.strftime("%Y-%m", Transaction.transaction_date).label("ym"),
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
        .group_by("ym", Transaction.category_id, Category.name, Category.color)
        .all()
    )

    rules = db.query(BudgetRule).all()
    total_budget = next((r.limit_amount for r in rules if r.is_total), None)
    cat_limits = {r.category_id: r.limit_amount for r in rules if not r.is_total}

    # Accumulate per-category totals for each window
    cat_meta: dict[int | None, dict] = {}
    for r in rows:
        k = r.category_id
        if k not in cat_meta:
            cat_meta[k] = {"name": r.cat_name or "Uncategorized", "color": r.cat_color,
                            "t6": 0.0, "t3": 0.0, "t1": 0.0}
        cat_meta[k]["t6"] += r.total
        if r.ym >= ym_3m:
            cat_meta[k]["t3"] += r.total
        if r.ym >= ym_1m:
            cat_meta[k]["t1"] += r.total

    # Also include categories that have a budget but no spending in this period
    for cat_id in cat_limits:
        if cat_id not in cat_meta:
            cat = db.get(Category, cat_id)
            cat_meta[cat_id] = {"name": cat.name if cat else "Unknown",
                                 "color": cat.color if cat else None,
                                 "t6": 0.0, "t3": 0.0, "t1": 0.0}

    categories = []
    for cat_id, m in cat_meta.items():
        categories.append({
            "category_id": cat_id,
            "category_name": m["name"],
            "category_color": m["color"],
            "avg_6m": round(m["t6"] / 6, 2),
            "avg_3m": round(m["t3"] / 3, 2),
            "avg_1m": round(m["t1"] / 1, 2),
            "avg_monthly": round(m["t6"] / 6, 2),  # kept for schema compat
            "limit_amount": cat_limits.get(cat_id),
        })

    categories.sort(key=lambda c: c["avg_6m"], reverse=True)
    return {"total": total_budget, "avg_months": 6, "categories": categories}


def _month_range(from_ym: str, to_ym: str) -> list[dict]:
    """Return [{ym, label}] for every month between from_ym and to_ym inclusive."""
    fy, fm = int(from_ym[:4]), int(from_ym[5:7])
    ty, tm = int(to_ym[:4]), int(to_ym[5:7])
    result = []
    y, m = fy, fm
    while (y, m) <= (ty, tm):
        ym = f"{y}-{str(m).zfill(2)}"
        label = date(y, m, 1).strftime("%b %Y")
        result.append({"ym": ym, "label": label})
        m += 1
        if m > 12:
            m, y = 1, y + 1
    return result


def get_monthly_summary(
    db: Session,
    months: int = 6,
    from_ym: str | None = None,
    to_ym: str | None = None,
) -> dict:
    today = date.today()

    if from_ym and to_ym:
        month_list = _month_range(from_ym, to_ym)
    else:
        month_list = []
        for i in range(months - 1, -1, -1):
            d = add_months(today, -i)
            month_list.append({"ym": _ym(d), "label": d.strftime("%b %Y")})

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
            Category.color.label("cat_color"),
            func.sum(Transaction.amount).label("total"),
        )
        .outerjoin(Category, Transaction.category_id == Category.id)
        .filter(
            Transaction.transaction_type == "expense",
            func.strftime("%Y-%m", Transaction.transaction_date) >= start_ym,
            func.strftime("%Y-%m", Transaction.transaction_date) <= end_ym,
        )
        .group_by("ym", Transaction.category_id, Category.name, Category.color)
        .all()
    )

    # Index: (ym, category_id) -> {name, color, spent}
    spending: dict[tuple, dict] = {}
    for r in rows:
        spending[(r.ym, r.category_id)] = {"cat_name": r.cat_name, "cat_color": r.cat_color, "spent": r.total}

    # Resolve category names/colors for budgeted cats not in spending
    cat_meta_cache: dict[int, dict] = {}
    for cat_id in budgeted_ids:
        if cat_id is not None:
            cat = db.get(Category, cat_id)
            cat_meta_cache[cat_id] = {"name": cat.name if cat else "Unknown", "color": cat.color if cat else None}

    monthly = []
    for mo in month_list:
        ym = mo["ym"]

        items = []
        for cat_id, budget_limit in cat_budgets.items():
            key = (ym, cat_id)
            spent = spending.get(key, {}).get("spent", 0.0)
            name = spending.get(key, {}).get("cat_name") or cat_meta_cache.get(cat_id, {}).get("name", "Unknown")
            color = spending.get(key, {}).get("cat_color") or cat_meta_cache.get(cat_id, {}).get("color")
            items.append({
                "category_id": cat_id,
                "category_name": name,
                "category_color": color,
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

    return {"months": len(month_list), "total_budget": total_budget, "monthly": monthly}
