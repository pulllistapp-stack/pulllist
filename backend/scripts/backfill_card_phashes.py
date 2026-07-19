"""Compute a perceptual hash for every card in the catalog and store it
on cards.image_phash so the client-side bulk scan feature can match
camera frames locally (no vision API call needed).

For each card with image_small NOT NULL and image_phash NULL:
  1. Download the image
  2. Compute pHash (16-char hex, 64 bits, DCT-based)
  3. UPDATE cards SET image_phash = ... WHERE id = ...

Resumable: rows that already have a hash are skipped, so re-running
after a partial completion picks up where it left off.

Usage:
    python -m scripts.backfill_card_phashes                    # process all missing
    python -m scripts.backfill_card_phashes --dry-run          # count-only
    python -m scripts.backfill_card_phashes --limit 500        # cap for a smoke test
    python -m scripts.backfill_card_phashes --force            # re-hash everything
    python -m scripts.backfill_card_phashes --only-set sv6     # scope to one set
    python -m scripts.backfill_card_phashes --concurrency 30   # tune HTTP concurrency
"""

from __future__ import annotations

import argparse
import asyncio
import io
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
import imagehash
from PIL import Image
from sqlalchemy import select, update

from app.database import SessionLocal, init_db
from app.models import Card


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("backfill_phashes")


HTTP_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
# Retry once on transient failures (5xx, timeout). Card images live on
# a bunch of different CDNs — Bulbapedia, TCGdex, weserv proxy — and any
# of them can hiccup during a long batch.
RETRIES = 2
COMMIT_EVERY = 100


async def _fetch_and_hash(
    http: httpx.AsyncClient,
    url: str,
) -> str | None:
    """Download the image at url and return its 16-char hex pHash, or
    None on any failure (network, decode, unsupported format)."""
    last_err: Exception | None = None
    for attempt in range(RETRIES + 1):
        try:
            resp = await http.get(url)
            if resp.status_code >= 500 and attempt < RETRIES:
                await asyncio.sleep(0.5 * (attempt + 1))
                continue
            resp.raise_for_status()
            data = resp.content
            img = Image.open(io.BytesIO(data))
            img.load()
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")
            return str(imagehash.phash(img))
        except (httpx.HTTPError, asyncio.TimeoutError) as e:
            last_err = e
            if attempt < RETRIES:
                await asyncio.sleep(0.5 * (attempt + 1))
                continue
        except Exception as e:
            # Decode / format errors — not worth retrying, just report.
            last_err = e
            break
    log.warning("hash failed for %s: %s", url, last_err)
    return None


async def _worker(
    idx: int,
    queue: asyncio.Queue,
    http: httpx.AsyncClient,
    results: dict[str, str | None],
    counter: dict[str, int],
) -> None:
    while True:
        item = await queue.get()
        if item is None:
            queue.task_done()
            return
        card_id, url = item
        h = await _fetch_and_hash(http, url)
        results[card_id] = h
        counter["done"] += 1
        if h is None:
            counter["fail"] += 1
        if counter["done"] % 200 == 0:
            log.info(
                "  %d / %d processed (%d failed, %.1f/s)",
                counter["done"],
                counter["total"],
                counter["fail"],
                counter["done"] / max(1e-3, time.monotonic() - counter["start"]),
            )
        queue.task_done()


async def run(
    dry_run: bool,
    limit: int | None,
    force: bool,
    only_set: str | None,
    concurrency: int,
) -> None:
    await init_db()

    async with SessionLocal() as db:
        stmt = select(Card.id, Card.image_small).where(
            Card.image_small.isnot(None)
        )
        if not force:
            stmt = stmt.where(Card.image_phash.is_(None))
        if only_set:
            stmt = stmt.where(Card.set_id == only_set)
        if limit:
            stmt = stmt.limit(limit)

        rows = (await db.execute(stmt)).all()

    total = len(rows)
    log.info(
        "Backfill scope: %d cards (dry_run=%s, force=%s, only_set=%s, "
        "concurrency=%d)",
        total,
        dry_run,
        force,
        only_set,
        concurrency,
    )

    if dry_run:
        log.info("Dry run — no HTTP fetches, no writes. Exiting.")
        return
    if total == 0:
        log.info("Nothing to do.")
        return

    queue: asyncio.Queue = asyncio.Queue()
    for card_id, url in rows:
        queue.put_nowait((card_id, url))
    for _ in range(concurrency):
        queue.put_nowait(None)  # poison-pill each worker

    results: dict[str, str | None] = {}
    counter = {"done": 0, "fail": 0, "total": total, "start": time.monotonic()}

    limits = httpx.Limits(
        max_connections=concurrency,
        max_keepalive_connections=concurrency,
    )
    async with httpx.AsyncClient(
        timeout=HTTP_TIMEOUT,
        limits=limits,
        headers={"User-Agent": "PullList-phash-backfill/1.0"},
        follow_redirects=True,
    ) as http:
        workers = [
            asyncio.create_task(_worker(i, queue, http, results, counter))
            for i in range(concurrency)
        ]
        await queue.join()
        for w in workers:
            w.cancel()

    log.info(
        "Hashing complete: %d succeeded, %d failed, %.1fs elapsed",
        counter["done"] - counter["fail"],
        counter["fail"],
        time.monotonic() - counter["start"],
    )

    # Write phash values back to the DB in batches. One transaction
    # per COMMIT_EVERY rows so a mid-run crash doesn't lose the whole
    # backfill — the next run picks up from wherever it stopped.
    async with SessionLocal() as db:
        written = 0
        batch: list[tuple[str, str]] = []
        for card_id, phash in results.items():
            if phash is None:
                continue
            batch.append((card_id, phash))
            if len(batch) >= COMMIT_EVERY:
                await _commit_batch(db, batch)
                written += len(batch)
                batch.clear()
                log.info("  wrote %d / %d", written, len(results))
        if batch:
            await _commit_batch(db, batch)
            written += len(batch)
        log.info("Wrote %d image_phash values to DB.", written)


async def _commit_batch(db, batch: list[tuple[str, str]]) -> None:
    for card_id, phash in batch:
        await db.execute(
            update(Card).where(Card.id == card_id).values(image_phash=phash)
        )
    await db.commit()


def _cli() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="Count-only, no writes")
    ap.add_argument("--limit", type=int, default=None, help="Cap number of cards")
    ap.add_argument("--force", action="store_true", help="Re-hash cards even if already set")
    ap.add_argument("--only-set", type=str, default=None, help="Restrict to one set_id")
    ap.add_argument("--concurrency", type=int, default=20, help="HTTP concurrency (default 20)")
    return ap.parse_args()


if __name__ == "__main__":
    args = _cli()
    asyncio.run(
        run(
            dry_run=args.dry_run,
            limit=args.limit,
            force=args.force,
            only_set=args.only_set,
            concurrency=args.concurrency,
        )
    )
