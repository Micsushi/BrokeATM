from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata
from typing import Any, Iterable


_SPACE_RE = re.compile(r"\s+")
_NON_WORD_RE = re.compile(r"[_\W]+", flags=re.UNICODE)


def normalize_match_text(value: str | None) -> str:
    text = unicodedata.normalize("NFKC", value or "").casefold()
    text = _NON_WORD_RE.sub(" ", text)
    text = _SPACE_RE.sub(" ", text).strip()
    return text


def normalize_keyword(value: str | None) -> str:
    return normalize_match_text(value)


def parse_keywords(value: str | None) -> list[str]:
    seen: set[str] = set()
    keywords: list[str] = []
    for raw in (value or "").split(","):
        normalized = normalize_keyword(raw)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        keywords.append(normalized)
    return keywords


def keywords_to_csv(keywords: Iterable[str]) -> str | None:
    vals = [normalize_keyword(k) for k in keywords]
    vals = [k for k in vals if k]
    deduped = list(dict.fromkeys(vals))
    return ", ".join(deduped) if deduped else None


@dataclass(frozen=True)
class KeywordRule:
    category_id: int | None
    category_name: str
    keyword: str

    @property
    def length(self) -> int:
        return len(self.keyword)


@dataclass
class _TrieNode:
    children: dict[str, "_TrieNode"]
    fail: "_TrieNode | None"
    outputs: list[KeywordRule]

    def __init__(self) -> None:
        self.children = {}
        self.fail = None
        self.outputs = []


class KeywordMatcher:
    def __init__(self, rules: Iterable[KeywordRule]) -> None:
        deduped: dict[tuple[int | None, str, str], KeywordRule] = {}
        for rule in rules:
            if not rule.keyword:
                continue
            key = (rule.category_id, rule.category_name, rule.keyword)
            deduped[key] = rule
        self.rules = sorted(
            deduped.values(),
            key=lambda r: (-r.length, r.category_name, r.keyword),
        )
        self._root = _TrieNode()
        if self.rules:
            self._build_trie()

    @classmethod
    def from_categories(cls, categories: Iterable[Any]) -> "KeywordMatcher":
        rules: list[KeywordRule] = []
        for cat in categories:
            category_id = getattr(cat, "id", None)
            category_name = str(getattr(cat, "name", "") or "").strip().lower()
            if not category_name:
                continue
            for keyword in parse_keywords(getattr(cat, "keywords", None)):
                rules.append(
                    KeywordRule(
                        category_id=category_id,
                        category_name=category_name,
                        keyword=keyword,
                    )
                )
        return cls(rules)

    def _build_trie(self) -> None:
        from collections import deque

        for rule in self.rules:
            node = self._root
            for ch in rule.keyword:
                node = node.children.setdefault(ch, _TrieNode())
            node.outputs.append(rule)

        queue: deque[_TrieNode] = deque()
        for child in self._root.children.values():
            child.fail = self._root
            queue.append(child)

        while queue:
            node = queue.popleft()
            for ch, child in node.children.items():
                fallback = node.fail
                while fallback is not None and ch not in fallback.children:
                    fallback = fallback.fail
                child.fail = fallback.children[ch] if fallback and ch in fallback.children else self._root
                if child.fail.outputs:
                    child.outputs.extend(child.fail.outputs)
                queue.append(child)

    def find_matches(self, merchant_name: str | None) -> list[KeywordRule]:
        text = normalize_match_text(merchant_name)
        if not text or not self.rules:
            return []

        node = self._root
        matched: dict[tuple[int | None, str, str], KeywordRule] = {}
        for ch in text:
            while node is not self._root and ch not in node.children:
                node = node.fail or self._root
            node = node.children.get(ch, self._root)
            for rule in node.outputs:
                matched[(rule.category_id, rule.category_name, rule.keyword)] = rule

        return sorted(matched.values(), key=lambda r: (-r.length, r.category_name, r.keyword))

    def analyze(self, merchant_name: str | None) -> dict[str, Any]:
        matches = self.find_matches(merchant_name)
        normalized_merchant = normalize_match_text(merchant_name)
        if not matches:
            return {
                "normalized_merchant": normalized_merchant,
                "keyword_matches": [],
                "keyword_resolution_needed": False,
                "keyword_conflict_categories": False,
                "suggested_category": None,
            }

        longest_len = matches[0].length
        longest = [m for m in matches if m.length == longest_len]
        suggested_category = sorted({m.category_name for m in longest})[0]
        category_count = len({m.category_name for m in matches})
        resolution_needed = category_count > 1

        return {
            "normalized_merchant": normalized_merchant,
            "keyword_matches": [
                {
                    "category_id": m.category_id,
                    "category_name": m.category_name,
                    "keyword": m.keyword,
                    "length": m.length,
                }
                for m in matches
            ],
            "keyword_resolution_needed": resolution_needed,
            "keyword_conflict_categories": resolution_needed,
            "suggested_category": suggested_category,
        }


def find_exact_keyword_conflicts(
    categories: Iterable[Any],
    candidate_keywords: Iterable[str],
    *,
    exclude_category_id: int | None = None,
) -> list[dict[str, Any]]:
    candidates = [normalize_keyword(k) for k in candidate_keywords]
    candidates = [k for k in candidates if k]
    conflicts: list[dict[str, Any]] = []
    seen: set[tuple[str, int | None, str]] = set()
    for candidate in candidates:
        for cat in categories:
            cat_id = getattr(cat, "id", None)
            if exclude_category_id is not None and cat_id == exclude_category_id:
                continue
            cat_name = str(getattr(cat, "name", "") or "")
            for existing in parse_keywords(getattr(cat, "keywords", None)):
                if existing != candidate:
                    continue
                key = (candidate, cat_id, cat_name)
                if key in seen:
                    continue
                seen.add(key)
                conflicts.append(
                    {
                        "keyword": candidate,
                        "category_id": cat_id,
                        "category_name": cat_name,
                    }
                )
    return conflicts
