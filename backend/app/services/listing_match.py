"""Score an eBay listing's title against a target card.

eBay's Browse API runs a fuzzy keyword search, so a query for
"Meowth ex 062/088" cheerfully returns the 107/088 Ultra Rare and the
121/088 Special Illustration Rare alongside the 062 base — same
Pokemon, same set, completely different cards trading at completely
different prices. Surfacing all three under one card's "Live listings"
panel breaks the foundation we want to build the wishlist price-alert
system on: an alert for "buy 062 if it drops to $5" cannot accept a
$14 hit on the 107.

`score_listing` returns one of four tiers per listing:

  100  exact card-number + set-total match — safe for alerts
   70  card-number matches but printed-total differs — usually safe
        (eBay sellers freely mix the official total with the
        secret-rare-inclusive total: "062/088" vs "062/198")
   30  no x/y pattern in the title at all — old promos and tournament
        cards often lack one; accept to avoid hiding real matches
    0  the title carries a different card number — reject

The /live-listings endpoint filters at >= 70 by default. Wishlist
alerts (when built) must require 100.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

_NUMBER_PAIR_RE = re.compile(r"(\d+)\s*/\s*(\d+)")


@dataclass(frozen=True)
class MatchResult:
    score: int
    reason: str


def _parse_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def score_listing(
    title: str,
    card_number: str | None,
    printed_total: int | None,
) -> MatchResult:
    """Tier the listing's match against the target card.

    Returns a `MatchResult(score, reason)` so callers can log *why* a
    listing got accepted or dropped — useful for tuning the threshold
    later without re-running queries.
    """
    if not title:
        return MatchResult(0, "empty title")

    target_n = _parse_int(card_number)
    if target_n is None:
        # Card has no numeric number (some old promos like "PROMO-XYZ").
        # We can't tier; let the caller fall back to the existing
        # name-keyword query result as-is.
        return MatchResult(70, "target has no numeric card_number")

    pairs = _NUMBER_PAIR_RE.findall(title)
    if not pairs:
        # No x/y in the title. Either an older card listed by name only
        # ("Charizard Holo Base Set") or a vendor-formatted title that
        # dropped the slash. Accept at the same tier as printed_total-
        # mismatch — it's not negative evidence, just absent evidence.
        return MatchResult(30, "no x/y pattern in title")

    saw_number_match = False
    for n_str, t_str in pairs:
        listing_n = _parse_int(n_str)
        listing_t = _parse_int(t_str)
        if listing_n is None:
            continue
        if listing_n == target_n:
            saw_number_match = True
            if printed_total is not None and listing_t == printed_total:
                return MatchResult(100, f"exact match {listing_n}/{listing_t}")

    if saw_number_match:
        return MatchResult(70, "card_number match, printed_total differs")

    # Pairs present, none of them matched our number — that's the
    # signal we want to catch: another print variant of the same Pokemon.
    return MatchResult(0, f"different card_number in title (target {target_n})")


def filter_listings(
    items: list[dict],
    card_number: str | None,
    printed_total: int | None,
    min_score: int = 70,
) -> tuple[list[dict], dict[int, int]]:
    """Filter a list of eBay itemSummaries by score.

    Returns (kept, dropped_breakdown). The breakdown counts per tier
    so the endpoint can include it in the response for debugging.
    """
    kept: list[dict] = []
    dropped: dict[int, int] = {0: 0, 30: 0, 70: 0, 100: 0}
    for it in items:
        title = (it.get("title") or "").strip()
        res = score_listing(title, card_number, printed_total)
        if res.score >= min_score:
            kept.append(it)
        else:
            dropped[res.score] = dropped.get(res.score, 0) + 1
    return kept, dropped
