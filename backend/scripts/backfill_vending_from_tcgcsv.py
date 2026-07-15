"""Replace JPP-VM* card images with hotlink-safe TCGCSV URLs.

The Bulbapedia scraper landed correct filenames but archives.bulbagarden.net
returns HTTP 403 for most of them when the browser sends a Referer of
www.pulllist.org — LO saw a wall of broken tiles. Only a lucky handful
(Bulbasaur) actually load.

TCGCSV hosts the same cards under three JP Vending groups:
    24206 → JPP-VM1 (Series 1 / Blue)
    24207 → JPP-VM2 (Series 2 / Red)
    24208 → JPP-VM3 (Series 3 / Green)
Their images live on tcgplayer-cdn.tcgplayer.com which allows any
Referer — that's why our S8a family fallback ended up there in the
first place.

This script matches each existing JPP-VM* card by name to the
corresponding TCGCSV product, then writes image_small = _200w and
image_large = _400w URLs. Also stashes tcgplayer_product_id so the
daily price sync can start tracking these.

Name normalisation: our card is stored as "Bulbasaur (Vending S1)";
TCGCSV lists it as "Bulbasaur". Strip the " (Vending S{N})" suffix
before comparing.

Idempotent — re-runs no-op on rows whose image_small already points
at tcgplayer-cdn.

Usage:
    python -m scripts.backfill_vending_from_tcgcsv --dry-run
    python -m scripts.backfill_vending_from_tcgcsv
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import re
import sys
from pathlib import Path

import httpx
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal, init_db  # noqa: E402


log = logging.getLogger("backfill_vending_from_tcgcsv")


TCGCSV_BASE = "https://tcgcsv.com/tcgplayer/85"
UA = "PullList-Catalog/1.0 (+https://pulllist.org)"

# set_id → TCGCSV group id
_GROUPS = {
    "JPP-VM1": 24206,
    "JPP-VM2": 24207,
    "JPP-VM3": 24208,
}

_NAME_STRIP_RE = re.compile(r"\s+\(Vending\s+S\d\)\s*$")


async def _fetch_products(client: httpx.AsyncClient, gid: int) -> list[dict]:
    r = await client.get(f"{TCGCSV_BASE}/{gid}/products", timeout=45)
    r.raise_for_status()
    payload = r.json()
    return payload.get("results") or []


def _normalize_name(name: str) -> str:
    return _NAME_STRIP_RE.sub("", name).strip().lower()


async def run(dry_run: bool) -> None:
    await init_db()

    stats = {"scanned": 0, "matched": 0, "unmatched": 0, "written": 0}

    async with httpx.AsyncClient(headers={"User-Agent": UA}) as client:
        for set_id, gid in _GROUPS.items():
            products = await _fetch_products(client, gid)
            # Build name → (productId, imageUrl) lookup keyed on
            # lowercased base name (no series suffix).
            by_name: dict[str, tuple[int, str]] = {}
            for p in products:
                name = _normalize_name(p.get("name") or "")
                pid = p.get("productId")
                img = p.get("imageUrl")
                if name and pid is not None and img:
                    # First-seen wins if TCGCSV lists variants.
                    by_name.setdefault(name, (int(pid), img))

            async with SessionLocal() as db:
                rows = (await db.execute(
                    text(
                        "SELECT id, name FROM cards WHERE set_id = :s"
                    ),
                    {"s": set_id},
                )).all()

            log.info(
                f"[{set_id}] TCGCSV group {gid}: {len(by_name)} named products; "
                f"DB: {len(rows)} cards"
            )

            for r in rows:
                stats["scanned"] += 1
                key = _normalize_name(r.name or "")
                hit = by_name.get(key)
                if hit is None:
                    stats["unmatched"] += 1
                    log.warning(f"  ? {r.id} — no TCGCSV product for {r.name!r}")
                    continue
                stats["matched"] += 1

                pid, img_small = hit
                # TCGCSV serves _200w and _400w — swap in _400w for image_large.
                img_large = img_small.replace("_200w", "_400w")

                if dry_run:
                    log.info(f"  [would] {r.id} → pid={pid} {img_small[:70]}")
                    continue

                async with SessionLocal() as db:
                    w = await db.execute(
                        text(
                            "UPDATE cards SET "
                            "  image_small = :s, "
                            "  image_large = :l, "
                            "  tcgplayer_product_id = :pid, "
                            "  tcgplayer_url = :url "
                            "WHERE id = :id"
                        ),
                        {
                            "s": img_small,
                            "l": img_large,
                            "pid": pid,
                            "url": f"https://www.tcgplayer.com/product/{pid}",
                            "id": r.id,
                        },
                    )
                    if w.rowcount:
                        stats["written"] += 1
                    await db.commit()

    log.info("=== Vending TCGCSV backfill ===")
    for k, v in stats.items():
        log.info(f"  {k}: {v}")
    if dry_run:
        log.info("MODE: DRY-RUN — no writes")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    asyncio.run(run(args.dry_run))


if __name__ == "__main__":
    main()
