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


# ── Seller trust + price anomaly ─────────────────────────────────────
# These two signals are weak alone but devastating together. A brand-
# new (0 feedback) seller listing a $900 card for $74 is the canonical
# scam pattern: stolen photo, fake card on delivery, or take-the-money-
# and-run. We flag rather than drop — users sometimes do want to see
# the noise floor, but the panel sorts safe listings to the top and
# the "Cheapest" badge skips suspicious tiles.

# Trust tiers, ordered worst → best
TRUST_NEW = "new"        # feedback score 0
TRUST_LOW = "low"        # score 1-9
TRUST_POOR = "poor"      # score >= 10 but feedback% < 95
TRUST_OK = "ok"          # score 10-99, feedback% >= 95
TRUST_TRUSTED = "trusted"  # score >= 100, feedback% >= 99

# Price-anomaly cutoff: listing total below this fraction of the
# card's market median is suspicious *when paired* with a weak seller.
# 0.40 catches the obvious 9%-of-market scams while sparing legitimate
# undercutters (sellers who price 15-25% below median to move stock).
PRICE_ANOMALY_THRESHOLD = 0.40


def seller_trust_tier(feedback_score: int | None, feedback_pct: float | None) -> str:
    score = feedback_score if feedback_score is not None else -1
    pct = feedback_pct if feedback_pct is not None else 0.0
    if score == 0:
        return TRUST_NEW
    if 0 < score < 10:
        return TRUST_LOW
    if pct < 95:
        return TRUST_POOR
    if score >= 100 and pct >= 99:
        return TRUST_TRUSTED
    return TRUST_OK


def is_suspicious(
    total_price: float,
    market_median: float | None,
    trust_tier: str,
) -> bool:
    """A listing is suspicious when *both* the seller is new/low-trust
    AND the price is anomalously below the market.

    Either signal alone is fine: trusted sellers can list low for a
    legit reason (damage, want to move stock, no time to research),
    and new sellers can list at full market without being scammers.
    The combination is what flags the pattern from the screenshot —
    bri_769542 (0) at $74.52 on a $900 card."""
    if trust_tier not in (TRUST_NEW, TRUST_LOW, TRUST_POOR):
        return False
    if market_median is None or market_median <= 0:
        return False
    return total_price < market_median * PRICE_ANOMALY_THRESHOLD
