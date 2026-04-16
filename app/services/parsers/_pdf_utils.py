from __future__ import annotations

import re
from datetime import date
from typing import Any

_SKIP_PATTERNS = re.compile(
    r"^\s*(opening|closing|balance\s*forward|previous\s*balance|new\s*balance|starting\s*balance|"
    r"total|subtotal|minimum\s*payment|credit\s*limit|available\s*credit|"
    r"statement\s*date|payment\s*due|brought\s*forward)\b",
    re.IGNORECASE,
)

_DATE_FORMATS = (
    "%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d",
    "%m-%d-%Y", "%d-%m-%Y",
    "%b %d %Y", "%b %d, %Y", "%B %d %Y", "%B %d, %Y",
    "%d %b %Y", "%d %B %Y",
    "%b %d", "%m/%d",
    "%b%d", "%b%d%Y",
)


def try_parse_date(raw: str, fallback_year: int | None = None) -> date | None:
    from datetime import datetime
    raw = raw.strip().split("\n")[0].strip()
    if not raw:
        return None
    for fmt in _DATE_FORMATS:
        try:
            d = datetime.strptime(raw, fmt)
            if d.year == 1900 and fallback_year:
                d = d.replace(year=fallback_year)
            return d.date()
        except ValueError:
            continue
    return None


def try_parse_amount(raw: str) -> float | None:
    s = raw.strip().replace(",", "").replace("$", "").replace(" ", "")
    if not s:
        return None
    if s.startswith("(") and s.endswith(")"):
        s = "-" + s[1:-1]
    try:
        return float(s)
    except ValueError:
        return None


def is_skip_row(text: str) -> bool:
    return bool(_SKIP_PATTERNS.match(text.strip()))


def infer_year_from_text(text: str) -> int | None:
    import datetime
    matches = re.findall(r"\b(20\d{2})\b", text[:1000])
    if matches:
        return int(matches[0])
    return datetime.date.today().year


def build_row(
    transaction_date: date | None,
    merchant: str,
    amount_raw: float,
    currency: str,
    filename: str,
    keyword_matcher: Any,
) -> dict[str, Any]:
    from app.services.csv_parser import _suggest_category, classify_transaction

    tx_type, amount = classify_transaction(amount_raw, merchant, "")
    suggested_category, kw_analysis = _suggest_category("", merchant, keyword_matcher)

    return {
        "transaction_date": transaction_date.isoformat() if transaction_date else None,
        "posted_date": None,
        "reference_number": None,
        "merchant_name": merchant.strip(),
        "merchant_city": None,
        "merchant_state": None,
        "merchant_country": None,
        "mcc_description": None,
        "amount": amount,
        "currency": currency,
        "transaction_type": tx_type,
        "suggested_category": suggested_category,
        "card_number_masked": None,
        "cardholder": None,
        "is_payment": tx_type == "transfer",
        "is_refund": tx_type == "refund",
        "duplicate": False,
        "exclude": False,
        "notes": None,
        "source_file": filename,
        "normalized_merchant": kw_analysis.get("normalized_merchant", ""),
        "keyword_matches": kw_analysis.get("keyword_matches", []),
        "keyword_resolution_needed": kw_analysis.get("keyword_resolution_needed", False),
        "keyword_conflict_categories": kw_analysis.get("keyword_conflict_categories", False),
        "suggestion_source": kw_analysis.get("suggestion_source", "none"),
    }
