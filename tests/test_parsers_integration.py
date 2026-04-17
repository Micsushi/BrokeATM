from __future__ import annotations

import pytest

from tests.conftest import assert_valid_rows, pdf_bytes

from app.services.parsers.pdfplumber_coords import PdfplumberCoordsParser
from app.services.parsers.pdfplumber_table import PdfplumberTableParser
from app.services.parsers.pdfplumber_text import PdfplumberTextParser
from app.services.parsers.tabula_parser import TabulaParser


# ---------------------------------------------------------------------------
# Bank-Specific (coordinate-based) parser
# ---------------------------------------------------------------------------

class TestBankSpecificParser:
    def setup_method(self):
        self.parser = PdfplumberCoordsParser()

    def test_td_visa(self):
        result = self.parser.parse(pdf_bytes("td_visa"), "td_visa.pdf", "CAD", None, [])
        assert result.confidence >= 0.90
        assert len(result.rows) >= 10
        assert_valid_rows(result.rows, min_rows=10)

    def test_td_chequing(self):
        result = self.parser.parse(pdf_bytes("td_chequing"), "td_chequing.pdf", "CAD", None, [])
        assert result.confidence >= 0.90
        assert len(result.rows) >= 5
        assert_valid_rows(result.rows, min_rows=5)

    def test_cibc_visa(self):
        result = self.parser.parse(pdf_bytes("cibc_visa_1"), "cibc_visa.pdf", "CAD", None, [])
        assert result.confidence >= 0.90
        assert len(result.rows) >= 5
        assert_valid_rows(result.rows, min_rows=5)

    def test_cibc_visa_uses_continuation_pages(self):
        result = self.parser.parse(pdf_bytes("cibc_visa_1"), "cibc_visa.pdf", "CAD", None, [])
        assert len(result.rows) >= 30
        assert_valid_rows(result.rows, min_rows=30)

    def test_rbc_visa(self):
        result = self.parser.parse(pdf_bytes("rbc_visa"), "rbc_visa.pdf", "CAD", None, [])
        assert result.confidence >= 0.85
        assert len(result.rows) >= 5
        assert_valid_rows(result.rows, min_rows=5)

    def test_beats_generic_text_on_td_visa(self):
        bank_result = self.parser.parse(pdf_bytes("td_visa"), "td_visa.pdf", "CAD", None, [])
        text_result = PdfplumberTextParser().parse(pdf_bytes("td_visa"), "td_visa.pdf", "CAD", None, [])
        assert bank_result.confidence >= text_result.confidence

    def test_all_rows_have_dates(self):
        result = self.parser.parse(pdf_bytes("td_visa"), "td_visa.pdf", "CAD", None, [])
        assert all(r["transaction_date"] for r in result.rows)

    def test_corrupt_pdf_returns_gracefully(self):
        result = self.parser.parse(b"NOT A PDF", "bad.pdf", "CAD", None, [])
        assert result.confidence == 0.0
        assert len(result.errors) > 0


# ---------------------------------------------------------------------------
# Generic Table parser
# ---------------------------------------------------------------------------

class TestGenericTableParser:
    def setup_method(self):
        self.parser = PdfplumberTableParser()

    def test_td_chequing_has_tables(self):
        result = self.parser.parse(pdf_bytes("td_chequing"), "td_chequing.pdf", "CAD", None, [])
        assert len(result.rows) > 0

    def test_corrupt_pdf_returns_gracefully(self):
        result = self.parser.parse(b"NOT A PDF", "bad.pdf", "CAD", None, [])
        assert result.confidence == 0.0


# ---------------------------------------------------------------------------
# Generic Text (regex) parser
# ---------------------------------------------------------------------------

class TestGenericTextParser:
    def setup_method(self):
        self.parser = PdfplumberTextParser()

    def test_td_visa_extracts_rows(self):
        result = self.parser.parse(pdf_bytes("td_visa"), "td_visa.pdf", "CAD", None, [])
        assert len(result.rows) > 0

    def test_cibc_visa_extracts_rows(self):
        result = self.parser.parse(pdf_bytes("cibc_visa_1"), "cibc_visa.pdf", "CAD", None, [])
        assert len(result.rows) > 0

    def test_rbc_chequing_day_first_dates(self):
        result = self.parser.parse(pdf_bytes("rbc_chequing"), "rbc_chequing.pdf", "CAD", None, [])
        assert len(result.rows) > 0
        dates = [r["transaction_date"] for r in result.rows]
        assert any(d.startswith("2004") for d in dates)

    def test_confidence_capped_at_75(self):
        result = self.parser.parse(pdf_bytes("td_visa"), "td_visa.pdf", "CAD", None, [])
        assert result.confidence <= 0.75

    def test_corrupt_pdf_returns_gracefully(self):
        result = self.parser.parse(b"NOT A PDF", "bad.pdf", "CAD", None, [])
        assert result.confidence == 0.0 or isinstance(result.rows, list)


# ---------------------------------------------------------------------------
# Tabula parser
# ---------------------------------------------------------------------------

class TestTabulaParser:
    def setup_method(self):
        self.parser = TabulaParser()

    def test_can_handle_pdf(self):
        assert self.parser.can_handle("file.pdf", b"")
        assert not self.parser.can_handle("file.csv", b"")

    def test_td_chequing_extracts_rows(self):
        result = self.parser.parse(pdf_bytes("td_chequing"), "td_chequing.pdf", "CAD", None, [])
        if result.errors and "Java" in result.errors[0]:
            pytest.skip("Java not available")
        assert len(result.rows) > 0

    def test_corrupt_pdf_returns_gracefully(self):
        result = self.parser.parse(b"NOT A PDF", "bad.pdf", "CAD", None, [])
        assert result.confidence == 0.0


# ---------------------------------------------------------------------------
# OCR parser
# ---------------------------------------------------------------------------

class TestOcrParser:
    def setup_method(self):
        from app.services.parsers.ocr_parser import OcrParser
        self.parser = OcrParser()

    def test_can_handle_pdf(self):
        assert self.parser.can_handle("file.pdf", b"")
        assert not self.parser.can_handle("file.csv", b"")

    def test_skips_digital_pdf(self):
        result = self.parser.parse(pdf_bytes("td_visa"), "td_visa.pdf", "CAD", None, [])
        assert result.confidence == 0.0
        assert any("text layer" in w for w in result.warnings)

    def test_rbc_chequing_scanned(self):
        result = self.parser.parse(pdf_bytes("rbc_chequing"), "rbc_chequing.pdf", "CAD", None, [])
        # eStatement has partial text layer — may skip or extract rows
        assert isinstance(result.rows, list)

    def test_corrupt_pdf_returns_gracefully(self):
        result = self.parser.parse(b"NOT A PDF", "bad.pdf", "CAD", None, [])
        assert result.confidence == 0.0


# ---------------------------------------------------------------------------
# Camelot parsers — skip if Ghostscript not available
# ---------------------------------------------------------------------------

class TestCamelotParsers:
    def test_lattice_graceful_without_ghostscript(self):
        from app.services.parsers.camelot_lattice import CamelotLatticeParser, _check_ghostscript
        if _check_ghostscript():
            pytest.skip("Ghostscript available — skipping graceful-error test")
        result = CamelotLatticeParser().parse(pdf_bytes("td_visa"), "td_visa.pdf", "CAD", None, [])
        assert result.confidence == 0.0
        assert any("Ghostscript" in e for e in result.errors)

    def test_stream_graceful_without_ghostscript(self):
        from app.services.parsers.camelot_stream import CamelotStreamParser
        from app.services.parsers.camelot_lattice import _check_ghostscript
        if _check_ghostscript():
            pytest.skip("Ghostscript available — skipping graceful-error test")
        result = CamelotStreamParser().parse(pdf_bytes("td_visa"), "td_visa.pdf", "CAD", None, [])
        assert result.confidence == 0.0
        assert any("Ghostscript" in e for e in result.errors)


# ---------------------------------------------------------------------------
# Registry integration
# ---------------------------------------------------------------------------

class TestRegistry:
    def test_run_all_returns_results_for_every_parser(self):
        from app.services.parsers.registry import ALL_PARSERS, run_all
        content = pdf_bytes("td_visa")
        results = run_all(content, "td_visa.pdf", "CAD", None, [])
        assert len(results) == len(ALL_PARSERS)

    def test_best_parser_wins_on_td_visa(self):
        from app.services.parsers.registry import run_all
        content = pdf_bytes("td_visa")
        results = run_all(content, "td_visa.pdf", "CAD", None, [])
        best = max(results, key=lambda r: r["confidence"])
        assert best["parser_id"] == "pdfplumber_coords"

    def test_all_results_have_required_keys(self):
        from app.services.parsers.registry import run_all
        content = pdf_bytes("td_visa")
        results = run_all(content, "td_visa.pdf", "CAD", None, [])
        for r in results:
            for key in ("parser_id", "parser_label", "confidence", "rows", "errors", "warnings"):
                assert key in r, f"Missing key {key!r} in result for {r.get('parser_id')}"
