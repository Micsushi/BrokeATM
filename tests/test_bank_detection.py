from app.services.parsers.pdfplumber_coords import _detect_bank


def test_detect_bank_prefers_rbc_chequing_for_rbc_statement_header():
    header = """
    Royal Bank of Canada Your personal chequing
    From March 12, 2004 to April 12, 2004
    RBCPDA0001-123456789-01-000001-1-0001
    Signature Plus 02782-5094431
    not already an RBC Royal Bank Online Banking
    """

    profile = _detect_bank(header)

    assert profile is not None
    assert profile.name == "RBC Chequing"


def test_detect_bank_keeps_td_visa_when_td_footer_text_is_present():
    header = """
    TD CASH BACK CARD
    STATEMENT DATE: February 13, 2026
    Chat with us on EasyWeb EasyWeb.td.com
    ACCOUNT ISSUED BY: THE TORONTO-DOMINION BANK
    """

    profile = _detect_bank(header)

    assert profile is not None
    assert profile.name == "TD Visa"
