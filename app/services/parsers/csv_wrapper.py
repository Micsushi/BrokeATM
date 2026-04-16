from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.services.parsers.base import BaseParser, ParseResult, compute_confidence

if TYPE_CHECKING:
    from app.services.keyword_matching import KeywordMatcher


class CsvWrapperParser(BaseParser):
    parser_id = "csv_wrapper"
    parser_label = "CSV"

    def can_handle(self, filename: str, content: bytes) -> bool:
        return filename.lower().endswith(".csv")

    def parse(
        self,
        content: bytes,
        filename: str,
        default_currency: str,
        keyword_matcher: KeywordMatcher | None,
        known_categories: list[str],
    ) -> ParseResult:
        from app.services.csv_parser import parse_csv

        try:
            result = parse_csv(content, default_currency=default_currency, keyword_matcher=keyword_matcher)
        except Exception as exc:
            return ParseResult(
                parser_id=self.parser_id,
                parser_label=self.parser_label,
                confidence=0.0,
                rows=[],
                errors=[str(exc)],
            )

        rows: list[dict[str, Any]] = []
        for r in result.get("rows", []):
            row = dict(r)
            for date_field in ("transaction_date", "posted_date"):
                if hasattr(row.get(date_field), "isoformat"):
                    row[date_field] = row[date_field].isoformat()
            row.setdefault("source_file", filename)
            rows.append(row)

        errors = result.get("errors", [])
        valid = len(rows)
        skipped = len(errors)
        confidence = compute_confidence(valid, skipped) if valid > 0 else 0.0
        if result.get("format") is None:
            confidence = 0.0

        return ParseResult(
            parser_id=self.parser_id,
            parser_label=self.parser_label,
            confidence=confidence,
            rows=rows,
            skipped_rows=skipped,
            errors=errors,
        )
