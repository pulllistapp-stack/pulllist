"""Backfill KR set logo_url via Playwright scrape of pokemonstore.co.kr.

pokemonstore.co.kr is Pokemon Korea's official online store (NHN
Commerce ShopBy platform). Its category page lists every current
TCG SKU with a shopby-images.cdn-nhncommerce.com main image, and
each product's detail page carries the set's Korean title in a
predictable spot. LO verified 2026-07-19 that individual detail
pages are the only place clean data exists — the list page only
surfaces a SOLD OUT overlay in textContent, no product name.

Two-phase scrape:

  Phase 1 — one list-page load (`pageSize=500` returns the full
  category in one request; 확장팩 category currently holds 248
  distinct products). Extract every productNo.

  Phase 2 — per-product detail-page load. Grab `document.title`
  for the Korean set name, then walk the DOM for the biggest
  shopby-images image (the product hero). Fuzzy-match the title
  to our `sets.name` where `language='ko' AND logo_url IS NULL`;
  when it clears a threshold, write the image URL as the logo.

Runs against multiple categoryNo values in one pass so LO doesn't
have to babysit each category (확장팩 + 하이클래스팩 + 스타터덱 etc.).
Idempotent — sets that already have a logo are skipped unless
--refresh.

Usage:
    python -m scripts.backfill_kr_logos_pokemonstore --dry-run
    python -m scripts.backfill_kr_logos_pokemonstore
    python -m scripts.backfill_kr_logos_pokemonstore --category 488339
    python -m scripts.backfill_kr_logos_pokemonstore --refresh   # re-scrape all
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from difflib import SequenceMatcher
from pathlib import Path

from playwright.async_api import async_playwright, Browser, BrowserContext
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal, init_db


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("backfill_kr_logos_pokemonstore")


STORE_BASE = "https://m.pokemonstore.co.kr"

# LO-verified category IDs (2026-07-19). 488339 = 확장팩 (expansion
# packs) is the biggest one — 248 SKUs. More may exist for starter
# decks / trainer boxes; add them here as we discover them so a
# single script run refreshes every category.
DEFAULT_CATEGORIES: list[int] = [488339]


# Fuzzy-match threshold on Korean names. First dry-run at 0.55 pulled
# 10 accessory-vs-set false positives (덱 케이스 / 카드 실드 /
# 플레이매트 titles matching real sets on 1-2 shared characters), so
# tighten to 0.70. Real sets sharing the store's "포켓몬 카드 게임
# {era} {classification} 「{set}」" template consistently land ≥0.75
# after `_norm()` strips the boilerplate, so 0.70 leaves headroom for
# the smaller edits (「」 wrappers, trailing spaces).
_NAME_MATCH_MIN = 0.70


# Accessory titles that pattern-match a real set but shouldn't own its
# logo — deck cases, card sleeves, playmats, collection refills, coin
# markers, jumbo card holders, damage counters. If the product title
# contains any of these tokens, skip it entirely so an unrelated
# accessory doesn't overwrite the real set's logo just because it
# borrows the set/pokemon name.
_ACCESSORY_TOKENS = (
    "덱 케이스", "덱케이스",
    "카드 실드", "카드실드",
    "플레이매트", "플레이 매트",
    "리필", "컬렉션 리필",
    "점보 카드", "점보카드",
    "슬리브",
    "데미지 카운터", "데미지카운터",
    "마커", "코인 세트", "동전",
    "정리 파일", "카드 파일",
    "이브이 덱 케이스",
)


def _is_accessory(product_title: str) -> bool:
    t = product_title or ""
    return any(tok in t for tok in _ACCESSORY_TOKENS)


LIST_JS = r"""
() => {
    const links = document.querySelectorAll('a[href*="productNo="]');
    const seen = new Set();
    const out = [];
    for (const a of links) {
        const m = (a.href || '').match(/productNo=(\d+)/);
        if (!m) continue;
        const pno = m[1];
        if (seen.has(pno)) continue;
        seen.add(pno);
        out.push(pno);
    }
    return out;
}
"""


# Per-detail extractor. Priority order for the "logo" image:
#   1. og:image meta (usually the canonical product photo)
#   2. Largest shopby-images image inside the product-detail area
# Skip UI chrome (mall logo, header icons) by rejecting the alt hints
# we know are non-product.
DETAIL_JS = r"""
() => {
    const title = document.title || '';
    // Prefer og:image
    const og = document.querySelector('meta[property="og:image"]');
    const ogSrc = og ? og.getAttribute('content') : null;
    // Fallback: biggest shopby-images not tagged as chrome
    const imgs = Array.from(document.querySelectorAll('img'))
        .filter(e => (e.src || '').includes('shopby-images.cdn-nhncommerce.com'))
        .map(e => ({src: e.src, alt: e.alt || '', w: e.naturalWidth || 0}));
    const _CHROME = ['로고', 'logo_', '_logo', 'header', 'footer', 'banner'];
    const clean = imgs.filter(i => {
        const bad = _CHROME.some(k =>
            (i.alt || '').toLowerCase().includes(k.toLowerCase()) ||
            (i.src || '').toLowerCase().includes(k.toLowerCase())
        );
        return !bad;
    });
    clean.sort((a, b) => b.w - a.w);
    return {
        title,
        og: ogSrc,
        biggest: clean[0] ? clean[0].src : null,
        cleanCount: clean.length,
    };
}
"""


def _norm(s: str | None) -> str:
    if not s:
        return ""
    # Strip common wrappers/noise. Product titles wrap the set name
    # in fullwidth quotes 「」 which don't appear on our DB name; strip
    # them so the fuzzy score reflects actual character overlap.
    for junk in ["포켓몬 카드 게임", "포켓몬카드게임", "「", "」", "『", "』",
                 "확장팩", "하이클래스팩", "스타터 덱", "스타트 덱",
                 "스칼렛&바이올렛", "스칼렛・바이올렛", "썬&문", "썬문",
                 "검과 방패", "소드&실드", "블랙&화이트", "XY", "메가에볼루션",
                 "-", "·", " "]:
        s = s.replace(junk, "")
    return s.lower()


async def _load_list(pg, category: int) -> list[str]:
    url = f"{STORE_BASE}/pages/product/product-list.html?categoryNo={category}&pageSize=500&pageNumber=1"
    log.info(f"  list: category={category} loading")
    await pg.goto(url, wait_until="domcontentloaded", timeout=30_000)
    await pg.wait_for_timeout(5000)
    await pg.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    await pg.wait_for_timeout(2000)
    return await pg.evaluate(LIST_JS)


async def _load_detail(pg, product_no: str) -> dict | None:
    url = f"{STORE_BASE}/pages/product/product-detail.html?productNo={product_no}"
    try:
        await pg.goto(url, wait_until="domcontentloaded", timeout=30_000)
        await pg.wait_for_timeout(3000)
        return await pg.evaluate(DETAIL_JS)
    except Exception as e:
        log.warning(f"  detail {product_no} failed: {e}")
        return None


async def _open_context(browser: Browser) -> BrowserContext:
    ctx = await browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0.0.0 Safari/537.36"
        ),
        locale="ko-KR",
        viewport={"width": 1280, "height": 2400},
    )
    return ctx


async def _match_and_write(product_title: str, image_url: str, dry_run: bool) -> tuple[str, str | None]:
    """Return (result_tag, matched_set_id_or_none)."""
    tnorm = _norm(product_title)
    if not tnorm:
        return ("no_title", None)
    async with SessionLocal() as db:
        # Get all KR sets missing a logo
        rows = (await db.execute(text(
            "SELECT id, name FROM sets "
            "WHERE language='ko' AND logo_url IS NULL"
        ))).all()
    best_id = None
    best_score = 0.0
    best_name = ""
    for r in rows:
        score = SequenceMatcher(None, tnorm, _norm(r.name)).ratio()
        if score > best_score:
            best_score = score
            best_id = r.id
            best_name = r.name
    if best_score < _NAME_MATCH_MIN or best_id is None:
        return ("no_match", None)
    log.info(f"    match \"{product_title[:35]}\" -> {best_id} \"{best_name[:25]}\" score={best_score:.2f}")
    if dry_run:
        return ("dry_run_match", best_id)
    # Normalize protocol-relative URLs (`//shopby-images...`) to
    # `https://` — pokemonstore's og:image sometimes drops the
    # scheme, and Next/Image on the frontend won't accept the bare
    # `//` form. Verified 2026-07-19 that ~55/56 first-run writes
    # came through protocol-relative.
    if image_url and image_url.startswith("//"):
        image_url = "https:" + image_url
    async with SessionLocal() as db:
        await db.execute(text("UPDATE sets SET logo_url=:u WHERE id=:s"),
                         {"u": image_url, "s": best_id})
        await db.commit()
    return ("wrote", best_id)


async def run(categories: list[int], dry_run: bool, refresh: bool) -> None:
    await init_db()

    if refresh:
        # Blank existing pokemonstore.co.kr logos so they get re-picked.
        async with SessionLocal() as db:
            r = await db.execute(text(
                "UPDATE sets SET logo_url = NULL "
                "WHERE language='ko' AND logo_url LIKE 'https://shopby-images.cdn-nhncommerce.com/%'"
            ))
            await db.commit()
            log.info(f"--refresh: cleared {r.rowcount} prior pokemonstore logos")

    stats = {"products_seen": 0, "matched": 0, "wrote": 0, "no_match": 0, "no_title": 0, "detail_failed": 0}
    used_sets: set[str] = set()  # first-write-wins per set

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await _open_context(browser)
        list_pg = await ctx.new_page()

        all_pnos: list[str] = []
        for cat in categories:
            pnos = await _load_list(list_pg, cat)
            log.info(f"  category {cat}: {len(pnos)} products")
            all_pnos.extend(pnos)
        # Dedupe across categories.
        seen = set()
        pnos = []
        for p_ in all_pnos:
            if p_ in seen: continue
            seen.add(p_); pnos.append(p_)
        log.info(f"total distinct products: {len(pnos)}")

        detail_pg = await ctx.new_page()
        for i, pno in enumerate(pnos, 1):
            stats["products_seen"] += 1
            d = await _load_detail(detail_pg, pno)
            if d is None:
                stats["detail_failed"] += 1
                continue
            title = (d.get("title") or "").strip()
            img = d.get("og") or d.get("biggest")
            if not title or not img:
                stats["no_title"] += 1
                continue
            if _is_accessory(title):
                # Skip deck cases / card shields / playmats etc. even
                # if their titles superficially name-match a real set.
                stats["accessory_skipped"] = stats.get("accessory_skipped", 0) + 1
                continue
            result, matched = await _match_and_write(title, img, dry_run)
            if matched and matched in used_sets:
                # A prior product already wrote this set; skip further
                # writes so a starter deck's tile doesn't overwrite the
                # main expansion's already-good logo.
                continue
            if result in ("wrote", "dry_run_match"):
                if matched: used_sets.add(matched)
                stats["matched"] += 1
                if result == "wrote":
                    stats["wrote"] += 1
            elif result == "no_match":
                stats["no_match"] += 1
            elif result == "no_title":
                stats["no_title"] += 1
            if i % 25 == 0:
                log.info(f"  progress {i}/{len(pnos)}  matched so far={stats['matched']}")

        await browser.close()

    log.info("=== summary ===")
    for k, v in stats.items():
        log.info(f"  {k}: {v}")
    if dry_run:
        log.info("DRY-RUN — no writes")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--refresh", action="store_true",
                   help="Clear existing pokemonstore.co.kr logos before scraping")
    p.add_argument("--category", type=int, action="append",
                   help="ShopBy categoryNo (repeatable). Defaults to 확장팩=488339")
    args = p.parse_args()
    cats = args.category or DEFAULT_CATEGORIES
    asyncio.run(run(cats, args.dry_run, args.refresh))


if __name__ == "__main__":
    main()
