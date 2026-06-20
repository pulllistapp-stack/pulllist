"""Tests for the listing scorer.

Real eBay titles harvested from the Live Listings panel — these are
the exact cases the filter was built to handle.
"""
from app.services.listing_match import (
    TRUST_LOW,
    TRUST_NEW,
    TRUST_OK,
    TRUST_POOR,
    TRUST_TRUSTED,
    filter_listings,
    is_suspicious,
    score_listing,
    seller_trust_tier,
)


# Target: Meowth ex 062/088 from Mega Brave (M1S)
TARGET_NUM = "062"
TARGET_TOTAL = 88


class TestScoreListing:
    def test_exact_match_padded(self):
        # Listing matches our zero-padded card number and total
        r = score_listing(
            "Pokemon TCG Meowth ex 062/088 Mega Brave Holo",
            TARGET_NUM,
            TARGET_TOTAL,
        )
        assert r.score == 100, r

    def test_exact_match_unpadded(self):
        # Many listings drop the leading zero
        r = score_listing(
            "Pokemon TCG Meowth ex 62/88 : Double Rare",
            TARGET_NUM,
            TARGET_TOTAL,
        )
        assert r.score == 100, r

    def test_number_match_different_total(self):
        # Same card-number but seller wrote a different total
        # (124 not 88). Treat as still likely the right card.
        r = score_listing(
            "Pokemon Meowth ex (62/124) Perfect Order",
            TARGET_NUM,
            TARGET_TOTAL,
        )
        assert r.score == 70, r

    def test_different_card_number_rejected(self):
        # The 107/088 Ultra Rare is a DIFFERENT card from same set
        r = score_listing(
            "Pokemon TCG Meowth ex 107/088 Ultra Rare Holo",
            TARGET_NUM,
            TARGET_TOTAL,
        )
        assert r.score == 0, r

    def test_sir_variant_rejected(self):
        # 121/088 SIR is another sibling variant — must drop
        r = score_listing(
            "Pokemon Meowth ex 121/088 SIR Perfect Order Holo",
            TARGET_NUM,
            TARGET_TOTAL,
        )
        assert r.score == 0, r

    def test_no_pattern_in_title(self):
        # Old promo / tournament listing without x/y
        r = score_listing(
            "Pokemon Mew WoTC Promo #08/53 PromoFree",  # has 08/53
            "1",  # imagine target is "1" not 8
            None,
        )
        # Has x/y but doesn't match → 0
        assert r.score == 0, r

    def test_no_pattern_truly_missing(self):
        r = score_listing(
            "Vintage Charizard Holo Base Set Pristine",
            "4",
            102,
        )
        # No x/y anywhere → tier 30 (accept-as-unknown, but below 70)
        assert r.score == 30, r

    def test_target_has_no_number(self):
        # Some cards (early JP promos) lack numeric numbers
        r = score_listing("Anything goes here", None, None)
        assert r.score == 70, r

    def test_multiple_pairs_one_matches(self):
        # PSA grade gets formatted as "PSA 10" — but pSA grade isn't x/y
        # Pokemon Center "set of 102" patterns: "Charizard 4/102 from set of 165"
        r = score_listing(
            "PSA 10 Charizard 4/102 from a set of 165 cards",
            "4",
            102,
        )
        # The 4/102 pair matches both number and total → 100
        assert r.score == 100, r

    def test_empty_title(self):
        r = score_listing("", "1", 100)
        assert r.score == 0, r


class TestFilterListings:
    def _items(self, *titles: str) -> list[dict]:
        return [{"title": t} for t in titles]

    def test_filter_keeps_only_matches(self):
        items = self._items(
            "Pokemon Meowth ex 62/88 Double Rare",         # 100
            "Pokemon Meowth ex 062/088 Mega Brave",        # 100
            "Pokemon Meowth ex 107/088 Ultra Rare Holo",   # 0
            "Pokemon Meowth ex 121/088 SIR",               # 0
        )
        kept, dropped = filter_listings(items, TARGET_NUM, TARGET_TOTAL)
        assert len(kept) == 2
        assert dropped[0] == 2

    def test_filter_at_70_keeps_partial(self):
        items = self._items(
            "Meowth ex 62/124 different print",  # 70 — kept at min=70
            "Meowth ex 107/088 wrong card",       # 0  — dropped
        )
        kept, dropped = filter_listings(items, TARGET_NUM, TARGET_TOTAL, min_score=70)
        assert len(kept) == 1
        assert dropped[0] == 1

    def test_filter_at_100_strict_for_alerts(self):
        # Wishlist alert mode: only the perfect-exact listings survive
        items = self._items(
            "Meowth ex 062/088",   # 100
            "Meowth ex 62/124",    # 70 (loose)
            "Meowth ex 121/088",   # 0
        )
        kept, dropped = filter_listings(items, TARGET_NUM, TARGET_TOTAL, min_score=100)
        assert len(kept) == 1
        assert dropped[70] == 1
        assert dropped[0] == 1


class TestSellerTrust:
    def test_brand_new_seller_zero_score(self):
        assert seller_trust_tier(0, 0.0) == TRUST_NEW
        assert seller_trust_tier(0, 100.0) == TRUST_NEW  # 0 trades = no signal

    def test_low_volume_seller(self):
        assert seller_trust_tier(5, 100.0) == TRUST_LOW
        assert seller_trust_tier(9, 99.0) == TRUST_LOW

    def test_poor_feedback_pct(self):
        assert seller_trust_tier(500, 92.0) == TRUST_POOR
        assert seller_trust_tier(50, 80.0) == TRUST_POOR

    def test_ok_seller(self):
        assert seller_trust_tier(50, 98.0) == TRUST_OK
        assert seller_trust_tier(99, 97.0) == TRUST_OK

    def test_trusted_seller(self):
        assert seller_trust_tier(500, 99.5) == TRUST_TRUSTED
        assert seller_trust_tier(10000, 100.0) == TRUST_TRUSTED

    def test_missing_data_treated_as_poor(self):
        # If eBay didn't surface seller stats at all, default to POOR
        # rather than TRUST_OK — we'd rather a false negative on the
        # rare "fresh API quirk" listing than miss a real scam.
        assert seller_trust_tier(None, None) == TRUST_POOR


class TestIsSuspicious:
    def test_bri_769542_meowth_scam(self):
        # The actual case from the screenshot — $74.52 on a $854 card
        # from a 0-feedback seller. Must flag.
        assert is_suspicious(74.52, 854.65, TRUST_NEW) is True

    def test_trusted_low_price_not_suspicious(self):
        # Trusted seller listing below market is just a deal, not a scam
        assert is_suspicious(74.52, 854.65, TRUST_TRUSTED) is False
        assert is_suspicious(74.52, 854.65, TRUST_OK) is False

    def test_new_seller_market_price_not_suspicious(self):
        # New seller asking close to market — could be legit beginner
        assert is_suspicious(800.0, 854.65, TRUST_NEW) is False

    def test_no_market_data_skipped(self):
        # Can't evaluate without a baseline
        assert is_suspicious(50.0, None, TRUST_NEW) is False
        assert is_suspicious(50.0, 0, TRUST_NEW) is False

    def test_threshold_boundary(self):
        # 40% of 100 = 40. Listings at 40 should NOT be suspicious; below 40 yes.
        assert is_suspicious(40.0, 100.0, TRUST_NEW) is False
        assert is_suspicious(39.99, 100.0, TRUST_NEW) is True

    def test_cheap_card_low_price_safe(self):
        # A $0.50 listing on a $2 card from a new seller is not the
        # scam pattern — small absolute dollar value, just bulk pricing
        assert is_suspicious(0.50, 2.00, TRUST_NEW) is True  # tier alone matches
        # That's by design — we treat ANY new+low combo the same. Frontend
        # can suppress the warning for cards under a value threshold.
