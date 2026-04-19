from __future__ import annotations

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
from app.services.parsers.ocr_parser import _pdf_to_images
from app.services.parsers.pdfplumber_text import _END_AMOUNT_RE, _LINE_DATE_RE

if TYPE_CHECKING:
    from app.services.keyword_matching import KeywordMatcher


def _check_tesseract() -> bool:
    import shutil
    return shutil.which("tesseract") is not None


class TesseractParser(BaseParser):
    parser_id = "tesseract_parser"
    parser_label = "OCR (Tesseract)"

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
        if not _check_tesseract():
            return ParseResult(
                parser_id=self.parser_id,
                parser_label=self.parser_label,
                confidence=0.0,
                rows=[],
                missing_dependency="Tesseract",
            )
        try:
            return self._parse_inner(content, filename, default_currency, keyword_matcher, known_categories)
        except Exception as exc:
            return ParseResult(
                parser_id=self.parser_id,
                parser_label=self.parser_label,
                confidence=0.0,
                rows=[],
                errors=[f"Tesseract OCR failed: {exc}"],
            )

    def _parse_inner(
        self,
        content: bytes,
        filename: str,
        default_currency: str,
        keyword_matcher: KeywordMatcher | None,
        known_categories: list[str],
    ) -> ParseResult:
        import pytesseract

        rows: list[dict[str, Any]] = []
        errors: list[str] = []
        skipped = 0
        warnings: list[str] = [
            "OCR-based (Tesseract): accuracy depends on scan quality",
        ]

        images = _pdf_to_images(content)
        if not images:
            return ParseResult(
                parser_id=self.parser_id,
                parser_label=self.parser_label,
                confidence=0.0,
                rows=[],
                errors=["Could not render PDF pages to images"],
            )

        all_text = ""
        for img in images:
            all_text += pytesseract.image_to_string(img, config="--psm 6") + "\n"

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
                    errors.append(f"Line {line_idx + 1}: no amount - '{line[:60]}'")
                    continue
            else:
                amount_str = am.group(1)
                merchant = rest[: am.start()].strip()

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

            row = build_row(txn_date, merchant, amount_raw, default_currency, filename, keyword_matcher)
            rows.append(row)

        if skipped > 0:
            warnings.append(f"{skipped} row(s) skipped: ambiguous lines after OCR")

        valid = sum(1 for r in rows if is_valid_row(r))
        confidence = min(compute_confidence(valid, skipped), 0.65)
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
