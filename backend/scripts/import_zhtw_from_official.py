"""Import zh-tw Pokemon catalog from asia.pokemon-card.com/tw.

Background:
  TCGdex's zh-tw feed is stale — its latest set is SV9a (Q1-2025 JP
  timeline) but Taiwan has been shipping past that: the 超級進化 (Mega
  Evolution) era launched 2025-08 and by mid-2026 has 16 sets on
  shelf. Since TCGdex isn't catching up, we scrape the Taiwan Pokemon
  Company's own training-site catalog directly. Their card-search
  page is a clean anchor grid with predictable image URLs.

Site structure (as of 2026-07-19):
  Index:  /tw/card-search/          — recent-releases carousel with
                                       anchor tags to each expansion
  Set:    /tw/card-search/list/?expansionCodes={code}
                                     — grid of `li.card` items, each
                                       carrying image + detail-page link
  Card:   /tw/card-search/detail/{numeric_id}/
                                     — full metadata + hi-res image

Storage:
  Set IDs use `zhtw-{expansion_code}` (Option B locale-prefix scheme),
  card IDs use `zhtw-{expansion_code}-{card_number_or_id}`. Language
  column is `zh-tw`. Series stored bilingually as `超級進化 (Mega
  Evolution)` — same pattern as KR/CN canonicalization.

Idempotent: existing rows update `logo_url`/`name`/etc.; existing
cards update their image URL. Nothing gets deleted on re-run.
"""
from __future__ import annotations
import argparse
import asyncio
import io
import logging
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402
from app.database import SessionLocal, init_db  # noqa: E402

logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")

BASE = "https://asia.pokemon-card.com"
INDEX_URL = f"{BASE}/tw/card-search/"
LIST_URL_FMT = f"{BASE}/tw/card-search/list/?expansionCodes={{code}}"

SERIES_MAP: dict[str, str] = {
    "超級進化": "超級進化 (Mega Evolution)",
    "朱＆紫":   "朱＆紫 (Scarlet & Violet)",
    "劍＆盾":   "劍＆盾 (Sword & Shield)",
    "太陽＆月亮": "太陽＆月亮 (Sun & Moon)",
    "XY BREAK": "XY BREAK",
    "XY":       "XY",
}


@dataclass
class Expansion:
    code: str
    series: str            # raw as shown on the site
    name: str              # 「product name」
    release: str           # "發售日 MM-DD-YYYY"
    card_ids: list[str] = field(default_factory=list)


def _clean_name(name: str) -> str:
    """Strip surrounding 「」/「」 quotes if the entire name is bracketed."""
    if name.startswith("擴充包") or name.startswith("高級擴充包") \
       or name.startswith("挑戰牌組") or name.startswith("戰術牌組") \
       or name.startswith("初階牌組") or name.startswith("特典卡"):
        # Product-category prefix, keep as-is
        return name
    return name


def _parse_release(s: str):
    """`發售日 07-17-2026` → date(2026, 7, 17)."""
    from datetime import date
    m = re.search(r"(\d{2})-(\d{2})-(\d{4})", s)
    if not m:
        return None
    mo, d, y = map(int, m.groups())
    try:
        return date(y, mo, d)
    except ValueError:
        return None


def _bilingual_series(raw: str) -> str:
    return SERIES_MAP.get(raw.strip(), raw.strip())


async def scrape_index(page) -> list[Expansion]:
    """Enumerate every expansion visible on the card-search homepage."""
    await page.goto(INDEX_URL, timeout=60_000, wait_until="domcontentloaded")
    await page.wait_for_timeout(3000)
    # Trigger any lazy sections
    prev_h = 0
    for _ in range(30):
        h = await page.evaluate("document.body.scrollHeight")
        if h == prev_h:
            break
        prev_h = h
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(500)

    rows = await page.evaluate("""
        () => {
            const anchors = Array.from(document.querySelectorAll('a[href*="expansionCodes"]'));
            return anchors.map(a => {
                const parts = (a.innerText || '').trim().split('\\n').map(s => s.trim());
                const url = new URL(a.href, location.href);
                return {
                    code: url.searchParams.get('expansionCodes'),
                    series: parts[0] || '',
                    name: parts[1] || '',
                    release: parts[2] || '',
                };
            }).filter(x => x.code);
        }
    """)
    # Dedupe by code (some show up multiple times)
    seen: dict[str, dict] = {}
    for r in rows:
        seen.setdefault(r["code"], r)
    return [Expansion(**r) for r in seen.values()]


async def scrape_set(page, code: str) -> tuple[list[dict], str | None]:
    """Return (list of card dicts, hero_image_url) for a single expansion.

    Handles pagination — Taiwan site's list view is paginated in blocks
    of 20 cards, controlled by `pageNo=N`. We read the '共 N 頁' counter
    on page 1 to find the total, then iterate."""
    all_cards: list[dict] = []
    hero: str | None = None
    seen_ids: set[str] = set()
    page_no = 1
    total_pages = 1

    while page_no <= total_pages:
        url = LIST_URL_FMT.format(code=code) + f"&pageNo={page_no}"
        await page.goto(url, timeout=60_000, wait_until="domcontentloaded")
        await page.wait_for_timeout(2000)
        # Trigger lazy image swap on this page
        for _ in range(5):
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(400)

        result = await page.evaluate("""
            () => {
                const cards = Array.from(document.querySelectorAll('li.card')).map(li => {
                    const a = li.querySelector('a[href*="detail"]');
                    const img = li.querySelector('img');
                    const src = img?.getAttribute('data-original') || img?.src || '';
                    const detailId = a ? (new URL(a.href, location.href).pathname.match(/detail\\/(\\d+)/) || [])[1] : null;
                    return {
                        detailId,
                        detailUrl: a ? a.href : null,
                        image: src,
                        alt: img?.alt || '',
                    };
                }).filter(c => c.detailId);
                const heroImg = document.querySelector('.expansionHeader img, .headerImage img, .setLogo img');
                // Extract '共 N 頁' counter — usually appears twice
                const bodyText = document.body.innerText;
                const m = bodyText.match(/共\\s*(\\d+)\\s*頁/);
                return {
                    cards,
                    hero: heroImg ? heroImg.src : null,
                    totalPages: m ? parseInt(m[1], 10) : 1,
                };
            }
        """)

        if page_no == 1:
            total_pages = result["totalPages"]
            hero = result["hero"]

        new_this_page = 0
        for c in result["cards"]:
            if c["detailId"] in seen_ids:
                continue
            seen_ids.add(c["detailId"])
            all_cards.append(c)
            new_this_page += 1

        if new_this_page == 0 and page_no > 1:
            # Server returned no new cards — likely at real end (some
            # counters lie)
            break

        page_no += 1

    return all_cards, hero


async def scrape_card_detail(page, detail_url: str) -> dict:
    """One-off — pull name/number/rarity from a detail page. Only used
    for a first-pass to confirm structure; bulk imports use image + id."""
    await page.goto(detail_url, timeout=60_000, wait_until="domcontentloaded")
    await page.wait_for_timeout(2000)
    return await page.evaluate("""
        () => {
            const h1 = document.querySelector('h1')?.innerText?.trim();
            const info = document.querySelector('.cardInformation, .card-detail, [class*="cardInfo"]');
            return {
                name: h1,
                infoHTML: info ? info.outerHTML.slice(0, 500) : null,
                title: document.title,
            };
        }
    """)


async def upsert_expansion(db, exp: Expansion, cards: list[dict], hero: str | None) -> tuple[int, int]:
    """Upsert one expansion + its cards. Returns (n_cards_upserted, existed?)."""
    set_id = f"zhtw-{exp.code}"
    series = _bilingual_series(exp.series)
    release = _parse_release(exp.release)

    # Check for existing set row
    r = await db.execute(text("SELECT id FROM sets WHERE id = :i"), {"i": set_id})
    existed = r.first() is not None

    if existed:
        await db.execute(text("""
            UPDATE sets
               SET name = :name, series = :series, release_date = :release,
                   language = 'zh-tw', updated_at = NOW()
             WHERE id = :i
        """), {"i": set_id, "name": exp.name, "series": series, "release": release})
    else:
        await db.execute(text("""
            INSERT INTO sets (id, name, name_local, series, release_date, language, created_at, updated_at)
            VALUES (:i, :name, :name_local, :series, :release, 'zh-tw', NOW(), NOW())
        """), {
            "i": set_id, "name": exp.name, "name_local": exp.name,
            "series": series, "release": release,
        })

    if hero:
        await db.execute(text("UPDATE sets SET logo_url = :u WHERE id = :i AND (logo_url IS NULL OR logo_url = '')"),
                         {"u": hero, "i": set_id})

    n_up = 0
    for c in cards:
        card_id = f"zhtw-{exp.code}-{c['detailId']}"
        # Use detailId as `number` sortable ordinal — Taiwan doesn't
        # expose card numbers in the list view, so we keep it simple
        r = await db.execute(text("SELECT id FROM cards WHERE id = :i"), {"i": card_id})
        if r.first():
            await db.execute(text("""
                UPDATE cards SET image_small = :img, image_large = :img,
                                 updated_at = NOW()
                 WHERE id = :i
            """), {"i": card_id, "img": c["image"]})
        else:
            await db.execute(text("""
                INSERT INTO cards (id, name, set_id, language, image_small, image_large,
                                   number, created_at, updated_at)
                VALUES (:i, :name, :set_id, 'zh-tw', :img, :img, :num, NOW(), NOW())
            """), {
                "i": card_id, "name": c.get("alt") or c["detailId"],
                "set_id": set_id, "img": c["image"], "num": c["detailId"],
            })
        n_up += 1
    return n_up, existed


async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--only", default=None,
                    help="Only import expansion codes matching this substring, "
                         "or a series filter like 'series:超級進化'")
    ap.add_argument("--series-only", default=None,
                    help="Import only expansions in this raw series name (e.g. 超級進化)")
    ap.add_argument("--limit", type=int, default=None,
                    help="Cap number of expansions this run (for testing)")
    args = ap.parse_args()

    from playwright.async_api import async_playwright
    await init_db()

    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        ctx = await b.new_context(user_agent=UA, viewport={"width": 1400, "height": 900})
        page = await ctx.new_page()

        print("Scraping expansion index …")
        expansions = await scrape_index(page)
        print(f"  found {len(expansions)} expansions total")
        by_series: dict[str, int] = {}
        for e in expansions:
            by_series[e.series] = by_series.get(e.series, 0) + 1
        for s, n in by_series.items():
            print(f"    {s}: {n}")

        if args.series_only:
            expansions = [e for e in expansions if e.series.strip() == args.series_only.strip()]
            print(f"  --series-only filter → {len(expansions)}")
        if args.only:
            expansions = [e for e in expansions if args.only.lower() in e.code.lower()]
            print(f"  --only filter → {len(expansions)}")
        if args.limit:
            expansions = expansions[:args.limit]
            print(f"  --limit {args.limit} → {len(expansions)}")

        async with SessionLocal() as db:
            total_cards = 0
            for i, exp in enumerate(expansions, 1):
                print(f"[{i}/{len(expansions)}] {exp.code:6s} {exp.name}")
                cards, hero = await scrape_set(page, exp.code)
                print(f"    cards found: {len(cards)}"
                      + (f", hero: {hero[:80]}" if hero else ""))

                if args.dry_run:
                    for c in cards[:3]:
                        print(f"      sample: id={c['detailId']} img={c['image'][:100]}")
                    continue

                n_up, existed = await upsert_expansion(db, exp, cards, hero)
                verb = "updated" if existed else "created"
                print(f"    {verb} set, {n_up} cards upserted")
                total_cards += n_up
                await db.commit()

            if not args.dry_run:
                print(f"done — {len(expansions)} sets, {total_cards} cards")

        await b.close()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
