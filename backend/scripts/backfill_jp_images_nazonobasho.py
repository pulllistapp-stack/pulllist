"""Backfill image_small for e-Card era JP cards (E1-E5, 364 cards)
via nazonobasho.com — the source LO surfaced 2026-06-30.

Each /cardlist-e{N}/ page renders the full set as a static HTML
gallery: card image filenames follow the clean convention
e{N}_{RARITY}_{NUM:03d}_{name}_copy.jpg. Plain httpx fetch works
(no Playwright lazy-load needed).

Match against DB by (set_id, language='ja', number_int) — same
images_only pattern as the Bulbapedia and learn-book backfills.

Usage:
    python -m scripts.backfill_jp_images_nazonobasho --dry-run
    python -m scripts.backfill_jp_images_nazonobasho --set E3
    python -m scripts.backfill_jp_images_nazonobasho  # full sweep E1-E5
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import re

import httpx
from sqlalchemy import text

from app.database import SessionLocal, init_db

log = logging.getLogger("backfill_jp_images_nazonobasho")

BASE = "https://nazonobasho.com/cardlist-{slug}/"

E_SLUGS = {
    "E1": "e1",
    "E2": "e2",
    "E3": "e3",
    "E4": "e4",
    "E5": "e5",
}

# Card filename: e{N}_{RARITY}_{NUM:03d}_{name}_copy[-{W}x{H}].jpg
_CARD_URL_RE = re.compile(
    r'(https://nazonobasho\.com/wp-content/uploads/\d{4}/\d{2}/'
    r'(e\d+)_[A-Za-z]+_(\d{1,3})_[^"\s]+?)\.(jpg|png|webp)',
    re.IGNORECASE,
)
_SIZE_SUFFIX_RE = re.compile(r"-\d+x\d+$")


def _strip_size_suffix(url: str, ext: str) -> str:
    """Return the original full-res URL (drop the -WxH thumbnail suffix)."""
    full = re.sub(r"-\d+x\d+(\.(?:jpg|png|webp))$", r"\1", url + "." + ext, flags=re.IGNORECASE)
    return full


async def _scrape_set(c: httpx.AsyncClient, slug: str) -> dict[int, str]:
    """Return {number_int: image_url} for a set page."""
    try:
        r = await c.get(BASE.format(slug=slug), timeout=30)
    except httpx.HTTPError as e:
        log.warning(f"  ! {slug}: {e}")
        return {}
    if r.status_code != 200:
        log.warning(f"  ! {slug}: HTTP {r.status_code}")
        return {}

    out: dict[int, str] = {}
    for url_no_ext, set_token, num_str, ext in _CARD_URL_RE.findall(r.text):
        if set_token.lower() != slug.lower():
            continue
        num = int(num_str)
        full = _strip_size_suffix(url_no_ext, ext)
        # Prefer first-seen full-res over later thumb-stripped variants
        if num not in out:
            out[num] = full
    return out


async def run(only: str | None, dry: bool) -> None:
    await init_db()
    targets = {only: E_SLUGS[only]} if only else E_SLUGS

    async with SessionLocal() as db:
        rows = (await db.execute(text("""
            SELECT set_id, number_int
            FROM cards
            WHERE language='ja' AND image_small IS NULL
              AND set_id = ANY(:sids) AND number_int IS NOT NULL
        """), {"sids": list(targets.keys())})).all()
    needed: dict[str, set[int]] = {}
    for sid, ni in rows:
        needed.setdefault(sid, set()).add(ni)
    total_needed = sum(len(s) for s in needed.values())
    log.info(f"Targets: {len(targets)} sets, {total_needed} NULL-image cards")
    if not total_needed:
        log.info("Nothing to do.")
        return

    written = 0
    no_image = 0
    headers = {"User-Agent": "PullList-Catalog/1.0 (+https://pulllist.org)"}
    async with httpx.AsyncClient(headers=headers, follow_redirects=True) as c:
        for idx, (set_id, slug) in enumerate(targets.items(), 1):
            need = needed.get(set_id, set())
            scraped = await _scrape_set(c, slug)
            log.info(f"[{idx}/{len(targets)}] {set_id}: scraped {len(scraped)} (needs {len(need)})")

            if dry:
                matched = sum(1 for n in scraped if n in need)
                log.info(f"   would write {matched} (dry-run)")
                continue

            async with SessionLocal() as db:
                for num, url in scraped.items():
                    if num not in need:
                        continue
                    r = await db.execute(text("""
                        UPDATE cards SET image_small = :img
                        WHERE set_id=:s AND language='ja'
                          AND number_int=:n AND image_small IS NULL
                    """), {"img": url, "s": set_id, "n": num})
                    if r.rowcount:
                        written += 1
                missing = need - set(scraped.keys())
                if missing:
                    no_image += len(missing)
                    log.info(f"   {len(missing)} numbers not on page: {sorted(missing)[:10]}")
                await db.commit()

    log.info("\n=== Summary ===")
    log.info(f"  image_small written:    {written}")
    log.info(f"  needed but not on page: {no_image}")
    if dry:
        log.info("  MODE: DRY-RUN — no writes")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--set", dest="only", help="One E-set id (E1..E5)")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    asyncio.run(run(args.only, args.dry_run))


if __name__ == "__main__":
    main()
