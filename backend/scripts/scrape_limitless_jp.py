"""Scrape JP card data from limitlesstcg.com for sets TCGdex left empty.

TCGdex's /v2/ja API returns set metadata for older SwSh and select SV sets
(S11a, S10b, SV5M, SV6a, etc.) but their `cards` array is empty and there
is no per-card endpoint. Limitless TCG has full Japanese coverage with
clean CDN-hosted images.

Pattern:
  list page  /cards/jp/{SET}            -> card numbers + SM image URLs
  detail     /cards/jp/{SET}/{N}        -> JP name (from <title>)
  image SM   .../tpc/{SET}/{SET}_{N}_{R}_JP_SM.png
  image LG   .../tpc/{SET}/{SET}_{N}_{R}_JP_LG.png

Usage:
    python -m scripts.scrape_limitless_jp                 # fill every empty visible set
    python -m scripts.scrape_limitless_jp --set S11a      # one set
    python -m scripts.scrape_limitless_jp --dry-run
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import re
from dataclasses import dataclass

import httpx
from sqlalchemy import select, text

from app.database import SessionLocal, init_db
from app.models import Card, Set

log = logging.getLogger("scrape_limitless_jp")

BASE = "https://limitlesstcg.com"
SEM = 8


@dataclass
class CardInfo:
    set_id: str
    number: str          # "1", "73", etc.
    name_jp: str
    image_small: str
    image_large: str


async def _empty_visible_sets(db) -> list[str]:
    rows = (await db.execute(text("""
        SELECT s.id FROM sets s
        LEFT JOIN cards c ON c.set_id=s.id AND c.language='ja'
        WHERE s.language='ja'
          AND s.logo_url IS NOT NULL
        GROUP BY s.id
        HAVING COUNT(c.id) = 0
        ORDER BY s.id
    """))).all()
    return [r[0] for r in rows]


async def _fetch_list(client: httpx.AsyncClient, set_id: str) -> list[tuple[str, str]]:
    """Returns [(card_number, sm_image_url), ...] for one set."""
    r = await client.get(f"{BASE}/cards/jp/{set_id}", timeout=20)
    if r.status_code != 200:
        log.warning(f"  ! {set_id} list HTTP {r.status_code}")
        return []
    html = r.text
    # Anchor blocks with both href + img inside
    blocks = re.findall(
        rf'<a[^>]+href="(/cards/jp/{re.escape(set_id)}/(\d+))"[^>]*>(.*?)</a>',
        html, re.DOTALL,
    )
    out = []
    seen = set()
    for _href, num, content in blocks:
        if num in seen:
            continue
        seen.add(num)
        img = re.search(r'src="([^"]+_SM\.png)"', content)
        if not img:
            continue
        out.append((num, img.group(1)))
    return out


_TITLE_RE = re.compile(r'<title>([^<]+)</title>', re.IGNORECASE)


async def _fetch_name(client: httpx.AsyncClient, set_id: str, num: str) -> str:
    r = await client.get(f"{BASE}/cards/jp/{set_id}/{num}", timeout=20)
    if r.status_code != 200:
        return ""
    m = _TITLE_RE.search(r.text)
    if not m:
        return ""
    title = m.group(1)
    # Format: "<JP name> - <set name> (<setid>) #<n> – Limitless"
    # Take everything before the first " - ".
    name = title.split(" - ", 1)[0].strip()
    return name


async def _scrape_set(client: httpx.AsyncClient, set_id: str) -> list[CardInfo]:
    listing = await _fetch_list(client, set_id)
    if not listing:
        log.info(f"  {set_id}: empty list")
        return []
    log.info(f"  {set_id}: {len(listing)} cards on list page, fetching names…")

    sem = asyncio.Semaphore(SEM)

    async def one(num: str, sm_url: str) -> CardInfo | None:
        async with sem:
            name = await _fetch_name(client, set_id, num)
        if not name:
            return None
        lg_url = sm_url.replace("_SM.png", "_LG.png")
        return CardInfo(set_id=set_id, number=num, name_jp=name,
                        image_small=sm_url, image_large=lg_url)

    results = await asyncio.gather(*[one(n, u) for n, u in listing])
    return [r for r in results if r]


async def _upsert(db, cards: list[CardInfo]) -> int:
    written = 0
    for c in cards:
        card_id = f"{c.set_id}-{c.number}"
        row = await db.get(Card, card_id)
        if row is not None and row.language != "ja":
            log.warning(f"  ! skip {card_id}: existing row language={row.language!r}")
            continue
        if row is None:
            row = Card(id=card_id, language="ja", set_id=c.set_id)
            db.add(row)
        row.name = c.name_jp
        row.name_local = c.name_jp
        row.number = c.number
        try:
            row.number_int = int(c.number)
        except ValueError:
            row.number_int = None
        row.image_small = c.image_small
        row.image_large = c.image_large
        row.set_id = c.set_id
        row.language = "ja"
        written += 1
    await db.commit()
    return written


async def run(only: str | None, dry: bool) -> None:
    await init_db()

    async with SessionLocal() as db:
        if only:
            targets = [only]
        else:
            targets = await _empty_visible_sets(db)
            log.info(f"Found {len(targets)} visible JP sets with 0 cards.")

    if not targets:
        log.info("Nothing to do.")
        return

    headers = {"User-Agent": "PullList-Catalog/1.0 (+https://pulllist.org)"}
    async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
        for i, sid in enumerate(targets, 1):
            log.info(f"[{i}/{len(targets)}] {sid}")
            cards = await _scrape_set(client, sid)
            if not cards:
                continue
            if dry:
                log.info(f"  {sid}: would write {len(cards)} cards (sample: {cards[0].name_jp})")
                continue
            async with SessionLocal() as db:
                n = await _upsert(db, cards)
                log.info(f"  {sid}: wrote {n} cards")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--set", dest="only", help="One TCGdex set id (e.g. S11a)")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    asyncio.run(run(args.only, args.dry_run))


if __name__ == "__main__":
    main()
