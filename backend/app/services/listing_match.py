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


# ── Accessory-listing denylist ───────────────────────────────────────
# Some sellers list custom display cases, acrylic stands, proxies, or
# empty wrappers and put the card's full name + number in the title for
# discoverability. The listing image often shows the actual card with
# "Card Not Included" superimposed. These are legitimate sellers (the
# Dragon Slabs example had 6938 feedback / 100% positive) so the seller-
# trust filter waves them through, and the card-number filter accepts
# them because the number is in the title. We drop them by title phrase.
#
# Phrases > single words because "case" alone would catch graded slabs
# ("PSA Case 9.5") which are real cards.
_ACCESSORY_PHRASES = [
    # Display / protection accessories
    "artwork case", "art case", "display case", "acrylic case",
    "custom case", "tcg case", "extended artwork",
    "display stand", "card stand", "acrylic stand",
    "card holder", "card display", "acrylic display",
    "acrylic frame", "card frame",
    # Sleeves / binders — only multi-word forms
    "card sleeve", "card sleeves", "card binder",
    # Proxies / fan art
    "custom proxy", "proxy card", "fan art", "fanart",
    "fan made", "custom print",
    # Empties
    "empty pack", "empty wrapper", "empty booster", "empty box",
    # Explicit "not the card" tells
    "card not included", "no card included", "case only",
    "slab only",
]

# Single-word red flags — strict word-boundary match.
_ACCESSORY_WORDS = [
    "proxy", "replica",
]
_ACCESSORY_WORD_RE = re.compile(
    r"\b(" + "|".join(_ACCESSORY_WORDS) + r")\b",
    re.IGNORECASE,
)


def is_accessory_listing(title: str) -> bool:
    """True when the title looks like a case/stand/proxy/empty rather
    than the actual card. Drop these entirely rather than flagging —
    they're not the same product class."""
    if not title:
        return False
    t = title.lower()
    for phrase in _ACCESSORY_PHRASES:
        if phrase in t:
            return True
    if _ACCESSORY_WORD_RE.search(t):
        return True
    return False


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
) -> tuple[list[dict], dict[str, int]]:
    """Filter a list of eBay itemSummaries by score.

    Returns (kept, dropped_breakdown). The breakdown buckets dropped
    items by reason (different-print / no-pattern / accessory) so the
    endpoint can surface counts for debugging or a future "show hidden"
    UI.
    """
    kept: list[dict] = []
    dropped: dict[str, int] = {
        "different_print": 0,
        "no_pattern": 0,
        "accessory": 0,
    }
    for it in items:
        title = (it.get("title") or "").strip()

        # Accessory check first — it doesn't matter what the card-number
        # match says if the listing is a case/stand/proxy/empty.
        if is_accessory_listing(title):
            dropped["accessory"] += 1
            continue

        res = score_listing(title, card_number, printed_total)
        if res.score >= min_score:
            kept.append(it)
        elif res.score == 0:
            dropped["different_print"] += 1
        else:
            dropped["no_pattern"] += 1
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
    """A listing is suspicious when EITHER

    1. low-trust seller + below 40% of market (the bri_769542 scam
       pattern: 0-feedback seller at 9% of market), OR
    2. ANY seller + below 10% of market on a >$30 card — even trusted
       sellers don't legitimately sell $854 cards for $12. That's
       either an accessory we missed (Dragon Slabs cases), a price
       typo, or a Buy-It-Now decoy. Worth a warning regardless of who.

    Otherwise we don't flag: trusted sellers can list 50% below market
    for damage / clearance / fast-sale reasons without it being a scam,
    and new sellers can list at full market without being scammers.
    """
    if market_median is None or market_median <= 0:
        return False

    # Rule 2 — ultra-low ratio, trust-agnostic. Skips low-value cards
    # ($30 floor) where small absolute prices are normal.
    if market_median >= 30 and total_price < market_median * 0.10:
        return True

    # Rule 1 — bad-seller + below 40%
    if trust_tier in (TRUST_NEW, TRUST_LOW, TRUST_POOR):
        return total_price < market_median * PRICE_ANOMALY_THRESHOLD

    return False
