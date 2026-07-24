"""Backfill KR-native chase-tier promo card images from eBay + Naver.

Two-source pipeline:
  1. eBay Sold/Active search (English pokemon name + KR-P code) —
     usually returns clean seller listings with card-only photos
     for international collectors reselling KR promos
  2. Naver Image Search fallback (KR name + code) — for cards eBay
     didn't index; hits Naver Smart Store sellers via the phinf CDN

Applied filters (both sources):
  - Aspect ratio 0.60–0.82 (Pokemon card portrait 63/88 = 0.716)
  - Min width 300px (rejects tiny placeholder thumbs)
  - Card-BACK detection — center 40×40 region avg RGB check;
    Pokemon back has pokéball red + blue frame (avg B > 130 AND
    avg R > 80 AND low green). Backs uploaded as seller thumbnails
    (common on Naver) get rejected here
  - Bad-keyword blocklist (JUMBO/OVERSIZED/LOT/BUNDLE/SLEEVE/…) to
    skip oversized promo cards, sleeved lots, box sets
  - Language filter — reject 일어판/영문판/일본판/영문판/일본어 alts;
    require "Korean" in eBay title
  - Exact number match — alt/title MUST contain the specific NNN/CODE
    (e.g. "042/BW-P" or "168/XY-P"). Fallback to closest-ratio candidate
    only if strict pass empties

HTTP-only Naver hosts (shop1.phinf.naver.net doesn't support HTTPS,
cert mismatch) get wrapped through images.weserv.nl so Next.js Image
optimizer serves them over HTTPS.

Target list is hardcoded — the 20 chase-tier KR promos identified via
the market-activity probe on /portfolio, focused on cards priced $20+
in USD. Scaling to the full uncovered 693 requires a KR-name → EN
translation table we don't yet have.

Usage:
    python -m scripts.backfill_kr_promo_chase_images                  # full
    python -m scripts.backfill_kr_promo_chase_images --dry-run        # no writes
    python -m scripts.backfill_kr_promo_chase_images --naver-only     # skip eBay
    python -m scripts.backfill_kr_promo_chase_images --ebay-only      # skip Naver
    python -m scripts.backfill_kr_promo_chase_images --card ko-p-xy-166   # single
"""
from __future__ import annotations

import argparse
import asyncio
import io
import logging
import re
import sys
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx  # noqa: E402
from PIL import Image  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.database import SessionLocal, init_db  # noqa: E402


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("backfill_kr_promo_chase_images")


UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/128.0.0.0 Safari/537.36"
)


# Chase-tier targets: KR promos LO identified as trading $20+ USD.
# (card_id, kr_name, en_name, era_code, num)
TARGETS: list[tuple[str, str, str, str, str]] = [
    ("ko-p-xy-122",   "뮤츠 EX",    "Mewtwo EX",       "XY-P", "122"),
    ("ko-p-xy-188",   "뮤츠 EX",    "Mewtwo EX",       "XY-P", "188"),
    ("ko-p-xy-011",   "리자몽 EX",  "Charizard EX",    "XY-P", "011"),
    ("ko-p-xy-147",   "리자몽 EX",  "Charizard EX",    "XY-P", "147"),
    ("ko-p-xy-166",   "레쿠쟈",     "Rayquaza",        "XY-P", "166"),
    ("ko-p-xy-191",   "루기아",     "Lugia",           "XY-P", "191"),
    ("ko-p-xy-170",   "거북왕 EX",  "Blastoise EX",    "XY-P", "170"),
    ("ko-p-xy-168",   "이상해씨 EX", "Venusaur EX",    "XY-P", "168"),
    ("ko-p-xy-178",   "M보만다 EX", "M Salamence EX",  "XY-P", "178"),
    ("ko-p-xy-183",   "마기아나 EX", "Magearna EX",    "XY-P", "183"),
    ("ko-p-bw-041",   "레시라무 EX", "Reshiram EX",    "BW-P", "041"),
    ("ko-p-bw-042",   "제크로무 EX", "Zekrom EX",      "BW-P", "042"),
    ("ko-p-bw-059",   "블랙큐레무",  "Black Kyurem",   "BW-P", "059"),
    ("ko-p-bw-060",   "화이트큐레무", "White Kyurem",  "BW-P", "060"),
    ("ko-p-bw-071",   "블래키",     "Umbreon",         "BW-P", "071"),
    ("ko-p-bw-068",   "글레이시아",  "Glaceon",        "BW-P", "068"),
    ("ko-p-bw-061",   "게노세크트",  "Genesect",       "BW-P", "061"),
    ("ko-p-base-001", "루기아",     "Lugia",           "",     "001"),
    ("ko-p-base-002", "칠색조",     "Ho-Oh",           "",     "002"),
    ("ko-p-base-006", "잠만보 LV. X", "Snorlax LV.X",  "",     "006"),
]


# ────────── Shared filters ──────────

FOREIGN_RE = re.compile(r"영문판|영어판|일어판|일본판|미국판|Japanese| JP | JA ", re.I)
BAD_WORDS = (
    "JUMBO", "OVERSIZED", "OVERSIZE", "LOT OF", " LOT ", "BUNDLE",
    "SLEEVE", "SET OF", "COLLECTION", "BOX", "PLAYMAT", "PIN",
    "DECK", "BOOSTER",
    "점보", "스탠드", "아크릴", "뱃지", "슬리브", "박스",
    "스티커", "봉투", "쿠션", "피규어", "봉지",
)
ALLOWED_NAVER_HOSTS = (
    "shop1.phinf.naver.net", "shop-phinf.pstatic.net",
    "cafefiles.naver.net", "blogfiles.naver.net",
    "kream-phinf.pstatic.net", "thumbnail.coupangcdn.com",
)
HTTP_HOSTS_NEEDING_WESERV = (
    "shop1.phinf.naver.net", "cafefiles.naver.net", "blogfiles.naver.net",
)

MIN_RATIO, MAX_RATIO = 0.60, 0.82
MIN_WIDTH = 300


def _is_bad_title(text_val: str) -> bool:
    up = text_val.upper()
    if any(bw in up for bw in BAD_WORDS):
        return True
    if FOREIGN_RE.search(text_val):
        return True
    return False


def _decode_naver_thumb(url: str) -> str:
    """search.pstatic.net/common/?src=<encoded> → real image url."""
    if "search.pstatic" in url:
        q = parse_qs(urlparse(url).query)
        return q.get("src", [""])[0] or url
    return url


def _wrap_https_via_weserv(url: str) -> str:
    """HTTP Naver hosts don't support HTTPS (SSL cert mismatch); wrap
    through weserv.nl so Next.js Image serves them over HTTPS."""
    parsed = urlparse(url)
    if parsed.scheme == "http" and any(
        h in parsed.netloc for h in HTTP_HOSTS_NEEDING_WESERV
    ):
        return f"https://images.weserv.nl/?url={parsed.netloc}{parsed.path}"
    return url


def _is_card_back(img: Image.Image) -> bool:
    """Heuristic card-back detector — samples the center 40×40 region.
    Pokemon backs are pokéball red on blue frame, so avg B>130, avg R>80,
    low G. Card fronts vary by pokemon type but rarely land in that
    same color signature."""
    try:
        img = img.convert("RGB")
        w, h = img.size
        cx, cy = w // 2, h // 2
        crop = img.crop((cx - 20, cy - 20, cx + 20, cy + 20))
        px = list(crop.getdata())
        n = len(px)
        r_avg = sum(p[0] for p in px) / n
        g_avg = sum(p[1] for p in px) / n
        b_avg = sum(p[2] for p in px) / n
        # Pokéball red + blue backdrop signature
        if b_avg > 130 and r_avg > 80 and g_avg < 130:
            return True
        # All-blue dominated (some crop offsets)
        if b_avg > 150 and r_avg < 100:
            return True
        return False
    except Exception:
        return False


async def _check_image(client: httpx.AsyncClient, url: str) -> dict | None:
    try:
        r = await client.get(
            url, timeout=15,
            headers={"User-Agent": UA,
                     "Referer": "https://search.naver.com/"},
        )
        if r.status_code != 200 or len(r.content) < 5000:
            return None
        img = Image.open(io.BytesIO(r.content))
        w, h = img.size
        if h == 0:
            return None
        return {
            "ratio": w / h, "width": w, "height": h,
            "is_back": _is_card_back(img),
        }
    except Exception:
        return None


# ────────── eBay source ──────────

async def _ebay_query(page, name: str, code: str, num: str) -> list[dict]:
    """Assemble a strict + loose query ladder and return listings."""
    q = f"{name} Korean {code} {num}" if code else f"{name} Korean {num} PROMO"
    url = f"https://www.ebay.com/sch/i.html?_nkw={quote(q)}&_sacat=0"
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        await page.wait_for_timeout(2800)
    except Exception:
        return []
    return await page.eval_on_selector_all(
        "li.s-item, li.s-card",
        """els => els.slice(0, 12).map(li => {
            const img = li.querySelector('img');
            const t = li.querySelector('.s-item__title, .s-card__title');
            const p = li.querySelector('.s-item__price, .s-card__price');
            return {
                title: (t?.innerText||'').slice(0, 130),
                price: (p?.innerText||'').slice(0, 40),
                img: img?.src || null,
            };
        }).filter(x => x.img && x.img.includes('i.ebayimg'))"""
    )


async def _find_ebay_shot(page, client, name, code, num) -> dict | None:
    specific = f"{num}/{code}" if code else num
    items = await _ebay_query(page, name, code, num)
    for it in items:
        title = it.get("title", "") or ""
        if _is_bad_title(title):
            continue
        if code and specific not in title:
            continue
        if "korean" not in title.lower():
            continue
        big_url = it["img"].replace("/s-l500.", "/s-l1600.").replace(
            "/s-l225.", "/s-l1600."
        )
        info = await _check_image(client, big_url)
        if not info or info["width"] < MIN_WIDTH:
            continue
        if not (MIN_RATIO <= info["ratio"] <= MAX_RATIO):
            continue
        if info["is_back"]:
            continue
        return {"source": "ebay", "url": big_url, "alt": title,
                "price": it.get("price", ""), **info}
    return None


# ────────── Naver source ──────────

async def _naver_query(page, kr_name: str, code: str, num: str) -> list[dict]:
    queries = [
        f"{kr_name} {num}/{code} 포켓몬카드",
        f"{kr_name} 프로모 {num}",
    ]
    all_items = []
    for q in queries:
        url = f"https://search.naver.com/search.naver?where=image&query={quote(q)}"
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            await page.wait_for_timeout(2500)
        except Exception:
            continue
        items = await page.eval_on_selector_all(
            "img",
            """els => els
                .filter(e => e.src && e.src.includes('search.pstatic'))
                .slice(0, 25)
                .map(e => ({src: e.src, alt: e.alt || ''}))"""
        )
        all_items.extend(items)
    return all_items


async def _find_naver_shot(page, client, kr_name, code, num) -> dict | None:
    specific = f"{num}/{code}".upper().replace(" ", "")
    items = await _naver_query(page, kr_name, code, num)
    for it in items:
        alt = it.get("alt", "") or ""
        if _is_bad_title(alt):
            continue
        alt_norm = alt.upper().replace(" ", "")
        if specific not in alt_norm:
            continue
        real = _decode_naver_thumb(it["src"])
        host = urlparse(real).hostname or ""
        if not any(h in host for h in ALLOWED_NAVER_HOSTS):
            continue
        info = await _check_image(client, real)
        if not info or info["width"] < MIN_WIDTH:
            continue
        if not (MIN_RATIO <= info["ratio"] <= MAX_RATIO):
            continue
        if info["is_back"]:
            continue
        return {"source": "naver", "url": _wrap_https_via_weserv(real),
                "alt": alt, **info}
    return None


# ────────── Runner ──────────

async def run(
    only_card: str | None,
    ebay_only: bool, naver_only: bool, dry_run: bool,
) -> None:
    await init_db()
    from playwright.async_api import async_playwright

    targets = TARGETS
    if only_card:
        targets = [t for t in TARGETS if t[0] == only_card]
        if not targets:
            log.error("card_id %s not in TARGETS list", only_card)
            return

    stats = {"ebay": 0, "naver": 0, "unmatched": 0}
    picks: list[tuple[str, str]] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(
            user_agent=UA, locale="ko-KR",
            viewport={"width": 1400, "height": 2400},
        )
        page = await ctx.new_page()
        async with httpx.AsyncClient() as client:
            for card_id, kr, en, code, num in targets:
                log.info("%s · %s (%s %s)", card_id, kr, code, num)
                pick = None
                if not naver_only:
                    pick = await _find_ebay_shot(page, client, en, code, num)
                    if pick:
                        stats["ebay"] += 1
                        log.info("  eBay ← %s", pick["alt"][:70])
                if not pick and not ebay_only:
                    pick = await _find_naver_shot(page, client, kr, code, num)
                    if pick:
                        stats["naver"] += 1
                        log.info("  Naver ← %s", pick["alt"][:70])
                if not pick:
                    stats["unmatched"] += 1
                    log.info("  NO MATCH")
                    continue
                picks.append((card_id, pick["url"]))
        await browser.close()

    if not dry_run and picks:
        async with SessionLocal() as db:
            for card_id, url in picks:
                await db.execute(text(
                    "UPDATE cards SET image_small = :u, image_large = :u "
                    "WHERE id = :c"
                ), {"u": url, "c": card_id})
            await db.commit()

    log.info("=== summary ===")
    for k, v in stats.items():
        log.info("  %-10s %d", k, v)
    if dry_run:
        log.info("MODE: DRY-RUN — no writes")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--ebay-only", action="store_true")
    p.add_argument("--naver-only", action="store_true")
    p.add_argument("--card", metavar="ID",
                   help="Limit to one card id (must be in TARGETS list).")
    args = p.parse_args()
    asyncio.run(run(args.card, args.ebay_only, args.naver_only, args.dry_run))


if __name__ == "__main__":
    main()
