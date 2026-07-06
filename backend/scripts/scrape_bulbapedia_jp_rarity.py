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
_SET_TO_SLUG: dict[str, str] = {**_LOGO_SLUGS}


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


# Row parser. Bulbapedia's Set list rows follow one of these shapes:
#   <tr>
#     <td>001/069</td>
#     <td><a href="...">Card Name</a> ...</td>
#     <td>[type icon]</td>
#     <td>C</td>
#   </tr>
# We grab the FIRST cell that looks like "NNN/DDD", then look for the
# rarity code in later cells.
_ROW_RE = re.compile(
    r"<tr[^>]*>(.*?)</tr>", re.DOTALL | re.IGNORECASE,
)
_CELL_RE = re.compile(
    r"<td[^>]*>(.*?)</td>", re.DOTALL | re.IGNORECASE,
)
_NUM_RE = re.compile(r"^\s*(\d{1,4})\s*/", re.MULTILINE)
_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(s: str) -> str:
    return unescape(_TAG_RE.sub("", s)).strip()


def _parse_set_list(html: str) -> list[tuple[int, str, str]]:
    """Return [(number_int, card_name, rarity_code), ...]."""
    out: list[tuple[int, str, str]] = []
    for m in _ROW_RE.finditer(html):
        row = m.group(1)
        cells = [_strip_html(c) for c in _CELL_RE.findall(row)]
        if len(cells) < 2:
            continue
        # Find the cell that looks like "NNN/DDD"
        num_int = None
        for cell in cells[:2]:  # number is usually first or second
            m2 = _NUM_RE.search(cell)
            if m2:
                num_int = int(m2.group(1))
                break
        if num_int is None:
            continue
        # Card name = the cell with the most alphabetic content that
        # isn't the number cell
        name_candidates = [
            c for c in cells
            if not _NUM_RE.search(c) and len(c) >= 2 and any(
                ch.isalpha() or "぀" <= ch <= "ヿ" or
                "一" <= ch <= "鿿" for ch in c
            )
        ]
        if not name_candidates:
            continue
        name = name_candidates[0]
        # Rarity code — one of the JP tier tokens, usually the LAST cell
        rarity = None
        for cell in reversed(cells):
            code = cell.strip().split()[0] if cell.strip() else ""
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
