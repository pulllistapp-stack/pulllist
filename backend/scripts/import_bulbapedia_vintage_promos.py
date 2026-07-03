"""Import vintage JP promo cards from Bulbapedia.

Two targets confirmed by probe:
  Southern_Islands_(TCG)          — 23 card anchors → JPP-SI
  P_Promotional_cards_(TCG)       — 47 card anchors → JPP-P

For each: enumerate card anchors, fetch each card's page, pull the
first non-EN image (Bulbapedia archives), pull the JP-name if
present in the infobox, insert under the given set_id.

We don't strip the existing JPP-P (has 10 cards already) — insert
new ids for the ones not present. IDs use "{set_id}-{num:03d}".
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import re

import httpx
from sqlalchemy import text

from app.database import SessionLocal, init_db
from app.models import Card, Set

log = logging.getLogger("import_bulbapedia_vintage_promos")

BASE = "https://bulbapedia.bulbagarden.net"

TARGETS = [
    # (set_id, wiki_page_slug, expected_prefix in anchor href)
    ("JPP-SI",  "Southern_Islands_(TCG)", "Southern_Islands"),
    ("JPP-P",   "P_Promotional_cards_(TCG)", "P_Promo"),
    # Vending Series 1/2/3 share the same wiki page — anchor filters
    # split them via prefix suffix "Vending_S1", "Vending_S2", "Vending_S3"
    ("JPP-VM1", "Vending_Machine_cards_(TCG)", "Vending_S1"),
    ("JPP-VM2", "Vending_Machine_cards_(TCG)", "Vending_S2"),
    ("JPP-VM3", "Vending_Machine_cards_(TCG)", "Vending_S3"),
]

# Match the /wiki/NAME_(PARENTHETICAL) shape and hand the caller the
# raw parenthetical to filter/split on. Numbered shape ends with _NN;
# unnumbered (Vending) shape is just the series suffix.
_ANCHOR_RE = re.compile(r'href="(/wiki/[A-Za-z0-9%\'_\-]+_\(([^)]+)\))"')
_CARDIMG_RE = re.compile(
    r'<a href="/wiki/File:([^"]+)\.(?:jpg|png)"[^>]*class="mw-file-description"[^>]*>'
    r'\s*<img[^>]+src="([^"]+)"',
    re.IGNORECASE,
)


async def _fetch(c: httpx.AsyncClient, url: str) -> str | None:
    try:
        r = await c.get(url, timeout=25)
    except httpx.HTTPError:
        return None
    return r.text if r.status_code == 200 else None


async def _enumerate_anchors(c: httpx.AsyncClient, slug: str, prefix: str) -> list[tuple[int, str]]:
    """Return [(num, href), …] unique by num. Prefix is the required
    LEADING label of the parenthetical part, e.g. "Southern_Islands"
    matches "Southern_Islands_5" but not "Wizards_Promo_49". For
    unnumbered anchors (Vending_S1 style), assign sequential ids in
    page order."""
    html = await _fetch(c, f"{BASE}/wiki/{slug}")
    if not html:
        return []
    numbered: dict[int, str] = {}
    unnumbered: list[str] = []
    seen_href = set()
    num_suffix_re = re.compile(r"_(\d+)$")
    for href, paren in _ANCHOR_RE.findall(html):
        # Trim trailing "_NN" (if any) then compare label leader
        m = num_suffix_re.search(paren)
        label = paren[: m.start()] if m else paren
        if label != prefix:
            continue
        if href in seen_href:
            continue
        seen_href.add(href)
        if m:
            numbered.setdefault(int(m.group(1)), href)
        else:
            unnumbered.append(href)
    if numbered:
        return sorted(numbered.items())
    return [(i + 1, href) for i, href in enumerate(unnumbered)]


async def _extract_page_data(c: httpx.AsyncClient, href: str) -> dict | None:
    html = await _fetch(c, BASE + href)
    if not html:
        return None
    # First image with mw-file-description
    img = None
    m = _CARDIMG_RE.search(html)
    if m:
        src = m.group(2)
        img = re.sub(r"/thumb/((?:[^/]+/){2}[^/]+\.(?:jpg|png))/\d+px-[^/]+$", r"/\1", src)
    # Try to find JP name in infobox: often "Japanese name" or JP-only ruby-ish text
    jp_name = None
    for m in re.finditer(r'>Japanese[^<]*<[^>]*>[^<]*<[^>]*>([぀-ヿ一-鿿\s・ーA-Za-z]+)<', html):
        cand = m.group(1).strip()
        if cand and len(cand) < 40:
            jp_name = cand
            break
    # EN name from the H1 title
    m = re.search(r'<h1[^>]*>\s*<span[^>]*>([^<]+)</span>', html)
    en_name = m.group(1).strip() if m else None
    return {"en_name": en_name, "jp_name": jp_name, "image_small": img}


async def run(dry: bool, only: str | None) -> None:
    await init_db()
    targets = [t for t in TARGETS if only is None or t[0] == only]

    stats = {"seeded_cards": 0, "skipped_existing": 0, "no_data": 0}
    headers = {"User-Agent": "PullList-Catalog/1.0 (+https://pulllist.org)"}
    async with httpx.AsyncClient(headers=headers, follow_redirects=True) as c:
        for set_id, slug, prefix in targets:
            anchors = await _enumerate_anchors(c, slug, prefix)
            log.info(f"[{set_id}] {slug} → {len(anchors)} anchors")

            # ensure set exists
            async with SessionLocal() as db:
                if not await db.get(Set, set_id):
                    db.add(Set(id=set_id, name=slug.replace("_"," ").replace("(TCG)","").strip(),
                               language="ja", series="Promos"))
                    await db.commit()

            for num, href in anchors:
                card_id = f"{set_id}-{num:03d}"
                async with SessionLocal() as db:
                    existing = await db.get(Card, card_id)
                if existing:
                    stats["skipped_existing"] += 1
                    continue
                data = await _extract_page_data(c, href)
                if not data:
                    stats["no_data"] += 1
                    continue
                log.info(f"  + {card_id} name={data['en_name']!r} jp={data.get('jp_name')} img={bool(data.get('image_small'))}")
                if dry:
                    continue
                async with SessionLocal() as db:
                    db.add(Card(
                        id=card_id,
                        set_id=set_id,
                        language="ja",
                        name=data["en_name"] or f"{set_id}-{num}",
                        name_local=data.get("jp_name"),
                        number=f"{num:03d}",
                        number_int=num,
                        image_small=data.get("image_small"),
                    ))
                    await db.commit()
                stats["seeded_cards"] += 1

    log.info(f"\n=== Summary ===")
    for k, v in stats.items():
        log.info(f"  {k}: {v}")
    if dry:
        log.info("MODE: DRY-RUN — no writes")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--only", help="One set id (JPP-SI or JPP-P)")
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    asyncio.run(run(args.dry_run, args.only))


if __name__ == "__main__":
    main()
