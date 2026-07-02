"""Download every EN card image in our catalog to a local backup dir.

Rationale:
    LO wants an offline copy of the English catalog artwork so a
    pokemontcg.io / TCGdex outage doesn't leave the site staring at
    broken thumbnails. All four upstream hosts (pokemontcg.io,
    scrydex.com, tcgplayer-cdn, pokemon.com) are public CDNs with
    no auth and no per-request cost to us — this is bandwidth only.

Layout:
    {backup_root}/en/{set_id}/{card_id}_small.{ext}
    {backup_root}/en/{set_id}/{card_id}_large.{ext}
    {backup_root}/en/_failures.jsonl   ← any URL that never resolved
    {backup_root}/en/_manifest.json    ← run stats

Runtime notes:
    - Idempotent — files already on disk are skipped. Interrupt and
      re-run at will; each run resumes exactly where the last one
      stopped.
    - Concurrency capped at 10 (semaphore); polite for the CDNs
      without dragging the total wall clock out.
    - Retry-once on network hiccup; a second failure lands in
      _failures.jsonl for later manual triage.

Run:
    python -m scripts.backup_en_card_images \
        --dest "C:/Users/Jinwon/Desktop/PullList_ImageBackup"
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DEBUG", "false")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

import httpx  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import Card  # noqa: E402


log = logging.getLogger("backup_en_card_images")


USER_AGENT = "PullList/1.0 (backup mirror; https://pulllist.org)"
CONCURRENCY = 10
PROGRESS_EVERY = 500


def _safe_ext(url: str) -> str:
    """Extract file extension from URL, default to .png."""
    tail = url.split("?")[0].rsplit(".", 1)
    if len(tail) == 2 and 2 <= len(tail[1]) <= 5:
        ext = tail[1].lower()
        if ext in {"png", "jpg", "jpeg", "webp", "gif"}:
            return "." + ext
    return ".png"


async def _download_one(
    client: httpx.AsyncClient,
    url: str,
    dest: Path,
    sem: asyncio.Semaphore,
    stats: dict,
) -> tuple[bool, str | None]:
    """Return (success, error_string). Never raises."""
    if dest.exists():
        stats["skipped"] += 1
        return True, None
    dest.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(2):
        try:
            async with sem:
                r = await client.get(url, timeout=30.0)
            if r.status_code == 200 and r.content:
                dest.write_bytes(r.content)
                stats["downloaded"] += 1
                stats["bytes"] += len(r.content)
                return True, None
            # 404 / 403 → skip retry, log
            if r.status_code in (404, 403):
                return False, f"HTTP {r.status_code}"
        except httpx.HTTPError as e:
            if attempt == 1:
                return False, f"{type(e).__name__}: {e}"
            await asyncio.sleep(1.0)
    return False, "retries exhausted"


async def main(dest_root: Path) -> None:
    en_root = dest_root / "en"
    en_root.mkdir(parents=True, exist_ok=True)
    failures_path = en_root / "_failures.jsonl"
    manifest_path = en_root / "_manifest.json"

    log.info("querying EN card image list…")
    async with SessionLocal() as db:
        rows = (
            await db.execute(
                select(
                    Card.id, Card.set_id, Card.image_small, Card.image_large
                ).where(
                    Card.language == "en",
                    (Card.image_small.isnot(None)) | (Card.image_large.isnot(None)),
                ).order_by(Card.set_id, Card.number_int)
            )
        ).all()
    log.info("cards with images: %d", len(rows))

    stats = {
        "cards_scanned": 0,
        "downloaded": 0,
        "skipped": 0,
        "failed": 0,
        "bytes": 0,
    }
    sem = asyncio.Semaphore(CONCURRENCY)
    started = time.time()

    fail_log = failures_path.open("a", encoding="utf-8")
    try:
      async with httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT},
        follow_redirects=True,
      ) as client:
        tasks: list[asyncio.Task] = []

        async def _one(url: str, dest: Path, card_id: str, kind: str):
            ok, err = await _download_one(client, url, dest, sem, stats)
            if not ok:
                stats["failed"] += 1
                fail_log.write(
                    json.dumps(
                        {"card_id": card_id, "kind": kind, "url": url, "error": err},
                        ensure_ascii=False,
                    )
                    + "\n"
                )
                fail_log.flush()

        for card_id, set_id, img_small, img_large in rows:
            stats["cards_scanned"] += 1
            set_dir = en_root / (set_id or "_unset")
            if img_small:
                dest = set_dir / f"{card_id}_small{_safe_ext(img_small)}"
                tasks.append(asyncio.create_task(_one(img_small, dest, card_id, "small")))
            if img_large:
                dest = set_dir / f"{card_id}_large{_safe_ext(img_large)}"
                tasks.append(asyncio.create_task(_one(img_large, dest, card_id, "large")))

            if stats["cards_scanned"] % PROGRESS_EVERY == 0:
                # Drain current queue before printing progress so numbers
                # reflect actually-done work, not scheduled work.
                await asyncio.sleep(0)
                elapsed = time.time() - started
                mb = stats["bytes"] / 1024 / 1024
                log.info(
                    "  [%d/%d] downloaded=%d skipped=%d failed=%d  %.1fMB  %.0fs",
                    stats["cards_scanned"], len(rows),
                    stats["downloaded"], stats["skipped"], stats["failed"],
                    mb, elapsed,
                )

        # Drain remaining tasks
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    finally:
        fail_log.close()

    elapsed = time.time() - started
    stats["elapsed_seconds"] = round(elapsed, 1)
    stats["dest_root"] = str(en_root)
    stats["total_mb"] = round(stats["bytes"] / 1024 / 1024, 1)
    manifest_path.write_text(
        json.dumps(stats, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    log.info("=== summary ===")
    for k, v in stats.items():
        log.info("  %s: %s", k, v)


def cli() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--dest",
        default=r"C:\Users\Jinwon\Desktop\PullList_ImageBackup",
        help="Root directory for the backup (an 'en/' subdir is created inside).",
    )
    args = p.parse_args()
    asyncio.run(main(Path(args.dest)))


if __name__ == "__main__":
    cli()
