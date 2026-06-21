"""Backfill JP-native rarity from Bulbapedia set list tables.

Limitless's EN-equivalent picker gets us to ~95% but collapses JP-only
tiers (Mega Attack Rare, Triple Rare variants etc.) to the nearest
English rarity. Pokemon-card.com — the official Japanese site — does
NOT display rarity anywhere on its card detail pages, so it's a dead
end. Bulbapedia's per-set wiki page DOES — every JP set has a card
list table with columns:

    No. | Mark | Card name | Type | Rarity | Promotion

…and the Rarity column carries the JP-native abbreviation (C, U, R,
RR, AR, SR, SAR, UR). One HTTP call per set, ~65 sets, ~30 minutes
total runtime.

We map the JP abbreviations to our canonical pokemontcg.io-style
rarity labels — the frontend filter groups already key off those.

Usage:
    python -m scripts.backfill_jp_rarity_bulbapedia
    python -m scripts.backfill_jp_rarity_bulbapedia --set M2a
    python -m scripts.backfill_jp_rarity_bulbapedia --dry-run
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import re
from collections import Counter
from typing import Optional

import httpx
from sqlalchemy import text

from app.database import SessionLocal, init_db

log = logging.getLogger("backfill_jp_rarity_bulb")

BASE = "https://bulbapedia.bulbagarden.net/wiki/"
SEM = 4

# Our DB set_id → Bulbapedia page slug. Mirrors the table in
# scripts/import_bulbapedia_logos.py — keeping a parallel copy here
# so the rarity backfill can run independently when logos already
# settled.
JP_SET_TO_BULBAPEDIA: dict[str, str] = {
    # SV-era
    "SV11W": "White_Flare_(TCG)",
    "SV11B": "Black_Bolt_(TCG)",
    "SV10":  "Glory_of_Team_Rocket_(TCG)",
    "SV9a":  "Heat_Wave_Arena_(TCG)",
    "SV9":   "Battle_Partners_(TCG)",
    "SV8a":  "Terastal_Festival_ex_(TCG)",
    "SV8":   "Super-Electric_Breaker_(TCG)",
    "SV7a":  "Paradise_Dragona_(TCG)",
    "SV7":   "Stellar_Miracle_(TCG)",
    "SV6a":  "Night_Wanderer_(TCG)",
    "SV6":   "Mask_of_Change_(TCG)",
    "SV5a":  "Crimson_Haze_(TCG)",
    "SV5M":  "Cyber_Judge_(TCG)",
    "SV5K":  "Wild_Force_(TCG)",
    "SV4a":  "Shiny_Treasure_ex_(TCG)",
    "SV4M":  "Future_Flash_(TCG)",
    "SV4K":  "Ancient_Roar_(TCG)",
    "SV3a":  "Raging_Surf_(TCG)",
    "SV3":   "Ruler_of_the_Black_Flame_(TCG)",
    "SV2a":  "Pokémon_Card_151_(TCG)",
    "SV2D":  "Clay_Burst_(TCG)",
    "SV2P":  "Snow_Hazard_(TCG)",
    "SV1V":  "Violet_ex_(TCG)",
    "SV1S":  "Scarlet_ex_(TCG)",
    # MEGA-era (new)
    "M3":    "Nihil_Zero_(TCG)",
    "M2a":   "Mega_Dream_ex_(TCG)",
    "M2":    "Inferno_X_(TCG)",
    "M1S":   "Mega_Symphonia_(TCG)",
    "M1L":   "Mega_Brave_(TCG)",
    # SwSh-era (S1..S12)
    "S12a":  "VSTAR_Universe_(TCG)",
    "S12":   "Paradigm_Trigger_(TCG)",
    "S11a":  "Incandescent_Arcana_(TCG)",
    "S11":   "Lost_Abyss_(TCG)",
    "S10D":  "Time_Gazer_(TCG)",
    "S10P":  "Space_Juggler_(TCG)",
    "S10b":  "Pokémon_GO_(TCG)",
    "S10a":  "Dark_Phantasma_(TCG)",
    "S9a":   "Battle_Region_(TCG)",
    "S9":    "Star_Birth_(TCG)",
    "S8b":   "VMAX_Climax_(TCG)",
    "S8a":   "25th_Anniversary_Collection_(TCG)",
    "S8":    "Fusion_Arts_(TCG)",
    "S7R":   "Blue_Sky_Stream_(TCG)",
    "S7D":   "Towering_Perfection_(TCG)",
    "S6a":   "Eevee_Heroes_(TCG)",
    "S6K":   "Jet-Black_Spirit_(TCG)",
    "S6H":   "Silver_Lance_(TCG)",
    "S5a":   "Matchless_Fighters_(TCG)",
    "S5R":   "Rapid_Strike_Master_(TCG)",
    "S5I":   "Single_Strike_Master_(TCG)",
    "S4a":   "Shiny_Star_V_(TCG)",
    "S4":    "Amazing_Volt_Tackle_(TCG)",
    "S3a":   "Legendary_Heartbeat_(TCG)",
    "S3":    "Infinity_Zone_(TCG)",
    "S2a":   "Explosive_Walker_(TCG)",
    "S2":    "Rebellion_Crash_(TCG)",
    "S1a":   "VMAX_Rising_(TCG)",
    "S1H":   "Shield_(TCG)",
    "S1W":   "Sword_(TCG)",
}


# JP rarity abbreviations from Bulbapedia table → pokemontcg.io-style
# label our frontend filter understands. Bulbapedia uses both short
# abbreviations (RR, SAR) and the full English form (Rare Ultra, Rare
# Rainbow) — both are mapped here. Match exact first, then case-
# insensitive contains.
_RARITY_MAP: dict[str, str] = {
    # JP abbreviations (top tier first)
    "UR":   "Hyper Rare",
    "HR":   "Hyper Rare",
    "MR":   "Mega Hyper Rare",
    "MAR":  "Mega Hyper Rare",
    "MUR":  "Mega Hyper Rare",
    "SAR":  "Special Illustration Rare",
    "AR":   "Illustration Rare",
    "SR":   "Special Rare",
    "SSR":  "Shiny Ultra Rare",
    "CSR":  "Character Super Rare",
    "CHR":  "Character Holo Rare",
    "K":    "Hyper Rare",
    "S":    "Shiny Rare",
    "RRR":  "Triple Rare",
    "RR":   "Double Rare",
    "PR":   "Promo",
    "P":    "Promo",
    "R":    "Rare",
    "U":    "Uncommon",
    "C":    "Common",
    # JP era-specific
    "ACE":  "Rare ACE",
    "LEG":  "LEGEND",
    "BREAK": "Rare BREAK",
    "PRIME": "Rare Prime",
    # Bulbapedia full-form (alt attribute sometimes carries English name)
    "Rare Ultra": "Ultra Rare",
    "Ultra-Rare Rare": "Ultra Rare",
    "Rare Rainbow": "Rainbow Rare",
    "Rare Secret": "Rare Secret",
    "Rare Holo": "Rare Holo",
    "Rare Holo EX": "Rare Holo EX",
    "Rare Holo GX": "Rare Holo GX",
    "Rare Holo V": "Rare Holo V",
    "Rare Holo VMAX": "Rare Holo VMAX",
    "Rare Holo VSTAR": "Rare Holo VSTAR",
    "Rare VMAX": "Rare Holo VMAX",
    "Rare VSTAR": "Rare Holo VSTAR",
    "Rare V": "Rare Holo V",
    "Rare Shiny": "Shiny Rare",
    "Rare Shiny GX": "Shiny Rare",
    "ACE SPEC Rare": "Rare ACE",
    "Rare ACE": "Rare ACE",
    "Rare Classic": "Classic Collection",
    "Radiant Rare": "Radiant Rare",
    "Amazing Rare": "Amazing Rare",
    "Black White Rare": "Black White Rare",
    "Hyper Rare": "Hyper Rare",
    "Ultra Rare": "Ultra Rare",
    "Double Rare": "Double Rare",
    "Triple Rare": "Triple Rare",
    "Illustration Rare": "Illustration Rare",
    "Special Illustration Rare": "Special Illustration Rare",
    "Common": "Common",
    "Uncommon": "Uncommon",
    "Rare": "Rare",
}


def _normalize_jp_rarity(token: str) -> Optional[str]:
    """`'RR'` -> `'Double Rare'`. Returns None for unknown codes."""
    if not token:
        return None
    t = token.strip()
    # Bulbapedia sometimes has the rarity in formatted form like "RR" or
    # links like "[[Double Rare]]" — strip wiki markup if any leaked.
    t = re.sub(r"[\[\]]", "", t).strip()
    # Try multi-letter codes first
    if t in _RARITY_MAP:
        return _RARITY_MAP[t]
    # Fall back to common full English words
    for word, mapped in (
        ("Special Art Rare", "Special Illustration Rare"),
        ("Special Illustration Rare", "Special Illustration Rare"),
        ("Illustration Rare", "Illustration Rare"),
        ("Hyper Rare", "Hyper Rare"),
        ("Ultra Rare", "Ultra Rare"),
        ("Double Rare", "Double Rare"),
        ("Triple Rare", "Triple Rare"),
        ("Rare Holo", "Rare Holo"),
        ("Uncommon", "Uncommon"),
        ("Common", "Common"),
    ):
        if word.lower() in t.lower():
            return mapped
    return None


# Bulbapedia card-list rows look like (note: Type uses <th>, others <td>):
#   <tr>
#     <td>001/100</td>            ← cell 0: number
#     <td><img alt="I"></td>      ← cell 1: regulation mark icon
#     <td><a>Caterpie</a></td>    ← cell 2: name
#     <th><img alt="Grass"></th>  ← cell 3: type icon (Bulbapedia uses <th> here)
#     <td><img alt="C"></td>      ← cell 4: rarity icon (alt = abbrev)
#     <td>Promotion</td>          ← cell 5
#   </tr>
# Rarity is an icon's alt attribute, not visible text. Match both td/th.
_ROW_RE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.DOTALL | re.IGNORECASE)
_CELL_RE = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.DOTALL | re.IGNORECASE)
_ALT_RE = re.compile(r'alt="([^"]+)"')
_NUM_RE = re.compile(r"(\d+)\s*/\s*\d+")


def _strip_html(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"&nbsp;", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def _extract_rarity_map(html: str) -> dict[str, str]:
    """Parse the set list table → {card_number: jp_rarity_code}."""
    out: dict[str, str] = {}
    for row_match in _ROW_RE.finditer(html):
        row_html = row_match.group(1)
        cells = _CELL_RE.findall(row_html)
        if len(cells) < 5:
            continue
        # Cell 0: number, cell 4: rarity icon's alt
        num_text = _strip_html(cells[0])
        m = _NUM_RE.search(num_text)
        if not m:
            continue
        number = m.group(1).lstrip("0") or "0"

        # Try img alt first (the canonical "C"/"RR"/"SAR" abbreviation),
        # fall back to cell text content if no img is present.
        rarity_alt = _ALT_RE.search(cells[4])
        rarity_text = (
            rarity_alt.group(1) if rarity_alt else _strip_html(cells[4])
        )
        if rarity_text:
            out[number] = rarity_text
    return out


async def _fetch_set(client: httpx.AsyncClient, slug: str) -> str | None:
    url = f"{BASE}{slug}"
    try:
        r = await client.get(url, timeout=30)
    except httpx.HTTPError as e:
        log.warning(f"  ! {slug}: {e}")
        return None
    if r.status_code != 200:
        log.warning(f"  ! {slug}: HTTP {r.status_code}")
        return None
    return r.text


async def run(only_set: str | None, dry: bool) -> None:
    await init_db()
    targets = (
        [only_set] if only_set else list(JP_SET_TO_BULBAPEDIA.keys())
    )
    log.info(f"Targets: {len(targets)} JP sets")

    headers = {"User-Agent": "PullList-Catalog/1.0 (+https://pulllist.org)"}
    total_updated = 0
    unknown_codes: Counter[str] = Counter()

    async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
        for i, set_id in enumerate(targets, 1):
            slug = JP_SET_TO_BULBAPEDIA.get(set_id)
            if not slug:
                log.warning(f"[{i}/{len(targets)}] {set_id}: no Bulbapedia mapping — skip")
                continue
            html = await _fetch_set(client, slug)
            if not html:
                continue
            rarity_map = _extract_rarity_map(html)
            if not rarity_map:
                log.warning(f"[{i}/{len(targets)}] {set_id}: no table rows extracted")
                continue

            # Map JP codes → canonical labels, count unknowns
            mapped: dict[str, str] = {}
            for num, code in rarity_map.items():
                label = _normalize_jp_rarity(code)
                if label:
                    mapped[num] = label
                else:
                    unknown_codes[code] += 1

            log.info(
                f"[{i}/{len(targets)}] {set_id:6s}: parsed {len(rarity_map)} rows, "
                f"mapped {len(mapped)}, unknown {len(rarity_map) - len(mapped)}"
            )

            if dry or not mapped:
                continue

            # Update each card's rarity. Match by (set_id, number).
            async with SessionLocal() as db:
                for num, label in mapped.items():
                    r = await db.execute(
                        text(
                            "UPDATE cards SET rarity=:r "
                            "WHERE set_id=:s AND number=:n AND language='ja'"
                        ),
                        {"r": label, "s": set_id, "n": num},
                    )
                    if r.rowcount:
                        total_updated += r.rowcount
                # Also try padded numbers like "001" since some JP sets
                # store the padded form in cards.number.
                for num, label in mapped.items():
                    padded = num.zfill(3)
                    if padded == num:
                        continue
                    r = await db.execute(
                        text(
                            "UPDATE cards SET rarity=:r "
                            "WHERE set_id=:s AND number=:n AND language='ja'"
                        ),
                        {"r": label, "s": set_id, "n": padded},
                    )
                    if r.rowcount:
                        total_updated += r.rowcount
                await db.commit()

    log.info("\n=== Summary ===")
    log.info(f"  cards updated: {total_updated}")
    if unknown_codes:
        log.info(f"  unknown JP rarity codes (need mapping): {dict(unknown_codes.most_common(20))}")
    if dry:
        log.info("  MODE: DRY-RUN — no writes")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--set", dest="only_set", help="One JP set id")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    asyncio.run(run(args.only_set, args.dry_run))


if __name__ == "__main__":
    main()
