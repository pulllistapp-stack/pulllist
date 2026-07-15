"""Backfill missing JP set logos from Limitless CDN.

Probe results (2026-07-15): 12/14 sample DECK sets return HTTP 200 at
    https://s3.limitlesstcg.com/sets/jp/{SET_ID}.png

Limitless is already whitelisted in next.config.mjs so no proxy or
local hosting is needed — the URL drops into ``sets.logo_url`` and
renders in the browser directly, hotlink-safe.

Only touches sets where logo_url IS NULL and the Limitless URL
returns 200. Case-insensitive fallback covers PullList's mixed-case
convention (SVLN vs svLN etc.).

Idempotent — a second run over sets that already have a logo skips
them; ones we couldn't resolve first pass stay NULL for a later
source (Bulbapedia scrape + local save via
backfill_jp_set_logos.py, or manual).

Usage:
    python -m scripts.backfill_jp_set_logos_limitless --dry-run
    python -m scripts.backfill_jp_set_logos_limitless
    python -m scripts.backfill_jp_set_logos_limitless --only DECK
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

import httpx
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal, init_db  # noqa: E402


log = logging.getLogger("backfill_jp_set_logos_limitless")


BASE = "https://s3.limitlesstcg.com/sets/jp"
UA = "PullList-Catalog/1.0 (+https://pulllist.org)"
SEM_LIMIT = 8


async def _head(client: httpx.AsyncClient, url: str) -> bool:
    try:
        r = await client.head(url, timeout=15)
    except httpx.HTTPError:
        return False
    return r.status_code == 200


async def _probe(client: httpx.AsyncClient, set_id: str) -> str | None:
    """Try {set_id}.png then {set_id.lower()}.png; return first that 200s."""
    for candidate in {set_id, set_id.lower(), set_id.upper()}:
        url = f"{BASE}/{candidate}.png"
        if await _head(client, url):
            return url
    return None


async def run(only_type: str | None, dry_run: bool) -> None:
    await init_db()

    async with SessionLocal() as db:
        base_sql = (
            "SELECT id, set_type, name FROM sets "
            "WHERE language = 'ja' AND logo_url IS NULL"
        )
        params: dict[str, str] = {}
        if only_type:
            base_sql += " AND set_type = :t"
            params["t"] = only_type
        rows = (await db.execute(text(base_sql), params)).all()

    log.info(f"no-logo JP sets to probe: {len(rows)}")

    stats = {"probed": 0, "resolved": 0, "unresolved": 0, "written": 0}
    sem = asyncio.Semaphore(SEM_LIMIT)

    async with httpx.AsyncClient(headers={"User-Agent": UA}) as client:

        async def worker(sid: str) -> tuple[str, str | None]:
            async with sem:
                return sid, await _probe(client, sid)

        results = await asyncio.gather(*[worker(r.id) for r in rows])

    async with SessionLocal() as db:
        for sid, url in results:
            stats["probed"] += 1
            if url is None:
                stats["unresolved"] += 1
                continue
            stats["resolved"] += 1
            if dry_run:
                log.info(f"  [would] {sid} → {url}")
                continue
            r = await db.execute(
                text(
                    "UPDATE sets SET logo_url = :u "
                    "WHERE id = :i AND logo_url IS NULL"
                ),
                {"u": url, "i": sid},
            )
            if r.rowcount:
                stats["written"] += 1
        if not dry_run:
            await db.commit()

    log.info("=== Limitless logo backfill ===")
    for k, v in stats.items():
        log.info(f"  {k}: {v}")
    if dry_run:
        log.info("MODE: DRY-RUN — no writes")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--only", help="Limit to a single set_type (e.g. DECK)")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    asyncio.run(run(args.only, args.dry_run))


if __name__ == "__main__":
    main()
