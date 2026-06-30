"""Backfill image_small for PCG1-9 (722 vintage cards) via learn-book.com.

learn-book.com (per LO 2026-06-30) hosts a 356x500 portrait card grid
on each /pokemon-cardlist-pcg{N}/ page, lazy-loaded. Image URLs use a
clean filename convention: pcg{N}{num:03d}.jpg (e.g. pcg9001.jpg =
PCG9 card #1).

Confirmed coverage on probe:
  /pokemon-cardlist-pcg1 .. /pokemon-cardlist-pcg9 → all HTTP 200
  /pokemon-cardlist-vs           → 200 (but we already have VS1 via Bulbapedia)
  /pokemon-cardlist-{e1-5,web,pmcg1-6} → 404 (not indexed)

So this scraper handles ONLY the PCG1-9 cohort (~722 cards).

Lazy-load means we need Playwright to scroll the page and let the
images resolve before scraping the rendered DOM. After scroll, every
card image has a 356x500 natural size + className containing
"wp-image-" which distinguishes them from blog-post thumbnails.

Match against DB by (set_id, language='ja', number_int) — same
images_only pattern as backfill_jp_images_bulbapedia.py.

Usage:
    python -m scripts.backfill_jp_images_learnbook --dry-run
    python -m scripts.backfill_jp_images_learnbook --set PCG9
    python -m scripts.backfill_jp_images_learnbook  # full sweep PCG1-9
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import re

from playwright.async_api import async_playwright
from sqlalchemy import text

from app.database import SessionLocal, init_db

log = logging.getLogger("backfill_jp_images_learnbook")

# Target set ids (our DB) → learn-book.com URL slug suffix.
PCG_SLUGS = {
    "PCG1": "pcg1",
    "PCG2": "pcg2",
    "PCG3": "pcg3",
    "PCG4": "pcg4",
    "PCG5": "pcg5",
    "PCG6": "pcg6",
    "PCG7": "pcg7",
    "PCG8": "pcg8",
    "PCG9": "pcg9",
}

BASE = "https://learn-book.com/pokemon-cardlist-{slug}/"
# Filename pattern: pcg9001.jpg, pcg10052.jpg etc.
_FN_RE = re.compile(r"/pcg(\d+)(\d{3})(?:-\d+x\d+)?\.(?:jpg|png|webp)$", re.IGNORECASE)


async def _scrape_set_page(page, slug: str) -> dict[int, str]:
    """Return {number_int: image_url} for one set page."""
    url = BASE.format(slug=slug)
    # networkidle times out on the bigger PCG3-style pages because of
    # long-poll ad scripts. domcontentloaded + manual scroll/wait is
    # more reliable across the cohort.
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
    except Exception as e:
        log.warning(f"  ! goto {url}: {e}")
        return {}
    # Aggressive scroll — matches the pattern that worked on probe.
    for _ in range(30):
        await page.evaluate("window.scrollBy(0, window.innerHeight)")
        await page.wait_for_timeout(500)
    await page.wait_for_timeout(2000)

    # Collect images with the wp-image-NNN class (excludes blog thumbnails)
    imgs = await page.evaluate(r"""
        () => {
          const out = [];
          for (const i of document.querySelectorAll('img.wp-image-, img[class*="wp-image-"]')) {
            const src = i.currentSrc || i.src || i.dataset.src || '';
            if (!src) continue;
            out.push({
              src,
              w: i.naturalWidth, h: i.naturalHeight,
              cls: i.className,
            });
          }
          return out;
        }
    """)
    out: dict[int, str] = {}
    expected_set_num = int(re.search(r"\d+", slug).group(0))
    for img in imgs:
        src = img.get("src", "")
        m = _FN_RE.search(src)
        if not m:
            continue
        set_num, card_num = int(m.group(1)), int(m.group(2))
        if set_num != expected_set_num:
            # Cross-set image embedded on this page — skip
            continue
        # Prefer original (no -WxH suffix in URL — already stripped by regex)
        # Pick first-seen
        if card_num not in out:
            out[card_num] = src
    return out


async def run(only: str | None, dry: bool) -> None:
    await init_db()
    targets = {only: PCG_SLUGS[only]} if only else PCG_SLUGS

    # Pre-query DB for which numbers need image
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

    written = total_no_match = total_scraped = 0
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(
            locale="ja-JP",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1400, "height": 900},
        )
        page = await ctx.new_page()

        for idx, (set_id, slug) in enumerate(targets.items(), 1):
            need = needed.get(set_id, set())
            log.info(f"[{idx}/{len(targets)}] {set_id}: rendering {slug} ({len(need)} targets)")
            scraped = await _scrape_set_page(page, slug)
            total_scraped += len(scraped)
            log.info(f"   scraped {len(scraped)} card images from page")

            if dry:
                matched = sum(1 for n in scraped if n in need)
                log.info(f"   would write {matched} (dry-run)")
                continue

            async with SessionLocal() as db:
                for num, src in scraped.items():
                    if num not in need:
                        continue
                    r = await db.execute(text("""
                        UPDATE cards SET image_small = :img
                        WHERE set_id = :s AND language='ja'
                          AND number_int = :n AND image_small IS NULL
                    """), {"img": src, "s": set_id, "n": num})
                    if r.rowcount:
                        written += 1
                    else:
                        total_no_match += 1
                await db.commit()

        await browser.close()

    log.info("\n=== Summary ===")
    log.info(f"  images scraped:      {total_scraped}")
    log.info(f"  image_small written: {written}")
    log.info(f"  no DB match (skipped): {total_no_match}")
    if dry:
        log.info("  MODE: DRY-RUN — no writes")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--set", dest="only", help="One set id (e.g. PCG9)")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    asyncio.run(run(args.only, args.dry_run))


if __name__ == "__main__":
    main()
