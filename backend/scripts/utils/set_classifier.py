"""Shared name-pattern classifier for JP set_type.

Used by:
    scripts/classify_jp_set_types.py — bulk pass over the whole catalog
    scripts/seed_and_scrape_limitless_batch.py — auto-tag new imports
    scripts/seed_promo_group.py — same
    (any future JP set importer)

Categories returned:
    MAIN          — main booster expansion (SV1, Dark Rush, PMCG1, ...)
    DECK          — starter set / preconstructed deck / trainer box /
                    build box / half deck / etc.
    STUB          — set row exists but no cards seeded
    PROMO_LEGACY  — pre-existing JP promo groups (JPP-P, JPP-SI, etc.)
    PROMO_NEW     — Bulbapedia-derived year buckets (JPP-U*)

Keep the reject/pattern lists in sync with:
    docs/JP_SET_TYPE_TAXONOMY.md (if it exists)
    the classify_jp_set_types script (currently authoritative source)
"""
from __future__ import annotations

import re

DECK_PATTERNS: list[str] = [
    r"\bdeck\b", r"half deck", r"starter set", r"starter pack",
    r"starter deck", r"battle box", r"battle deck", r"battle gift",
    r"battle master deck", r"deck build box", r"deck kit",
    r"special deck set", r"special set", r"special card set",
    r"premium trainer box", r"trainer battle deck", r"gift set",
    r"evolution pack", r"family pok", r"jumbo-?pack",
    r"v starter", r"ex starter", r"gx starter", r"vstar starter",
    r"master deck build", r"ex special set", r"collection sheet",
    r"starting set", r"perfect battle deck", r"high-class deck",
    r"starter decks 100", r"v-union special",
    r"デッキビルド", r"スターターセット", r"ハーフデッキ",
    r"トレーナーボックス", r"バトル.*デッキ",
]

MAIN_NAME_OVERRIDE: list[str] = [
    "battle boost", "plasma gale", "megalo cannon", "gaia volcano",
    "raiden knuckle", "miracle twin", "tidal storm", "shining legends",
    "ultra force", "red collection", "white collection", "black collection",
    "red light flash", "freeze bolt", "cold flare", "dark rush",
    "psycho drive", "dragon blast", "dragon blade", "spiral force",
    "heat burst fighter", "hail blizzard", "triplet beat",
    "sun and moon plus", "best of xy", "shiny collection", "gg end",
    "ruler of the black flame", "collection x", "collection y",
    "cruel traitor", "new trials", "exciting battle",
]

# Specific set_id overrides (wins over pattern match)
FORCE_STUB: set[str] = {
    "ADV1", "ADV2", "ADV3", "ADV4", "ADV5", "PCG10",
    "L1a", "L1b", "L2", "L3", "LL", "XY11a",
    "JPP-VM", "JPP-PKC", "JPP-PPP", "JPP-MCD",
    "JPP-ADV", "JPP-PCG", "JPP-L", "JPP-WC",
}
FORCE_MAIN: set[str] = {"web1", "CP3", "CP5"}
FORCE_DECK: set[str] = {"SVK"}
FORCE_PROMO_LEGACY: set[str] = {"JPP-VM1", "JPP-VM2", "JPP-VM3"}


def classify_set(
    set_id: str,
    name: str,
    name_en: str | None = None,
    card_count: int = 0,
) -> str:
    """Return one of MAIN / DECK / STUB / PROMO_LEGACY / PROMO_NEW.

    Order of precedence:
      1. Specific set_id overrides
      2. JPP-U* → PROMO_NEW  (year-bucket promos)
      3. JPP-*  → PROMO_LEGACY (existing promo groups)
      4. MAIN_NAME_OVERRIDE hit
      5. DECK_PATTERNS hit
      6. Card-count heuristic (>=50 = MAIN, <30 = DECK)
      7. Fallback MAIN
    """
    if set_id in FORCE_STUB:
        return "STUB"
    if set_id in FORCE_MAIN:
        return "MAIN"
    if set_id in FORCE_DECK:
        return "DECK"
    if set_id in FORCE_PROMO_LEGACY:
        return "PROMO_LEGACY"
    if set_id.startswith("JPP-U"):
        return "PROMO_NEW"
    if set_id.startswith("JPP-"):
        return "PROMO_LEGACY"

    n = ((name or "") + " " + (name_en or "")).lower()

    for m in MAIN_NAME_OVERRIDE:
        if m in n:
            return "MAIN"
    for p in DECK_PATTERNS:
        if re.search(p, n):
            return "DECK"

    if card_count >= 50:
        return "MAIN"
    if 0 < card_count < 30:
        return "DECK"
    if card_count == 0:
        return "STUB"
    return "MAIN"
