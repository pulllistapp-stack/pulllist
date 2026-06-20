"""Import scraped JP promo cards into the DB + mirror their images.

Reads data/scraped/promos_all.json produced by scrape_jp_promos.py,
downloads each card image into frontend/public/promo-cards/{id}.jpg,
and inserts a Card row with language='ja' and set_id pointing at the
matching JPP-* era.

Card id format: JPP-{set_code}-{filename}, e.g. "JPP-M5-050220_P_TOROPIUSU".
The opaque pokemon-card.com filename is preserved as the local id so
we can re-run idempotently without duplicating rows when the scraper
returns the same card.

Usage:
    python -m scripts.import_jp_promos
    python -m scripts.import_jp_promos --dry-run
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
from pathlib import Path

import httpx
from sqlalchemy import select

from app.database import SessionLocal, init_db
from app.models import Card, Set

log = logging.getLogger("import_jp_promos")

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRAPED_PATH = REPO_ROOT / "backend" / "data" / "scraped" / "promos_all.json"
MIRROR_DIR = REPO_ROOT / "frontend" / "public" / "promo-cards"


async def _download(client: httpx.AsyncClient, url: str, dest: Path) -> bool:
    if dest.exists():
        return True  # idempotent re-run
    try:
        r = await client.get(url, timeout=30)
        r.raise_for_status()
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(r.content)
        return True
    except httpx.HTTPError as e:
        log.warning(f"  ! download {url}: {e}")
        return False


async def run(dry: bool) -> None:
    if not SCRAPED_PATH.exists():
        log.error(f"No scraped data at {SCRAPED_PATH} — run scrape_jp_promos.py first.")
        return
    promos = json.loads(SCRAPED_PATH.read_text(encoding="utf-8"))
    log.info(f"Loaded {len(promos)} scraped promos.")

    await init_db()

    # Confirm the JPP-* eras exist (Phase 1 should have seeded them).
    async with SessionLocal() as db:
        present = {
            row[0] for row in (
                await db.execute(select(Set.id).where(Set.id.like("JPP-%")))
            ).all()
        }
    needed = {p["era_id"] for p in promos}
    missing = needed - present
    if missing:
        log.warning(f"era Set rows missing: {missing} (run seed_promo_eras first)")

    MIRROR_DIR.mkdir(parents=True, exist_ok=True)

    headers = {"User-Agent": "PullList-Catalog/1.0"}
    inserted = 0
    updated = 0
    img_ok = 0
    img_fail = 0

    async with httpx.AsyncClient(headers=headers) as http:
        for p in promos:
            card_id = f"JPP-{p['set_code']}-{p['filename']}"
            ext = p["image_url"].rsplit(".", 1)[-1].lower()
            if ext not in ("jpg", "jpeg", "png", "gif", "webp"):
                ext = "jpg"
            local_filename = f"{card_id}.{ext}"
            local_rel = f"/promo-cards/{local_filename}"
            local_abs = MIRROR_DIR / local_filename

            if not dry:
                ok = await _download(http, p["image_url"], local_abs)
                if ok:
                    img_ok += 1
                else:
                    img_fail += 1
                    continue

                async with SessionLocal() as db:
                    row = await db.get(Card, card_id)
                    if row is None:
                        row = Card(
                            id=card_id,
                            language="ja",
                            set_id=p["era_id"],
                            name=p["name_jp"],
                            name_local=p["name_jp"],
                            image_small=local_rel,
                            image_large=local_rel,
                        )
                        db.add(row)
                        inserted += 1
                    else:
                        row.name = p["name_jp"]
                        row.name_local = p["name_jp"]
                        row.image_small = local_rel
                        row.image_large = local_rel
                        row.set_id = p["era_id"]
                        row.language = "ja"
                        updated += 1
                    await db.commit()

    log.info("\n=== Summary ===")
    log.info(f"  cards inserted : {inserted}")
    log.info(f"  cards updated  : {updated}")
    log.info(f"  images ok      : {img_ok}")
    log.info(f"  images failed  : {img_fail}")
    if dry:
        log.info("  MODE           : DRY RUN")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    asyncio.run(run(args.dry_run))


if __name__ == "__main__":
    main()
