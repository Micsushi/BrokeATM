from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.services.keyword_matching import KeywordMatcher


@dataclass
class ParseResult:
    parser_id: str
    parser_label: str
    confidence: float
    rows: list[dict[str, Any]]
    skipped_rows: int = 0
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    unknown_pdf_categories: list[str] = field(default_factory=list)
    missing_dependency: str | None = None


class BaseParser(ABC):
    parser_id: str
    parser_label: str

    @abstractmethod
    def can_handle(self, filename: str, content: bytes) -> bool: ...

    @abstractmethod
    def parse(
        self,
        content: bytes,
        filename: str,
        default_currency: str,
        keyword_matcher: KeywordMatcher | None,
        known_categories: list[str],
    ) -> ParseResult: ...


def compute_confidence(valid_rows: int, skipped_rows: int) -> float:
    total = valid_rows + skipped_rows
    return round(valid_rows / total, 3) if total > 0 else 0.0


def is_valid_row(row: dict[str, Any]) -> bool:
    return bool(
        row.get("transaction_date")
        and str(row.get("merchant_name", "")).strip()
        and row.get("amount") is not None
        and row.get("amount") != 0
    )


def detect_unknown_categories(
    rows: list[dict[str, Any]], known_categories: list[str]
) -> list[str]:
    known = {c.lower() for c in known_categories}
    seen: set[str] = set()
    unknown: list[str] = []
    for row in rows:
        cat = (row.get("suggested_category") or "").strip()
        if cat and cat.lower() not in known and cat.lower() != "uncategorized" and cat not in seen:
            seen.add(cat)
            unknown.append(cat)
    return unknown
