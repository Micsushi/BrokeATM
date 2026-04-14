from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.models import Transaction


def _duplicate_groups_sql() -> str:
    # import_batch_id excluded: differs every re-import, shouldn't break grouping
    return """
        SELECT MIN(id) AS keep_id, GROUP_CONCAT(id) AS id_list, COUNT(*) AS cnt
        FROM transactions
        GROUP BY
          transaction_date,
          posted_date,
          IFNULL(reference_number, ''),
          merchant_name,
          IFNULL(merchant_city, ''),
          IFNULL(merchant_state, ''),
          IFNULL(merchant_country, ''),
          IFNULL(mcc_description, ''),
          ROUND(amount, 4),
          currency,
          transaction_type,
          IFNULL(account_id, -999999999),
          IFNULL(category_id, -999999999),
          IFNULL(notes, ''),
          is_excluded
        HAVING COUNT(*) > 1
    """


def find_exact_duplicate_groups(db: Session) -> list[dict[str, Any]]:
    rows = db.execute(text(_duplicate_groups_sql())).fetchall()
    groups: list[dict[str, Any]] = []
    for r in rows:
        keep_id = int(r.keep_id)
        raw = (r.id_list or "").strip()
        ids = sorted(int(x) for x in raw.split(",") if x.strip().isdigit())
        if len(ids) < 2:
            continue
        tx = db.get(Transaction, keep_id)
        if not tx:
            continue
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
                "row_count": int(r.cnt),
                "summary": summary,
            }
        )
    return groups


def ids_to_delete_for_prune(db: Session) -> list[int]:
    to_delete: list[int] = []
    for g in find_exact_duplicate_groups(db):
        keep = g["keep_id"]
        for tid in g["transaction_ids"]:
            if tid != keep:
                to_delete.append(tid)
    return to_delete


def prune_exact_duplicates(db: Session) -> int:
    ids = ids_to_delete_for_prune(db)
    if not ids:
        return 0
    db.query(Transaction).filter(Transaction.id.in_(ids)).delete(synchronize_session=False)
    return len(ids)
