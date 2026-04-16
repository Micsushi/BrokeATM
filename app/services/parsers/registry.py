from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.services.parsers.base import BaseParser, ParseResult
from app.services.parsers.camelot_lattice import CamelotLatticeParser
from app.services.parsers.camelot_stream import CamelotStreamParser
from app.services.parsers.csv_wrapper import CsvWrapperParser
from app.services.parsers.ocr_parser import OcrParser
from app.services.parsers.ofx_parser import OfxParser
from app.services.parsers.pdfplumber_coords import PdfplumberCoordsParser
from app.services.parsers.pdfplumber_table import PdfplumberTableParser
from app.services.parsers.pdfplumber_text import PdfplumberTextParser
from app.services.parsers.tabula_parser import TabulaParser
from app.services.parsers.tesseract_parser import TesseractParser, _check_tesseract

if TYPE_CHECKING:
    from app.services.keyword_matching import KeywordMatcher

ALL_PARSERS: list[BaseParser] = [
    PdfplumberCoordsParser(),
    CamelotLatticeParser(),
    PdfplumberTableParser(),
    CamelotStreamParser(),
    TabulaParser(),
    PdfplumberTextParser(),
    OcrParser(),
    *([TesseractParser()] if _check_tesseract() else []),
    OfxParser(),
    CsvWrapperParser(),
]


def run_all(
    content: bytes,
    filename: str,
    default_currency: str,
    keyword_matcher: KeywordMatcher | None,
    known_categories: list[str],
) -> list[dict[str, Any]]:
    results: list[ParseResult] = []
    for parser in ALL_PARSERS:
        if parser.can_handle(filename, content):
            result = parser.parse(
                content, filename, default_currency, keyword_matcher, known_categories
            )
            results.append(result)
        else:
            results.append(ParseResult(
                parser_id=parser.parser_id,
                parser_label=parser.parser_label,
                confidence=0.0,
                rows=[],
                warnings=["Not applicable for this file type."],
            ))
    return [_result_to_dict(r) for r in results]


def get_parser(parser_id: str) -> BaseParser | None:
    return next((p for p in ALL_PARSERS if p.parser_id == parser_id), None)


def _result_to_dict(r: ParseResult) -> dict[str, Any]:
    return {
        "parser_id": r.parser_id,
        "parser_label": r.parser_label,
        "confidence": r.confidence,
        "rows": r.rows,
        "skipped_rows": r.skipped_rows,
        "warnings": r.warnings,
        "errors": r.errors,
        "unknown_pdf_categories": r.unknown_pdf_categories,
    }
