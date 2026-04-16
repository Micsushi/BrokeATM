from __future__ import annotations

from tests.conftest import assert_valid_rows, fixture_bytes

from app.services.parsers.csv_wrapper import CsvWrapperParser


def make_parser():
    return CsvWrapperParser()


def test_can_handle_csv():
    p = make_parser()
    assert p.can_handle("statement.csv", b"")
    assert not p.can_handle("statement.pdf", b"")
    assert not p.can_handle("statement.ofx", b"")


def test_parses_sample_csv():
    p = make_parser()
    content = fixture_bytes("sample.csv")
    result = p.parse(content, "sample.csv", "CAD", None, [])

    assert result.confidence > 0
    assert len(result.rows) == 5
    assert_valid_rows(result.rows, min_rows=5)


def test_expense_row():
    p = make_parser()
    content = fixture_bytes("sample.csv")
    result = p.parse(content, "sample.csv", "CAD", None, [])

    tim = next(r for r in result.rows if "Tim Hortons" in r["merchant_name"])
    assert tim["transaction_date"] == "2023-06-05"
    assert tim["amount"] == 45.67
    assert tim["transaction_type"] == "expense"
    assert tim["currency"] == "CAD"


def test_credit_row_positive_amount():
    p = make_parser()
    content = fixture_bytes("sample.csv")
    result = p.parse(content, "sample.csv", "CAD", None, [])

    payroll = next(r for r in result.rows if "PAYROLL" in r["merchant_name"])
    assert payroll["amount"] > 0


def test_transfer_row():
    p = make_parser()
    content = fixture_bytes("sample.csv")
    result = p.parse(content, "sample.csv", "CAD", None, [])

    payment = next(r for r in result.rows if "PAYMENT" in r["merchant_name"])
    assert payment["is_payment"] is True


def test_source_file_recorded():
    p = make_parser()
    content = fixture_bytes("sample.csv")
    result = p.parse(content, "sample.csv", "CAD", None, [])

    assert all(r["source_file"] == "sample.csv" for r in result.rows)


def test_empty_csv_returns_no_rows():
    p = make_parser()
    result = p.parse(b"col1,col2\n", "empty.csv", "CAD", None, [])
    assert result.rows == [] or result.confidence == 0.0


def test_malformed_csv_does_not_crash():
    p = make_parser()
    result = p.parse(b"not,a,real,csv\nbad data here\n", "bad.csv", "CAD", None, [])
    assert isinstance(result.rows, list)
