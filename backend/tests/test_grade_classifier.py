"""Coverage for services.grade_classifier — the eBay title → grade tag
router that feeds `card_price_snapshots.grade`. Cases below mirror
real-world title patterns pulled from eBay listings; extend when a
new pattern shows up in the wild."""

import pytest

from app.services.grade_classifier import classify_grade


@pytest.mark.parametrize(
    "title, expected",
    [
        # Bare cards / no grader mention.
        ("2024 Pokemon SV Charizard ex Holo Ungraded", "raw"),
        ("Pikachu VMAX 044/185 NM/M", "raw"),
        ("", "raw"),
        # PSA — the compact + spaced + hyphenated + dotted variants.
        ("Charizard 4/102 Base Set PSA 10 GEM MINT", "psa10"),
        ("Blastoise Shadowless PSA10", "psa10"),
        ("Pokemon Umbreon VMAX Alt Art PSA 9 MINT", "psa9"),
        ("Mewtwo GX PSA-8 NM MINT", "psa8"),
        ("Charizard PSA 7 EX Grade", "other"),
        ("P.S.A. 10 Charizard V", "psa10"),
        # CGC including 9.5 half-grade.
        ("Rayquaza VMAX Alt CGC 9.5 Gem Mint", "cgc9.5"),
        ("Umbreon VMAX Alt CGC 10 Pristine", "cgc10"),
        ("Charizard Base CGC 9 Mint", "cgc9"),
        ("Zacian V CGC 8.5 NM", "other"),
        # BGS.
        ("Pikachu Illustrator BGS 10 Black Label", "bgs10"),
        ("Trainer Card BGS 9.5 Gem Mint", "bgs9.5"),
        ("Machamp BGS 9", "bgs9"),
        ("Old Card BGS 7.5", "other"),
        # Other graders → bucket 'other'.
        ("Vintage Charizard SGC 10", "other"),
        ("Cheap Slab GMA 8", "other"),
        ("ACE 10 Grade Charizard", "other"),
        # Fuzzy — "grade 10" without a grader.
        ("Pokemon Card Grade 10 Mint Condition", "other"),
        # Multiple graders — first (PSA) wins.
        ("PSA 10 CGC 9.5 twin-slab pair Charizard", "psa10"),
        # Card name containing digits shouldn't trip PSA regex.
        ("Zacian V-Union Set of 4 Sealed Promo", "raw"),
        ("Charizard 4/102 near-mint sleeved", "raw"),
    ],
)
def test_classify_grade(title: str, expected: str) -> None:
    assert classify_grade(title) == expected
