from __future__ import annotations

import calendar
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import extract, func, or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.schemas import BarMonth, DashboardResponse, LargeExpenseRow, LargeExpensesResponse, PieSlice
from app.models.models import Category, Transaction, TransactionType

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

CATEGORY_COLORS = [
    "#6366f1", "#f59e0b", "#10b981", "#ef4444", "#3b82f6",
    "#8b5cf6", "#ec4899", "#14b8a6", "#f97316", "#84cc16",
    "#06b6d4", "#a855f7", "#e11d48", "#0ea5e9", "#22c55e",
]


def _parse_month_list(raw: str | None) -> list[tuple[int, int]]:
    if not raw:
        return []
    pairs = []
    for part in raw.split(","):
        try:
            y, m = part.strip().split("-")
            pairs.append((int(y), int(m)))
        except ValueError:
            continue
    return pairs


@router.get("/available-months")
def available_months(db: Session = Depends(get_db)) -> Any:
    rows = (
        db.query(
            extract("year", Transaction.transaction_date).label("year"),
            extract("month", Transaction.transaction_date).label("month"),
            func.count(Transaction.id).label("cnt"),
        )
        .filter(Transaction.is_excluded.is_(False))
        .group_by("year", "month")
        .order_by(
            extract("year", Transaction.transaction_date).desc(),
            extract("month", Transaction.transaction_date).desc(),
        )
        .all()
    )
    return [
        {
            "ym": f"{int(r.year)}-{int(r.month):02d}",
            "year": int(r.year),
            "month": int(r.month),
            "count": r.cnt,
        }
        for r in rows
    ]


@router.get("", response_model=DashboardResponse)
def get_dashboard(
    months: str | None = Query(None, description="Comma-separated YYYY-MM for pie charts + totals"),
    bar_months: str | None = Query(None, description="Comma-separated YYYY-MM for bar chart"),
    db: Session = Depends(get_db),
) -> Any:
    pie_pairs = _parse_month_list(months)
    bar_pairs = _parse_month_list(bar_months)

    def pie_query(tx_type: str) -> Any:
        q = (
            db.query(
                Category.name.label("category"),
                Category.color.label("color"),
                func.sum(Transaction.amount).label("total"),
            )
            .join(Category, Transaction.category_id == Category.id, isouter=True)
            .filter(
                Transaction.transaction_type == tx_type,
                Transaction.is_excluded.is_(False),
            )
        )
        if pie_pairs:
            q = q.filter(
                or_(
                    *[
                        (extract("year", Transaction.transaction_date) == y)
                        & (extract("month", Transaction.transaction_date) == m)
                        for y, m in pie_pairs
                    ]
                )
            )
        return q.group_by(Category.name, Category.color).order_by(func.sum(Transaction.amount).desc())

    def make_pie(rows: list[Any]) -> list[PieSlice]:
        return [
            PieSlice(
                category=row.category or "Uncategorized",
                amount=round(row.total or 0, 2),
                color=row.color or CATEGORY_COLORS[i % len(CATEGORY_COLORS)],
            )
            for i, row in enumerate(rows)
        ]

    expense_pie = make_pie(pie_query(TransactionType.expense).all())
    income_pie = make_pie(pie_query(TransactionType.income).all())
    total_expenses = sum(s.amount for s in expense_pie)
    total_income = sum(s.amount for s in income_pie)

    bar_q = (
        db.query(
            extract("year", Transaction.transaction_date).label("year"),
            extract("month", Transaction.transaction_date).label("month"),
            Transaction.transaction_type,
            func.sum(Transaction.amount).label("total"),
        )
        .filter(Transaction.is_excluded.is_(False))
    )
    if bar_pairs:
        bar_q = bar_q.filter(
            or_(
                *[
                    (extract("year", Transaction.transaction_date) == y)
                    & (extract("month", Transaction.transaction_date) == m)
                    for y, m in bar_pairs
                ]
            )
        )
    bar_q = bar_q.group_by("year", "month", Transaction.transaction_type).order_by("year", "month")

    bar_map: dict[tuple[int, int], dict[str, float]] = {}
    for row in bar_q.all():
        key = (int(row.year), int(row.month))
        if key not in bar_map:
            bar_map[key] = {"expenses": 0.0, "income": 0.0}
        if row.transaction_type == TransactionType.expense:
            bar_map[key]["expenses"] += row.total or 0
        elif row.transaction_type == TransactionType.income:
            bar_map[key]["income"] += row.total or 0

    if bar_pairs:
        for p in bar_pairs:
            if p not in bar_map:
                bar_map[p] = {"expenses": 0.0, "income": 0.0}
        ordered_keys = bar_pairs
    else:
        ordered_keys = sorted(bar_map.keys())

    bar_chart = [
        BarMonth(
            month=m,
            year=y,
            label=f"{calendar.month_abbr[m]} {y}",
            expenses=round(bar_map[(y, m)]["expenses"], 2),
            income=round(bar_map[(y, m)]["income"], 2),
        )
        for y, m in ordered_keys
    ]

    return DashboardResponse(
        expense_pie=expense_pie,
        income_pie=income_pie,
        bar_chart=bar_chart,
        total_expenses=round(total_expenses, 2),
        total_income=round(total_income, 2),
        net=round(total_income - total_expenses, 2),
    )


@router.get("/large-expenses", response_model=LargeExpensesResponse)
def large_expenses(
    date_from: str | None = Query(None, description="YYYY-MM start (inclusive), omit for all time"),
    date_to: str | None = Query(None, description="YYYY-MM end (inclusive), omit for all time"),
    min_amount: float | None = Query(None, description="Fixed amount threshold (CAD)"),
    min_pct: float | None = Query(None, description="% of all-time total expenses (0-100)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=500),
    db: Session = Depends(get_db),
) -> Any:
    """Return expense rows that exceed either threshold, sorted latest first, paginated."""
    base_q = db.query(Transaction).filter(
        Transaction.transaction_type == TransactionType.expense,
        Transaction.is_excluded.is_(False),
    )

    if date_from:
        try:
            y, m = int(date_from[:4]), int(date_from[5:7])
            base_q = base_q.filter(Transaction.transaction_date >= date(y, m, 1))
        except (ValueError, IndexError):
            pass
    if date_to:
        try:
            y, m = int(date_to[:4]), int(date_to[5:7])
            base_q = base_q.filter(Transaction.transaction_date <= date(y, m, calendar.monthrange(y, m)[1]))
        except (ValueError, IndexError):
            pass

    all_in_range = base_q.all()
    range_total = sum(r.amount for r in all_in_range)

    matched = []
    for r in all_in_range:
        passes_amount = min_amount is not None and r.amount >= min_amount
        pct = (r.amount / range_total * 100) if range_total else 0
        passes_pct = min_pct is not None and pct >= min_pct
        if passes_amount or passes_pct:
            matched.append((r, round(pct, 1)))

    matched.sort(key=lambda x: x[0].transaction_date, reverse=True)

    total_count = len(matched)
    page_items = matched[(page - 1) * page_size: page * page_size]

    return LargeExpensesResponse(
        items=[
            LargeExpenseRow(
                id=r.id,
                transaction_date=r.transaction_date,
                merchant_name=r.merchant_name,
                category=r.category.name if r.category else None,
                amount=round(r.amount, 2),
                pct_of_total=pct,
                currency=r.currency,
            )
            for r, pct in page_items
        ],
        total=total_count,
        page=page,
        page_size=page_size,
    )
