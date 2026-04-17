from __future__ import annotations

import io
import re
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

_DATE_PART = (
    r"(?:\d{1,2}[/\-]\d{1,2}(?:[/\-]\d{2,4})?"   # 01/15, 01-15, 01/15/2024
    r"|[A-Za-z]{3,}\s*\d{1,2}(?:[,\s]+\d{4})?"    # Jan 15, January 15 2024
    r"|\d{1,2}[-\s][A-Za-z]{3}(?:\s+\d{4})?)"     # 15 Mar, 15-Jul
)
_LINE_DATE_RE = re.compile(
    r"^(" + _DATE_PART + r")"
    r"(?:\s+" + _DATE_PART + r")?"
    r"\s+(.+)"
)

_END_AMOUNT_RE = re.compile(r"[\-\+]?\$?\s*([\d,]+\.\d{2})\s*(?:CR|DB|DR)?\s*$")

# Descriptions that indicate a credit/deposit (amount should be negative in expense view)
_CREDIT_DESC_RE = re.compile(
    r"\b(credit\s*memo|direct\s*deposit|e[\-\s]?deposit"
    r"|payroll\s*deposit|refund|reversal|interest\s*paid|dividend\s*paid)\b",
    re.IGNORECASE,
)


class PdfplumberTextParser(BaseParser):
    parser_id = "pdfplumber_text"
    parser_label = "Generic Text"

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
                errors=[f"Text extraction failed: {exc}"],
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
        warnings: list[str] = [
            "Regex-based: may not distinguish transaction date vs post date",
        ]

        with pdfplumber.open(io.BytesIO(content)) as pdf:
            all_text = ""
            for page in pdf.pages:
                all_text += (page.extract_text() or "") + "\n"
            fallback_year = infer_year_from_text(all_text)

        lines = all_text.splitlines()

        for line_idx, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue

            m = _LINE_DATE_RE.match(line)
            if not m:
                continue

            date_str = m.group(1).strip()
            rest = m.group(2).strip()

            if is_skip_row(rest):
                continue

            am = _END_AMOUNT_RE.search(rest)
            if not am:
                next_line = lines[line_idx + 1].strip() if line_idx + 1 < len(lines) else ""
                am2 = _END_AMOUNT_RE.search(next_line)
                if am2:
                    amount_str = am2.group(1)
                    merchant = rest
                else:
                    skipped += 1
                    errors.append(f"Line {line_idx + 1}: no amount found — '{line[:60]}'")
                    continue
            else:
                # Check if there's a second (earlier) amount before the last one.
                # Debit/Credit/Balance format ends with: ... txn_amount  balance
                # In that case the last number is the running balance — use the one before it.
                pre = rest[: am.start()].rstrip()
                inner_am = _END_AMOUNT_RE.search(pre)
                if inner_am:
                    amount_str = inner_am.group(1)
                    merchant = pre[: inner_am.start()].strip()
                else:
                    amount_str = am.group(1)
                    merchant = pre.strip()

            if not merchant:
                skipped += 1
                continue

            txn_date = try_parse_date(date_str, fallback_year)
            if txn_date is None:
                skipped += 1
                errors.append(f"Line {line_idx + 1}: bad date '{date_str}'")
                continue

            amount_raw = try_parse_amount(amount_str)
            if amount_raw is None:
                skipped += 1
                errors.append(f"Line {line_idx + 1}: bad amount '{amount_str}'")
                continue

            if re.search(r"\bCR\b", line, re.IGNORECASE):
                amount_raw = -abs(amount_raw)
            elif _CREDIT_DESC_RE.search(merchant):
                amount_raw = -abs(amount_raw)

            row = build_row(txn_date, merchant, amount_raw, default_currency, filename, keyword_matcher)
            rows.append(row)

        if skipped > 0:
            warnings.append(f"{skipped} row(s) skipped: ambiguous or unparseable lines")

        valid = sum(1 for r in rows if is_valid_row(r))
        confidence = min(compute_confidence(valid, skipped), 0.75)
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
