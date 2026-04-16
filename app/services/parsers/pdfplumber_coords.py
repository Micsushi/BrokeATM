from __future__ import annotations

import io
from dataclasses import dataclass
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

if TYPE_CHECKING:
    from app.services.keyword_matching import KeywordMatcher


@dataclass
class BankProfile:
    name: str
    detect_patterns: list[str]
    date_x: tuple[float, float]
    desc_x: tuple[float, float]
    amount_x: tuple[float, float] | None = None
    debit_x: tuple[float, float] | None = None
    credit_x: tuple[float, float] | None = None
    balance_x: tuple[float, float] | None = None
    needs_year_inference: bool = True


BANK_PROFILES: list[BankProfile] = [
    BankProfile(
        name="TD Visa",
        # must come before TD Chequing — generic "td.com" pattern would match both
        detect_patterns=["TD Visa", "TD® Visa", "TD Credit Card", "TD CASH BACK", "TD Cash Back"],
        date_x=(30, 92),
        desc_x=(136, 316),
        amount_x=(316, 360),
    ),
    BankProfile(
        name="TD Chequing",
        # statement footer: "ACCOUNTISSUEDBY:THETORONTO-DOMINIONBANK" / "www.td.com"
        detect_patterns=["TD Canada Trust", "TD Bank", "Personal Chequing", "TORONTO-DOMINION", "td.com"],
        # date is rightmost column (x~416), desc is leftmost (x~69)
        date_x=(408, 470),
        desc_x=(60, 225),
        debit_x=(225, 335),
        credit_x=(335, 410),
        balance_x=(470, 565),
    ),
    BankProfile(
        name="CIBC Visa",
        # must come before CIBC Chequing — "CIBC" alone would match chequing profile first
        detect_patterns=["CIBC Visa", "CIBC Credit Card", "CIBC Dividend"],
        # transactions on page 2: trans date x=37-50, post date x=79-92 (excluded), desc x=119+, amount x=516
        date_x=(30, 72),
        desc_x=(115, 495),
        amount_x=(495, 560),
    ),
    BankProfile(
        name="CIBC Chequing",
        detect_patterns=["CIBC", "Canadian Imperial Bank", "Personal Banking", "Chequing Account"],
        date_x=(28, 88),
        desc_x=(88, 380),
        debit_x=(380, 455),
        credit_x=(455, 530),
        balance_x=(530, 610),
    ),
    BankProfile(
        name="EQ Bank",
        detect_patterns=["EQ Bank", "Equitable Bank", "EQ Personal", "eqbank"],
        # date x=42-55 ("Jan 9"), desc x=113+, withdrawals x=361, deposits x=448, balance x=522
        date_x=(35, 105),
        desc_x=(105, 350),
        debit_x=(350, 440),
        credit_x=(440, 515),
        balance_x=(515, 570),
    ),
    BankProfile(
        name="RBC Visa",
        # must come before RBC Chequing — "Royal Bank" matches both
        detect_patterns=["RBC Visa", "RBC Rewards", "RBC Avion", "Visa Platinum", "RBC Credit Card"],
        date_x=(55, 105),
        desc_x=(105, 295),
        amount_x=(295, 390),
    ),
    BankProfile(
        name="RBC Chequing",
        detect_patterns=["Royal Bank", "RBC Royal Bank", "RBC Direct", "Day-to-Day Banking", "RBC Chequing"],
        date_x=(28, 72),
        desc_x=(72, 310),
        debit_x=(310, 405),
        credit_x=(405, 520),
        balance_x=(520, 600),
    ),
    BankProfile(
        name="BMO",
        detect_patterns=["Bank of Montreal", "BMO Bank", "BMO Financial"],
        date_x=(28, 90),
        desc_x=(90, 390),
        debit_x=(390, 460),
        credit_x=(460, 535),
        balance_x=(535, 615),
    ),
    BankProfile(
        name="Scotiabank",
        detect_patterns=["Scotiabank", "Bank of Nova Scotia", "Scotia"],
        date_x=(28, 90),
        desc_x=(90, 380),
        debit_x=(380, 455),
        credit_x=(455, 530),
        balance_x=(530, 610),
    ),
]


def _detect_bank(text: str) -> BankProfile | None:
    text_upper = text.upper()
    for profile in BANK_PROFILES:
        if any(p.upper() in text_upper for p in profile.detect_patterns):
            return profile
    return None


def _words_in_range(words: list[dict[str, Any]], x0: float, x1: float) -> list[dict[str, Any]]:
    return [w for w in words if x0 <= w.get("x0", 0) <= x1]


def _text_in_range(words: list[dict[str, Any]], x0: float, x1: float) -> str:
    return " ".join(w["text"] for w in _words_in_range(words, x0, x1)).strip()


class PdfplumberCoordsParser(BaseParser):
    parser_id = "pdfplumber_coords"
    parser_label = "Bank-Specific"

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
            return self._parse_inner(content, filename, default_currency, keyword_matcher, known_categories)
        except Exception as exc:
            return ParseResult(
                parser_id=self.parser_id,
                parser_label=self.parser_label,
                confidence=0.0,
                rows=[],
                errors=[f"Coordinate extraction failed: {exc}"],
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

        rows: list[dict[str, Any]] = []
        errors: list[str] = []
        skipped = 0
        warnings: list[str] = []

        with pdfplumber.open(io.BytesIO(content)) as pdf:
            header_text = ""
            for page in pdf.pages[:2]:
                header_text += (page.extract_text() or "") + "\n"

            profile = _detect_bank(header_text)
            if profile is None:
                warnings.append(
                    "Bank not recognized — coordinate extraction may be inaccurate. "
                    "Try Generic Table or Generic Text parsers for better results."
                )
                profile = BANK_PROFILES[0]

            fallback_year: int | None = None
            if profile.needs_year_inference:
                fallback_year = infer_year_from_text(header_text)
                if fallback_year:
                    warnings.append(f"Year inferred from statement header: {fallback_year}")

            for page_num, page in enumerate(pdf.pages, start=1):
                words = page.extract_words(x_tolerance=3, y_tolerance=3)
                if not words:
                    continue

                lines_by_y: dict[int, list[dict[str, Any]]] = {}
                for word in words:
                    y_key = round(word.get("top", 0) / 4) * 4
                    lines_by_y.setdefault(y_key, []).append(word)

                for y_key in sorted(lines_by_y):
                    line_words = sorted(lines_by_y[y_key], key=lambda w: w.get("x0", 0))

                    date_str = _text_in_range(line_words, *profile.date_x)
                    merchant = _text_in_range(line_words, *profile.desc_x)

                    if not date_str or not merchant:
                        continue
                    if is_skip_row(merchant):
                        continue

                    txn_date = try_parse_date(date_str, fallback_year)
                    if txn_date is None:
                        continue

                    if profile.amount_x:
                        amount_str = _text_in_range(line_words, *profile.amount_x)
                        if profile.balance_x:
                            balance_str = _text_in_range(line_words, *profile.balance_x)
                            if balance_str and amount_str == balance_str:
                                skipped += 1
                                continue
                        amount_raw = try_parse_amount(amount_str)
                        if amount_raw is None:
                            skipped += 1
                            errors.append(
                                f"Page {page_num}: bad amount '{amount_str}' for '{merchant[:40]}'"
                            )
                            continue
                    elif profile.debit_x or profile.credit_x:
                        debit_str = _text_in_range(line_words, *profile.debit_x) if profile.debit_x else ""
                        credit_str = _text_in_range(line_words, *profile.credit_x) if profile.credit_x else ""
                        debit = try_parse_amount(debit_str) or 0.0
                        credit = try_parse_amount(credit_str) or 0.0
                        if debit == 0.0 and credit == 0.0:
                            skipped += 1
                            continue
                        amount_raw = debit if debit else -credit
                    else:
                        skipped += 1
                        continue

                    row = build_row(txn_date, merchant, amount_raw, default_currency, filename, keyword_matcher)
                    rows.append(row)

        valid = sum(1 for r in rows if is_valid_row(r))
        confidence = compute_confidence(valid, skipped)
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
