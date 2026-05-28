from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models.models import Transaction


def _group_key(tx: Transaction) -> tuple[Any, ...]:
    # import_batch_id excluded: differs every re-import, shouldn't break grouping
    return (
        tx.transaction_date,
        tx.posted_date,
        tx.reference_number or "",
        tx.merchant_name,
        tx.merchant_city or "",
        tx.merchant_state or "",
        tx.merchant_country or "",
        tx.mcc_description or "",
        round(float(tx.amount or 0.0), 4),
        tx.currency,
        tx.transaction_type,
        tx.account_id if tx.account_id is not None else -999999999,
        tx.category_id if tx.category_id is not None else -999999999,
        tx.notes or "",
        tx.is_excluded,
    )


def find_exact_duplicate_groups(db: Session, user_id: str | None = None) -> list[dict[str, Any]]:
    q = db.query(Transaction)
    if user_id is not None:
        q = q.filter(Transaction.user_id == user_id)
    else:
        q = q.filter(Transaction.user_id.is_(None))
    txs = q.all()
    grouped: dict[tuple[Any, ...], list[Transaction]] = {}
    for tx in txs:
        grouped.setdefault(_group_key(tx), []).append(tx)

    groups: list[dict[str, Any]] = []
    for matches in grouped.values():
        if len(matches) < 2:
            continue
        matches.sort(key=lambda row: row.id)
        tx = matches[0]
        ids = [row.id for row in matches]
        keep_id = tx.id
        summary = {
            "transaction_date": tx.transaction_date.isoformat() if tx.transaction_date else None,
            "posted_date": tx.posted_date.isoformat() if tx.posted_date else None,
            "reference_number": tx.reference_number,
            "merchant_name": tx.merchant_name,
            "merchant_city": tx.merchant_city,
            "merchant_state": tx.merchant_state,
            "merchant_country": tx.merchant_country,
            "mcc_description": tx.mcc_description,
            "amount": tx.amount,
            "currency": tx.currency,
            "transaction_type": tx.transaction_type,
            "account_id": tx.account_id,
            "category_id": tx.category_id,
            "notes": tx.notes,
            "import_batch_id": tx.import_batch_id,
            "is_excluded": tx.is_excluded,
        }
        groups.append(
            {
                "keep_id": keep_id,
                "transaction_ids": ids,
                "row_count": len(matches),
                "summary": summary,
            }
        )
    return groups


def ids_to_delete_for_prune(db: Session, user_id: str | None = None) -> list[int]:
    to_delete: list[int] = []
    for g in find_exact_duplicate_groups(db, user_id=user_id):
        keep = g["keep_id"]
        for tid in g["transaction_ids"]:
            if tid != keep:
                to_delete.append(tid)
    return to_delete


def prune_exact_duplicates(db: Session, user_id: str | None = None) -> int:
    ids = ids_to_delete_for_prune(db, user_id=user_id)
    if not ids:
        return 0
    db.query(Transaction).filter(Transaction.id.in_(ids)).delete(synchronize_session=False)
    return len(ids)
