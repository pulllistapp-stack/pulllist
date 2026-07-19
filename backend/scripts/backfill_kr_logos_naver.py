"""Backfill remaining KR set logo_url via Naver Image Search scrape.

pokemonstore.co.kr covered current-stock SV/MEGA era (56 sets), and
collectory covered pre-2016 (7 sets), and LO hand-provided a few
more (SV6 / MEGA starter set / etc.). ~143 KR sets are still without
a logo — mostly SM / S / BW / XY era where the KR store no longer
carries the physical product but Naver still surfaces user-uploaded
product photos on 스마트스토어, 블로그, 갤러리.

Naver Image Search is bot-tolerant (Google's headless-Chrome bot
detection is aggressive; Naver isn't) and Korean-first, which
matches our target catalog exactly. Standard Playwright scrape:

  * Query `{set.name} 포켓몬 카드` on
    https://search.naver.com/search.naver?where=image&query=...
  * Skip the N페이 promo banner that always occupies slot 0.
  * Take the first search.pstatic.net image whose `src=` param
    decodes to a real seller/blog URL — decode the param out so we
    store the underlying image, not Naver's redirect wrapper.

Idempotent — sets that already carry a logo_url are skipped unless
--refresh. Dry-run mode logs the intended writes without touching
the DB so LO can review the matches before commit.

Usage:
    python -m scripts.backfill_kr_logos_naver --dry-run
    python -m scripts.backfill_kr_logos_naver
    python -m scripts.backfill_kr_logos_naver --limit 20
    python -m scripts.backfill_kr_logos_naver --set ko-SM1M
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import re
import sys
import urllib.parse
from pathlib import Path

from playwright.async_api import async_playwright, Page
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal, init_db


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("backfill_kr_logos_naver")


NAVER_IMG_SEARCH = "https://search.naver.com/search.naver?where=image&query={q}"


# Naver's image proxy wraps results as
#   https://search.pstatic.net/common/?src=<url-encoded>&...
# and
#   https://search.pstatic.net/sunny/?src=<url-encoded>&...
# The N페이 promo banner is always the first `img` element on the
# page — filter by src prefix.
_NAVER_PROMO = "ssl.pstatic.net/static/common/gnb/"


PAGE_JS = r"""
() => {
    const els = document.querySelectorAll('img');
    return Array.from(els).slice(0, 40).map(e => ({src: e.src || '', alt: e.alt || ''}));
}
"""


def _extract_source_url(pstatic_url: str) -> str | None:
    """Naver's `search.pstatic.net/common/?src=<encoded>&...` wraps
    the actual image URL. Decode `src=` back to the original so we
    don't store Naver's rewriter (which might expire / Referer-block
    non-Naver traffic later)."""
    m = re.search(r"[?&]src=([^&]+)", pstatic_url)
    if not m:
        return pstatic_url  # not a wrapped URL — return as-is
    try:
        decoded = urllib.parse.unquote(m.group(1))
        return decoded
    except Exception:
        return pstatic_url


async def _search_one(pg: Page, query: str) -> str | None:
    url = NAVER_IMG_SEARCH.format(q=urllib.parse.quote(query))
    try:
        await pg.goto(url, wait_until="domcontentloaded", timeout=30_000)
        await pg.wait_for_timeout(2500)
    except Exception as e:
        log.warning(f"  goto failed for {query!r}: {e}")
        return None

    imgs = await pg.evaluate(PAGE_JS)
    for im in imgs:
        src = im.get("src") or ""
        if not src:
            continue
        if _NAVER_PROMO in src:
            continue
        if "search.pstatic.net" not in src and "phinf.naver.net" not in src:
            continue
        return _extract_source_url(src)
    return None


async def _list_targets(only_set: str | None, refresh: bool, limit: int | None) -> list[tuple[str, str]]:
    async with SessionLocal() as db:
        sql = "SELECT id, name FROM sets WHERE language='ko' AND name IS NOT NULL AND name <> ''"
        params: dict = {}
        if only_set:
            sql += " AND id = :sid"
            params["sid"] = only_set
        if not refresh:
            sql += " AND logo_url IS NULL"
        sql += " ORDER BY release_date DESC NULLS LAST"
        if limit:
            sql += " LIMIT :lim"
            params["lim"] = limit
        rows = (await db.execute(text(sql), params)).all()
    return [(r.id, r.name) for r in rows]


async def run(only_set: str | None, dry_run: bool, refresh: bool, limit: int | None) -> None:
    await init_db()

    targets = await _list_targets(only_set, refresh, limit)
    log.info(f"KR sets needing a Naver-search logo: {len(targets)}")
    if not targets:
        return

    stats = {"found": 0, "missing": 0, "wrote": 0}
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0.0.0 Safari/537.36"
            ),
            locale="ko-KR",
            viewport={"width": 1280, "height": 2400},
        )
        pg = await ctx.new_page()

        for i, (sid, name) in enumerate(targets, 1):
            # Two-query fallback: first with `포켓몬 카드` qualifier
            # for disambiguation, then bare set name if that whiffs.
            url = await _search_one(pg, f"{name} 포켓몬 카드")
            if url is None:
                url = await _search_one(pg, name)
            if url is None:
                stats["missing"] += 1
                log.info(f"  [{i:>3}/{len(targets)}] {sid:22s} MISS  {name}")
                continue
            stats["found"] += 1
            log.info(f"  [{i:>3}/{len(targets)}] {sid:22s} OK    {name!r:25s} -> {url[:70]}")
            if not dry_run:
                async with SessionLocal() as db:
                    await db.execute(
                        text("UPDATE sets SET logo_url=:u WHERE id=:s"),
                        {"u": url, "s": sid},
                    )
                    await db.commit()
                    stats["wrote"] += 1
            # Naver is bot-tolerant but not immune — a small delay
            # per query keeps us well under any hidden rate limit.
            await asyncio.sleep(1.5)

        await browser.close()

    log.info("=== summary ===")
    for k, v in stats.items():
        log.info(f"  {k}: {v}")
    if dry_run:
        log.info("DRY-RUN — no writes")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--set", dest="only_set", help="Limit to one ko-* set id")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--refresh", action="store_true",
                   help="Re-scrape sets whose logo already resolved")
    p.add_argument("--limit", type=int, help="Cap on sets processed (for testing)")
    args = p.parse_args()
    asyncio.run(run(args.only_set, args.dry_run, args.refresh, args.limit))


if __name__ == "__main__":
    main()
