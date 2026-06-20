"""Scrape Japanese promo cards from pokemon-card.com (official).

The official site lazy-loads results behind a JS paginator
(?regulation_sidebar_form=P&pg=N). Each page returns ~10 cards drawn
from across every promo era (DP1..DP4, SV1..SV4, M5 etc.), so we walk
pages 1..N until empty rather than filtering per era. Set code is
read off each card's image URL path and mapped to one of our JPP-*
era Set ids at import time.

Run locally (needs a real browser):

    pip install playwright httpx
    playwright install chromium

    # quick probe
    python -m scripts.scrape_jp_promos --max-pages 5

    # full sweep (slow — ~1 sec/page, expect 5-15 min for all promos)
    python -m scripts.scrape_jp_promos --max-pages 999

Output: backend/data/scraped/promos_all.json (one record per card,
JSON-serialisable). The sibling import_jp_promos.py consumes this.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path

from playwright.async_api import async_playwright

log = logging.getLogger("scrape_jp_promos")

OUT_PATH = Path(__file__).resolve().parent.parent / "data" / "scraped" / "promos_all.json"
SEARCH_URL = "https://www.pokemon-card.com/card-search/?regulation_sidebar_form=P&pg={pg}"
THROTTLE_MS = 700


# pokemon-card.com set-code prefix -> our JPP-* era. Anything not in
# the map falls back to JPP-P (the generic "P Promotional" bucket).
SETCODE_TO_ERA: dict[str, str] = {
    # Newest first
    "M":     "JPP-SV",  # M5+ = SV-era promos in their schema
    "SV":    "JPP-SV",
    "S":     "JPP-S",   # S/Sword & Shield (S1..S12)
    "SM":    "JPP-SM",
    "XY":    "JPP-XY",
    "BW":    "JPP-BW",
    "L":     "JPP-L",
    "DPt":   "JPP-DPt",
    "DP":    "JPP-DP",
    "PCG":   "JPP-PCG",
    "ADV":   "JPP-ADV",
    "PPP":   "JPP-PPP",
}


def _setcode_to_era(set_code: str) -> str:
    """Map a pokemon-card.com set code (e.g. 'DP1', 'SV5K', 'M5') to our
    JPP-* era id. Longest-prefix match wins so 'DPt' beats 'DP' for
    DPt-era codes."""
    sc = set_code.upper()
    # Try long prefixes first
    for prefix in sorted(SETCODE_TO_ERA.keys(), key=len, reverse=True):
        if sc.startswith(prefix.upper()):
            return SETCODE_TO_ERA[prefix]
    return "JPP-P"


@dataclass
class ScrapedPromo:
    era_id: str           # JPP-SV etc
    set_code: str         # M5, DP1, etc - pokemon-card.com's notation
    filename: str         # raw filename like "050220_P_TOROPIUSU"
    name_jp: str          # alt text on the img
    image_url: str        # absolute URL on pokemon-card.com
    detail_url: str       # parent <a> href if available


async def _harvest_page(page) -> list[ScrapedPromo]:
    raw = await page.evaluate(r"""
    () => {
        const out = [];
        for (const img of document.querySelectorAll('img')) {
            const src = img.src || '';
            const m = src.match(/card_images\/large\/([^/]+)\/([^.]+)\.(?:jpg|png|gif)/i);
            if (!m) continue;
            const parent = img.closest('a');
            out.push({
                src,
                alt: img.alt || '',
                href: parent ? parent.href : '',
                set_code: m[1],
                filename: m[2],
            });
        }
        return out;
    }
    """)
    return [
        ScrapedPromo(
            era_id=_setcode_to_era(c["set_code"]),
            set_code=c["set_code"],
            filename=c["filename"],
            name_jp=c["alt"],
            image_url=c["src"],
            detail_url=c["href"],
        )
        for c in raw
    ]


async def run(max_pages: int) -> None:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    all_cards: list[ScrapedPromo] = []
    seen_urls: set[str] = set()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
            ),
            locale="ja-JP",
        )
        page = await ctx.new_page()

        empty_streak = 0
        for pg in range(1, max_pages + 1):
            url = SEARCH_URL.format(pg=pg)
            try:
                await page.goto(url, wait_until="networkidle", timeout=20000)
            except Exception as e:
                log.warning(f"  ! pg={pg} navigation: {e}")
                continue
            await page.wait_for_timeout(THROTTLE_MS)
            cards = await _harvest_page(page)
            # Dedup against what we've already seen
            fresh = [c for c in cards if c.image_url not in seen_urls]
            for c in fresh:
                seen_urls.add(c.image_url)
            all_cards.extend(fresh)

            if not fresh:
                empty_streak += 1
                log.info(f"  pg={pg:>3}: 0 fresh cards (streak={empty_streak})")
                if empty_streak >= 3:
                    log.info(f"  3 empty pages in a row - stopping early at pg={pg}")
                    break
            else:
                empty_streak = 0
                log.info(f"  pg={pg:>3}: +{len(fresh)} cards (total {len(all_cards)})")

        await browser.close()

    OUT_PATH.write_text(
        json.dumps([asdict(c) for c in all_cards], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    # Per-era summary
    from collections import Counter
    by_era = Counter(c.era_id for c in all_cards)
    log.info(f"\n=== Scraped {len(all_cards)} cards across {len(by_era)} eras ===")
    for era, n in sorted(by_era.items()):
        log.info(f"  {era}: {n} cards")
    log.info(f"\n  written -> {OUT_PATH}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-pages", type=int, default=200, help="Page ceiling (default 200)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    asyncio.run(run(args.max_pages))


if __name__ == "__main__":
    main()
