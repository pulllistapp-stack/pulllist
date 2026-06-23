"""One-off pricing-data cleanup — folds the maintenance SQL we've been
running by hand into a single, dry-runnable script.

Three independent sections; each one is idempotent so re-running is
safe.

  1. fpic-*  (--only fpic)
     The First Partner Illustration eBay snapshot for today's date was
     written before the multi-card-bundle noise filter + low-pricing
     display logic shipped. Delete today's fpic eBay snapshot rows and
     NULL the denormalised Card.market_price_usd so the next
     `snapshot_ebay --set-ids fpic-s1,fpic-s2` writes clean numbers
     with the current filter stack.

  2. tcg-ceiling  (--only tcg-ceiling)
     Pre-PR-#9 the daily TCGCSV sync stored TCGplayer's raw market
     price even when a single-seller typo ($46.63 → $4663) or a
     graded-slab mis-map pushed it above the rarity-appropriate ceiling.
     Delete historical TCGplayer snapshots whose market_price_usd
     exceeds the per-rarity cap (same table the eBay client uses); the
     next daily sync replaces them cleanly. Cards whose denormalised
     market price is also above the cap get NULLed so the catalog
     doesn't keep displaying the spike.

  3. stale  (--only stale)
     Card.market_price_usd never gets cleared when its source goes
     quiet, so vintage cards with zero recent listings keep flashing a
     historical price as if it were current. NULL the field for any
     card whose most recent snapshot of any source is older than
     --stale-days (default 60).

Run:
    # Preview everything (no writes):
    python -m scripts.cleanup_pricing_data --dry-run

    # Run all three sections:
    python -m scripts.cleanup_pricing_data

    # Just one section:
    python -m scripts.cleanup_pricing_data --only fpic
    python -m scripts.cleanup_pricing_data --only tcg-ceiling
    python -m scripts.cleanup_pricing_data --only stale --stale-days 90
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from datetime import date
from pathlib import Path

os.environ.setdefault("DEBUG", "false")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from app.database import SessionLocal, init_db  # noqa: E402
from app.services.ebay_client import (  # noqa: E402
    _DEFAULT_ABS_CEILING,
    _RARITY_ABS_CEILING,
)

log = logging.getLogger("cleanup_pricing_data")


# ── Section 1: fpic snapshot reset ─────────────────────────────────────


async def reset_fpic_snapshots(db: AsyncSession, *, dry_run: bool) -> None:
    today = date.today().isoformat()

    count_q = text(
        "SELECT COUNT(*) FROM card_price_snapshots "
        "WHERE snapshot_date = :d AND source = 'ebay' "
        "AND card_id LIKE 'fpic-%'"
    )
    n_snaps = (await db.execute(count_q, {"d": today})).scalar() or 0

    market_q = text(
        "SELECT COUNT(*) FROM cards "
        "WHERE id LIKE 'fpic-%' AND market_price_usd IS NOT NULL"
    )
    n_prices = (await db.execute(market_q)).scalar() or 0

    log.info(
        "fpic reset preview: %d eBay snapshot rows for %s, %d denormalised "
        "prices to NULL.",
        n_snaps, today, n_prices,
    )
    if dry_run:
        return

    await db.execute(
        text(
            "DELETE FROM card_price_snapshots "
            "WHERE snapshot_date = :d AND source = 'ebay' "
            "AND card_id LIKE 'fpic-%'"
        ),
        {"d": today},
    )
    await db.execute(
        text(
            "UPDATE cards SET market_price_usd = NULL "
            "WHERE id LIKE 'fpic-%'"
        )
    )
    await db.commit()
    log.info("fpic reset committed.")


# ── Section 2: TCGplayer rarity-ceiling cleanup ────────────────────────


def _ceiling_clauses_for_rarities() -> tuple[str, dict]:
    """Build a parameterised SQL fragment for 'is above rarity ceiling',
    one branch per known rarity + a default-fallback branch."""
    branches: list[str] = []
    params: dict[str, float] = {}
    for i, (rarity, cap) in enumerate(_RARITY_ABS_CEILING.items()):
        params[f"r{i}_rarity"] = rarity  # type: ignore[assignment]
        params[f"r{i}_cap"] = cap
        branches.append(
            f"(c.rarity = :r{i}_rarity AND s.market_price_usd > :r{i}_cap)"
        )
    params["default_cap"] = _DEFAULT_ABS_CEILING
    rarity_keys = list(_RARITY_ABS_CEILING.keys())
    rarity_param_names = [f":r{i}_rarity" for i in range(len(rarity_keys))]
    branches.append(
        "((c.rarity IS NULL OR c.rarity NOT IN ("
        + ", ".join(rarity_param_names)
        + ")) AND s.market_price_usd > :default_cap)"
    )
    return " OR ".join(branches), params


async def clean_tcgplayer_ceiling(db: AsyncSession, *, dry_run: bool) -> None:
    where_sql, params = _ceiling_clauses_for_rarities()

    preview_q = text(
        "SELECT COUNT(*) AS n_snaps, "
        "COUNT(DISTINCT s.card_id) AS n_cards "
        "FROM card_price_snapshots s "
        "JOIN cards c ON c.id = s.card_id "
        f"WHERE s.source = 'tcgplayer' AND ({where_sql})"
    )
    row = (await db.execute(preview_q, params)).one()
    n_snaps, n_cards = row.n_snaps, row.n_cards

    bad_market_q = text(
        "SELECT COUNT(*) FROM cards c "
        f"WHERE c.market_price_usd IS NOT NULL AND ("
        + where_sql.replace("s.market_price_usd", "c.market_price_usd") + ")"
    )
    n_market = (await db.execute(bad_market_q, params)).scalar() or 0

    log.info(
        "tcg-ceiling preview: %d snapshot rows over cap across %d cards; "
        "%d denormalised prices also over cap (will NULL).",
        n_snaps, n_cards, n_market,
    )
    if dry_run:
        return

    delete_snaps = text(
        "DELETE FROM card_price_snapshots s "
        "USING cards c "
        f"WHERE s.card_id = c.id AND s.source = 'tcgplayer' AND ({where_sql})"
    )
    await db.execute(delete_snaps, params)

    null_market = text(
        "UPDATE cards c SET market_price_usd = NULL "
        f"WHERE c.market_price_usd IS NOT NULL AND ("
        + where_sql.replace("s.market_price_usd", "c.market_price_usd") + ")"
    )
    await db.execute(null_market, params)
    await db.commit()
    log.info("tcg-ceiling cleanup committed.")


# ── Section 3: stale market_price NULL-out ─────────────────────────────


async def null_stale_market(
    db: AsyncSession, *, dry_run: bool, stale_days: int
) -> None:
    # `card_price_snapshots.snapshot_date` is VARCHAR (ISO YYYY-MM-DD),
    # not DATE, so direct interval comparison errors with
    # "operator does not exist: character varying >= timestamp". Cast
    # to ::date for the comparison; ISO format makes the cast cheap
    # and unambiguous.
    days = int(stale_days)

    preview_sql = (
        "SELECT COUNT(*) FROM cards c "
        "WHERE c.market_price_usd IS NOT NULL "
        "AND NOT EXISTS ("
        "  SELECT 1 FROM card_price_snapshots s "
        "  WHERE s.card_id = c.id "
        f"  AND s.snapshot_date::date >= CURRENT_DATE - INTERVAL '{days} days'"
        ")"
    )
    n = (await db.execute(text(preview_sql))).scalar() or 0

    log.info(
        "stale preview: %d cards with market_price set + no snapshot in "
        "the last %d days.",
        n, stale_days,
    )
    if dry_run:
        return

    update_sql = (
        "UPDATE cards SET market_price_usd = NULL "
        "WHERE market_price_usd IS NOT NULL "
        "AND NOT EXISTS ("
        "  SELECT 1 FROM card_price_snapshots s "
        "  WHERE s.card_id = cards.id "
        f"  AND s.snapshot_date::date >= CURRENT_DATE - INTERVAL '{days} days'"
        ")"
    )
    await db.execute(text(update_sql))
    await db.commit()
    log.info("stale cleanup committed.")


# ── Driver ─────────────────────────────────────────────────────────────


SECTIONS = ("fpic", "tcg-ceiling", "stale")


async def run(
    *, dry_run: bool, only: str | None, stale_days: int
) -> None:
    await init_db()

    selected = SECTIONS if only is None else (only,)
    async with SessionLocal() as db:
        if "fpic" in selected:
            log.info("── Section: fpic snapshot reset ──")
            await reset_fpic_snapshots(db, dry_run=dry_run)
        if "tcg-ceiling" in selected:
            log.info("── Section: TCGplayer rarity-ceiling cleanup ──")
            await clean_tcgplayer_ceiling(db, dry_run=dry_run)
        if "stale" in selected:
            log.info("── Section: stale market_price NULL-out ──")
            await null_stale_market(
                db, dry_run=dry_run, stale_days=stale_days
            )
    log.info("done (dry_run=%s).", dry_run)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--dry-run", action="store_true",
        help="Show counts without writing.",
    )
    p.add_argument(
        "--only", choices=SECTIONS, default=None,
        help="Run only one section (default: all three).",
    )
    p.add_argument(
        "--stale-days", type=int, default=60,
        help="Stale threshold for section 3 (default 60).",
    )
    args = p.parse_args()
    asyncio.run(
        run(dry_run=args.dry_run, only=args.only, stale_days=args.stale_days)
    )


if __name__ == "__main__":
    main()
