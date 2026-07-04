"""Backfill JPP-U* card images from pokumon.com.

Pokumon.com is a public community-run Pokemon TCG promo catalog with
463 "Unnumbered" cards indexed via WordPress REST API. Their metadata
(name, release context, year) is granular enough to cleanly match
against our Bulbapedia-seeded JPP-U rows.

Pipeline:
  1) Enumerate `promo_set=Unnumbered` cards via `/wp-json/wp/v2/card`.
  2) Resolve each card's `featured_media` -> `source_url` (CDN image).
  3) Fuzzy-match pokumon titles to our JPP-U cards by (bare name +
     context keywords + year).
  4) Download image locally to frontend/public/jp-unn/{card_id}.jpg,
     update cards.image_small / image_large.

Idempotent. Rate-limited (1 req/sec to be polite). Skips card_ids that
already have image_small set unless --force is passed.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import html as htmlmod
import json
import logging
import re
from datetime import datetime
from pathlib import Path

import httpx
from sqlalchemy import text

from app.database import SessionLocal, init_db

log = logging.getLogger("backfill_jpp_unn_from_pokumon")

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
MIRROR_DIR = REPO_ROOT / "frontend" / "public" / "jp-unn"

API = "https://pokumon.com/wp-json/wp/v2"
TERM_UNNUMBERED = 1103
UA = "PullList-Catalog/1.0 (+https://pulllist.org; ja-promo-backfill)"

# Pokumon.com serves a "Card Image Missing" placeholder for entries
# that don't have a real scan yet. If we download that, we'd be
# claiming coverage we don't actually have. Detect and reject.
# The placeholder is a distinctive Pikachu-face-on-blue image with the
# POKUMON logo. Verified content hashes:
_PLACEHOLDER_HASHES = {
    "c6ad5f3b830f86ad9ed471f81c98f4fd",  # "Card Image Missing" placeholder, 139468 bytes
    "4511c088189886ed487eec4930191a8a",  # Composite w/ "POKUMON" watermark (BR2002 No.2 Trainer)
}

# Distinctive keyword pairs (pokumon title fragment <-> our flavor_text
# fragment). Used to score match quality when multiple pokumon entries
# share a Pokemon base name.
_CTX_PAIRS = [
    ("corocoro", "corocoro"),
    ("fan book", "fan book"), ("fanbook", "fan book"),
    ("fan club", "fan club"),
    ("nintendo 64", "nintendo 64"),
    ("world hobby fair", "world hobby fair"),
    ("nippon airlines", "nippon airlines"),
    ("stamp rally", "stamp rally"),
    ("jr train rally", "jr east"), ("jr east", "jr east"),
    ("trade please", "trade please"),
    ("premium file", "premium file"),
    ("garura", "garura"), ("parent/child", "garura"),
    ("tropical mega battle", "tropical mega battle"),
    ("champion road", "champion road"),
    ("grand party", "grand party"),
    ("secret super battle", "secret super battle"),
    ("lawrence iii", "lawrence"), ("mewtwo strikes", "mewtwo strikes"),
    ("mirage", "mirage"), ("lugia's explosive", "lugia"),
    ("song best collection", "song best collection"),
    ("pokemon plaza", "pokemon plaza"),
    ("summer vacation", "summer vacation"),
    ("neo premium", "premium file"),
    ("official card file", "official card file"),
    ("gameboy", "gameboy"), ("game boy", "game boy"),
    ("toyota", "toyota"),
    ("playmat", "playmat"),
    ("snap", "snap"),
    ("nintendo power", "nintendo power"),
    ("no.1 trainer", "no.1 trainer"),
    ("no.2 trainer", "no.2 trainer"),
    ("no.3 trainer", "no.3 trainer"),
    ("phone card", "phone card"),
    ("celadon", "celadon"), ("hyper professor", "hyper professor"),
    ("communication evolution", "communication evolution"),
    ("neo imakuni", "imakuni"),
    ("lucky stadium", "lucky stadium"),
    ("crystal tower", "crystal tower"),
    ("mega battle", "mega battle"),
    ("all nippon airlines", "nippon airlines"),
    ("first partner", "first partner"),
    ("champion's league", "champion's league"),
    ("battle carnival", "battle carnival"),
    ("battle road", "battle road"),
    ("training tournament", "training tournament"),
    ("beauty contest", "beauty contest"),
    ("bilingual", "bilingual"),
    ("dvd", "dvd"),
    ("cd", " cd "), ("insert", "insert"),
    ("mcdonald", "mcdonald"),
    ("world championships", "world championship"),
]

# Year fragments to include in matcher
_YEAR_RE = re.compile(r"\b(19\d\d|20\d\d)\b")


def _clean_title(title_html: str) -> tuple[str, str]:
    """Split 'Name  (Context Year) (Unnumbered)' into (name, context)."""
    t = htmlmod.unescape(title_html)
    t = re.sub(r"\s*\(Unnumbered\)\s*$", "", t).strip()
    # Split on last paren for context
    m = re.match(r"^(.*?)\s*\(([^()]+)\)\s*$", t)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return t, ""


def _norm(s: str) -> str:
    s = re.sub(r"[^a-z0-9]", " ", (s or "").lower())
    return re.sub(r"\s+", " ", s).strip()


def _score(pokumon_ctx: str, pokumon_name: str, our_flavor: str, our_name: str) -> int:
    pc = pokumon_ctx.lower(); pn = pokumon_name.lower()
    f = (our_flavor or "").lower(); n = (our_name or "").lower()
    s = 0
    for pk, ok in _CTX_PAIRS:
        if pk in pc or pk in pn:
            if ok in f or ok in n:
                s += 3
    # Year match bonus
    py = _YEAR_RE.search(pokumon_ctx)
    if py and py.group(1) in f:
        s += 2
    # Variant bracket alignment (e.g. Jumbo in both)
    for tag in ("jumbo", "glossy", "non-holo", "phone card", "postcard",
                "bilingual", "prerelease", "first place", "trophy",
                "movie promo", "japanese exclusive"):
        if tag in pc or tag in pn:
            if tag in f or tag in n:
                s += 2
    return s


async def _fetch_cards(client: httpx.AsyncClient) -> list[dict]:
    """Enumerate all promo_set=Unnumbered cards from WP REST."""
    out: list[dict] = []
    page = 1
    while True:
        r = await client.get(
            f"{API}/card",
            params={
                "promo_set": TERM_UNNUMBERED,
                "per_page": 100,
                "page": page,
                "_fields": "id,slug,title,featured_media,link",
            },
            timeout=30,
        )
        r.raise_for_status()
        chunk = r.json()
        out.extend(chunk)
        log.info(f"  page {page}: {len(chunk)} cards")
        if len(chunk) < 100:
            break
        page += 1
        await asyncio.sleep(0.4)
    return out


async def _resolve_media(
    client: httpx.AsyncClient, media_ids: list[int]
) -> dict[int, str]:
    """Batch-fetch media source_urls. WP media endpoint doesn't accept
    include[] filter for arbitrary IDs, so we fetch one-by-one but
    with concurrency=6 to stay polite."""
    sem = asyncio.Semaphore(6)
    results: dict[int, str] = {}

    async def one(mid: int) -> None:
        async with sem:
            try:
                r = await client.get(f"{API}/media/{mid}",
                                     params={"_fields": "source_url"},
                                     timeout=30)
                if r.status_code == 200:
                    url = r.json().get("source_url")
                    if url:
                        results[mid] = url
            except httpx.HTTPError:
                pass

    tasks = [asyncio.create_task(one(mid)) for mid in media_ids if mid]
    for i in range(0, len(tasks), 20):
        await asyncio.gather(*tasks[i:i+20])
        await asyncio.sleep(0.2)
    return results


async def run(dry: bool, only: str | None, force: bool) -> None:
    await init_db()
    MIRROR_DIR.mkdir(parents=True, exist_ok=True)

    # ---- Phase 1: enumerate pokumon.com Unnumbered cards
    async with httpx.AsyncClient(headers={"User-Agent": UA},
                                 follow_redirects=True) as client:
        log.info("Enumerating pokumon.com Unnumbered set…")
        pk_cards = await _fetch_cards(client)
        log.info(f"  total: {len(pk_cards)} pokumon entries")

        media_ids = [c.get("featured_media") for c in pk_cards
                     if c.get("featured_media")]
        log.info(f"Resolving {len(media_ids)} media entries…")
        media = await _resolve_media(client, media_ids)
        log.info(f"  resolved: {len(media)}")

    # Enrich pokumon entries with parsed (name, context) + image url
    for c in pk_cards:
        n, ctx = _clean_title(c["title"]["rendered"])
        c["_name"] = n
        c["_ctx"] = ctx
        c["_img"] = media.get(c.get("featured_media"), "")

    # Index pokumon by normalized bare name (strip variant parens)
    from collections import defaultdict
    by_name = defaultdict(list)
    for c in pk_cards:
        key_bare = _norm(re.sub(r"\s*\[[^\]]+\]", "", c["_name"]))
        by_name[key_bare].append(c)
        # Also index by full norm
        by_name[_norm(c["_name"])].append(c)

    # ---- Phase 2: query our missing JPP-U rows
    async with SessionLocal() as db:
        q = """SELECT id, name, flavor_text, image_small FROM cards
               WHERE set_id LIKE 'JPP-U%' AND language='ja'"""
        if not force:
            q += " AND image_small IS NULL"
        if only:
            q += f" AND id = '{only}'"
        rows = (await db.execute(text(q))).all()
    our_rows = [{"id": r.id, "name": r.name or "",
                 "flavor": r.flavor_text or "",
                 "img": r.image_small} for r in rows]
    log.info(f"Our target JPP-U rows: {len(our_rows)}")

    # ---- Phase 3: match + download
    stats = {"matched": 0, "downloaded": 0, "skipped_dup": 0,
             "no_match": 0, "download_failed": 0, "no_img_url": 0}
    updates: list[tuple[str, str]] = []

    async with httpx.AsyncClient(headers={"User-Agent": UA},
                                 follow_redirects=True) as client:
        for r in our_rows:
            key_full = _norm(r["name"])
            key_bare = _norm(re.sub(r"\s*\[[^\]]+\]", "", r["name"]))
            cands = list({c["id"]: c for c in
                          by_name.get(key_full, []) + by_name.get(key_bare, [])}
                         .values())
            if not cands:
                stats["no_match"] += 1
                continue

            scored = sorted(
                ((_score(c["_ctx"], c["_name"], r["flavor"], r["name"]), c)
                 for c in cands),
                key=lambda x: -x[0],
            )
            top_score, best = scored[0]
            if len(scored) > 1 and scored[1][0] == top_score:
                # Ambiguous tie — skip to avoid mismatch.
                stats["no_match"] += 1
                continue
            # For single-candidate case, we still require some signal
            # unless the name is truly unique (bracket variants like
            # "Trade Please!" have only one pokumon entry).
            if top_score < 2 and len(scored) > 1:
                stats["no_match"] += 1
                continue

            # Year sanity gate — the card_id embeds an era (JPP-U2015 =
            # 2015+, JPP-U1996 = 1996-2005 bucket). If pokumon's context
            # year is grossly outside our era, that's a spurious
            # single-candidate match. Skip.
            our_era = r["id"].replace("JPP-U", "")[:4]
            pk_year_match = _YEAR_RE.search(best["_ctx"])
            if pk_year_match and our_era.isdigit():
                pk_year = int(pk_year_match.group(1))
                our_year = int(our_era)
                if our_year == 1996:  # 1996-2005 bucket
                    if pk_year < 1996 or pk_year > 2005:
                        stats["no_match"] += 1
                        continue
                elif abs(pk_year - our_year) > 2:
                    # For yearly buckets, allow ±2 year slack (some cards
                    # span multiple event years, e.g. "2007,2008")
                    stats["no_match"] += 1
                    continue

            if not best.get("_img"):
                stats["no_img_url"] += 1
                continue

            stats["matched"] += 1
            img_url = best["_img"]
            # Prefer the 'full' size if not the original
            ext = Path(img_url.split("?")[0]).suffix.lower() or ".jpg"
            if ext not in (".jpg", ".jpeg", ".png", ".webp"):
                ext = ".jpg"
            dest = MIRROR_DIR / f"{r['id']}{ext}"
            local_rel = f"/jp-unn/{r['id']}{ext}"

            if not force and dest.exists() and dest.stat().st_size > 500:
                stats["skipped_dup"] += 1
                if r["img"] != local_rel:
                    updates.append((r["id"], local_rel))
                continue

            log.info(f"  + {r['id']:20s} <- {best['_name']!r} ({best['_ctx']}) "
                     f"[score={top_score}]")
            if dry:
                continue

            try:
                resp = await client.get(img_url, timeout=30)
            except httpx.HTTPError as e:
                log.warning(f"    ! download: {e}")
                stats["download_failed"] += 1
                continue
            if resp.status_code != 200 or len(resp.content) < 500:
                log.warning(f"    ! HTTP {resp.status_code}, bytes={len(resp.content)}")
                stats["download_failed"] += 1
                continue

            # Reject pokumon.com's own "Card Image Missing" placeholder.
            # This got past our earlier pass and contaminated 9 rows.
            content_hash = hashlib.md5(resp.content).hexdigest()
            if content_hash in _PLACEHOLDER_HASHES:
                log.warning(f"    ! {r['id']} pokumon placeholder — skip")
                stats.setdefault("placeholder_rejected", 0)
                stats["placeholder_rejected"] += 1
                continue

            dest.write_bytes(resp.content)
            stats["downloaded"] += 1
            updates.append((r["id"], local_rel))
            await asyncio.sleep(0.15)  # polite rate

    if updates and not dry:
        async with SessionLocal() as db:
            for cid, path in updates:
                await db.execute(
                    text("""UPDATE cards
                            SET image_small=:p, image_large=:p, updated_at=:now
                            WHERE id=:i"""),
                    {"p": path, "now": datetime.utcnow(), "i": cid},
                )
            await db.commit()
        log.info(f"DB updated: {len(updates)}")

    log.info("=== Summary ===")
    for k, v in stats.items():
        log.info(f"  {k}: {v}")
    if dry:
        log.info("MODE: DRY-RUN")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--only", help="Single card id, e.g. JPP-U1996-113")
    p.add_argument("--force", action="store_true",
                   help="Overwrite even if image_small already set")
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    asyncio.run(run(args.dry_run, args.only, args.force))


if __name__ == "__main__":
    main()
