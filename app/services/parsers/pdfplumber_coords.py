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


@dataclass(frozen=True)
class PageColumns:
    date_x: tuple[float, float]
    desc_x: tuple[float, float]
    amount_x: tuple[float, float] | None = None
    debit_x: tuple[float, float] | None = None
    credit_x: tuple[float, float] | None = None
    balance_x: tuple[float, float] | None = None


BANK_PROFILES: list[BankProfile] = [
    BankProfile(
        name="TD Visa",
        # must come before TD Chequing; generic "td.com" would match both
        detect_patterns=["TD Visa", "TD® Visa", "TD Credit Card", "TD CASH BACK", "TD Cash Back"],
        date_x=(30, 92),
        desc_x=(136, 316),
        amount_x=(316, 360),
    ),
    BankProfile(
        name="TD Chequing",
        # statement footer: "ACCOUNTISSUEDBY:THETORONTO-DOMINIONBANK" / "www.td.com"
        detect_patterns=["TD Canada Trust", "TD Bank", "TORONTO-DOMINION", "td.com"],
        # date is rightmost column (x~416), desc is leftmost (x~69)
        date_x=(408, 470),
        desc_x=(60, 225),
        debit_x=(225, 335),
        credit_x=(335, 410),
        balance_x=(470, 565),
    ),
    BankProfile(
        name="CIBC Visa",
        # must come before CIBC Chequing; "CIBC" alone would match chequing first
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
        # must come before RBC Chequing; "Royal Bank" matches both
        detect_patterns=["RBC Visa", "RBC Rewards", "RBC Avion", "Visa Platinum", "RBC Credit Card"],
        date_x=(55, 105),
        desc_x=(105, 295),
        amount_x=(295, 390),
    ),
    BankProfile(
        name="RBC Chequing",
        detect_patterns=[
            "Royal Bank of Canada",
            "RBC Royal Bank",
            "Royal Bank",
            "RBC Direct",
            "Day-to-Day Banking",
            "RBC Chequing",
            "RBCPDA",
            "Signature Plus",
        ],
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


def _norm_header_token(text: str) -> str:
    return "".join(ch.lower() for ch in text if ch.isalnum())


def _first_header_x(
    line_words: list[dict[str, Any]],
    *needles: str,
) -> float | None:
    for word in line_words:
        norm = _norm_header_token(word["text"])
        if any(needle in norm for needle in needles):
            return float(word.get("x0", 0))
    return None


def _date_header_positions(line_words: list[dict[str, Any]]) -> list[float]:
    xs: list[float] = []
    for word in line_words:
        norm = _norm_header_token(word["text"])
        if norm == "date" or norm.endswith("date"):
            xs.append(float(word.get("x0", 0)))
    return xs


def _shift_range(
    bounds: tuple[float, float] | None,
    delta: float | None,
    *,
    pad_left: float = 0.0,
    pad_right: float = 0.0,
) -> tuple[float, float] | None:
    if bounds is None or delta is None:
        return bounds
    return (
        max(0.0, bounds[0] + delta - pad_left),
        max(0.0, bounds[1] + delta + pad_right),
    )


def _find_header_columns(
    line_words: list[dict[str, Any]],
    profile: BankProfile,
) -> PageColumns | None:
    date_headers = _date_header_positions(line_words)
    if not date_headers:
        return None

    desc_x0 = _first_header_x(line_words, "description", "activitydescription", "particulars", "details")
    activity_x0 = _first_header_x(line_words, "activity")
    desc_anchor = min(
        x for x in (activity_x0, desc_x0) if x is not None
    ) if (activity_x0 is not None or desc_x0 is not None) else None

    # Always check for debit/credit/balance headers first regardless of profile format.
    # This makes unknown banks with W/D/Balance columns work without a specific profile.
    debit_x0 = _first_header_x(line_words, "withdrawal", "withdrawals", "debit")
    credit_x0 = _first_header_x(line_words, "deposit", "deposits", "credit")
    balance_x0 = _first_header_x(line_words, "balance")

    if debit_x0 is not None or credit_x0 is not None:
        # Build column ranges directly from detected header x-positions.
        # Each column spans from its header to just before the next header starts.
        anchors = sorted(
            (x, name)
            for x, name in [(debit_x0, "debit"), (credit_x0, "credit"), (balance_x0, "balance")]
            if x is not None
        )
        col_ranges: dict[str, tuple[float, float]] = {}
        for i, (x, name) in enumerate(anchors):
            end = anchors[i + 1][0] - 4.0 if i + 1 < len(anchors) else x + 90.0
            col_ranges[name] = (max(0.0, x - 8.0), end)

        desc_start = desc_anchor if desc_anchor is not None else profile.desc_x[0]
        desc_end = anchors[0][0] - 4.0 if anchors else profile.desc_x[1]
        date_shift = date_headers[0] - profile.date_x[0]
        return PageColumns(
            date_x=_shift_range(profile.date_x, date_shift, pad_left=8) or profile.date_x,
            desc_x=(desc_start, desc_end),
            debit_x=col_ranges.get("debit"),
            credit_x=col_ranges.get("credit"),
            balance_x=col_ranges.get("balance"),
        )

    if profile.amount_x is not None:
        amount_x0 = _first_header_x(line_words, "amount")
        if desc_anchor is None or amount_x0 is None:
            return None
        return PageColumns(
            date_x=_shift_range(profile.date_x, date_headers[0] - profile.date_x[0], pad_left=8) or profile.date_x,
            desc_x=_shift_range(profile.desc_x, desc_anchor - profile.desc_x[0]) or profile.desc_x,
            amount_x=_shift_range(profile.amount_x, amount_x0 - profile.amount_x[0], pad_left=8, pad_right=8),
        )

    # Profile uses debit/credit but headers weren't found above
    if not any(x is not None for x in (debit_x0, credit_x0, balance_x0)):
        return None

    return PageColumns(
        date_x=_shift_range(profile.date_x, date_headers[0] - profile.date_x[0], pad_left=8) or profile.date_x,
        desc_x=profile.desc_x,
        debit_x=_shift_range(profile.debit_x, debit_x0 - profile.debit_x[0], pad_left=6, pad_right=6) if debit_x0 is not None and profile.debit_x is not None else profile.debit_x,
        credit_x=_shift_range(profile.credit_x, credit_x0 - profile.credit_x[0], pad_left=6, pad_right=6) if credit_x0 is not None and profile.credit_x is not None else profile.credit_x,
        balance_x=_shift_range(profile.balance_x, balance_x0 - profile.balance_x[0], pad_left=6, pad_right=6) if balance_x0 is not None and profile.balance_x is not None else profile.balance_x,
    )


def _page_columns(
    lines_by_y: dict[int, list[dict[str, Any]]],
    profile: BankProfile,
    previous: PageColumns | None,
) -> PageColumns:
    for y_key in sorted(lines_by_y):
        line_words = sorted(lines_by_y[y_key], key=lambda w: w.get("x0", 0))
        inferred = _find_header_columns(line_words, profile)
        if inferred is not None:
            return inferred

    if previous is not None:
        return previous

    return PageColumns(
        date_x=profile.date_x,
        desc_x=profile.desc_x,
        amount_x=profile.amount_x,
        debit_x=profile.debit_x,
        credit_x=profile.credit_x,
        balance_x=profile.balance_x,
    )


def _parse_page_rows(
    *,
    lines_by_y: dict[int, list[dict[str, Any]]],
    columns: PageColumns,
    fallback_year: int | None,
    default_currency: str,
    filename: str,
    keyword_matcher: KeywordMatcher | None,
    page_num: int,
) -> tuple[list[dict[str, Any]], int, list[str]]:
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    skipped = 0

    for y_key in sorted(lines_by_y):
        line_words = sorted(lines_by_y[y_key], key=lambda w: w.get("x0", 0))

        date_str = _text_in_range(line_words, *columns.date_x)
        merchant = _text_in_range(line_words, *columns.desc_x)

        if not date_str or not merchant:
            continue
        if is_skip_row(merchant):
            continue

        txn_date = try_parse_date(date_str, fallback_year)
        if txn_date is None:
            continue

        if columns.amount_x:
            amount_str = _text_in_range(line_words, *columns.amount_x)
            if columns.balance_x:
                balance_str = _text_in_range(line_words, *columns.balance_x)
                if balance_str and amount_str == balance_str:
                    skipped += 1
                    continue
            amount_raw = try_parse_amount(amount_str)
            if amount_raw is None:
                skipped += 1
                errors.append(f"Page {page_num}: bad amount '{amount_str}' for '{merchant[:40]}'")
                continue
        elif columns.debit_x or columns.credit_x:
            debit_str = _text_in_range(line_words, *columns.debit_x) if columns.debit_x else ""
            credit_str = _text_in_range(line_words, *columns.credit_x) if columns.credit_x else ""
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

    return rows, skipped, errors


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
                    "Bank not recognized - coordinate extraction may be inaccurate. "
                    "Try Generic Table or Generic Text parsers for better results."
                )
                profile = BANK_PROFILES[0]

            fallback_year: int | None = None
            if profile.needs_year_inference:
                fallback_year = infer_year_from_text(header_text)
                if fallback_year:
                    warnings.append(f"Year inferred from statement header: {fallback_year}")

            default_columns = PageColumns(
                date_x=profile.date_x,
                desc_x=profile.desc_x,
                amount_x=profile.amount_x,
                debit_x=profile.debit_x,
                credit_x=profile.credit_x,
                balance_x=profile.balance_x,
            )
            page_columns: PageColumns | None = None
            for page_num, page in enumerate(pdf.pages, start=1):
                words = page.extract_words(x_tolerance=3, y_tolerance=3)
                if not words:
                    continue

                lines_by_y: dict[int, list[dict[str, Any]]] = {}
                for word in words:
                    y_key = round(word.get("top", 0) / 4) * 4
                    lines_by_y.setdefault(y_key, []).append(word)

                inferred_columns = _page_columns(lines_by_y, profile, page_columns)
                fixed_rows, fixed_skipped, fixed_errors = _parse_page_rows(
                    lines_by_y=lines_by_y,
                    columns=default_columns,
                    fallback_year=fallback_year,
                    default_currency=default_currency,
                    filename=filename,
                    keyword_matcher=keyword_matcher,
                    page_num=page_num,
                )
                inferred_rows, inferred_skipped, inferred_errors = _parse_page_rows(
                    lines_by_y=lines_by_y,
                    columns=inferred_columns,
                    fallback_year=fallback_year,
                    default_currency=default_currency,
                    filename=filename,
                    keyword_matcher=keyword_matcher,
                    page_num=page_num,
                )

                fixed_score = (len(fixed_rows), -fixed_skipped, -len(fixed_errors))
                inferred_score = (len(inferred_rows), -inferred_skipped, -len(inferred_errors))
                if inferred_score > fixed_score:
                    page_rows, page_skipped, page_errors = inferred_rows, inferred_skipped, inferred_errors
                    page_columns = inferred_columns
                else:
                    page_rows, page_skipped, page_errors = fixed_rows, fixed_skipped, fixed_errors
                    page_columns = default_columns

                rows.extend(page_rows)
                skipped += page_skipped
                errors.extend(page_errors)

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
