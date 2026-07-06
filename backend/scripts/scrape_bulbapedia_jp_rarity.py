"""Rebuild JP card rarity from Bulbapedia set articles.

The old backfill_jp_rarity.py used Limitless's EN-print equivalents,
which broke on DECK reprints and on any JP card whose EN counterpart
lives in a different set (same-name inheritance bug). This script
uses the Japanese set list on Bulbapedia directly, which lists the
actual JP rarity code (C / U / R / RR / RRR / AR / SR / SAR / HR / UR /
CHR / CSR / SSR) for each card in each set.

For each JP MAIN set with a Bulbapedia article:
    1. Fetch the article HTML
    2. Locate the "Set list" table
    3. Parse each row: (card number, card name, rarity code)
    4. Match rows to our DB cards by (set_id, number_int)
    5. Update cards.rarity to the JP code (native taxonomy)

JP native codes stored as-is — same column, but the value is a JP
tier code rather than an EN label. Frontend filters branch on card
language to render the right taxonomy in the filter sidebar. This
keeps queries simple (one rarity column) while letting the two
naming systems coexist.

Idempotent. Doesn't touch DECK / STUB / PROMO_NEW sets.

Usage:
    python -m scripts.scrape_bulbapedia_jp_rarity --dry-run
    python -m scripts.scrape_bulbapedia_jp_rarity
    python -m scripts.scrape_bulbapedia_jp_rarity --set BW4
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import re
from html import unescape

import httpx
from sqlalchemy import text

from app.database import SessionLocal, init_db

log = logging.getLogger("scrape_bulbapedia_jp_rarity")

BULBAPEDIA = "https://bulbapedia.bulbagarden.net"
UA = "PullList-Catalog/1.0 (+https://pulllist.org; jp-rarity-backfill)"

# Reuse the slugs we mapped for logo hunting. Extend for MAIN sets not
# already covered.
from scripts.backfill_jp_set_logos import _BULBAPEDIA_SLUGS as _LOGO_SLUGS

# Set IDs where we know Bulbapedia has a Japanese Set list section.
# Falls back to sets.name_en → "{Name}_(TCG)" when not listed here.
_SET_TO_SLUG: dict[str, str] = {
    **_LOGO_SLUGS,
    # SV era (2023–2026)
    "SV2a":  "Pok%C3%A9mon_Card_151_(TCG)",
    "SV4a":  "Shiny_Treasure_ex_(TCG)",
    "SV6":   "Mask_of_Change_(TCG)",
    "SV8":   "Super-Electric_Breaker_(TCG)",
    "SV8a":  "Terastal_Festival_ex_(TCG)",
    "SV9a":  "Heat_Wave_Arena_(TCG)",
    "SV11W": "White_Flare_(TCG)",
    "SV11B": "Black_Bolt_(TCG)",
    "S6K":   "Jet-Black_Poltergeist_(TCG)",
    "S7D":   "Towering_Perfection_(TCG)",
    "S8b":   "VMAX_Climax_(TCG)",
    "S10b":  "Pok%C3%A9mon_GO_(TCG)",
    "S12a":  "VSTAR_Universe_(TCG)",
    "S4a":   "Shiny_Star_V_(TCG)",
    # SM era (2016–2019)
    "SM4p":  "GX_Battle_Boost_(TCG)",
    "SM5M":  "Ultra_Moon_(TCG)",
    "SM5S":  "Ultra_Sun_(TCG)",
    "SM6b":  "Champion_Road_(TCG)",
    "SM7a":  "Thunderclap_Spark_(TCG)",
    "SM8b":  "GX_Ultra_Shiny_(TCG)",
    "SM11a": "Remix_Bout_(TCG)",
    "SM11b": "Dream_League_(TCG)",
    "SM12a": "Tag_All_Stars_(TCG)",
    # e-Card era (2001–2002)
    "E1":    "Expedition_Base_Set_(TCG)",
    "E2":    "Aquapolis_(TCG)",
    "E4":    "Split_Earth_(TCG)",
    "E5":    "Mysterious_Mountains_(TCG)",
    # PMCG (WoTC era, 1996–1999)
    "PMCG5": "Gym_Heroes_(TCG)",
    "PMCG6": "Gym_Challenge_(TCG)",
    # PCG era (2004–2006)
    "PCG2":  "Clash_of_the_Blue_Sky_(TCG)",
    "PCG3":  "Rocket_Gang_Strikes_Back_(TCG)",
    "PCG5":  "Mirage_Forest_(TCG)",
    "PCG6":  "Holon_Research_Tower_(TCG)",
    "PCG8":  "Miracle_Crystal_(TCG)",
    "PCG9":  "Battle_at_Furthest_Ends_(TCG)",
}


# Canonical JP rarity codes we accept. Anything else surfaces in the
# "unknown rarity code" bucket and gets skipped so we don't write a
# freeform string into a categorised column.
_JP_RARITIES: set[str] = {
    "C", "U", "R",
    "RR", "RRR",
    "AR", "SR", "SAR",
    "HR", "UR",
    "CHR", "CSR", "SSR",
    "ACE",           # Rare ACE (older era)
    "K",             # Kirakira / Shiny — older tier
    "SP",            # Special Rare — rare, some vintage sets
    "Promo", "P",    # promo stamp
}


# Row parser. Bulbapedia's Set list rows look like:
#   <tr>
#     <td align="center">001/073</td>
#     <td><img src="RegMark_G.png"></td>       <-- regulation mark
#     <td><a href="/wiki/Tropius_(...)">Tropius</a></td>
#     <th><img alt="Grass" ...></th>            <-- type icon
#     <td><img alt="C" src="Rarity_C.png"></td> <-- RARITY (image, not text!)
#     <td>Promotion</td>
#   </tr>
# Rarity is a Rarity_X.png image with alt="X". We look for either the
# alt attribute or the filename to recover the code.
_ROW_RE = re.compile(
    r"<tr[^>]*>(.*?)</tr>", re.DOTALL | re.IGNORECASE,
)
_CELL_RE = re.compile(
    r"<t[dh][^>]*>(.*?)</t[dh]>", re.DOTALL | re.IGNORECASE,
)
_NUM_RE = re.compile(r"(\d{1,4})\s*/\s*\d{1,4}")
_RARITY_IMG_RE = re.compile(
    r'/Rarity_([A-Z]{1,4})\.png|<img[^>]+alt="([A-Za-z0-9]{1,4})"[^>]+/Rarity_',
    re.IGNORECASE,
)
_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(s: str) -> str:
    return unescape(_TAG_RE.sub("", s)).strip()


def _parse_set_list(html: str) -> list[tuple[int, str, str]]:
    """Return [(number_int, card_name, rarity_code), ...]."""
    out: list[tuple[int, str, str]] = []
    for m in _ROW_RE.finditer(html):
        row = m.group(1)
        cells_html = _CELL_RE.findall(row)
        if len(cells_html) < 3:
            continue
        cells_text = [_strip_html(c) for c in cells_html]

        # Card number ("NNN/DDD")
        num_int = None
        for t in cells_text[:3]:
            m2 = _NUM_RE.search(t)
            if m2:
                num_int = int(m2.group(1))
                break
        if num_int is None:
            continue

        # Card name — non-number, non-empty cell with letters/kana/kanji
        name = None
        for t in cells_text:
            if not t or _NUM_RE.search(t):
                continue
            if any(
                ch.isalpha() or "぀" <= ch <= "ヿ" or "一" <= ch <= "鿿"
                for ch in t
            ):
                name = t
                break
        if name is None:
            continue

        # Rarity — search cell HTML for Rarity_X.png filename
        rarity = None
        for cell_html in cells_html:
            m3 = _RARITY_IMG_RE.search(cell_html)
            if m3:
                code = (m3.group(1) or m3.group(2) or "").upper()
                if code in _JP_RARITIES:
                    rarity = code
                    break
        if rarity is None:
            continue
        out.append((num_int, name, rarity))
    return out


async def _fetch_set(client: httpx.AsyncClient, slug: str) -> list[tuple[int, str, str]]:
    try:
        r = await client.get(f"{BULBAPEDIA}/wiki/{slug}", timeout=25)
    except httpx.HTTPError:
        return []
    if r.status_code != 200:
        return []
    return _parse_set_list(r.text)


async def run(only_set: str | None, dry: bool) -> None:
    await init_db()

    async with SessionLocal() as db:
        q = """
            SELECT s.id, s.name, s.name_en
            FROM sets s
            WHERE s.language = 'ja'
              AND s.set_type IN ('MAIN', 'PROMO_LEGACY')
        """
        if only_set:
            q += f" AND s.id = '{only_set}'"
        set_rows = (await db.execute(text(q))).all()

    log.info(f"JP MAIN + PROMO_LEGACY sets to process: {len(set_rows)}")

    stats = {"sets_scraped": 0, "sets_empty": 0, "cards_updated": 0,
             "cards_skipped_unknown_rarity": 0, "cards_not_matched": 0}

    async with httpx.AsyncClient(
        headers={"User-Agent": UA}, follow_redirects=True
    ) as client:
        for srow in set_rows:
            sid = srow.id
            slug = _SET_TO_SLUG.get(sid)
            if not slug and srow.name_en:
                slug = srow.name_en.strip().replace(" ", "_") + "_(TCG)"
            if not slug:
                continue

            entries = await _fetch_set(client, slug)
            if not entries:
                stats["sets_empty"] += 1
                log.info(f"  [{sid:10s}] empty (slug={slug})")
                continue

            stats["sets_scraped"] += 1
            log.info(f"  [{sid:10s}] {len(entries)} entries from Bulbapedia")

            # Apply
            async with SessionLocal() as db:
                for num_int, card_name, rarity in entries:
                    if rarity not in _JP_RARITIES:
                        stats["cards_skipped_unknown_rarity"] += 1
                        continue
                    if dry:
                        continue
                    r = await db.execute(
                        text("""
                            UPDATE cards SET rarity=:r, updated_at=NOW()
                            WHERE set_id=:s AND number_int=:n
                        """),
                        {"r": rarity, "s": sid, "n": num_int},
                    )
                    if r.rowcount == 0:
                        stats["cards_not_matched"] += 1
                    else:
                        stats["cards_updated"] += r.rowcount
                if not dry:
                    await db.commit()
            await asyncio.sleep(0.2)  # polite

    log.info("=== summary ===")
    for k, v in stats.items():
        log.info(f"  {k}: {v}")
    if dry:
        log.info("MODE: DRY-RUN — no writes")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--set", dest="only_set", help="One JP set id")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    asyncio.run(run(args.only_set, args.dry_run))


if __name__ == "__main__":
    main()
