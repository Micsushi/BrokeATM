from __future__ import annotations

from app.services.keyword_matching import normalize_keyword, normalize_match_text
from app.services.starter_categories import starter_category_seed_tuples

MCC_TO_CATEGORY: dict[str, str] = {
    "eating places and restaurants": "dining",
    "quick payment service-fast food restaurants": "fast food",
    "miscellaneous food stores-convenience stores and specialty markets": "convenience store",
    "grocery stores and supermarkets": "groceries",
    "wholesale club with or without membership fee": "wholesale / costco",
    "taxicabs and limousines": "transportation",
    "cable satellite and other pay television and radio services": "cable / internet",
    "telecommunication services including local and long distance calls credit card calls"
    " call through use of magnetic-strip-reading telephones and fax services": "phone",
    "utilities-electric gas water and sanitary": "utilities",
    "business services": "business services",
    "computer network/information services and other online services such as electronic"
    " bulletin board e-mail web site hosting services or internet access": "online shopping",
    "computer software stores": "software",
    "digital goods \u2013 games": "gaming",
    "digital goods \u2013 media books movies music": "media / streaming",
    "large digital goods merchant": "digital goods",
    "continuity/subscription merchants": "subscriptions",
    "colleges universities professional schools and junior colleges": "education",
    "continuity/subscription": "subscriptions",
}

PAYMENT_KEYWORDS = ["payment thank you", "payment - thank you", "remboursement"]
CASHBACK_KEYWORDS = ["cash back", "cash back / remises", "rebate"]

# Starter categories now live in app/data/starter_categories.json.
# This alias stays here for backward compatibility and easy discovery.
DEFAULT_CATEGORIES: list[tuple[str, str, str]] = starter_category_seed_tuples()


def mcc_to_category(mcc_description: str) -> str:
    if not mcc_description:
        return "uncategorized"
    key = mcc_description.strip().lower()
    return MCC_TO_CATEGORY.get(key, key)


def match_by_keywords(merchant_name: str, keyword_map: dict[str, list[str]]) -> str | None:
    name_lower = normalize_match_text(merchant_name)
    best: tuple[int, str] | None = None
    for cat_name, keywords in keyword_map.items():
        for kw in keywords:
            normalized = normalize_keyword(kw)
            if not normalized or normalized not in name_lower:
                continue
            candidate = (len(normalized), cat_name)
            if best is None or candidate[0] > best[0] or (
                candidate[0] == best[0] and candidate[1] < best[1]
            ):
                best = candidate
    return best[1] if best else None


def is_payment(merchant_name: str, mcc_description: str) -> bool:
    combined = f"{merchant_name} {mcc_description}".lower()
    return any(kw in combined for kw in PAYMENT_KEYWORDS)


def is_cashback(merchant_name: str, mcc_description: str) -> bool:
    combined = f"{merchant_name} {mcc_description}".lower()
    return any(kw in combined for kw in CASHBACK_KEYWORDS)
