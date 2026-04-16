from __future__ import annotations

from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
REPO_ROOT = Path(__file__).parent.parent

SAMPLE_PDFS: dict[str, Path] = {
    "td_visa": REPO_ROOT / "TD_CASH_BACK_VISA__CARD_4390_Feb_13-2026.pdf",
    "td_chequing": REPO_ROOT / "TD_STUDENT_CHEQUING_ACCOUNT_8255-6147767_Feb_27-Mar_31_2026.pdf",
    "cibc_visa_1": REPO_ROOT / "onlineStatement (1).pdf",
    "cibc_visa_2": REPO_ROOT / "onlineStatement (2).pdf",
    "rbc_visa": REPO_ROOT / "rbc-visa-platinum-avion-estatement.pdf",
    "rbc_chequing": REPO_ROOT / "eStatement.pdf",
}


def pdf_bytes(key: str) -> bytes:
    path = SAMPLE_PDFS[key]
    if not path.exists():
        pytest.skip(f"Sample PDF not found: {path.name}")
    return path.read_bytes()


def fixture_bytes(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def assert_valid_rows(rows: list[dict], min_rows: int = 1) -> None:
    assert len(rows) >= min_rows, f"Expected >= {min_rows} rows, got {len(rows)}"
    for row in rows:
        assert row["transaction_date"], f"Missing transaction_date: {row}"
        assert row["merchant_name"] and row["merchant_name"].strip(), f"Missing merchant: {row}"
        assert row["amount"] is not None and row["amount"] != 0, f"Bad amount: {row}"
        assert row["transaction_type"] in ("expense", "income", "transfer", "refund"), \
            f"Bad type: {row['transaction_type']}"
        assert row["currency"], f"Missing currency: {row}"
