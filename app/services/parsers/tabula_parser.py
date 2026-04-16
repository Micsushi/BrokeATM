from __future__ import annotations

import io
import os
import tempfile
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
from app.services.parsers.pdfplumber_table import _match_headers

if TYPE_CHECKING:
    from app.services.keyword_matching import KeywordMatcher

_JAVA_ERROR = (
    "Java not found — install from https://java.com and add to PATH. "
    "Tabula requires Java for PDF table extraction."
)


def _check_java() -> bool:
    import shutil
    return shutil.which("java") is not None


class TabulaParser(BaseParser):
    parser_id = "tabula"
    parser_label = "Tabula"

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
        if not _check_java():
            return ParseResult(
                parser_id=self.parser_id,
                parser_label=self.parser_label,
                confidence=0.0,
                rows=[],
                errors=[_JAVA_ERROR],
            )
        try:
            return self._parse_inner(content, filename, default_currency, keyword_matcher, known_categories)
        except Exception as exc:
            return ParseResult(
                parser_id=self.parser_id,
                parser_label=self.parser_label,
                confidence=0.0,
                rows=[],
                errors=[f"Tabula failed: {exc}"],
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
        import tabula

        rows: list[dict[str, Any]] = []
        errors: list[str] = []
        skipped = 0
        warnings: list[str] = []

        with pdfplumber.open(io.BytesIO(content)) as pdf:
            first_text = pdf.pages[0].extract_text() or "" if pdf.pages else ""
            fallback_year = infer_year_from_text(first_text)

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        try:
            dfs = tabula.read_pdf(
                tmp_path,
                pages="all",
                multiple_tables=True,
                stream=True,
                silent=True,
            )
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

        if not dfs:
            warnings.append("No tables detected.")
            return ParseResult(
                parser_id=self.parser_id,
                parser_label=self.parser_label,
                confidence=0.0,
                rows=[],
                warnings=warnings,
            )

        for tbl_idx, df in enumerate(dfs):
            if df.empty or len(df) < 1:
                continue

            df = df.fillna("")
            headers = [str(c).strip() for c in df.columns.tolist()]
            col_map = _match_headers(headers)

            if "date" not in col_map or "merchant" not in col_map:
                warnings.append(f"Table {tbl_idx + 1}: skipped — no date/merchant columns identified")
                skipped += len(df)
                continue

            has_split = "debit" in col_map or "credit" in col_map
            has_amount = "amount" in col_map

            if not has_amount and not has_split:
                warnings.append(f"Table {tbl_idx + 1}: skipped — no amount column identified")
                skipped += len(df)
                continue

            for row_idx, raw_row in df.iterrows():
                try:
                    cells = [str(v).strip() for v in raw_row.tolist()]

                    date_str = cells[col_map["date"]].split("\n")[0].strip() if col_map["date"] < len(cells) else ""
                    merchant = cells[col_map["merchant"]].replace("\n", " ").strip() if col_map["merchant"] < len(cells) else ""

                    if not date_str and not merchant:
                        continue
                    if is_skip_row(merchant):
                        continue

                    txn_date = try_parse_date(date_str, fallback_year)
                    if txn_date is None and date_str:
                        skipped += 1
                        errors.append(f"Table {tbl_idx + 1} row {row_idx}: date not recognized — '{date_str}'")
                        continue

                    if has_split:
                        debit_raw = cells[col_map["debit"]] if "debit" in col_map and col_map["debit"] < len(cells) else ""
                        credit_raw = cells[col_map["credit"]] if "credit" in col_map and col_map["credit"] < len(cells) else ""
                        debit = try_parse_amount(debit_raw) or 0.0
                        credit = try_parse_amount(credit_raw) or 0.0
                        amount_raw = debit if debit else -credit
                        if amount_raw == 0.0:
                            skipped += 1
                            continue
                    else:
                        amount_raw = try_parse_amount(cells[col_map["amount"]] if col_map["amount"] < len(cells) else "")
                        if amount_raw is None:
                            skipped += 1
                            errors.append(f"Table {tbl_idx + 1} row {row_idx}: bad amount")
                            continue

                    row = build_row(txn_date, merchant, amount_raw, default_currency, filename, keyword_matcher)
                    rows.append(row)

                except Exception as row_exc:
                    skipped += 1
                    errors.append(f"Table {tbl_idx + 1} row {row_idx}: {row_exc}")

        valid = sum(1 for r in rows if is_valid_row(r))
        confidence = min(compute_confidence(valid, skipped), 0.82)
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
