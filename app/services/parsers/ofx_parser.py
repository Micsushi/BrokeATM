from __future__ import annotations

import io
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from app.services.parsers.base import (
    BaseParser,
    ParseResult,
    compute_confidence,
    detect_unknown_categories,
    is_valid_row,
)

if TYPE_CHECKING:
    from app.services.keyword_matching import KeywordMatcher

_TRNTYPE_MAP: dict[str, str] = {
    "DEBIT": "expense",
    "CHECK": "expense",
    "ATM": "expense",
    "POS": "expense",
    "PAYMENT": "transfer",
    "XFER": "transfer",
    "CREDIT": "income",
    "DEP": "income",
    "DIRECTDEP": "income",
    "INT": "income",
    "DIV": "income",
    "FEE": "expense",
    "SRVCHG": "expense",
    "OTHER": "expense",
}


class OfxParser(BaseParser):
    parser_id = "ofx_parser"
    parser_label = "OFX / QFX"

    def can_handle(self, filename: str, content: bytes) -> bool:
        ext = filename.lower().rsplit(".", 1)[-1]
        return ext in {"ofx", "qfx"}

    def parse(
        self,
        content: bytes,
        filename: str,
        default_currency: str,
        keyword_matcher: KeywordMatcher | None,
        known_categories: list[str],
    ) -> ParseResult:
        try:
            return self._parse_inner(content, filename, default_currency, keyword_matcher, known_categories)
        except Exception as exc:
            return ParseResult(
                parser_id=self.parser_id,
                parser_label=self.parser_label,
                confidence=0.0,
                rows=[],
                errors=[f"OFX parse failed: {exc}"],
            )

    def _parse_inner(
        self,
        content: bytes,
        filename: str,
        default_currency: str,
        keyword_matcher: KeywordMatcher | None,
        known_categories: list[str],
    ) -> ParseResult:
        from ofxtools.Parser import OFXTree

        from app.services.csv_parser import _suggest_category, classify_transaction

        parser = OFXTree()
        parser.parse(io.BytesIO(content))
        ofx = parser.convert()

        rows: list[dict[str, Any]] = []
        errors: list[str] = []
        skipped = 0

        for stmtrs in ofx.statements:
            stmt_currency = getattr(stmtrs, "curdef", default_currency) or default_currency
            for txn in stmtrs.transactions:
                try:
                    amount_raw = float(txn.trnamt if isinstance(txn.trnamt, (int, float)) else Decimal(str(txn.trnamt)))
                    amount_raw = -amount_raw

                    name_part = (txn.name or "").strip()
                    memo_part = (txn.memo or "").strip() if hasattr(txn, "memo") else ""
                    merchant = name_part
                    if memo_part and memo_part.lower() != name_part.lower():
                        merchant = f"{name_part} {memo_part}".strip() if name_part else memo_part

                    trntype = (txn.trntype or "OTHER").upper()
                    tx_type_hint = _TRNTYPE_MAP.get(trntype, "expense")

                    tx_type, amount = classify_transaction(amount_raw, merchant, "")
                    if tx_type_hint == "income" and amount_raw <= 0:
                        tx_type = "income"
                        amount = abs(amount_raw)
                    elif tx_type_hint == "transfer":
                        tx_type = "transfer"
                        amount = abs(amount_raw)

                    suggested_category, kw_analysis = _suggest_category("", merchant, keyword_matcher)

                    txn_date = txn.dtposted.date() if hasattr(txn.dtposted, "date") else txn.dtposted
                    posted = txn.dtavail.date() if (hasattr(txn, "dtavail") and txn.dtavail) else None

                    row: dict[str, Any] = {
                        "transaction_date": txn_date.isoformat() if txn_date else None,
                        "posted_date": posted.isoformat() if posted else None,
                        "reference_number": getattr(txn, "fitid", None),
                        "merchant_name": merchant,
                        "merchant_city": None,
                        "merchant_state": None,
                        "merchant_country": None,
                        "mcc_description": None,
                        "amount": amount,
                        "currency": stmt_currency,
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
                    rows.append(row)
                except Exception as row_exc:
                    skipped += 1
                    errors.append(f"Transaction skipped: {row_exc}")

        valid = sum(1 for r in rows if is_valid_row(r))
        confidence = 0.95 if (valid > 0 and not errors) else compute_confidence(valid, skipped)
        unknown_cats = detect_unknown_categories(rows, known_categories)

        return ParseResult(
            parser_id=self.parser_id,
            parser_label=self.parser_label,
            confidence=confidence,
            rows=rows,
            skipped_rows=skipped,
            errors=errors,
            unknown_pdf_categories=unknown_cats,
        )
