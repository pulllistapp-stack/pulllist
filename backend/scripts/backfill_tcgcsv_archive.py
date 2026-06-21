"""Backfill TCGplayer price history from TCGCSV daily archives.

TCGCSV (tcgcsv.com) republishes TCGplayer's daily price snapshots into
compressed .7z archives, going back to 2024-02-08. Our own daily cron
only started recording recently, so 90d/30d trending was thin and 1y
charts were essentially empty. Pulling the archive gives us 2+ years
of real history per card overnight.

Sampling strategy (Neon free-tier-aware):
- last 90 days: every day
- 91 - 365 days ago: every 7 days
- 366+ days ago: every 14 days

We only insert rows for cards whose tcgplayer_product_id is set in our
DB (~7,900 cards as of writing), and only for subTypeNames that map to
a known variant. ON CONFLICT DO NOTHING keeps the script idempotent.

Usage:
    python scripts/backfill_tcgcsv_archive.py            # full sampling backfill
    python scripts/backfill_tcgcsv_archive.py --days 30  # last N days only

Attribution: data from https://tcgcsv.com (CptSpaceToaster). Identify
your client by setting USER_AGENT below — TCGCSV bounces unbranded UAs.
"""

from __future__ import annotations

import argparse
import asyncio
import io
import json
import logging
import os
import sys
import tempfile

# Configure logging FIRST so it sticks for everyone, including library code.
os.environ["DEBUG"] = "false"
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s %(levelname)s %(message)s",
)
from datetime import date, timedelta
from pathlib import Path

import httpx
import py7zr
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Force the SQL echo off BEFORE we import the app — settings.debug=True in
# dev makes asyncpg log every parameter, which buries our progress log.
os.environ["DEBUG"] = "false"

from app.database import SessionLocal, engine  # noqa: E402
from app.models import Card, CardPriceSnapshot  # noqa: E402

# Belt-and-suspenders: even if echo was set on engine creation, mute it.
engine.echo = False
logging.getLogger("sqlalchemy").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


POKEMON_CATEGORY = "3"
ARCHIVE_BASE = "https://tcgcsv.com/archive/tcgplayer"
USER_AGENT = "PullList/1.0 (https://pulllist.org; LO)"
TCGCSV_EARLIEST = date(2024, 2, 8)

# TCGCSV subTypeName -> our variant column
VARIANT_MAP = {
    "Normal": "normal",
    "Foil": "holofoil",
    "Holofoil": "holofoil",
    "Reverse Holofoil": "reverseHolofoil",
    "1st Edition": "1stEdition",
    "1st Edition Holofoil": "1stEditionHolofoil",
    "Unlimited": "unlimited",
    "Unlimited Holofoil": "unlimitedHolofoil",
}

log = logging.getLogger("tcgcsv_backfill")
log.setLevel(logging.INFO)


def _sampled_dates(start: date, end: date) -> list[date]:
    """Daily for last 90d, weekly to 365d, biweekly older. Newest first
    so a partial run still produces useful recent history."""
    today = end
    out: list[date] = []
    cursor = end
    while cursor >= start:
        days_back = (today - cursor).days
        out.append(cursor)
        if days_back < 90:
            cursor -= timedelta(days=1)
        elif days_back < 365:
            cursor -= timedelta(days=7)
        else:
            cursor -= timedelta(days=14)
    return out


async def _load_product_map(session) -> dict[int, str]:
    stmt = select(Card.id, Card.tcgplayer_product_id).where(
        Card.tcgplayer_product_id.isnot(None)
    )
    rows = (await session.execute(stmt)).all()
    return {pid: cid for cid, pid in rows if pid is not None}


async def _download_archive(client: httpx.AsyncClient, target_date: date) -> bytes | None:
    url = f"{ARCHIVE_BASE}/prices-{target_date.isoformat()}.ppmd.7z"
    try:
        r = await client.get(url, timeout=300.0)
    except Exception as exc:
        log.warning(f"  ! {target_date}: download failed ({exc})")
        return None
    if r.status_code == 404:
        return None  # archive doesn't exist for this date
    if r.status_code != 200:
        log.warning(f"  ! {target_date}: HTTP {r.status_code}")
        return None
    return r.content


def _parse_archive(archive_bytes: bytes, target_date: date) -> list[dict]:
    """Yield dicts ready to feed into card_price_snapshots, one per product+variant."""
    rows: list[dict] = []
    with tempfile.TemporaryDirectory() as tmp:
        try:
            with py7zr.SevenZipFile(io.BytesIO(archive_bytes), mode="r") as z:
                names = [
                    n for n in z.getnames()
                    if f"/{POKEMON_CATEGORY}/" in n and n.endswith("prices")
                ]
                if not names:
                    return rows
                z.extract(path=tmp, targets=names)
        except Exception as exc:
            log.warning(f"  ! {target_date}: extract failed ({exc})")
            return rows

        for rel in names:
            p = os.path.join(tmp, rel)
            if not os.path.exists(p):
                continue
            try:
                with open(p, "rb") as f:
                    parsed = json.loads(f.read())
            except Exception:
                continue
            for entry in parsed.get("results", []):
                product_id = entry.get("productId")
                if product_id is None:
                    continue
                variant = VARIANT_MAP.get(entry.get("subTypeName"))
                if not variant:
                    continue
                market = entry.get("marketPrice") or entry.get("midPrice")
                if not market or market <= 0:
                    continue
                rows.append({
                    "product_id": product_id,
                    "variant": variant,
                    "market": float(market),
                    "low": _float_or_none(entry.get("lowPrice")),
                    "mid": _float_or_none(entry.get("midPrice")),
                    "high": _float_or_none(entry.get("highPrice")),
                })
    return rows


def _float_or_none(v) -> float | None:
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if f <= 0:
        return None
    return f


async def _insert_for_date(
    session,
    target_date: date,
    parsed_rows: list[dict],
    product_to_card: dict[int, str],
) -> int:
    """Map parsed rows onto card_ids and insert with ON CONFLICT DO NOTHING."""
    snapshot_date = target_date.isoformat()
    to_insert: list[dict] = []
    for r in parsed_rows:
        card_id = product_to_card.get(r["product_id"])
        if not card_id:
            continue
        to_insert.append({
            "card_id": card_id,
            "source": "tcgplayer",
            "variant": r["variant"],
            "snapshot_date": snapshot_date,
            "market_price_usd": r["market"],
            "low_price_usd": r["low"],
            "mid_price_usd": r["mid"],
            "high_price_usd": r["high"],
            "sales_count": None,
        })
    if not to_insert:
        return 0

    # Chunk inserts so a single failure doesn't kill the whole day, and so
    # asyncpg's parameter limit (32767) is not exceeded — 8 columns × 4000
    # rows = 32,000.
    CHUNK = 2000
    total = 0
    for i in range(0, len(to_insert), CHUNK):
        chunk = to_insert[i:i + CHUNK]
        stmt = (
            insert(CardPriceSnapshot)
            .values(chunk)
            .on_conflict_do_nothing(
                index_elements=["card_id", "source", "variant", "snapshot_date"]
            )
        )
        result = await session.execute(stmt)
        total += result.rowcount or 0
    await session.commit()
    return total


async def backfill(start: date, end: date) -> None:
    async with SessionLocal() as session:
        product_to_card = await _load_product_map(session)
    log.info(f"loaded {len(product_to_card)} tcgplayer_product_id -> card_id mappings")

    dates = _sampled_dates(start, end)
    log.info(f"{len(dates)} dates to process ({start} → {end}, newest first)")

    grand_total = 0
    async with httpx.AsyncClient(headers={"User-Agent": USER_AGENT}, timeout=300.0) as client:
        async with SessionLocal() as session:
            for i, d in enumerate(dates, 1):
                archive = await _download_archive(client, d)
                if archive is None:
                    log.info(f"[{i}/{len(dates)}] {d}: no archive")
                    continue
                rows = _parse_archive(archive, d)
                inserted = await _insert_for_date(session, d, rows, product_to_card)
                grand_total += inserted
                log.info(
                    f"[{i}/{len(dates)}] {d}: {len(rows)} entries, {inserted} new rows "
                    f"(total inserted: {grand_total})"
                )
                # Be polite: TCGCSV is a one-person hobby site, archives are
                # cheap but rapid-fire is rude. 250ms is what their FAQ
                # example uses.
                await asyncio.sleep(0.25)
    log.info(f"DONE: total rows inserted: {grand_total}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--days", type=int, default=None,
        help="Only backfill last N days (default: full sampled history back to 2024-02-08)",
    )
    args = parser.parse_args()

    end = date.today()
    if args.days is not None:
        start = end - timedelta(days=args.days)
    else:
        start = TCGCSV_EARLIEST
    if start < TCGCSV_EARLIEST:
        start = TCGCSV_EARLIEST
    asyncio.run(backfill(start, end))


if __name__ == "__main__":
    main()
