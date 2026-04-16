from __future__ import annotations

import pytest
from datetime import date

from app.services.parsers._pdf_utils import (
    infer_year_from_text,
    is_skip_row,
    try_parse_amount,
    try_parse_date,
)


class TestTryParseDate:
    def test_iso(self):
        assert try_parse_date("2023-06-15") == date(2023, 6, 15)

    def test_slash_mdy(self):
        assert try_parse_date("06/15/2023") == date(2023, 6, 15)

    def test_slash_md_fallback_year(self):
        assert try_parse_date("06/15", fallback_year=2023) == date(2023, 6, 15)

    def test_month_day_year(self):
        assert try_parse_date("Jun 15 2023") == date(2023, 6, 15)

    def test_month_day_no_year(self):
        assert try_parse_date("Jun 15", fallback_year=2023) == date(2023, 6, 15)

    def test_day_month(self):
        assert try_parse_date("15 Mar", fallback_year=2023) == date(2023, 3, 15)

    def test_day_dash_month(self):
        assert try_parse_date("10-Jul", fallback_year=2023) == date(2023, 7, 10)

    def test_compact_month_day(self):
        assert try_parse_date("FEB27", fallback_year=2023) == date(2023, 2, 27)

    def test_strips_newline(self):
        assert try_parse_date("Jun 15\nextra", fallback_year=2023) == date(2023, 6, 15)

    def test_empty_returns_none(self):
        assert try_parse_date("") is None

    def test_garbage_returns_none(self):
        assert try_parse_date("NOT A DATE") is None

    def test_1900_year_replaced_by_fallback(self):
        d = try_parse_date("Jun 15", fallback_year=2024)
        assert d is not None and d.year == 2024


class TestTryParseAmount:
    def test_plain_float(self):
        assert try_parse_amount("45.67") == 45.67

    def test_comma_thousands(self):
        assert try_parse_amount("1,234.56") == 1234.56

    def test_dollar_sign(self):
        assert try_parse_amount("$99.00") == 99.0

    def test_negative(self):
        assert try_parse_amount("-50.00") == -50.0

    def test_parentheses_negative(self):
        assert try_parse_amount("(120.00)") == -120.0

    def test_empty_returns_none(self):
        assert try_parse_amount("") is None

    def test_text_returns_none(self):
        assert try_parse_amount("N/A") is None

    def test_spaces_stripped(self):
        assert try_parse_amount(" 10.00 ") == 10.0


class TestIsSkipRow:
    @pytest.mark.parametrize("text", [
        "Opening Balance",
        "Closing Balance",
        "Balance Forward",
        "Previous Balance",
        "New Balance",
        "Starting Balance",
        "Total",
        "Subtotal",
        "Minimum Payment",
        "Credit Limit",
        "Available Credit",
        "Statement Date",
        "Payment Due",
        "Brought Forward",
        "STARTINGBALANCE",
        "opening balance",
    ])
    def test_skip_rows(self, text: str):
        assert is_skip_row(text), f"Expected {text!r} to be skipped"

    @pytest.mark.parametrize("text", [
        "Tim Hortons",
        "PAYMENT THANK YOU",
        "Netflix subscription",
        "Superstore #1234",
    ])
    def test_keep_rows(self, text: str):
        assert not is_skip_row(text), f"Expected {text!r} to NOT be skipped"


class TestInferYear:
    def test_finds_year_in_text(self):
        assert infer_year_from_text("Statement for 2023") == 2023

    def test_picks_first_year(self):
        assert infer_year_from_text("From 2022 to 2023") == 2022

    def test_fallback_to_today(self):
        import datetime
        result = infer_year_from_text("no year here")
        assert result == datetime.date.today().year
