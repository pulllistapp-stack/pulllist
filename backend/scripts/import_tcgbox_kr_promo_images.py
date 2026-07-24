"""Backfill KR-native card scans + insert missing rows using tcgbox.co.kr.

TCGBOX is a KR TCG retail marketplace whose product images ARE the
actual KR-language card scans (physical cards sold to KR collectors).
Unlike collectory.cc (which serves JP/EN scans with KR name overlays)
or namu.wiki (list page with no images), tcgbox is the only KR-native
image source we've probed that returns anything real.

Pipeline:
  1. Fetch the full sitemap (5 gzipped chunks) — ~8,200 product URLs
  2. Filter to slugs containing an era code (`bw-p`, `xy-p`, `sm-p`,
     `s-p`, `sv-p`, `m-p`) with a trailing card number
  3. Visit each product page, extract the largest product image URL
  4. Map era-code → our `ko-p-{era}` set, match by number
  5. UPDATE image_small/image_large on existing cards; INSERT new rows
     for the KR promos namu missed but tcgbox stocks (mostly recent SV)

Trade-off: We link directly to tcgbox.co.kr URLs rather than mirroring
to R2. Rationale — only 30-60 hits per run, tiny compared to the 74k
already on R2, and tcgbox is stable enough for the friends-beta window.
A later batch can mirror + rewrite in place if we outgrow the direct
link (same shape as backfill_kr_logos_naver.py's plan).

Coverage note: tcgbox is a retail marketplace and only carries recent
in-stock promos. Historical eras (XY, BW, base 2010) have zero
coverage there — those need a different source. Current sweep lands
~30-60 cards depending on tcgbox's shifting stock, concentrated in the
SV / SM / SS / MEGA range.

Usage:
    python -m scripts.import_tcgbox_kr_promo_images                 # full
    python -m scripts.import_tcgbox_kr_promo_images --dry-run       # inspect
    python -m scripts.import_tcgbox_kr_promo_images --skip-insert   # only update matches, don't add new rows
"""
from __future__ import annotations

import argparse
import asyncio
import gzip
import io
import logging
import re
import sys
from pathlib import Path
from urllib.parse import unquote

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.database import SessionLocal, init_db  # noqa: E402
from app.models import Card  # noqa: E402


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("import_tcgbox_kr_promo_images")


BASE = "https://tcgbox.co.kr"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/128.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9",
    "Referer": "https://tcgbox.co.kr/",
}

# TCGBOX era-code → our ko-p-* set_id suffix. s8a-p / dp-p / hgss-p
# are intentionally absent — those belong to the legacy `ko-c-*`
# 25th anniversary set, not the ko-p-* era buckets.
CODE_TO_SET: dict[str, str] = {
    "bw-p":  "ko-p-bw",
    "xy-p":  "ko-p-xy",
    "sm-p":  "ko-p-sm",
    "s-p":   "ko-p-ss",
    "sv-p":  "ko-p-sv",
    "m-p":   "ko-p-mega",
}


# Match era-code + number from product slug.
# e.g. `묘두기-sv-p-012` → (sv-p, 012)
_SLUG_CODE_NUM_RE = re.compile(
    r"(bw-p|xy-p|sm-p|s-p|sv-p|m-p|dp-p|hgss-p|s8a-p)-(\d{2,4}|e\d+)(?:$|[^0-9])",
    re.IGNORECASE,
)
_IMG_RE = re.compile(
    r'/web/product/(?:original|big|medium)/[^"\']{5,200}\.(?:jpg|png|webp)',
    re.IGNORECASE,
)


def parse_slug(slug: str) -> tuple[str, str, str]:
    """(clean_name, era_code, num) — era_code lowercased, num zero-pad 3.

    Card name = slug with the `-{code}-{num}` suffix stripped and
    hyphens turned into spaces so `달이-빛나는-언덕-sv-p-048` →
    `달이 빛나는 언덕`. Namu-style formatting.
    """
    m = _SLUG_CODE_NUM_RE.search(slug)
    if not m:
        return "", "", ""
    code = m.group(1).lower()
    num = m.group(2)
    if num.isdigit():
        num = f"{int(num):03d}"
    # Trim everything from the matched code onwards, then clean hyphens
    name = slug[: m.start()].rstrip("-").replace("-", " ").strip()
    return name, code, num


async def fetch_sitemap_urls(client: httpx.AsyncClient) -> list[str]:
    idx = (await client.get(f"{BASE}/sitemap.xml")).text
    sub_sitemaps = re.findall(r"<loc>([^<]+sitemap\d+[^<]+)</loc>", idx)
    log.info("sub-sitemaps: %d", len(sub_sitemaps))
    all_urls: list[str] = []
    for sm in sub_sitemaps:
        r = await client.get(sm)
        data = gzip.decompress(r.content).decode("utf-8", errors="ignore")
        urls = re.findall(r"<loc>([^<]+)</loc>", data)
        all_urls.extend(u for u in urls if "/product/" in u)
    return all_urls


async def fetch_best_image(client: httpx.AsyncClient, url: str) -> str | None:
    """Grab the largest product image on this product page."""
    try:
        r = await client.get(url, timeout=20, follow_redirects=True)
    except Exception:
        return None
    if r.status_code != 200:
        return None
    imgs = sorted(set(_IMG_RE.findall(r.text)))
    # Prefer bigger sizes
    for size_pref in ("original", "big", "medium"):
        match = next((im for im in imgs if f"/{size_pref}/" in im), None)
        if match:
            return f"{BASE}{match}"
    return None


async def run(dry_run: bool, skip_insert: bool) -> None:
    await init_db()
    async with httpx.AsyncClient(headers=HEADERS) as client:
        all_urls = await fetch_sitemap_urls(client)
        log.info("total product urls: %d", len(all_urls))

        # Filter to promo-shaped slugs
        candidates: list[tuple[str, str, str, str, str]] = []
        for url in all_urls:
            slug = unquote(url.split("/product/", 1)[-1].split("/")[0])
            name, code, num = parse_slug(slug)
            if code in CODE_TO_SET and num:
                candidates.append((url, slug, name, code, num))
        log.info("promo candidates: %d", len(candidates))

        # Fetch each product page for its best image URL
        stats = {"matched_update": 0, "inserted": 0, "no_image": 0}
        async with SessionLocal() as db:
            for i, (url, slug, name, code, num) in enumerate(candidates, 1):
                img = await fetch_best_image(client, url)
                if not img:
                    stats["no_image"] += 1
                    log.info("  [%d/%d] %s NO IMG", i, len(candidates), slug[:50])
                    continue

                set_id = CODE_TO_SET[code]
                # Match namu-side card id first, fall back to zero-padded
                # variants. Namu importer used the raw digits from the
                # "번호" cell zero-pad-3, so both '012' and '12' can
                # exist historically.
                for cid in (f"{set_id}-{num}",
                            f"{set_id}-{int(num):03d}",
                            f"{set_id}-{int(num)}",
                            f"{set_id}-{num.lstrip('0') or '0'}"):
                    r = await db.execute(
                        text("SELECT id FROM cards WHERE id = :c"),
                        {"c": cid},
                    )
                    if r.first():
                        found_id = cid
                        break
                else:
                    found_id = None

                if found_id:
                    await db.execute(text(
                        "UPDATE cards SET image_small = :u, image_large = :u "
                        "WHERE id = :c"
                    ), {"u": img, "c": found_id})
                    stats["matched_update"] += 1
                    log.info("  [%d/%d] UPD %s ← %s (%s)",
                             i, len(candidates), found_id, name or "?", num)
                elif not skip_insert:
                    new_id = f"{set_id}-{num}"
                    await db.execute(text(
                        "INSERT INTO cards (id, name, name_local, number, "
                        "number_int, rarity, image_small, image_large, "
                        "set_id, language, created_at, updated_at) "
                        "VALUES (:id, :n, :n, :num, :ni, 'Promo', :u, :u, "
                        ":sid, 'ko', now(), now())"
                    ), {"id": new_id, "n": name or new_id, "num": num,
                        "ni": int(num) if num.isdigit() else None,
                        "u": img, "sid": set_id})
                    stats["inserted"] += 1
                    log.info("  [%d/%d] NEW %s ← %s (%s)",
                             i, len(candidates), new_id, name or "?", num)

            # Also refresh set.total to reflect new inserts
            if not dry_run:
                await db.execute(text("""
                    UPDATE sets s
                       SET total = (SELECT COUNT(*) FROM cards c WHERE c.set_id = s.id),
                           printed_total = (SELECT COUNT(*) FROM cards c WHERE c.set_id = s.id)
                     WHERE s.id LIKE 'ko-p-%'
                """))
                await db.commit()
                log.info("committed")
            else:
                await db.rollback()
                log.info("DRY-RUN — rolled back")

    log.info("=== summary ===")
    for k, v in stats.items():
        log.info("  %-16s %d", k, v)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--skip-insert", action="store_true",
                   help="Only update existing cards; skip INSERTs for new numbers.")
    args = p.parse_args()
    asyncio.run(run(args.dry_run, args.skip_insert))


if __name__ == "__main__":
    main()
