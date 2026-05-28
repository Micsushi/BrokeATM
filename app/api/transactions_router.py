from __future__ import annotations

import calendar
import re
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import String, and_, asc, cast, desc, extract, func, or_
from sqlalchemy.orm import Session

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
from app.core.user_context import (
    UserContext,
    assign_user,
    get_current_user,
    get_db_for_user,
    require_owned_record,
    user_filter,
)
from app.models.models import Account, Category, Transaction
from app.services.transaction_duplicates import find_exact_duplicate_groups, prune_exact_duplicates

router = APIRouter(prefix="/api/transactions", tags=["transactions"])
NO_MONTHS_SENTINEL = "__none__"


def _enrich(
    tx: Transaction,
    db: Session,
    user: UserContext,
    *,
    exact_duplicate: bool = False,
) -> TransactionOut:
    out = TransactionOut.model_validate(tx)
    if tx.category_id:
        cat = (
            db.query(Category)
            .filter(Category.id == tx.category_id, user_filter(Category, user))
            .first()
        )
        out.category_name = cat.name if cat else None
    if tx.account_id:
        acc = (
            db.query(Account)
            .filter(Account.id == tx.account_id, user_filter(Account, user))
            .first()
        )
        out.account_name = acc.name if acc else None
    return out.model_copy(update={"exact_duplicate": exact_duplicate})


def _apply_month_filter(q: Any, months: str | None, year: int | None, month: int | None) -> Any:
    if months:
        if months == NO_MONTHS_SENTINEL:
            return q.filter(False)
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


def _apply_date_range_filter(q: Any, date_from: str | None, date_to: str | None) -> Any:
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
    return q


def _apply_amount_filter(q: Any, min_amount: float | None, max_amount: float | None) -> Any:
    if min_amount is not None:
        q = q.filter(Transaction.amount >= min_amount)
    if max_amount is not None:
        q = q.filter(Transaction.amount <= max_amount)
    return q


def _apply_search_filter(q: Any, search: str | None) -> Any:
    if not search:
        return q

    search_text = search.strip()
    if not search_text:
        return q

    pattern = f"%{search_text}%"
    clauses: list[Any] = [
        Transaction.merchant_name.ilike(pattern),
        Transaction.notes.ilike(pattern),
        Transaction.merchant_city.ilike(pattern),
        cast(Transaction.amount, String).ilike(pattern),
    ]

    numeric_search = re.sub(r"[^0-9.\-]", "", search_text.replace(",", ""))
    if numeric_search:
        try:
            amount_value = float(numeric_search)
        except ValueError:
            amount_value = None
        if amount_value is not None:
            clauses.append(Transaction.amount == amount_value)
            if numeric_search != search_text:
                clauses.append(cast(Transaction.amount, String).ilike(f"%{numeric_search}%"))

    return q.filter(or_(*clauses))


def _apply_common_filters(
    q: Any,
    *,
    transaction_type: str | None,
    category_id: int | None,
    account_id: int | None,
    search: str | None,
    min_amount: float | None,
    max_amount: float | None,
) -> Any:
    if transaction_type:
        q = q.filter(Transaction.transaction_type == transaction_type)
    if category_id:
        q = q.filter(Transaction.category_id == category_id)
    if account_id:
        q = q.filter(Transaction.account_id == account_id)

    q = _apply_amount_filter(q, min_amount, max_amount)
    q = _apply_search_filter(q, search)
    return q


_SORTABLE = {
    "date": Transaction.transaction_date,
    "date_added": Transaction.created_at,
    "merchant": Transaction.merchant_name,
    "amount": Transaction.amount,
    "type": Transaction.transaction_type,
    "category": Category.name,
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
    min_amount: float | None = Query(None, ge=0),
    max_amount: float | None = Query(None, ge=0),
    include_excluded: bool = Query(False),
    sort_by: str = Query(
        "date",
        description="Column to sort by: date, date_added, merchant, amount, type",
    ),
    sort_dir: str = Query("asc", description="asc or desc"),
    duplicate_only: bool = Query(
        False,
        description="Only rows in an exact duplicate group; date filters ignored",
    ),
    db: Session = Depends(get_db_for_user),
    user: UserContext = Depends(get_current_user),
) -> Any:
    dup_groups = find_exact_duplicate_groups(db, user_id=user.user_id)
    dup_set: set[int] = set()
    for g in dup_groups:
        dup_set.update(g["transaction_ids"])

    q = db.query(Transaction).filter(user_filter(Transaction, user))
    if not include_excluded:
        q = q.filter(Transaction.is_excluded.is_(False))

    if not duplicate_only:
        if date_from or date_to:
            q = _apply_date_range_filter(q, date_from, date_to)
        else:
            q = _apply_month_filter(q, months, year, month)

    if duplicate_only:
        if not dup_set:
            return TransactionListResponse(items=[], total=0, page=page, page_size=page_size)
        q = q.filter(Transaction.id.in_(dup_set))

    q = _apply_common_filters(
        q,
        transaction_type=transaction_type,
        category_id=category_id,
        account_id=account_id,
        search=search,
        min_amount=min_amount,
        max_amount=max_amount,
    )

    if sort_by == "category":
        q = q.outerjoin(
            Category,
            and_(Transaction.category_id == Category.id, user_filter(Category, user)),
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
        items=[_enrich(tx, db, user, exact_duplicate=tx.id in dup_set) for tx in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/latest-month")
def latest_month(
    db: Session = Depends(get_db_for_user),
    user: UserContext = Depends(get_current_user),
) -> Any:
    row = (
        db.query(
            extract("year", Transaction.transaction_date).label("year"),
            extract("month", Transaction.transaction_date).label("month"),
        )
        .filter(Transaction.is_excluded.is_(False), user_filter(Transaction, user))
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
    min_amount: float | None = Query(None, ge=0),
    max_amount: float | None = Query(None, ge=0),
    db: Session = Depends(get_db_for_user),
    user: UserContext = Depends(get_current_user),
) -> Any:
    q = db.query(
        Transaction.transaction_type,
        func.sum(Transaction.amount).label("total"),
        func.count(Transaction.id).label("count"),
    ).filter(Transaction.is_excluded.is_(False), user_filter(Transaction, user))

    if date_from or date_to:
        q = _apply_date_range_filter(q, date_from, date_to)
    else:
        q = _apply_month_filter(q, months, year, month)

    q = _apply_common_filters(
        q,
        transaction_type=transaction_type,
        category_id=category_id,
        account_id=account_id,
        search=search,
        min_amount=min_amount,
        max_amount=max_amount,
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
def duplicate_report(
    db: Session = Depends(get_db_for_user),
    user: UserContext = Depends(get_current_user),
) -> Any:
    raw = find_exact_duplicate_groups(db, user_id=user.user_id)
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
    db: Session = Depends(get_db_for_user),
    user: UserContext = Depends(get_current_user),
) -> Any:
    if not payload.confirm:
        raise HTTPException(
            status_code=400,
            detail=(
                'Send {"confirm": true} to delete duplicate copies. '
                "Lowest id is kept per group."
            ),
        )
    deleted = prune_exact_duplicates(db, user_id=user.user_id)
    db.commit()
    return PruneExactDuplicatesResponse(deleted=deleted)


@router.post("", response_model=TransactionOut, status_code=201)
def create_transaction(
    payload: TransactionCreate,
    db: Session = Depends(get_db_for_user),
    user: UserContext = Depends(get_current_user),
) -> Any:
    require_owned_record(db, Category, payload.category_id, user, "Category")
    require_owned_record(db, Account, payload.account_id, user, "Account")
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
    assign_user(tx, user)
    db.add(tx)
    db.commit()
    db.refresh(tx)
    return _enrich(tx, db, user)


@router.post("/bulk-delete", status_code=200)
def bulk_delete(
    payload: BulkDeleteRequest,
    db: Session = Depends(get_db_for_user),
    user: UserContext = Depends(get_current_user),
) -> Any:
    txs = (
        db.query(Transaction)
        .filter(Transaction.id.in_(payload.ids), user_filter(Transaction, user))
        .all()
    )
    for tx in txs:
        db.delete(tx)
    db.commit()
    return {"deleted": len(txs)}


@router.post("/bulk-update", status_code=200)
def bulk_update(
    payload: BulkUpdateRequest,
    db: Session = Depends(get_db_for_user),
    user: UserContext = Depends(get_current_user),
) -> Any:
    if payload.category_id is not None:
        require_owned_record(db, Category, payload.category_id, user, "Category")
    txs = (
        db.query(Transaction)
        .filter(Transaction.id.in_(payload.ids), user_filter(Transaction, user))
        .all()
    )
    for tx in txs:
        if payload.category_id is not None:
            tx.category_id = payload.category_id
        if payload.transaction_type is not None:
            tx.transaction_type = payload.transaction_type
    db.commit()
    return {"updated": len(txs)}


@router.get("/{tx_id}", response_model=TransactionOut)
def get_transaction(
    tx_id: int,
    db: Session = Depends(get_db_for_user),
    user: UserContext = Depends(get_current_user),
) -> Any:
    tx = (
        db.query(Transaction)
        .filter(Transaction.id == tx_id, user_filter(Transaction, user))
        .first()
    )
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return _enrich(tx, db, user)


@router.patch("/{tx_id}", response_model=TransactionOut)
def update_transaction(
    tx_id: int,
    payload: TransactionUpdate,
    db: Session = Depends(get_db_for_user),
    user: UserContext = Depends(get_current_user),
) -> Any:
    tx = (
        db.query(Transaction)
        .filter(Transaction.id == tx_id, user_filter(Transaction, user))
        .first()
    )
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
    updates = payload.model_dump(exclude_unset=True)
    if updates.get("category_id") is not None:
        require_owned_record(db, Category, updates["category_id"], user, "Category")
    if updates.get("account_id") is not None:
        require_owned_record(db, Account, updates["account_id"], user, "Account")
    for field, value in updates.items():
        setattr(tx, field, value)
    db.commit()
    db.refresh(tx)
    return _enrich(tx, db, user)


@router.delete("/{tx_id}", status_code=204)
def delete_transaction(
    tx_id: int,
    db: Session = Depends(get_db_for_user),
    user: UserContext = Depends(get_current_user),
) -> None:
    tx = (
        db.query(Transaction)
        .filter(Transaction.id == tx_id, user_filter(Transaction, user))
        .first()
    )
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
    db.delete(tx)
    db.commit()


@router.post("/delete-all", status_code=200)
def delete_all_transactions(
    db: Session = Depends(get_db_for_user),
    user: UserContext = Depends(get_current_user),
) -> Any:
    deleted = (
        db.query(Transaction)
        .filter(user_filter(Transaction, user))
        .delete(synchronize_session=False)
    )
    db.commit()
    return {"deleted": deleted}
