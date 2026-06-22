"""Map a NewsItem to one of the PullList categories using simple
keyword heuristics. Claude-driven classification for ambiguous cases
is deferred to Phase 2 — keyword coverage is decent for the curated
Phase 1 sources, and a wrong category is recoverable (LO edits it
before publishing the draft).
"""
from __future__ import annotations

from .sources import NewsItem

# Order matters — first match wins. Keep more-specific categories
# above more-generic ones so e.g. "Pokémon Center exclusive" doesn't
# get caught by the broader "exclusive" / drops bucket later.
RULES: list[tuple[str, list[str]]] = [
    ("center", ["pokémon center", "pokemon center", "pokecen", "in-store"]),
    (
        "drops",
        [
            "release",
            "releases",
            "released",
            "pre-order",
            "preorder",
            "drops",
            "available",
            "launches",
            "launch",
            "restock",
        ],
    ),
    (
        "market",
        [
            "price",
            "prices",
            "trending",
            "value",
            "market",
            "spike",
            "spiked",
            "crash",
            "tanked",
            "$",
        ],
    ),
    (
        "tcg",
        [
            "set",
            "deck",
            "tournament",
            "worlds",
            "regionals",
            "meta",
            "format",
            "ban",
            "rotation",
        ],
    ),
    (
        "guide",
        ["how to", "guide", "tips", "best ", "tier list", "beginners"],
    ),
]


def classify(item: NewsItem) -> str:
    """Returns one of: drops | market | tcg | center | guide | news.

    Default category is 'news' — generic announcements that don't
    match any keyword bucket fall there.
    """
    haystack = " ".join((item.title, item.summary, item.raw_text[:2000])).lower()
    # Cheap word-boundary check via substring + word edge — exact regex
    # per keyword would be sounder but for ~30 rules this is fine.
    for category, keywords in RULES:
        for kw in keywords:
            if kw in haystack:
                return category
    return "news"


def slugify(title: str, max_len: int = 80) -> str:
    """Kebab-case slug, same shape the admin UI builds in PostForm.tsx.

    Keeps unicode letters/numbers; collapses everything else to '-'.
    Truncated to fit the news_posts.slug column (128 chars; we cap at
    80 to leave room for any future suffix collisions). Stdlib `re`
    doesn't support `\\p{L}`, so we filter char-by-char on str.isalnum
    which is unicode-aware in Python 3.
    """
    out_chars = []
    prev_dash = False
    for ch in title.lower():
        if ch.isalnum():
            out_chars.append(ch)
            prev_dash = False
        elif not prev_dash:
            out_chars.append("-")
            prev_dash = True
    slug = "".join(out_chars).strip("-")
    return slug[:max_len] or "untitled"
