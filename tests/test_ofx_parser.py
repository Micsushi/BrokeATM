from __future__ import annotations

from tests.conftest import assert_valid_rows, fixture_bytes

from app.services.parsers.ofx_parser import OfxParser


def make_parser():
    return OfxParser()


def test_can_handle_ofx():
    p = make_parser()
    assert p.can_handle("statement.ofx", b"")
    assert p.can_handle("statement.qfx", b"")
    assert not p.can_handle("statement.pdf", b"")
    assert not p.can_handle("statement.csv", b"")


def test_parses_sample_ofx():
    p = make_parser()
    content = fixture_bytes("sample.ofx")
    result = p.parse(content, "sample.ofx", "CAD", None, [])

    assert result.confidence > 0
    assert len(result.rows) == 4
    assert_valid_rows(result.rows, min_rows=4)


def test_expense_row():
    p = make_parser()
    content = fixture_bytes("sample.ofx")
    result = p.parse(content, "sample.ofx", "CAD", None, [])

    tim = next(r for r in result.rows if "Tim Hortons" in r["merchant_name"])
    assert tim["transaction_date"] == "2023-06-05"
    assert tim["amount"] == 45.67
    assert tim["transaction_type"] == "expense"


def test_income_row():
    p = make_parser()
    content = fixture_bytes("sample.ofx")
    result = p.parse(content, "sample.ofx", "CAD", None, [])

    payroll = next(r for r in result.rows if "PAYROLL" in r["merchant_name"])
    assert payroll["transaction_type"] == "income"
    assert payroll["amount"] > 0


def test_transfer_row():
    p = make_parser()
    content = fixture_bytes("sample.ofx")
    result = p.parse(content, "sample.ofx", "CAD", None, [])

    payment = next(r for r in result.rows if "CREDIT CARD PAYMENT" in r["merchant_name"])
    assert payment["is_payment"] is True


def test_currency_from_statement():
    p = make_parser()
    content = fixture_bytes("sample.ofx")
    result = p.parse(content, "sample.ofx", "CAD", None, [])

    assert all(r["currency"] == "CAD" for r in result.rows)


def test_reference_number_populated():
    p = make_parser()
    content = fixture_bytes("sample.ofx")
    result = p.parse(content, "sample.ofx", "CAD", None, [])

    assert any(r["reference_number"] for r in result.rows)


def test_high_confidence_on_clean_file():
    p = make_parser()
    content = fixture_bytes("sample.ofx")
    result = p.parse(content, "sample.ofx", "CAD", None, [])
    assert result.confidence >= 0.9


def test_corrupt_ofx_does_not_crash():
    p = make_parser()
    result = p.parse(b"THIS IS NOT OFX DATA", "bad.ofx", "CAD", None, [])
    assert result.confidence == 0.0
    assert len(result.errors) > 0
