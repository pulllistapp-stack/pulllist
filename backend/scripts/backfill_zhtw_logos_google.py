"""Backfill zh-tw set logo_url via Bing Image Search scrape.

The Taiwan Pokemon Company trainer site (asia.pokemon-card.com/tw)
that seeded our zh-tw catalog is a pure card database — no per-set
marketing art. So each of the 27 zh-tw sets lands with a NULL logo.

First tried Google Image Search — first request returns rich results
but by the second query Google's bot detection kicks in and serves
empty pages. Bing is markedly more tolerant (same headless-Chrome
stack pulled 3/3 hits on M4/CSV9.5C/SV7a in a row) and its zh-TW
market returns the same retail-shop pack photos.

Query shape (unchanged from the Google draft): `寶可夢 {clean_name}
卡盒` — 寶可夢 is Traditional-locale "Pokemon", 卡盒 = "card box".
Bing's alt-text is a boilerplate `{query} 的圖片結果` template so the
alt-text confidence check trivially passes once we've built the
query from the set name.

Image proxy: `th.bing.com/th/id/OIP.<hash>?w=200&h=200&...` — stable
HTTPS CDN, unaffected by source-site hot-link protection because
Bing already re-hosted the image.

next.config.mjs needs `th.bing.com` in the image remotePatterns list
for the tiles to render (added in the same commit).

Idempotent — sets with a logo_url already are skipped unless
--refresh. Dry-run mode prints planned writes without touching the
DB.

Usage:
    python -m scripts.backfill_zhtw_logos_google --dry-run
    python -m scripts.backfill_zhtw_logos_google
    python -m scripts.backfill_zhtw_logos_google --limit 3
    python -m scripts.backfill_zhtw_logos_google --set zhtw-M4
"""
from __future__ import annotations
import argparse
import asyncio
import io
import logging
import re
import sys
import urllib.parse
from pathlib import Path

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from playwright.async_api import async_playwright, Page  # noqa: E402
from sqlalchemy import text  # noqa: E402
from app.database import SessionLocal, init_db  # noqa: E402

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("backfill_zhtw_logos_google")

BING_IMG = "https://www.bing.com/images/search?q={q}&mkt=zh-TW&form=IQFRML"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")

# Product-type prefixes we strip from the Taiwan set names before
# forming the search query — leaves just the marketing name inside
# the 「」 quotes (or the raw name for products without quotes).
_PRODUCT_PREFIXES = ("擴充包", "高級擴充包", "挑戰牌組", "戰術牌組",
                     "初階牌組", "特典卡")

# Bing chrome images we always skip regardless of order
_CHROME_HINTS = ("r.bing.com/rp/", "bing.com/images/branding/", "bing.com/sa/")


def _clean_name(raw: str) -> str:
    """Strip product-type prefix + Chinese quote brackets.

    擴充包「忍者飛旋」        → 忍者飛旋
    高級擴充包「超級進化夢想ex」 → 超級進化夢想ex
    特典卡 超級進化           → 特典卡 超級進化 (no quotes → leave as-is)
    New Trainer Journey     → New Trainer Journey
    """
    s = raw.strip()
    for prefix in _PRODUCT_PREFIXES:
        if s.startswith(prefix):
            # Strip prefix, then any surrounding 「」 or 「 」 whitespace
            s = s[len(prefix):].strip()
            break
    # Peel 「...」 wrapper
    if s.startswith("「") and s.endswith("」"):
        s = s[1:-1].strip()
    return s or raw


def _looks_relevant(alt: str, query_terms: set[str]) -> bool:
    """A result is relevant if its alt-text shares at least one
    meaningful token with the query — filters Google UI slop that
    slips through the URL filter."""
    if not alt:
        return False
    alt_lower = alt.lower()
    return any(term.lower() in alt_lower for term in query_terms)


PAGE_JS = r"""
() => Array.from(document.querySelectorAll('img')).slice(0, 30).map(e => ({
    src: e.src || '',
    alt: (e.alt || '').trim(),
    w: e.naturalWidth || e.width,
    h: e.naturalHeight || e.height,
}))
"""


async def _search_one(pg: Page, query: str, query_terms: set[str]) -> str | None:
    url = BING_IMG.format(q=urllib.parse.quote(query))
    try:
        await pg.goto(url, wait_until="domcontentloaded", timeout=30_000)
        await pg.wait_for_timeout(2500)
    except Exception as e:
        log.warning(f"  goto failed for {query!r}: {e}")
        return None

    imgs = await pg.evaluate(PAGE_JS)
    for im in imgs:
        src = im.get("src") or ""
        alt = im.get("alt") or ""
        if not src or not src.startswith("http"):
            continue
        if any(h in src for h in _CHROME_HINTS):
            continue
        if src.endswith(".svg"):
            continue
        # Only take Bing's stable thumbnail proxy (th.bing.com/th/id/OIP.*)
        if "th.bing.com/th/id/OIP" not in src:
            continue
        # Alt-text confidence — must overlap with query terms
        if not _looks_relevant(alt, query_terms):
            continue
        # Bump the requested size — Bing's proxy generates thumbs
        # on-demand, so a bigger w/h in the URL gets a bigger image.
        src = re.sub(r"([?&])w=\d+", r"\1w=400", src)
        src = re.sub(r"([?&])h=\d+", r"\1h=400", src)
        return src
    return None


async def _list_targets(only_set: str | None, refresh: bool,
                        limit: int | None) -> list[tuple[str, str]]:
    async with SessionLocal() as db:
        sql = ("SELECT id, name FROM sets "
               "WHERE language='zh-tw' AND name IS NOT NULL AND name <> ''")
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


async def run(only_set: str | None, dry_run: bool, refresh: bool,
              limit: int | None) -> None:
    await init_db()
    targets = await _list_targets(only_set, refresh, limit)
    log.info(f"zh-tw sets needing a Google-search logo: {len(targets)}")
    if not targets:
        return

    stats = {"found": 0, "missing": 0, "wrote": 0}
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(
            user_agent=UA,
            locale="zh-TW",
            viewport={"width": 1280, "height": 2400},
        )
        pg = await ctx.new_page()

        for i, (sid, name) in enumerate(targets, 1):
            clean = _clean_name(name)
            # Build query terms for the alt-text confidence check —
            # anything with 2+ CJK chars or an ASCII substring
            terms = set()
            if clean:
                terms.add(clean)
                # Also break into CJK-only chunk (drop 'ex' suffix etc.)
                cjk = re.sub(r"[a-zA-Z0-9\s]", "", clean).strip()
                if cjk:
                    terms.add(cjk)
            # Two-query fallback: qualifier query, then bare name
            queries = [f"寶可夢 {clean} 卡盒", f"寶可夢 {clean}", clean]

            url = None
            for q in queries:
                url = await _search_one(pg, q, terms)
                if url:
                    break

            if url is None:
                stats["missing"] += 1
                log.info(f"  [{i:>2}/{len(targets)}] {sid:15s} MISS  {name!r}")
                continue

            stats["found"] += 1
            log.info(f"  [{i:>2}/{len(targets)}] {sid:15s} OK    "
                     f"{name!r:36s} -> {url[:90]}")
            if not dry_run:
                async with SessionLocal() as db:
                    await db.execute(
                        text("UPDATE sets SET logo_url=:u, updated_at=NOW() "
                             "WHERE id=:s"),
                        {"u": url, "s": sid},
                    )
                    await db.commit()
                    stats["wrote"] += 1
            await asyncio.sleep(2.0)  # be polite

        await browser.close()

    log.info("=== summary ===")
    for k, v in stats.items():
        log.info(f"  {k}: {v}")
    if dry_run:
        log.info("DRY-RUN — no writes")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--set", dest="only_set",
                    help="Limit to one zhtw-* set id")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--refresh", action="store_true",
                    help="Re-scrape sets that already carry a logo")
    ap.add_argument("--limit", type=int,
                    help="Cap on sets processed (for testing)")
    args = ap.parse_args()
    asyncio.run(run(args.only_set, args.dry_run, args.refresh, args.limit))


if __name__ == "__main__":
    main()
