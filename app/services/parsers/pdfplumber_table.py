from __future__ import annotations

import io
from typing import TYPE_CHECKING, Any

from app.services.parsers._pdf_utils import (
    build_row,
    infer_year_from_text,
    is_skip_row,
    try_parse_amount,
    try_parse_date,
)
from app.services.parsers.base import (
    BaseParser,
    ParseResult,
    compute_confidence,
    detect_unknown_categories,
    is_valid_row,
)

if TYPE_CHECKING:
    from app.services.keyword_matching import KeywordMatcher

_HEADER_MAP: dict[str, list[str]] = {
    "date": ["date", "transaction date", "trans. date", "trans date", "activity date",
             "value date", "post date", "posted date"],
    "merchant": ["description", "merchant", "merchant name", "payee", "details",
                 "memo", "narrative", "particulars", "transaction description"],
    "amount": ["amount", "transaction amount", "cad amount", "net amount"],
    "debit": ["debit", "withdrawals", "withdrawal", "debit amount"],
    "credit": ["credit", "deposits", "deposit", "credit amount"],
}


def _match_headers(headers: list[str]) -> dict[str, int]:
    norm = [h.strip().lower() for h in headers]
    mapping: dict[str, int] = {}
    for field, aliases in _HEADER_MAP.items():
        for alias in aliases:
            if alias in norm:
                mapping[field] = norm.index(alias)
                break
    return mapping


class PdfplumberTableParser(BaseParser):
    parser_id = "pdfplumber_table"
    parser_label = "Generic Table"

    def can_handle(self, filename: str, content: bytes) -> bool:
        return filename.lower().endswith(".pdf")

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
                errors=[f"Table extraction failed: {exc}"],
            )

    def _parse_inner(
        self,
        content: bytes,
        filename: str,
        default_currency: str,
        keyword_matcher: KeywordMatcher | None,
        known_categories: list[str],
    ) -> ParseResult:
        import pdfplumber

        rows: list[dict[str, Any]] = []
        errors: list[str] = []
        skipped = 0
        warnings: list[str] = []

        with pdfplumber.open(io.BytesIO(content)) as pdf:
            first_text = pdf.pages[0].extract_text() or "" if pdf.pages else ""
            fallback_year = infer_year_from_text(first_text)

            for page_num, page in enumerate(pdf.pages, start=1):
                tables = page.extract_tables()
                if not tables:
                    continue

                for table in tables:
                    if not table or len(table) < 2:
                        continue

                    header_row = [str(c or "") for c in table[0]]
                    col_map = _match_headers(header_row)

                    has_split = "debit" in col_map or "credit" in col_map
                    has_amount = "amount" in col_map

                    if "date" not in col_map or "merchant" not in col_map:
                        warnings.append(
                            f"Page {page_num}: table skipped - could not identify date/merchant columns"
                        )
                        skipped += max(0, len(table) - 1)
                        continue

                    if not has_amount and not has_split:
                        warnings.append(
                            f"Page {page_num}: table skipped - no amount/debit/credit column found"
                        )
                        skipped += max(0, len(table) - 1)
                        continue

                    for row_idx, raw_row in enumerate(table[1:], start=2):
                        try:
                            cells = [str(c or "").strip() for c in raw_row]
                            if len(cells) <= max(col_map.values()):
                                skipped += 1
                                continue

                            date_str = cells[col_map["date"]].split("\n")[0].strip()
                            merchant = cells[col_map["merchant"]].replace("\n", " ").strip()

                            if not date_str and not merchant:
                                continue
                            if is_skip_row(merchant):
                                continue

                            txn_date = try_parse_date(date_str, fallback_year)
                            if txn_date is None and date_str:
                                skipped += 1
                                errors.append(f"Page {page_num} row {row_idx}: bad date '{date_str}'")
                                continue

                            if has_split:
                                debit_raw = cells[col_map["debit"]] if "debit" in col_map else ""
                                credit_raw = cells[col_map["credit"]] if "credit" in col_map else ""
                                debit = try_parse_amount(debit_raw) or 0.0
                                credit = try_parse_amount(credit_raw) or 0.0
                                amount_raw = debit if debit else -credit
                            else:
                                amount_raw = try_parse_amount(cells[col_map["amount"]])
                                if amount_raw is None:
                                    skipped += 1
                                    errors.append(f"Page {page_num} row {row_idx}: bad amount")
                                    continue

                            row = build_row(txn_date, merchant, amount_raw, default_currency, filename, keyword_matcher)
                            rows.append(row)

                        except Exception as row_exc:
                            skipped += 1
                            errors.append(f"Page {page_num} row {row_idx}: {row_exc}")

        if not rows and not errors:
            warnings.append("No tables found in PDF - try a different parser")

        valid = sum(1 for r in rows if is_valid_row(r))
        confidence = compute_confidence(valid, skipped)
        unknown_cats = detect_unknown_categories(rows, known_categories)

        return ParseResult(
            parser_id=self.parser_id,
            parser_label=self.parser_label,
            confidence=confidence,
            rows=rows,
            skipped_rows=skipped,
            warnings=warnings,
            errors=errors,
            unknown_pdf_categories=unknown_cats,
        )
