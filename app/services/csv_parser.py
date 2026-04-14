from __future__ import annotations

import csv
import io
import re
from collections import Counter
from datetime import date, datetime
from typing import Any

from app.models.models import TransactionType
from app.services.mcc_map import DEFAULT_CATEGORIES, is_cashback, is_payment, match_by_keywords, mcc_to_category

# Build a static keyword map from the default categories for use during parse preview.
# At parse time we don't have DB access, so we use the built-in defaults.
_STATIC_KW_MAP: dict[str, list[str]] = {
    name: [k.strip().lower() for k in kws.split(",") if k.strip()]
    for name, _color, kws in DEFAULT_CATEGORIES
    if kws
}

# Candidate header names per logical field, matched case-insensitively, first match wins.
FIELD_ALIASES: dict[str, list[str]] = {
    "date": [
        "Date", "Transaction Date", "Trans. Date", "Trans Date", "TransDate",
        "Activity Date", "Effective Date", "Value Date", "Trade Date",
        # fallback for banks that only export one date column
        "Post Date", "Posted Date", "Posting Date", "Settlement Date",
        "Cleared Date", "Process Date", "Processed Date",
    ],
    "posted_date": [
        "Posted Date", "Post Date", "Posting Date", "Settlement Date",
        "Cleared Date", "Process Date", "Processed Date",
    ],
    "amount": [
        "Amount", "Transaction Amount", "CAD Amount", "CAD$ Amount", "CAD $Amount",
        "Debit/Credit Amount", "Net Amount", "Charge Amount", "Payment Amount",
    ],
    "merchant_name": [
        "Merchant Name", "Description", "Description 1", "Description 2",
        "Transaction Description", "Payee", "Payee Name", "Name", "Details",
        "Memo", "Narrative", "Particulars", "Reference", "Beneficiary", "Store Name",
    ],
    "mcc_description": [
        "Merchant Category Description", "Category", "MCC Description",
        "Merchant Category", "Transaction Category", "Transaction Type", "Type",
    ],
    "card_number": [
        "Card Number", "Card No.", "Card No", "Card #",
        "Account Number", "Account No.", "Account No", "Acct No", "Card Last 4",
    ],
    "cardholder": [
        "Name on Card", "Cardholder Name", "Card Holder", "Cardholder",
        "Account Holder", "Account Name", "Customer Name",
    ],
    "reference_number": [
        "Reference Number", "Reference #", "Reference No", "Ref No", "Ref #",
        "Transaction ID", "Transaction #", "Confirmation #", "Confirmation Number",
        "Auth Code", "Authorization Code", "Cheque Number", "Check Number",
    ],
    "merchant_city": ["Merchant City", "City", "Location"],
    "merchant_state": [
        "Merchant State or Province", "Merchant Province", "Province",
        "State", "State/Province", "Region",
    ],
    "merchant_country": ["Merchant Country Code", "Merchant Country", "Country", "Country Code"],
}

REQUIRED_FIELDS = {"date", "amount"}

_DEBIT_ALIASES = ["Debit", "Withdrawals", "Withdrawal", "Debit Amount"]
_CREDIT_ALIASES = ["Credit", "Deposits", "Deposit", "Credit Amount"]


def _norm(h: str) -> str:
    return h.strip().lower()


def _build_col_map(headers: list[str]) -> dict[str, str] | None:
    norm_to_actual: dict[str, str] = {_norm(h): h for h in headers}
    col_map: dict[str, str] = {}

    for field, aliases in FIELD_ALIASES.items():
        for alias in aliases:
            if _norm(alias) in norm_to_actual:
                col_map[field] = norm_to_actual[_norm(alias)]
                break

    if "amount" not in col_map:
        debit_key = next((norm_to_actual[_norm(a)] for a in _DEBIT_ALIASES if _norm(a) in norm_to_actual), None)
        credit_key = next((norm_to_actual[_norm(a)] for a in _CREDIT_ALIASES if _norm(a) in norm_to_actual), None)
        if debit_key or credit_key:
            col_map["_debit_col"] = debit_key or ""
            col_map["_credit_col"] = credit_key or ""
            col_map["amount"] = "__split__"

    if any(req not in col_map for req in REQUIRED_FIELDS):
        return None

    return col_map


def _resolve_amount(raw_row: dict[str, str], col_map: dict[str, str]) -> float:
    if col_map["amount"] == "__split__":
        debit_raw = raw_row.get(col_map.get("_debit_col", ""), "") or ""
        credit_raw = raw_row.get(col_map.get("_credit_col", ""), "") or ""
        debit = _parse_amount(debit_raw) if debit_raw.strip() else 0.0
        credit = _parse_amount(credit_raw) if credit_raw.strip() else 0.0
        # debit = money out (positive), credit = money in (negative → refund/income path)
        return debit if debit else -credit
    return _parse_amount(raw_row.get(col_map["amount"], "0"))


def _parse_amount(raw: str) -> float:
    s = raw.strip()
    if not s:
        return 0.0
    if s.startswith("(") and s.endswith(")"):
        s = "-" + s[1:-1]
    return float(re.sub(r"[,$\s]", "", s))


def _parse_date(raw: str) -> date:
    for fmt in (
        "%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d",
        "%m-%d-%Y", "%d-%m-%Y",
        "%b %d, %Y", "%B %d, %Y", "%d %b %Y", "%d %B %Y",
        "%Y%m%d",
    ):
        try:
            return datetime.strptime(raw.strip(), fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Cannot parse date: {raw!r}")


def _get(raw_row: dict[str, str], col_map: dict[str, str], field: str) -> str:
    col = col_map.get(field, "")
    if not col or col == "__split__":
        return ""
    return (raw_row.get(col) or "").strip()


def detect_format(headers: list[str]) -> tuple[str | None, dict[str, str] | None]:
    col_map = _build_col_map(headers)
    return ("generic", col_map) if col_map is not None else (None, None)


def detect_month_year(rows: list[dict[str, Any]]) -> tuple[int, int]:
    counter: Counter[tuple[int, int]] = Counter()
    for row in rows:
        d = row.get("transaction_date")
        if isinstance(d, date):
            counter[(d.month, d.year)] += 1
    if counter:
        (month, year), _ = counter.most_common(1)[0]
        return month, year
    return 1, 2000


def classify_transaction(amount_raw: float, merchant_name: str, mcc_description: str) -> tuple[str, float]:
    if is_payment(merchant_name, mcc_description):
        return TransactionType.transfer, abs(amount_raw)
    if is_cashback(merchant_name, mcc_description):
        return TransactionType.refund, abs(amount_raw)
    if amount_raw < 0:
        return TransactionType.refund, abs(amount_raw)
    return TransactionType.expense, abs(amount_raw)


def _suggest_category(mcc_desc: str, merchant_name: str) -> str:
    cat = mcc_to_category(mcc_desc)
    if cat and cat != "uncategorized" and cat != mcc_desc.strip().lower():
        return cat
    return match_by_keywords(merchant_name, _STATIC_KW_MAP) or "uncategorized"


def parse_csv(content: bytes) -> dict[str, Any]:
    text = content.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    headers = reader.fieldnames or []

    fmt_name, col_map = detect_format(list(headers))
    if fmt_name is None or col_map is None:
        return {
            "format": None,
            "rows": [],
            "detected_month": None,
            "detected_year": None,
            "errors": [
                "Unrecognized CSV format: could not find a date column and an amount column. "
                "Expected headers like 'Date'/'Transaction Date' and 'Amount'/'Debit'/'Credit'."
            ],
        }

    rows: list[dict[str, Any]] = []
    errors: list[str] = []

    for i, raw_row in enumerate(reader, start=2):
        try:
            amount_raw = _resolve_amount(raw_row, col_map)
            merchant_name = _get(raw_row, col_map, "merchant_name")
            mcc_desc = _get(raw_row, col_map, "mcc_description")
            tx_type, amount = classify_transaction(amount_raw, merchant_name, mcc_desc)

            date_str = _get(raw_row, col_map, "date")
            posted_str = _get(raw_row, col_map, "posted_date")

            rows.append({
                "transaction_date": _parse_date(date_str) if date_str else None,
                "posted_date": _parse_date(posted_str) if posted_str else None,
                "reference_number": _get(raw_row, col_map, "reference_number"),
                "merchant_name": merchant_name,
                "merchant_city": _get(raw_row, col_map, "merchant_city"),
                "merchant_state": _get(raw_row, col_map, "merchant_state"),
                "merchant_country": _get(raw_row, col_map, "merchant_country"),
                "mcc_description": mcc_desc,
                "amount": amount,
                "currency": "CAD",
                "transaction_type": tx_type,
                "suggested_category": _suggest_category(mcc_desc, merchant_name),
                "card_number_masked": _get(raw_row, col_map, "card_number"),
                "cardholder": _get(raw_row, col_map, "cardholder"),
                "is_payment": tx_type == TransactionType.transfer,
                "is_refund": tx_type == TransactionType.refund,
            })
        except Exception as exc:
            errors.append(f"Row {i}: {exc}")

    month, year = detect_month_year(rows)
    return {
        "format": fmt_name,
        "rows": rows,
        "detected_month": month,
        "detected_year": year,
        "errors": errors,
    }
