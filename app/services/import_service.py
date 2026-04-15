from __future__ import annotations

import uuid
from collections import Counter, defaultdict
from datetime import date
from typing import Any

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.models import Account, Category, ImportBatch, Transaction
from app.services.keyword_matching import KeywordMatcher
from app.services.starter_categories import seed_starter_categories


def _normalize_reference_number(value: Any) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    return s or None


def _normalize_card_masked(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _digits_only(s: str) -> str:
    return "".join(ch for ch in (s or "") if ch.isdigit())


def _find_account_by_card_mask(db: Session, card: str) -> Account | None:
    """Exact match on card mask, falling back to last-4 digits ('3600' vs '************3600')."""
    card = _normalize_card_masked(card)
    if not card:
        return None
    hit = db.query(Account).filter_by(card_number_masked=card).first()
    if hit is not None:
        return hit
    d = _digits_only(card)
    if len(d) < 4:
        return None
    suf4 = d[-4:]
    for a in db.query(Account).all():
        ad = _digits_only(a.card_number_masked or "")
        if len(ad) >= 4 and ad.endswith(suf4):
            return a
    return None


def _default_card_masked_for_rows(rows: list[dict[str, Any]]) -> str:
    # Some rows (interest charges) omit card number; fall back to file's most common mask.
    counts: Counter[str] = Counter()
    for row in rows:
        c = _normalize_card_masked(row.get("card_number_masked"))
        if c:
            counts[c] += 1
    if not counts:
        return ""
    return counts.most_common(1)[0][0]


def _effective_card_for_row(row: dict[str, Any], default_card: str) -> str:
    c = _normalize_card_masked(row.get("card_number_masked"))
    return c or default_card


def _row_transaction_date(row: dict[str, Any]) -> date | None:
    v = row.get("transaction_date")
    if v is None:
        return None
    if isinstance(v, date):
        return v
    if isinstance(v, str) and v.strip():
        s = v.strip()[:10]
        try:
            return date.fromisoformat(s)
        except ValueError:
            return None
    return None


def _row_statement_date(row: dict[str, Any]) -> date | None:
    d = _row_transaction_date(row)
    if d is not None:
        return d
    v = row.get("posted_date")
    if v is None:
        return None
    if isinstance(v, date):
        return v
    if isinstance(v, str) and v.strip():
        s = v.strip()[:10]
        try:
            return date.fromisoformat(s)
        except ValueError:
            return None
    return None


# Interest rows often reuse reference numbers across cycles; match by amount/date instead.
_INTEREST_MERCHANT_MARKERS = (
    "cash interest",
    "interest payment",
    "interest earned",
    "interest charge",
    "interest paid",
)


def _interest_like_row(row: dict[str, Any]) -> bool:
    m = _normalize_merchant_for_fingerprint(row.get("merchant_name") or "")
    if not m:
        return False
    return any(tok in m for tok in _INTEREST_MERCHANT_MARKERS)


def _normalize_merchant_for_fingerprint(name: str) -> str:
    return " ".join((name or "").strip().lower().split())[:200]


def _find_interest_account_date_amount_duplicate(
    db: Session,
    account: Account,
    tx_d: date,
    amount: float,
) -> Transaction | None:
    amt = float(amount)
    candidates = (
        db.query(Transaction)
        .filter(
            Transaction.account_id == account.id,
            func.abs(Transaction.amount - amt) < 0.0001,
            or_(Transaction.transaction_date == tx_d, Transaction.posted_date == tx_d),
        )
        .limit(25)
        .all()
    )
    for tx in candidates:
        if _interest_like_row({"merchant_name": tx.merchant_name or ""}):
            return tx
    return None


def _find_existing_transaction_duplicate(
    db: Session,
    *,
    account: Account | None,
    ref: str | None,
    tx_d: date | None,
    amount: float,
    merchant_fp: str,
    interest_like: bool,
) -> Transaction | None:
    if account is None:
        return None
    if ref:
        q = (
            db.query(Transaction)
            .filter_by(reference_number=ref, account_id=account.id)
        )
        if tx_d is not None:
            hit = q.filter_by(transaction_date=tx_d).first()
            if hit is None:
                hit = q.filter(Transaction.posted_date == tx_d).first()
            if hit is not None:
                return hit
            if interest_like:
                hit_i = _find_interest_account_date_amount_duplicate(db, account, tx_d, amount)
                if hit_i is not None:
                    return hit_i
            return None
        # No transaction_date or posted_date: do not match by ref alone (avoids wrong-row matches).
        return None
    if interest_like and tx_d is not None and merchant_fp:
        amt = float(amount)
        candidates = (
            db.query(Transaction)
            .filter(
                Transaction.account_id == account.id,
                Transaction.transaction_date == tx_d,
                Transaction.reference_number.is_(None),
                func.abs(Transaction.amount - amt) < 0.0001,
            )
            .limit(50)
            .all()
        )
        for tx in candidates:
            if _normalize_merchant_for_fingerprint(tx.merchant_name or "") == merchant_fp:
                return tx
        return _find_interest_account_date_amount_duplicate(db, account, tx_d, amount)
    return None


def seed_defaults(db: Session) -> None:
    # Backward-compatible wrapper; starter templates now live outside mcc_map.py.
    seed_starter_categories(db)


def _keyword_matcher(db: Session) -> KeywordMatcher:
    return KeywordMatcher.from_categories(db.query(Category).all())


def get_or_create_account(db: Session, card_number_masked: str, cardholder: str) -> Account:
    card_number_masked = _normalize_card_masked(card_number_masked)
    account = _find_account_by_card_mask(db, card_number_masked)
    if not account:
        name = f"{cardholder} ({card_number_masked})" if cardholder else card_number_masked
        account = Account(name=name, card_number_masked=card_number_masked)
        db.add(account)
        db.flush()
    return account


def get_or_create_category(db: Session, name: str) -> Category:
    normalized = name.strip().lower()
    cat = db.query(Category).filter(Category.name == normalized).first()
    if not cat:
        cat = Category(name=normalized)
        db.add(cat)
        db.flush()
    return cat


def check_duplicates(db: Session, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    seen_ref_line: set[tuple[str, str, str]] = set()
    seen_interest_fp: set[tuple[str, str, str, float, str]] = set()
    default_card = _default_card_masked_for_rows(rows)
    for row in rows:
        ref = _normalize_reference_number(row.get("reference_number"))
        card = _effective_card_for_row(row, default_card)
        tx_d = _row_statement_date(row)
        dkey = tx_d.isoformat() if tx_d else ""
        amount = float(row.get("amount") or 0.0)
        merch_fp = _normalize_merchant_for_fingerprint(row.get("merchant_name") or "")
        interest_like = _interest_like_row(row)
        account = _find_account_by_card_mask(db, card) if card else None

        is_dup = False
        dup_in_import = False
        dup_in_db = False
        if ref:
            batch_key = (ref, card, dkey)
            if batch_key in seen_ref_line:
                is_dup = True
                dup_in_import = True
            else:
                existing = _find_existing_transaction_duplicate(
                    db,
                    account=account,
                    ref=ref,
                    tx_d=tx_d,
                    amount=amount,
                    merchant_fp=merch_fp,
                    interest_like=interest_like,
                )
                if existing is not None:
                    is_dup = True
                    dup_in_db = True
                seen_ref_line.add(batch_key)
        elif interest_like and tx_d is not None and merch_fp:
            fp_key = ("__int__", card, dkey, round(amount, 2), merch_fp)
            if fp_key in seen_interest_fp:
                is_dup = True
                dup_in_import = True
            else:
                existing = _find_existing_transaction_duplicate(
                    db,
                    account=account,
                    ref=None,
                    tx_d=tx_d,
                    amount=amount,
                    merchant_fp=merch_fp,
                    interest_like=True,
                )
                if existing is not None:
                    is_dup = True
                    dup_in_db = True
                seen_interest_fp.add(fp_key)

        # duplicate flag is advisory; UI defaults to unchecked so user decides
        exclude = bool(row.get("exclude"))
        out = {
            **row,
            "duplicate": is_dup,
            "reference_number": ref,
            "exclude": exclude,
            "duplicate_in_import": dup_in_import,
            "duplicate_in_database": dup_in_db,
        }
        if not _normalize_card_masked(row.get("card_number_masked")) and card:
            out["card_number_masked"] = card
        results.append(out)
    return results


def _row_import_batch_group(
    row: dict[str, Any],
    *,
    default_filename: str,
    default_month: int,
    default_year: int,
) -> tuple[str, int, int]:
    label = (row.get("source_file") or default_filename or "import").strip()[:255]
    try:
        im = int(row["import_month"]) if row.get("import_month") is not None else int(default_month)
    except (TypeError, ValueError, KeyError):
        im = int(default_month)
    try:
        iy = int(row["import_year"]) if row.get("import_year") is not None else int(default_year)
    except (TypeError, ValueError, KeyError):
        iy = int(default_year)
    return label, im, iy


def commit_import(
    db: Session,
    rows: list[dict[str, Any]],
    filename: str,
    month: int,
    year: int,
) -> tuple[list[ImportBatch], int, int]:
    default_label = (filename or "import").strip()[:255] or "import"

    totals: defaultdict[tuple[str, int, int], int] = defaultdict(int)
    for row in rows:
        gk = _row_import_batch_group(row, default_filename=default_label, default_month=month, default_year=year)
        totals[gk] += 1

    batch_id_by_key = {gk: str(uuid.uuid4()) for gk in totals}
    imported_by: defaultdict[tuple[str, int, int], int] = defaultdict(int)
    skipped_by: defaultdict[tuple[str, int, int], int] = defaultdict(int)

    keyword_matcher = _keyword_matcher(db)
    seen_ref_line: set[tuple[str, int, str]] = set()
    seen_interest_fp: set[tuple[int, str, float, str]] = set()
    default_card = _default_card_masked_for_rows(rows)

    for row in rows:
        gk = _row_import_batch_group(row, default_filename=default_label, default_month=month, default_year=year)
        if row.get("exclude", False):
            skipped_by[gk] += 1
            continue

        card = _effective_card_for_row(row, default_card)
        cardholder = row.get("cardholder", "")
        account = get_or_create_account(db, card, cardholder)
        ref = _normalize_reference_number(row.get("reference_number"))
        tx_d = _row_statement_date(row)
        dkey = tx_d.isoformat() if tx_d else ""
        amount = float(row.get("amount") or 0.0)
        merch_fp = _normalize_merchant_for_fingerprint(row.get("merchant_name") or "")
        interest_like = _interest_like_row(row)

        if ref:
            key = (ref, account.id, dkey)
            if key in seen_ref_line:
                skipped_by[gk] += 1
                continue
            existing = _find_existing_transaction_duplicate(
                db,
                account=account,
                ref=ref,
                tx_d=tx_d,
                amount=amount,
                merchant_fp=merch_fp,
                interest_like=interest_like,
            )
            if existing is not None:
                skipped_by[gk] += 1
                continue
            seen_ref_line.add(key)
        elif interest_like and tx_d is not None and merch_fp:
            ikey = (account.id, dkey, round(amount, 2), merch_fp)
            if ikey in seen_interest_fp:
                skipped_by[gk] += 1
                continue
            existing = _find_existing_transaction_duplicate(
                db,
                account=account,
                ref=None,
                tx_d=tx_d,
                amount=amount,
                merchant_fp=merch_fp,
                interest_like=True,
            )
            if existing is not None:
                skipped_by[gk] += 1
                continue
            seen_interest_fp.add(ikey)

        raw_cat = row.get("category_name") or row.get("suggested_category")
        if not raw_cat or raw_cat == "uncategorized":
            merchant = row.get("merchant_name", "")
            raw_cat = keyword_matcher.analyze(merchant)["suggested_category"] or raw_cat or "uncategorized"

        category = get_or_create_category(db, raw_cat)
        bid = batch_id_by_key[gk]

        tx = Transaction(
            transaction_date=row["transaction_date"],
            posted_date=row.get("posted_date"),
            reference_number=ref,
            merchant_name=row.get("merchant_name", ""),
            merchant_city=row.get("merchant_city") or None,
            merchant_state=row.get("merchant_state") or None,
            merchant_country=row.get("merchant_country") or None,
            mcc_description=row.get("mcc_description") or None,
            amount=row["amount"],
            currency=row.get("currency", "CAD"),
            transaction_type=row.get("transaction_type", "expense"),
            account_id=account.id,
            category_id=category.id,
            notes=row.get("notes") or None,
            import_batch_id=bid,
            is_excluded=False,
        )
        db.add(tx)
        imported_by[gk] += 1

    batches: list[ImportBatch] = []
    for gk in totals:
        blabel, bm, by = gk
        batches.append(
            ImportBatch(
                id=batch_id_by_key[gk],
                filename=blabel[:255],
                month=bm,
                year=by,
                total_rows=totals[gk],
                imported_rows=imported_by[gk],
                skipped_rows=skipped_by[gk],
            )
        )
        db.add(batches[-1])

    total_imported = sum(imported_by.values())
    total_skipped = sum(skipped_by.values())
    batches.sort(key=lambda b: (b.year, b.month, b.filename))
    db.commit()
    return batches, total_imported, total_skipped
