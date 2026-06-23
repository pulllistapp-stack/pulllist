"""Backfill Card.tcgplayer_product_id by resolving each card against
TCGplayer's search page and grabbing the first product hit.

We need this for manually-seeded sets (First Partner Illustration
Collection, future promo bundles) that don't flow through pokemontcg.io
— without the product id, our affiliate wrapper falls through to a
search URL instead of the exact product page, costing one click of UX
friction (the Impact cookie still drops on the search landing, so the
commission isn't lost, but the conversion rate is lower).

Usage:
    # Default — fill missing ids for the manual fpic-* sets:
    python -m scripts.backfill_tcgplayer_product_id

    # Specific set:
    python -m scripts.backfill_tcgplayer_product_id --set-ids fpic-s2

    # Refresh (overwrite existing ids — rare, for stale rows):
    python -m scripts.backfill_tcgplayer_product_id --refresh

    # Dry-run (don't write, just log what would be set):
    python -m scripts.backfill_tcgplayer_product_id --dry-run
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import re
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
from sqlalchemy import select, update

from app.database import SessionLocal, init_db
from app.models import Card

log = logging.getLogger("backfill_tcgplayer_product_id")

TCGPLAYER_SEARCH = (
    "https://www.tcgplayer.com/search/pokemon/product"
    "?q={q}&productLineName=pokemon&view=grid"
)

# TCGplayer search result links look like
# <a href="/product/673436/pokemon-first-partner-collection-2026...">.
# Grab the numeric id from the first match; the search result page is
# server-rendered enough that the first product appears in the raw
# HTML, so a plain httpx GET is sufficient (no browser needed).
_PRODUCT_HREF_RE = re.compile(r'/product/(\d+)/[A-Za-z0-9-]+')

# Realistic-ish UA. TCGplayer's anti-bot is mild on the public search
# page (no Cloudflare gate, no captcha for moderate volume); a vanilla
# browser UA + an Accept header avoids the most basic 403s.
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# Throttle between requests so we don't rate-limit ourselves out.
# TCGplayer doesn't publish a documented rate cap; 800 ms is comfortable.
_THROTTLE_S = 0.8

# Default — every manually-seeded set that won't flow through
# pokemontcg.io's daily sync.
_DEFAULT_SETS = ("fpic-s1", "fpic-s2")


def build_query(name: str, number: str | None) -> str:
    parts = [name.strip()]
    if number:
        # Strip the "/<total>" suffix if present — TCGplayer keys promos
        # on the bare card number ("047" not "047/9").
        parts.append(number.strip().split("/")[0])
    return " ".join(p for p in parts if p)


async def fetch_first_product_id(
    client: httpx.AsyncClient, query: str
) -> int | None:
    url = TCGPLAYER_SEARCH.format(q=urllib.parse.quote_plus(query))
    try:
        r = await client.get(url, headers=_HEADERS, timeout=20.0)
    except httpx.HTTPError as exc:
        log.warning(f"  ! fetch failed for {query!r}: {exc}")
        return None
    if r.status_code != 200:
        log.warning(f"  ! HTTP {r.status_code} for {query!r}")
        return None
    match = _PRODUCT_HREF_RE.search(r.text)
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


async def backfill(
    set_ids: tuple[str, ...],
    refresh: bool,
    dry_run: bool,
) -> None:
    await init_db()

    async with SessionLocal() as db:
        stmt = select(Card).where(Card.set_id.in_(set_ids))
        if not refresh:
            stmt = stmt.where(Card.tcgplayer_product_id.is_(None))
        cards = list((await db.execute(stmt)).scalars())

    log.info(
        f"Selected {len(cards)} card(s) across sets={list(set_ids)} "
        f"(refresh={refresh}, dry_run={dry_run})"
    )

    if not cards:
        log.info("Nothing to do.")
        return

    resolved: list[tuple[str, int]] = []
    misses: list[str] = []
    async with httpx.AsyncClient() as client:
        for i, card in enumerate(cards, 1):
            query = build_query(card.name, card.number)
            pid = await fetch_first_product_id(client, query)
            if pid is None:
                misses.append(card.id)
                log.info(f"[{i}/{len(cards)}] {card.id} {card.name!r:30s} — no product match")
            else:
                resolved.append((card.id, pid))
                log.info(f"[{i}/{len(cards)}] {card.id} {card.name!r:30s} → product {pid}")
            await asyncio.sleep(_THROTTLE_S)

    if dry_run:
        log.info(f"Dry run: would update {len(resolved)} row(s), {len(misses)} miss(es).")
        return

    if not resolved:
        log.info("No rows to write.")
        return

    async with SessionLocal() as db:
        for card_id, pid in resolved:
            await db.execute(
                update(Card)
                .where(Card.id == card_id)
                .values(tcgplayer_product_id=pid)
            )
        await db.commit()
    log.info(f"Wrote {len(resolved)} tcgplayer_product_id(s). Misses: {len(misses)}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--set-ids",
        default=",".join(_DEFAULT_SETS),
        help="Comma-separated set ids to backfill (default: fpic-s1,fpic-s2)",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Re-resolve cards that already have a tcgplayer_product_id",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log what would be written without touching the DB",
    )
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    set_ids = tuple(s.strip() for s in args.set_ids.split(",") if s.strip())
    asyncio.run(backfill(set_ids=set_ids, refresh=args.refresh, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
