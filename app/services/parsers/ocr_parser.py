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
from app.services.parsers.pdfplumber_text import _END_AMOUNT_RE, _LINE_DATE_RE

if TYPE_CHECKING:
    from app.services.keyword_matching import KeywordMatcher

_reader = None

_LINE_Y_TOLERANCE = 12


def _ocr_image_to_text(reader: Any, img: Any) -> str:
    results = reader.readtext(img, detail=1)
    if not results:
        return ""

    # results: [(bbox, text, confidence), ...]
    # bbox: [[x0,y0],[x1,y0],[x1,y1],[x0,y1]] top-left origin
    words: list[tuple[float, float, str]] = []
    for bbox, text, _conf in results:
        x = bbox[0][0]
        y = bbox[0][1]
        words.append((y, x, text.strip()))

    words.sort(key=lambda w: (w[0], w[1]))

    lines: list[str] = []
    current_words: list[tuple[float, str]] = []
    current_y: float | None = None

    for y, x, text in words:
        if current_y is None or abs(y - current_y) <= _LINE_Y_TOLERANCE:
            current_words.append((x, text))
            if current_y is None:
                current_y = y
        else:
            current_words.sort(key=lambda w: w[0])
            lines.append(" ".join(t for _, t in current_words))
            current_words = [(x, text)]
            current_y = y

    if current_words:
        current_words.sort(key=lambda w: w[0])
        lines.append(" ".join(t for _, t in current_words))

    return "\n".join(lines)


def _get_reader() -> Any:
    global _reader
    if _reader is None:
        import easyocr
        _reader = easyocr.Reader(["en"], gpu=False, verbose=False)
    return _reader


def _pdf_to_images(content: bytes) -> list[Any]:
    import fitz
    import numpy as np

    doc = fitz.open(stream=content, filetype="pdf")
    images = []
    mat = fitz.Matrix(150 / 72, 150 / 72)
    for page in doc:
        pix = page.get_pixmap(matrix=mat)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
        images.append(img)
    doc.close()
    return images


class OcrParser(BaseParser):
    parser_id = "ocr_parser"
    parser_label = "OCR"

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
            return self._parse_inner(
                content, filename, default_currency, keyword_matcher, known_categories
            )
        except Exception as exc:
            return ParseResult(
                parser_id=self.parser_id,
                parser_label=self.parser_label,
                confidence=0.0,
                rows=[],
                errors=[f"OCR extraction failed: {exc}"],
            )

    def _parse_inner(
        self,
        content: bytes,
        filename: str,
        default_currency: str,
        keyword_matcher: KeywordMatcher | None,
        known_categories: list[str],
    ) -> ParseResult:
        import io
        import pdfplumber

        with pdfplumber.open(io.BytesIO(content)) as pdf:
            page_texts = [p.extract_text() or "" for p in pdf.pages]

        avg_chars = sum(len(t) for t in page_texts) / max(len(page_texts), 1)
        if avg_chars > 800:
            return ParseResult(
                parser_id=self.parser_id,
                parser_label=self.parser_label,
                confidence=0.0,
                rows=[],
                warnings=["PDF has a text layer — OCR skipped. Use Generic Text or Bank-Specific."],
            )

        rows: list[dict[str, Any]] = []
        errors: list[str] = []
        skipped = 0
        warnings: list[str] = [
            "OCR-based: accuracy depends on scan quality; best for scanned/image PDFs",
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

        reader = _get_reader()
        all_text = ""
        for img in images:
            all_text += _ocr_image_to_text(reader, img) + "\n"

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
                    errors.append(f"Line {line_idx + 1}: no amount — '{line[:60]}'")
                    continue
            else:
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
            elif re.search(
                r"\b(credit\s*memo|direct\s*deposit|refund|reversal)\b",
                merchant, re.IGNORECASE,
            ):
                amount_raw = -abs(amount_raw)

            row = build_row(
                txn_date, merchant, amount_raw, default_currency, filename, keyword_matcher
            )
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
