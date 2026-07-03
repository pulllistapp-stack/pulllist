"""Batch import missing JP sets from Limitless.

For each set id in the input list:
1. GET https://limitlesstcg.com/cards/jp/{id} → parse title + card count
2. Insert Set row (id / name / release_date / series / language='ja')
3. Call scrape_limitless_jp._scrape_set to grab cards + images
4. _upsert(images_only=False) to write cards

Skips sets already in DB. Idempotent.

Neo era is separate (TCGdex-only) — handled by a second script.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import re
from datetime import date

import httpx
from sqlalchemy import select

from app.database import SessionLocal, init_db
from app.models import Set
from scripts.scrape_limitless_jp import _scrape_set, _upsert

log = logging.getLogger("seed_limitless_batch")

BASE = "https://limitlesstcg.com/cards/jp/"

# Mainline sets missing from us that Limitless has. Skip pure promo
# pools (BWP/XYP/SMP/SVP — already covered by our JPP-* sets).
# Skip 25th Anniversary / SwSh sub-sets duplicating what we have.
TARGET_IDS = [
    # BW era mainline (Dec 2010 - Mar 2013)
    "BW1b", "BW1w", "BW2", "BW3h", "BW3p", "BW4",
    "BW5n", "BW5z", "BW6c", "BW6f", "BW7", "BW8f", "BW8n", "BW9",
    "BGS",  # 20th anniversary BW? not exactly but let's see
    "BKB", "BKR", "BKW", "BKZ", "BKc", "BKt", "BKv",  # BW promos & sub-sets
    "BTV", "CS1", "DS", "EBB", "GBR",
    "MDB",  # Beat of the Frontier
    "MGg", "MGm",  # Megalo Cannon sub-sets
    "PBG", "PPD",  # PokéKyun collection
    "SC", "SZD", "WAK",
    # HGSS / Legend era
    "HS", "HSP", "HSZ", "HXY",
    "KK", "KLD",  # Advent of Arceus / Reviving Legends
    # SM sub-sets and starters we don't have
    "SM10a", "SM11",
    "SM1p", "SM2p", "SM3p", "SM4p", "SM5p",
    "SMA", "SMB", "SMC", "SMD", "SME", "SMF", "SMG",
    "SMH", "SMI", "SMJ", "SMK", "SML", "SMM", "SMN",
    "SMP1", "SNPo", "SNPr",
    # XY concept packs & sub-sets we don't have
    "XY", "XY11b", "XY11r", "XY1x", "XY1y", "XY5g", "XY5t", "XY8r",
    "XYA", "XYB", "XYC", "XYD", "XYE", "XYF", "XYG", "XYH",
    # SwSh + SV sub-sets and specials we don't have
    "SB", "SC2", "SCd", "SCr", "SD", "SEF", "SEK", "SF",
    "SGG", "SGI", "SH", "SI", "SJ", "SK", "SLD", "SLL",
    "SN", "SO", "SP1", "SP2", "SP3", "SP4", "SP5", "SP6",
    "SPD", "SPZ",
    "SAf", "SAg", "SAl", "SAr", "SAw",
    "SV1a", "SVAL", "SVAM", "SVAW", "SVB", "SVC", "SVD",
    "SVEL", "SVEM", "SVF", "SVG", "SVHK", "SVHM", "SVI",
    "SVJL", "SVJP", "SVM", "SVN", "SVOD", "SVOM", "SVP1",
    # Mega era sub-sets we don't have
    "MA", "MBD", "MBG", "MC", "MP1", "MMBp", "MMBs",
    # Special / world championships
    "WCS23", "X30", "Y30", "20th",
]


def _parse_date(raw: str) -> date | None:
    """Limitless page titles sometimes carry "17 Dec 10" style dates but
    those live in the set index, not the /cards/jp/{id} page. Skip
    parsing the date from the page — leave release_date NULL for now
    and let a follow-up sync fill it in."""
    return None


async def _fetch_title(c: httpx.AsyncClient, sid: str) -> str | None:
    r = await c.get(BASE + sid, timeout=20)
    if r.status_code != 200:
        return None
    m = re.search(r"<title>([^<]+)</title>", r.text)
    if not m:
        return None
    title = m.group(1)
    # "Name (ID) – Limitless"
    return title.split(" (")[0].strip()


async def run(only: str | None, dry: bool, limit: int | None) -> None:
    await init_db()
    async with SessionLocal() as db:
        have = {r[0] for r in (await db.execute(select(Set.id).where(Set.language == "ja"))).all()}
    targets = [only] if only else [s for s in TARGET_IDS if s not in have]
    if limit:
        targets = targets[:limit]
    log.info(f"To import: {len(targets)} sets")

    headers = {"User-Agent": "PullList-Catalog/1.0 (+https://pulllist.org)"}
    seeded = imported_cards = failed = 0
    async with httpx.AsyncClient(headers=headers, follow_redirects=True) as c:
        for i, sid in enumerate(targets, 1):
            title = await _fetch_title(c, sid)
            if not title:
                log.warning(f"[{i}/{len(targets)}] {sid} — no title (404?)")
                failed += 1
                continue

            log.info(f"[{i}/{len(targets)}] {sid} — {title}")
            if dry:
                continue

            async with SessionLocal() as db:
                # Insert set row
                existing = await db.get(Set, sid)
                if existing is None:
                    db.add(Set(
                        id=sid, name=title, series="Japanese",
                        language="ja",
                    ))
                    await db.commit()
                    seeded += 1

            # Scrape cards
            try:
                cards = await _scrape_set(c, sid)
                if cards:
                    async with SessionLocal() as db:
                        n = await _upsert(db, cards, images_only=False)
                        log.info(f"   wrote {n} cards")
                        imported_cards += n
            except Exception as e:
                log.warning(f"   scrape failed: {e}")

    log.info("\n=== Summary ===")
    log.info(f"  Sets seeded: {seeded}")
    log.info(f"  Cards written: {imported_cards}")
    log.info(f"  Failed (no title): {failed}")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--set", dest="only", help="One set id (test)")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--limit", type=int, help="Cap number of sets processed")
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    asyncio.run(run(args.only, args.dry_run, args.limit))


if __name__ == "__main__":
    main()
