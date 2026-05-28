from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from sqlalchemy.orm import Session

from app.models.models import Category
from app.services.keyword_matching import keywords_to_csv

STARTER_CATEGORIES_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "starter_categories.json"
)
_HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


@dataclass(frozen=True)
class StarterCategoryTemplate:
    name: str
    color: str
    keywords: tuple[str, ...] = ()

    def materialize_payload(self) -> dict[str, str | None]:
        return {
            "name": self.name,
            "color": self.color,
            "keywords": keywords_to_csv(self.keywords) or None,
        }


def _normalize_keywords(raw_keywords: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    seen: set[str] = set()
    normalized: list[str] = []
    for keyword in raw_keywords:
        kw = str(keyword or "").strip().lower()
        if not kw or kw in seen:
            continue
        seen.add(kw)
        normalized.append(kw)
    return tuple(normalized)


def _parse_template_row(raw: object, names_seen: set[str]) -> StarterCategoryTemplate:
    if not isinstance(raw, dict):
        raise ValueError("Each starter category must be an object.")

    name = str(raw.get("name") or "").strip().lower()
    color = str(raw.get("color") or "").strip()
    keywords_raw = raw.get("keywords") or []

    if not name:
        raise ValueError("Starter category is missing a name.")
    if name in names_seen:
        raise ValueError(f'Duplicate starter category name: "{name}".')
    if not _HEX_COLOR_RE.fullmatch(color):
        raise ValueError(f'Starter category "{name}" has invalid color "{color}".')
    if not isinstance(keywords_raw, list):
        raise ValueError(f'Starter category "{name}" must use a keyword list.')

    names_seen.add(name)
    return StarterCategoryTemplate(
        name=name,
        color=color,
        keywords=_normalize_keywords(keywords_raw),
    )


@lru_cache(maxsize=1)
def load_starter_category_templates() -> tuple[StarterCategoryTemplate, ...]:
    raw = json.loads(STARTER_CATEGORIES_PATH.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("Starter categories file must contain a JSON array.")

    names_seen: set[str] = set()
    templates = tuple(_parse_template_row(row, names_seen) for row in raw)
    if not templates:
        raise ValueError("Starter categories file cannot be empty.")
    return templates


def build_starter_category_payloads() -> list[dict[str, str | None]]:
    return [template.materialize_payload() for template in load_starter_category_templates()]


def starter_category_seed_tuples() -> list[tuple[str, str, str]]:
    return [
        (template.name, template.color, ",".join(template.keywords))
        for template in load_starter_category_templates()
    ]


def seed_starter_categories(db: Session, user_id: str | None = None) -> None:
    """Populate live categories from the starter templates if the table is empty."""
    q = db.query(Category.id)
    if user_id is None:
        q = q.filter(Category.user_id.is_(None))
    else:
        q = q.filter(Category.user_id == user_id)
    if q.limit(1).first() is not None:
        return

    for payload in build_starter_category_payloads():
        db.add(Category(**payload, user_id=user_id))
    db.commit()
