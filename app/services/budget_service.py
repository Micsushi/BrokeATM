from datetime import date
from typing import Any

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.utils import add_months
from app.models.models import BudgetHiddenCategory, BudgetRule, Category, Transaction

UNCATEGORIZED_BUDGET_KEY = "uncategorized"


def budget_category_key(category_id: int | None) -> str:
    if category_id is None:
        return UNCATEGORIZED_BUDGET_KEY
    return f"cat:{category_id}"


def _category_id_from_budget_key(category_key: str) -> int | None:
    if category_key == UNCATEGORIZED_BUDGET_KEY:
        return None
    if category_key.startswith("cat:"):
        try:
            return int(category_key.split(":", 1)[1])
        except ValueError:
            return None
    return None


def _ym(d: date) -> str:
    return f"{d.year}-{str(d.month).zfill(2)}"


def _ym_expr() -> Any:
    if settings.database_backend == "supabase_postgres":
        return func.to_char(Transaction.transaction_date, "YYYY-MM")
    return func.strftime("%Y-%m", Transaction.transaction_date)


def _scope(q: Any, model: Any, user_id: str | None) -> Any:
    if user_id is not None:
        return q.filter(model.user_id == user_id)
    return q.filter(model.user_id.is_(None))


def _category_join_condition(user_id: str | None) -> Any:
    owner_condition = (
        Category.user_id == user_id if user_id is not None else Category.user_id.is_(None)
    )
    return and_(Transaction.category_id == Category.id, owner_condition)


def _get_owned_category(db: Session, category_id: int, user_id: str | None) -> Category | None:
    return _scope(db.query(Category), Category, user_id).filter(Category.id == category_id).first()


def get_budget_rules(db: Session, user_id: str | None = None) -> dict:
    rules = _scope(db.query(BudgetRule), BudgetRule, user_id).all()
    hidden_keys = sorted(
        row.category_key
        for row in _scope(db.query(BudgetHiddenCategory), BudgetHiddenCategory, user_id).all()
    )
    return {
        "total": next((r.limit_amount for r in rules if r.is_total), None),
        "rules": [
            {"category_id": r.category_id, "limit_amount": r.limit_amount}
            for r in rules if not r.is_total
        ],
        "hidden_category_keys": hidden_keys,
    }


def save_budget_rules(
    db: Session,
    total: float | None,
    rules: list[dict],
    hidden_category_keys: list[str] | None = None,
    user_id: str | None = None,
) -> None:
    cat_sum = sum(r["limit_amount"] for r in rules)
    if total is not None and total < cat_sum:
        raise ValueError(
            f"Total budget ({total:.2f}) must be ≥ sum of category budgets ({cat_sum:.2f})"
        )

    visible_keys = {
        budget_category_key(rule["category_id"])
        for rule in rules
    }
    hidden_keys = {
        key
        for key in (hidden_category_keys or [])
        if key and key not in visible_keys
    }

    _scope(db.query(BudgetRule), BudgetRule, user_id).delete(synchronize_session=False)
    _scope(db.query(BudgetHiddenCategory), BudgetHiddenCategory, user_id).delete(
        synchronize_session=False
    )
    if total is not None:
        db.add(BudgetRule(category_id=None, limit_amount=total, is_total=True, user_id=user_id))
    for rule in rules:
        db.add(BudgetRule(
            category_id=rule["category_id"],
            limit_amount=rule["limit_amount"],
            is_total=False,
            user_id=user_id,
        ))
    for category_key in sorted(hidden_keys):
        db.add(BudgetHiddenCategory(
            category_key=category_key,
            category_id=_category_id_from_budget_key(category_key),
            user_id=user_id,
        ))
    db.commit()


def get_settings_with_averages(
    db: Session,
    avg_months: int = 6,
    user_id: str | None = None,
) -> dict:
    """Always computes 1, 3, and 6 month averages in one query. avg_months kept for compat."""
    today = date.today()
    start_6m = add_months(today, -6)
    start_date = date(start_6m.year, start_6m.month, 1)
    ym_expr = _ym_expr()

    # Compute cutoff YM strings for 1m and 3m windows
    ym_1m = _ym(add_months(today, -1))
    ym_3m = _ym(add_months(today, -3))

    rows_q = (
        db.query(
            ym_expr.label("ym"),
            Transaction.category_id,
            Category.name.label("cat_name"),
            Category.color.label("cat_color"),
            func.sum(Transaction.amount).label("total"),
        )
        .outerjoin(Category, _category_join_condition(user_id))
        .filter(
            Transaction.transaction_type == "expense",
            Transaction.transaction_date >= start_date,
        )
    )
    rows_q = _scope(rows_q, Transaction, user_id)
    rows = rows_q.group_by("ym", Transaction.category_id, Category.name, Category.color).all()
    rules = _scope(db.query(BudgetRule), BudgetRule, user_id).all()
    total_budget = next((r.limit_amount for r in rules if r.is_total), None)
    cat_limits = {r.category_id: r.limit_amount for r in rules if not r.is_total}
    hidden_keys = {
        row.category_key
        for row in _scope(db.query(BudgetHiddenCategory), BudgetHiddenCategory, user_id).all()
    }

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
            cat = _get_owned_category(db, cat_id, user_id)
            cat_meta[cat_id] = {"name": cat.name if cat else "Unknown",
                                 "color": cat.color if cat else None,
                                 "t6": 0.0, "t3": 0.0, "t1": 0.0}

    categories = []
    for cat_id, m in cat_meta.items():
        categories.append({
            "category_id": cat_id,
            "category_key": budget_category_key(cat_id),
            "category_name": m["name"],
            "category_color": m["color"],
            "avg_6m": round(m["t6"] / 6, 2),
            "avg_3m": round(m["t3"] / 3, 2),
            "avg_1m": round(m["t1"] / 1, 2),
            "avg_monthly": round(m["t6"] / 6, 2),  # kept for schema compat
            "limit_amount": cat_limits.get(cat_id),
        })

    categories.sort(key=lambda c: c["avg_6m"], reverse=True)
    return {
        "total": total_budget,
        "avg_months": 6,
        "categories": categories,
        "hidden_category_keys": sorted(hidden_keys),
    }


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
    user_id: str | None = None,
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

    rules = _scope(db.query(BudgetRule), BudgetRule, user_id).all()
    total_budget = next((r.limit_amount for r in rules if r.is_total), None)
    cat_budgets = {r.category_id: r.limit_amount for r in rules if not r.is_total}
    budgeted_ids = set(cat_budgets.keys())

    ym = _ym_expr()
    rows = (
        db.query(
            ym.label("ym"),
            Transaction.category_id,
            Category.name.label("cat_name"),
            Category.color.label("cat_color"),
            func.sum(Transaction.amount).label("total"),
        )
        .outerjoin(Category, _category_join_condition(user_id))
        .filter(
            Transaction.transaction_type == "expense",
            ym >= start_ym,
            ym <= end_ym,
        )
    )
    rows = (
        _scope(rows, Transaction, user_id)
        .group_by("ym", Transaction.category_id, Category.name, Category.color)
        .all()
    )

    # Index: (ym, category_id) -> {name, color, spent}
    spending: dict[tuple, dict] = {}
    for r in rows:
        spending[(r.ym, r.category_id)] = {
            "cat_name": r.cat_name,
            "cat_color": r.cat_color,
            "spent": r.total,
        }

    # Resolve category names/colors for budgeted cats not in spending
    cat_meta_cache: dict[int, dict] = {}
    for cat_id in budgeted_ids:
        if cat_id is not None:
            cat = _get_owned_category(db, cat_id, user_id)
            cat_meta_cache[cat_id] = {
                "name": cat.name if cat else "Unknown",
                "color": cat.color if cat else None,
            }

    monthly = []
    for mo in month_list:
        ym = mo["ym"]

        items = []
        for cat_id, budget_limit in cat_budgets.items():
            key = (ym, cat_id)
            spent = spending.get(key, {}).get("spent", 0.0)
            name = spending.get(key, {}).get("cat_name") or cat_meta_cache.get(
                cat_id, {}
            ).get("name", "Unknown")
            color = spending.get(key, {}).get("cat_color") or cat_meta_cache.get(
                cat_id, {}
            ).get("color")
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
