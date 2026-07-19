"""Backfill zh-tw set logo_url from koca.shop (Taiwan Pokemon
retailer LO pointed to after the Bing-scrape misfire).

Bing Image Search proved unusable — its alt text is a boilerplate
`{query} 的圖片結果` string that always contains the query, so the
alt-based confidence check trivially passed and Bing's noisy top
results (FC Dallas logo, Michael Myers mask, NFL) sailed straight
into the catalog. Rolled that back.

koca.shop, by contrast, has a curated Pokemon planet with a public
JSON API (`/api/planets/pokemoncard_tw/series?limit=N`) that returns
each zh-tw series with a proper `media` array of retailer-verified
product photos. Name → series-ID mapping is done in Python via a
Simplified/Traditional-tolerant normalized-string match against the
27 zhtw-* rows in our DB; misses are logged for LO to hand-supply
URLs (small number expected, likely just the newest tactical decks
or promo-only sets).

Storage: the image URL is Bing^H^H^H koca's own CDN,
`api.koca.shop/images/{media_id}.jpeg` — stable HTTPS, no hot-link
protection. Whitelisted in next.config.mjs alongside the earlier
zh-tw work.

Usage:
    python -m scripts.backfill_zhtw_logos_koca --dry-run
    python -m scripts.backfill_zhtw_logos_koca
    python -m scripts.backfill_zhtw_logos_koca --set zhtw-M4
"""
from __future__ import annotations
import argparse
import asyncio
import io
import json
import logging
import re
import subprocess
import sys
from difflib import SequenceMatcher
from pathlib import Path

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402
from app.database import SessionLocal, init_db  # noqa: E402

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("backfill_zhtw_logos_koca")


KOCA_API = "https://koca.shop/api/planets/pokemoncard_tw/series?limit=100"
KOCA_IMG = "https://api.koca.shop/images/{media_id}.jpeg"

# Product-type prefixes we strip from BOTH sides before comparing so
# our stored `擴充包「忍者飛旋」` matches koca's `忍者飛旋`.
_PRODUCT_PREFIXES = ("擴充包", "高級擴充包", "挑戰牌組", "戰術牌組",
                     "初階牌組", "特典卡", "ex初階牌組")


def _normalize(s: str | None) -> str:
    """Strip product-type prefix, 「」brackets, whitespace, and lower
    ASCII to make matching prefix-insensitive."""
    if not s:
        return ""
    t = s.strip()
    for prefix in _PRODUCT_PREFIXES:
        if t.startswith(prefix):
            t = t[len(prefix):].strip()
            break
    if t.startswith("「") and t.endswith("」"):
        t = t[1:-1].strip()
    # Collapse ASCII spaces/punct and lower
    t = re.sub(r"[\s\-_「」『』（）()【】\[\]]", "", t).lower()
    return t


def _fetch_koca_series() -> list[dict]:
    # koca's edge returns 500 to urllib's HTTP/1.1 requests (some
    # protocol/UA discriminator); curl gets HTTP/2 and a clean 200.
    # Also: `?limit=200+` blows the server up but `limit=100` returns
    # every zh-tw Pokemon series in one shot (currently 82 records).
    result = subprocess.run(
        ["curl", "-s", "-A", "Mozilla/5.0",
         "-H", "Accept: application/json", KOCA_API],
        capture_output=True, text=True, timeout=30, encoding="utf-8",
    )
    if result.returncode != 0:
        raise RuntimeError(f"curl failed: {result.stderr}")
    payload = json.loads(result.stdout)
    records = payload.get("records", [])
    out: list[dict] = []
    for rec in records:
        media = rec.get("media") or []
        # Prefer explicit `category: front` — that's the pack-shot
        front = next((m for m in media if m.get("category") == "front"), None)
        first = front or (media[0] if media else None)
        if not first or not first.get("id"):
            continue
        out.append({
            "id": rec["id"],
            "name": rec.get("name", ""),
            "url": rec.get("url"),
            "release": rec.get("releaseDate"),
            "logo": KOCA_IMG.format(media_id=first["id"]),
        })
    return out


async def _list_targets(only_set: str | None) -> list[tuple[str, str]]:
    async with SessionLocal() as db:
        sql = ("SELECT id, name FROM sets "
               "WHERE language='zh-tw' AND name IS NOT NULL AND name <> '' "
               "AND logo_url IS NULL")
        params: dict = {}
        if only_set:
            sql = sql.replace("AND logo_url IS NULL", "")
            sql += " AND id = :sid"
            params["sid"] = only_set
        rows = (await db.execute(text(sql), params)).all()
    return [(r.id, r.name) for r in rows]


def _best_match(our_name: str, catalog: list[dict]) -> tuple[dict | None, float]:
    ours = _normalize(our_name)
    if not ours:
        return None, 0.0
    best = None
    best_score = 0.0
    for c in catalog:
        theirs = _normalize(c["name"])
        if not theirs:
            continue
        # Exact match short-circuits
        if ours == theirs:
            return c, 1.0
        # Substring bonus — ONLY when the ratio of the shorter to
        # longer is high. Otherwise 噴火龍 (Charizard) matches
        # 超級噴火龍Xex (Charizard X ex) at 0.94 even though they're
        # different sets.
        if ours in theirs or theirs in ours:
            ratio = min(len(ours), len(theirs)) / max(len(ours), len(theirs))
            if ratio >= 0.75:
                score = 0.9 + 0.1 * ratio
            else:
                score = SequenceMatcher(None, ours, theirs).ratio()
        else:
            score = SequenceMatcher(None, ours, theirs).ratio()
        if score > best_score:
            best_score = score
            best = c
    return best, best_score


async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--set", dest="only_set", default=None,
                    help="Limit to one zhtw-* set id")
    ap.add_argument("--min-score", type=float, default=0.90,
                    help="Reject matches below this SequenceMatcher score")
    args = ap.parse_args()

    log.info("Fetching koca zh-tw series catalog …")
    catalog = _fetch_koca_series()
    log.info(f"  got {len(catalog)} koca series")

    await init_db()
    targets = await _list_targets(args.only_set)
    log.info(f"zh-tw sets awaiting a logo: {len(targets)}")
    if not targets:
        return 0

    matched: list[tuple[str, str, str, float]] = []
    unmatched: list[tuple[str, str]] = []

    for sid, name in targets:
        best, score = _best_match(name, catalog)
        if best and score >= args.min_score:
            matched.append((sid, name, best["logo"], score))
            log.info(f"  {sid:15s} {name!r:40s} → {best['name']!r} "
                     f"[score={score:.2f}] → {best['logo']}")
        else:
            unmatched.append((sid, name))
            koca_guess = best["name"] if best else "(none)"
            log.info(f"  {sid:15s} {name!r:40s} MISS "
                     f"(best guess {koca_guess!r} score={score:.2f})")

    print()
    print(f"matched: {len(matched)}, unmatched: {len(unmatched)}")

    if args.dry_run:
        print("--dry-run: no writes")
        return 0

    if not matched:
        return 0

    async with SessionLocal() as db:
        for sid, _name, url, _score in matched:
            await db.execute(
                text("UPDATE sets SET logo_url=:u, updated_at=NOW() WHERE id=:s"),
                {"u": url, "s": sid},
            )
        await db.commit()
    print(f"wrote {len(matched)} logo_urls")

    if unmatched:
        print()
        print("=== NEEDS LO HAND-SUPPLY ===")
        for sid, name in unmatched:
            print(f"  {sid:15s}  {name}")

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
