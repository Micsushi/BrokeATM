from __future__ import annotations

import calendar
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import asc, desc, extract, func, or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.schemas import (
    BulkDeleteRequest,
    BulkUpdateRequest,
    DuplicateGroupOut,
    DuplicateReportResponse,
    PruneExactDuplicatesRequest,
    PruneExactDuplicatesResponse,
    TransactionCreate,
    TransactionListResponse,
    TransactionOut,
    TransactionUpdate,
)
from app.models.models import Transaction
from app.services.transaction_duplicates import find_exact_duplicate_groups, prune_exact_duplicates

router = APIRouter(prefix="/api/transactions", tags=["transactions"])


def _enrich(tx: Transaction, *, exact_duplicate: bool = False) -> TransactionOut:
    out = TransactionOut.model_validate(tx)
    out.category_name = tx.category.name if tx.category else None
    out.account_name = tx.account.name if tx.account else None
    return out.model_copy(update={"exact_duplicate": exact_duplicate})


def _apply_month_filter(q: Any, months: str | None, year: int | None, month: int | None) -> Any:
    if months:
        pairs = []
        for part in months.split(","):
            try:
                y, m = part.strip().split("-")
                pairs.append((int(y), int(m)))
            except ValueError:
                continue
        if pairs:
            q = q.filter(
                or_(
                    *[
                        (extract("year", Transaction.transaction_date) == y)
                        & (extract("month", Transaction.transaction_date) == m)
                        for y, m in pairs
                    ]
                )
            )
    else:
        if year:
            q = q.filter(extract("year", Transaction.transaction_date) == year)
        if month:
            q = q.filter(extract("month", Transaction.transaction_date) == month)
    return q


_SORTABLE = {
    "date": Transaction.transaction_date,
    "date_added": Transaction.created_at,
    "merchant": Transaction.merchant_name,
    "amount": Transaction.amount,
    "type": Transaction.transaction_type,
}


@router.get("", response_model=TransactionListResponse)
def list_transactions(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=5000),
    month: int | None = Query(None),
    year: int | None = Query(None),
    months: str | None = Query(None, description="Comma-separated YYYY-MM"),
    date_from: str | None = Query(None, description="YYYY-MM start of range (inclusive)"),
    date_to: str | None = Query(None, description="YYYY-MM end of range (inclusive)"),
    transaction_type: str | None = Query(None),
    category_id: int | None = Query(None),
    account_id: int | None = Query(None),
    search: str | None = Query(None),
    include_excluded: bool = Query(False),
    sort_by: str = Query("date", description="Column to sort by: date, date_added, merchant, amount, type"),
    sort_dir: str = Query("asc", description="asc or desc"),
    duplicate_only: bool = Query(
        False,
        description=(
            "Only rows that are part of an exact duplicate group (same fields except id and timestamps). "
            "Year/month/months filters are ignored so every copy in a group is visible."
        ),
    ),
    db: Session = Depends(get_db),
) -> Any:
    dup_groups = find_exact_duplicate_groups(db)
    dup_set: set[int] = set()
    for g in dup_groups:
        dup_set.update(g["transaction_ids"])

    q = db.query(Transaction)
    if not include_excluded:
        q = q.filter(Transaction.is_excluded.is_(False))

    if not duplicate_only:
        if date_from or date_to:
            # date_from / date_to are YYYY-MM strings; match whole months
            if date_from:
                try:
                    y, m = int(date_from[:4]), int(date_from[5:7])
                    from_date = date(y, m, 1)
                    q = q.filter(Transaction.transaction_date >= from_date)
                except (ValueError, IndexError):
                    pass
            if date_to:
                try:
                    y, m = int(date_to[:4]), int(date_to[5:7])
                    last_day = calendar.monthrange(y, m)[1]
                    to_date = date(y, m, last_day)
                    q = q.filter(Transaction.transaction_date <= to_date)
                except (ValueError, IndexError):
                    pass
        else:
            q = _apply_month_filter(q, months, year, month)

    if duplicate_only:
        if not dup_set:
            return TransactionListResponse(items=[], total=0, page=page, page_size=page_size)
        q = q.filter(Transaction.id.in_(dup_set))

    if transaction_type:
        q = q.filter(Transaction.transaction_type == transaction_type)
    if category_id:
        q = q.filter(Transaction.category_id == category_id)
    if account_id:
        q = q.filter(Transaction.account_id == account_id)
    if search:
        pattern = f"%{search}%"
        q = q.filter(
            or_(
                Transaction.merchant_name.ilike(pattern),
                Transaction.notes.ilike(pattern),
                Transaction.merchant_city.ilike(pattern),
            )
        )

    sort_col = _SORTABLE.get(sort_by, Transaction.transaction_date)
    order_fn = asc if sort_dir == "asc" else desc
    # Always secondary-sort by date asc so pages are stable
    secondary = asc(Transaction.transaction_date) if sort_by != "date" else asc(Transaction.id)

    total = q.count()
    items = (
        q.order_by(order_fn(sort_col), secondary)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return TransactionListResponse(
        items=[_enrich(tx, exact_duplicate=tx.id in dup_set) for tx in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/latest-month")
def latest_month(db: Session = Depends(get_db)) -> Any:
    row = (
        db.query(
            extract("year", Transaction.transaction_date).label("year"),
            extract("month", Transaction.transaction_date).label("month"),
        )
        .filter(Transaction.is_excluded.is_(False))
        .group_by("year", "month")
        .order_by(
            extract("year", Transaction.transaction_date).desc(),
            extract("month", Transaction.transaction_date).desc(),
        )
        .first()
    )
    if row:
        return {"year": int(row.year), "month": int(row.month)}
    today = date.today()
    return {"year": today.year, "month": today.month}


@router.get("/summary")
def summary(
    month: int | None = Query(None),
    year: int | None = Query(None),
    months: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    transaction_type: str | None = Query(None),
    category_id: int | None = Query(None),
    account_id: int | None = Query(None),
    search: str | None = Query(None),
    db: Session = Depends(get_db),
) -> Any:
    q = db.query(
        Transaction.transaction_type,
        func.sum(Transaction.amount).label("total"),
        func.count(Transaction.id).label("count"),
    ).filter(Transaction.is_excluded.is_(False))

    if date_from or date_to:
        if date_from:
            try:
                y, m = int(date_from[:4]), int(date_from[5:7])
                q = q.filter(Transaction.transaction_date >= date(y, m, 1))
            except (ValueError, IndexError):
                pass
        if date_to:
            try:
                y, m = int(date_to[:4]), int(date_to[5:7])
                q = q.filter(Transaction.transaction_date <= date(y, m, calendar.monthrange(y, m)[1]))
            except (ValueError, IndexError):
                pass
    else:
        q = _apply_month_filter(q, months, year, month)

    if transaction_type:
        q = q.filter(Transaction.transaction_type == transaction_type)
    if category_id:
        q = q.filter(Transaction.category_id == category_id)
    if account_id:
        q = q.filter(Transaction.account_id == account_id)
    if search:
        pattern = f"%{search}%"
        q = q.filter(
            or_(
                Transaction.merchant_name.ilike(pattern),
                Transaction.notes.ilike(pattern),
                Transaction.merchant_city.ilike(pattern),
            )
        )

    rows = q.group_by(Transaction.transaction_type).all()
    totals: dict[str, float] = {"expense": 0, "income": 0, "refund": 0, "transfer": 0}
    counts: dict[str, int] = {"expense": 0, "income": 0, "refund": 0, "transfer": 0}
    for row in rows:
        totals[row.transaction_type] = round(row.total or 0, 2)
        counts[row.transaction_type] = row.count or 0

    net = round(totals["income"] - totals["expense"] + totals["refund"], 2)
    return {
        "expense": totals["expense"],
        "income": totals["income"],
        "refund": totals["refund"],
        "transfer": totals["transfer"],
        "net": net,
        "counts": counts,
    }


@router.get("/duplicate-report", response_model=DuplicateReportResponse)
def duplicate_report(db: Session = Depends(get_db)) -> Any:
    raw = find_exact_duplicate_groups(db)
    groups = [DuplicateGroupOut(**g) for g in raw]
    extra = sum(g.row_count - 1 for g in groups)
    return DuplicateReportResponse(
        groups=groups,
        total_groups=len(groups),
        total_extra_rows=extra,
    )


@router.post("/prune-exact-duplicates", response_model=PruneExactDuplicatesResponse)
def prune_exact_duplicates_route(
    payload: PruneExactDuplicatesRequest,
    db: Session = Depends(get_db),
) -> Any:
    if not payload.confirm:
        raise HTTPException(
            status_code=400,
            detail='Send {"confirm": true} to delete duplicate copies. Lowest id is kept per group.',
        )
    deleted = prune_exact_duplicates(db)
    db.commit()
    return PruneExactDuplicatesResponse(deleted=deleted)


@router.post("", response_model=TransactionOut, status_code=201)
def create_transaction(payload: TransactionCreate, db: Session = Depends(get_db)) -> Any:
    tx = Transaction(
        transaction_date=payload.transaction_date,
        posted_date=payload.posted_date,
        merchant_name=payload.merchant_name,
        merchant_city=payload.merchant_city,
        merchant_country=payload.merchant_country,
        amount=payload.amount,
        currency=payload.currency,
        transaction_type=payload.transaction_type,
        category_id=payload.category_id,
        account_id=payload.account_id,
        notes=payload.notes,
        is_excluded=False,
    )
    db.add(tx)
    db.commit()
    db.refresh(tx)
    return _enrich(tx)


@router.post("/bulk-delete", status_code=200)
def bulk_delete(payload: BulkDeleteRequest, db: Session = Depends(get_db)) -> Any:
    txs = db.query(Transaction).filter(Transaction.id.in_(payload.ids)).all()
    for tx in txs:
        db.delete(tx)
    db.commit()
    return {"deleted": len(txs)}


@router.post("/bulk-update", status_code=200)
def bulk_update(payload: BulkUpdateRequest, db: Session = Depends(get_db)) -> Any:
    txs = db.query(Transaction).filter(Transaction.id.in_(payload.ids)).all()
    for tx in txs:
        if payload.category_id is not None:
            tx.category_id = payload.category_id
        if payload.transaction_type is not None:
            tx.transaction_type = payload.transaction_type
    db.commit()
    return {"updated": len(txs)}


@router.get("/{tx_id}", response_model=TransactionOut)
def get_transaction(tx_id: int, db: Session = Depends(get_db)) -> Any:
    tx = db.get(Transaction, tx_id)
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return _enrich(tx)


@router.patch("/{tx_id}", response_model=TransactionOut)
def update_transaction(
    tx_id: int,
    payload: TransactionUpdate,
    db: Session = Depends(get_db),
) -> Any:
    tx = db.get(Transaction, tx_id)
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(tx, field, value)
    db.commit()
    db.refresh(tx)
    return _enrich(tx)


@router.delete("/{tx_id}", status_code=204)
def delete_transaction(tx_id: int, db: Session = Depends(get_db)) -> None:
    tx = db.get(Transaction, tx_id)
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
    db.delete(tx)
    db.commit()
