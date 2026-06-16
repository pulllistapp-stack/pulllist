"""Unit tests for the eBay client filter stack.

Pin down the behavior we've spent several rounds tweaking so future filter
adjustments can't silently regress the Meowth ex / Mega Charizard X cases.

Layout:
  - Pure-function tests for build_card_query, _classify_listing, _compute_aggregate
  - Integration tests for price_summary_with_trace using a stub browse_search

Run:
    cd backend && pytest
    cd backend && pytest -q                # quiet
    cd backend && pytest -k chase          # filter by name
"""
from __future__ import annotations

import asyncio
import re

from app.services.ebay_client import (
    EbayClient,
    FilterConfig,
    _CHASE_RARITIES,
    _RARITY_ABS_FLOOR,
    _classify_listing,
    _compute_aggregate,
    build_card_query,
)


# ────────────────────────────── build_card_query ─────────────────────────────


def test_build_card_query_basic():
    q = build_card_query(card_name="Charizard")
    assert q == "pokemon Charizard"


def test_build_card_query_with_number_and_total():
    q = build_card_query(card_name="Charizard", card_number="4", printed_total=102)
    assert q == "pokemon Charizard 4/102"


def test_build_card_query_number_already_has_slash():
    q = build_card_query(card_name="Mega Charizard X ex", card_number="125/94", printed_total=94)
    assert q == "pokemon Mega Charizard X ex 125/94"


def test_build_card_query_with_set_name():
    q = build_card_query(card_name="Meowth ex", card_number="121", printed_total=68, set_name="Perfect Order")
    assert q == "pokemon Meowth ex 121/68 Perfect Order"


def test_build_card_query_rarity_is_ignored():
    """We deliberately stopped appending rarity hints (eBay was over-filtering)."""
    q_with = build_card_query(card_name="Meowth ex", rarity="Special Illustration Rare")
    q_without = build_card_query(card_name="Meowth ex")
    assert q_with == q_without


# ────────────────────────────── _classify_listing ────────────────────────────


def _make_item(title: str, value: float | str | None = 10.0, currency: str = "USD") -> dict:
    item: dict = {"title": title, "itemWebUrl": "https://example.com/x"}
    if value is None:
        item["price"] = {"currency": currency}
    else:
        item["price"] = {"value": value, "currency": currency}
    return item


def test_classify_clean_listing_kept():
    cfg = FilterConfig()
    r = _classify_listing(_make_item("Pokemon Charizard 4/102 Base Set"), cfg)
    assert r.kept is True
    assert r.drop_reason is None
    assert r.price_usd == 10.0


def test_classify_title_noise_graded():
    cfg = FilterConfig()
    r = _classify_listing(_make_item("Charizard PSA 10 Gem Mint"), cfg)
    assert r.kept is False
    assert r.drop_reason is not None and r.drop_reason.startswith("title_noise:")
    assert "psa 10" in r.drop_reason


def test_classify_title_noise_sealed_booster():
    cfg = FilterConfig()
    r = _classify_listing(_make_item("Perfect Order Booster Box Sealed"), cfg)
    assert r.kept is False
    assert r.drop_reason is not None and "booster box" in r.drop_reason


def test_classify_wrong_currency():
    cfg = FilterConfig()
    r = _classify_listing(_make_item("Charizard 4/102", value=10.0, currency="GBP"), cfg)
    assert r.kept is False
    assert r.drop_reason == "wrong_currency:GBP"


def test_classify_no_price():
    cfg = FilterConfig()
    r = _classify_listing(_make_item("Charizard 4/102", value=None), cfg)
    assert r.kept is False
    assert r.drop_reason == "no_price"


def test_classify_below_floor():
    cfg = FilterConfig(sanity_floor=5.0)
    r = _classify_listing(_make_item("Meowth 121/068", value=2.50), cfg)
    assert r.kept is False
    assert r.drop_reason == "below_floor:5.00"


def test_classify_above_ceiling():
    cfg = FilterConfig(sanity_ceiling=1000.0)
    r = _classify_listing(_make_item("Charizard 4/102", value=2500.0), cfg)
    assert r.kept is False
    assert r.drop_reason == "above_ceiling:1000.00"


def test_classify_number_required_present():
    cfg = FilterConfig(number_pattern=re.compile(r"\b121\b"))
    r = _classify_listing(_make_item("Meowth ex 121/068 SIR"), cfg)
    assert r.kept is True


def test_classify_number_required_missing():
    cfg = FilterConfig(number_pattern=re.compile(r"\b121\b"))
    r = _classify_listing(_make_item("Meowth ex Double Rare 60/86"), cfg)
    assert r.kept is False
    assert r.drop_reason is not None and r.drop_reason.startswith("missing_number:")


def test_classify_number_word_boundary_rejects_substring_false_positive():
    """The whole point of the regex switch: '121' should NOT match 'set121cards'
    or '121g' (grams in a sealed-product title)."""
    cfg = FilterConfig(number_pattern=re.compile(r"\b121\b"))
    r = _classify_listing(_make_item("Pokemon mystery box 121g card lot"), cfg)
    # Substring "121" appears in "121g" but \b121\b does not match (boundary
    # blocked by the trailing word char 'g').
    assert r.kept is False
    assert r.drop_reason is not None and r.drop_reason.startswith("missing_number:")


def test_classify_floor_priority_over_ceiling():
    """Floor and ceiling can both be set; floor wins when price below floor."""
    cfg = FilterConfig(sanity_floor=10.0, sanity_ceiling=100.0)
    r = _classify_listing(_make_item("Charizard 4/102", value=5.0), cfg)
    assert r.kept is False
    assert "below_floor" in (r.drop_reason or "")


# ────────────────────────────── _compute_aggregate ───────────────────────────


def test_aggregate_odd_count():
    r = _compute_aggregate([1.0, 2.0, 3.0, 4.0, 5.0])
    assert r["low"] == 1.0
    assert r["median"] == 3.0
    assert r["high"] == 5.0
    assert r["count_sampled"] == 5


def test_aggregate_even_count():
    r = _compute_aggregate([1.0, 2.0, 3.0, 4.0])
    assert r["median"] == 2.5  # (2+3)/2
    assert r["count_sampled"] == 4


def test_aggregate_n_under_8_no_trim():
    r = _compute_aggregate([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0])
    assert r["low"] == 1.0
    assert r["high"] == 7.0
    assert r["count_sampled"] == 7


def test_aggregate_n_8_trims_one_each_end():
    # Sorted: [1,2,3,4,5,6,7,100]. n=8 -> trim n//8 = 1 from each end.
    # Core becomes [2,3,4,5,6,7], median = 4.5, low=2, high=7.
    r = _compute_aggregate([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 100.0])
    assert r["count_sampled"] == 6
    assert r["low"] == 2.0
    assert r["high"] == 7.0
    assert r["median"] == 4.5


def test_aggregate_n_16_trims_two_each_end():
    prices = [float(i) for i in range(1, 17)]  # 1..16
    r = _compute_aggregate(prices)
    assert r["count_sampled"] == 12  # 16 - 2*2
    assert r["low"] == 3.0
    assert r["high"] == 14.0


def test_aggregate_handles_unsorted_input():
    r = _compute_aggregate([5.0, 1.0, 3.0])
    assert r["low"] == 1.0
    assert r["high"] == 5.0
    assert r["median"] == 3.0


# ────────────────────── price_summary_with_trace (E2E) ───────────────────────


class _StubEbay(EbayClient):
    """EbayClient subclass that returns canned browse_search responses.

    We don't call EbayClient.__init__ (which expects credentials and an
    httpx client) — the only method our tests need is browse_search, which
    we override completely.
    """

    def __init__(self, responses: list[dict]):
        # Skip super().__init__ — we don't need credentials or httpx for these tests.
        self._responses = responses
        self._call_log: list[dict] = []

    async def browse_search(self, query: str, **kwargs) -> dict:  # type: ignore[override]
        idx = len(self._call_log)
        self._call_log.append({"query": query, **kwargs})
        if idx >= len(self._responses):
            return {"itemSummaries": [], "total": 0}
        return self._responses[idx]


def _items(*titles_and_prices: tuple[str, float]) -> list[dict]:
    return [
        {
            "title": t,
            "price": {"value": p, "currency": "USD"},
            "itemWebUrl": f"https://example.com/{i}",
        }
        for i, (t, p) in enumerate(titles_and_prices)
    ]


def test_price_summary_clean_listings_returns_aggregate():
    items = _items(
        ("Charizard 4/102 NM", 90.0),
        ("Charizard 4/102 LP", 80.0),
        ("Charizard 4/102 MP", 70.0),
        ("Charizard 4/102 Played", 60.0),
        ("Charizard 4/102 Heavy", 50.0),
    )
    ebay = _StubEbay([{"itemSummaries": items, "total": 5}])

    detail = asyncio.run(
        ebay.price_summary_with_trace("pokemon Charizard 4/102 Base Set")
    )

    s = detail["summary"]
    assert s is not None
    assert s["count_sampled"] == 5
    assert s["median"] == 70.0
    assert s["low"] == 50.0
    assert s["high"] == 90.0


def test_price_summary_all_noise_returns_none():
    items = _items(
        ("Charizard PSA 10", 1000.0),
        ("Charizard PSA 9", 500.0),
        ("Charizard booster box sealed", 200.0),
    )
    ebay = _StubEbay([{"itemSummaries": items, "total": 3}])

    detail = asyncio.run(ebay.price_summary_with_trace("pokemon Charizard"))

    assert detail["summary"] is None
    # All 3 dropped on title noise.
    cls = detail["passes"][0]["classifications"]
    assert all(not c.kept for c in cls)


def test_price_summary_below_min_required_returns_none():
    """Two listings + non-chase rarity => below the min-of-3 threshold."""
    items = _items(("Charizard 4/102 NM", 80.0), ("Charizard 4/102 LP", 70.0))
    ebay = _StubEbay([{"itemSummaries": items, "total": 2}])

    detail = asyncio.run(ebay.price_summary_with_trace("pokemon Charizard"))

    assert detail["summary"] is None
    assert detail["min_required"] == 3
    assert detail["is_chase"] is False


def test_price_summary_chase_min_is_two():
    """Same two listings but a chase rarity => min of 2, succeeds."""
    items = _items(
        ("Meowth ex 121/068 SIR", 50.0),
        ("Meowth ex 121/068 Special Illustration Rare", 60.0),
    )
    ebay = _StubEbay([{"itemSummaries": items, "total": 2}])

    detail = asyncio.run(
        ebay.price_summary_with_trace(
            "pokemon Meowth ex 121/068 Perfect Order",
            card_number="121",
            rarity="Special Illustration Rare",
        )
    )

    assert detail["is_chase"] is True
    assert detail["min_required"] == 2
    assert detail["summary"] is not None
    assert detail["summary"]["count_sampled"] == 2


def test_price_summary_chase_no_tcg_ref_applies_rarity_floor():
    """When there's no TCG reference, the rarity floor still drops cheap leaks."""
    items = _items(
        ("Meowth ex 121/068 SIR", 50.0),
        ("Meowth ex 121/068 SIR mint", 60.0),
        ("Meowth ex 121 SIR", 70.0),
        ("Meowth ex 121/068 SIR holo", 2.50),  # <- below SIR floor of $5, should drop
    )
    ebay = _StubEbay([{"itemSummaries": items, "total": 4}])

    detail = asyncio.run(
        ebay.price_summary_with_trace(
            "pokemon Meowth ex 121/068 Perfect Order",
            card_number="121",
            rarity="Special Illustration Rare",
        )
    )

    assert detail["summary"] is not None
    assert detail["summary"]["count_sampled"] == 3  # the $2.50 dropped
    # Confirm the cheap one was dropped via floor.
    cls = detail["passes"][0]["classifications"]
    dropped = [c for c in cls if not c.kept]
    assert len(dropped) == 1
    assert dropped[0].drop_reason is not None
    assert dropped[0].drop_reason.startswith("below_floor:")


def test_price_summary_chase_with_tcg_ref_applies_relative_band():
    """TCG ref $800 -> floor max(800*0.30, $5 SIR floor) = $240, ceiling $4000."""
    items = _items(
        ("Mega Charizard X ex 125/094 SIR", 800.0),
        ("Mega Charizard X ex 125/094 Special Illustration", 750.0),
        ("Mega Charizard X ex 125/094 NM", 900.0),
        ("Mega Charizard X ex 125 Double Rare", 50.0),  # below floor, dropped
        ("Mega Charizard X ex 125/094 PSA", 5000.0),  # title noise (PSA), dropped
    )
    ebay = _StubEbay([{"itemSummaries": items, "total": 5}])

    detail = asyncio.run(
        ebay.price_summary_with_trace(
            "pokemon Mega Charizard X ex 125/094 Phantasmal Flames",
            reference_price_usd=800.0,
            card_number="125",
            rarity="Special Illustration Rare",
        )
    )

    assert detail["summary"] is not None
    assert detail["summary"]["count_sampled"] == 3
    # Verify the floor that was applied.
    assert detail["config"].sanity_floor is not None
    assert detail["config"].sanity_floor >= 240.0


def test_price_summary_auction_fallback_kicks_in():
    """First pass (FIXED_PRICE) empty -> retry without buyingOptions."""
    fixed_pass: list[dict] = []  # empty result
    auction_pass = _items(
        ("Meowth ex 121/068 SIR", 50.0),
        ("Meowth ex 121/068 SIR mint", 60.0),
    )
    ebay = _StubEbay([
        {"itemSummaries": fixed_pass, "total": 0},
        {"itemSummaries": auction_pass, "total": 2},
    ])

    detail = asyncio.run(
        ebay.price_summary_with_trace(
            "pokemon Meowth ex 121/068 Perfect Order",
            card_number="121",
            rarity="Special Illustration Rare",
        )
    )

    assert detail["summary"] is not None
    assert len(detail["passes"]) == 2
    assert detail["passes"][0]["label"] == "fixed_price"
    assert detail["passes"][1]["label"] == "auction_fallback"
    # Auction-fallback call should not have the buyingOptions filter.
    second_call = ebay._call_log[1]
    filters = second_call.get("filters") or {}
    assert "buyingOptions" not in filters


def test_price_summary_chase_rarities_constant_matches_rarity_floor_keys():
    """Sanity: every chase rarity should also have a price floor configured,
    otherwise a non-TCG-ref chase card with no floor would fall through."""
    for rarity in _CHASE_RARITIES:
        assert rarity in _RARITY_ABS_FLOOR, f"{rarity!r} has no rarity floor"
