"""Backfill DECK-set logos with real box photos scraped from eBay.

LO wants DECK-type sets (starter decks, build boxes, trainer boxes,
preconstructed decks) to display the actual product photo, matching
how e-commerce sites surface these SKUs.

Phase 1 (backfill_deck_logos_from_sealed.py) handled 28 sets where
we already had a TCGCSV sealed image. This phase 2 targets the
remaining ~90 sets that have no sealed record — searches eBay Browse
API for the set name, takes the top listing's primary image, saves
as logo_url.

Search shape:
    query = f"{name_en} pokemon japanese"  (biased toward JP printing)
    filter to items with imageUrl set
    take the first result

Notes:
- eBay's i.ebayimg.com is already whitelisted in next.config.mjs.
- Uses the shared EbayClient (backend/app/services/ebay_client.py).
  Depends on EBAY_APP_ID + EBAY_APP_CERT_ID env vars — already set
  in GH Actions secrets for daily-ebay-snapshot.yml.
- Only touches DECK sets whose current logo_url is missing or comes
  from s3.limitlesstcg.com (the generic set-mark logo). Leaves
  tcgplayer-cdn logos (phase 1 output) and local /set-logos/ paths
  alone.
- Skips sets with no name_en (SVK, CP2) — can't build a meaningful
  English query. Those two need a JP-name search pass separately.

Idempotent — a re-run just no-ops any set whose logo now points at
i.ebayimg.com.

Usage:
    python -m scripts.backfill_deck_logos_from_ebay --dry-run
    python -m scripts.backfill_deck_logos_from_ebay
    python -m scripts.backfill_deck_logos_from_ebay --limit 5
"""

from __future__ import annotations

import argparse
import asyncio
import html
import logging
import sys
from pathlib import Path

from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal, init_db  # noqa: E402
from app.services.ebay_client import EbayClient, EbayClientError  # noqa: E402


log = logging.getLogger("backfill_deck_logos_from_ebay")


async def _query_ebay_image(
    client: EbayClient, name_en: str
) -> str | None:
    """Return first eBay listing image for a JP Pokemon product name."""
    query = f"{name_en} pokemon japanese"
    try:
        res = await client.browse_search(
            query,
            limit=5,
            filters={"buyingOptions": "FIXED_PRICE"},
        )
    except EbayClientError as e:
        log.warning(f"  eBay search failed for {name_en!r}: {e}")
        return None
    items = res.get("itemSummaries") or []
    for item in items:
        img = (item.get("image") or {}).get("imageUrl")
        if img:
            return img
    return None


async def run(dry_run: bool, limit: int | None) -> None:
    await init_db()

    async with SessionLocal() as db:
        # Target DECK sets whose current logo isn't already a
        # tcgplayer-cdn box photo (phase 1) or an eBay hit (phase 2
        # re-run). Also require name_en so we have a search query.
        rows = (await db.execute(text("""
            SELECT id, name_en
            FROM sets
            WHERE language = 'ja'
              AND set_type = 'DECK'
              AND name_en IS NOT NULL AND name_en <> ''
              AND (
                logo_url IS NULL
                OR logo_url LIKE '%s3.limitlesstcg.com%'
              )
            ORDER BY id
        """))).all()

    log.info(f"DECK sets to search on eBay: {len(rows)}")
    if limit:
        rows = rows[:limit]
        log.info(f"  --limit trimmed to {len(rows)}")

    stats = {"searched": 0, "found": 0, "not_found": 0, "written": 0}

    async with EbayClient() as ebay:
        # Sequential to stay under eBay's per-second throttle; the
        # daily EbaySnapshot job hits ~50 rps and we're small enough
        # to just not race.
        for r in rows:
            stats["searched"] += 1
            # Names may contain HTML entities like "&amp;" from the
            # TCGdex import — decode so the query looks natural.
            name = html.unescape(r.name_en)
            img = await _query_ebay_image(ebay, name)
            if img is None:
                stats["not_found"] += 1
                log.info(f"  ? {r.id:10s} — no result for {name!r}")
                continue
            stats["found"] += 1

            if dry_run:
                log.info(f"  [would] {r.id:10s} → {img[:80]}")
                continue

            async with SessionLocal() as db:
                w = await db.execute(
                    text("UPDATE sets SET logo_url = :u WHERE id = :i"),
                    {"u": img, "i": r.id},
                )
                if w.rowcount:
                    stats["written"] += 1
                    log.info(f"  ✓ {r.id:10s} → {img[:70]}")
                await db.commit()

    log.info("=== eBay DECK logo backfill ===")
    for k, v in stats.items():
        log.info(f"  {k}: {v}")
    if dry_run:
        log.info("MODE: DRY-RUN — no writes")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument(
        "--limit",
        type=int,
        help="Stop after N searches (smoke test).",
    )
    args = p.parse_args()
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    asyncio.run(run(args.dry_run, args.limit))


if __name__ == "__main__":
    main()
