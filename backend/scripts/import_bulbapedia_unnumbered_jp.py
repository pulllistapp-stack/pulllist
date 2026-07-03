"""Import Japanese unnumbered promos from Bulbapedia.

Bulbapedia's `Unnumbered_Promotional_cards_(TCG)` page splits at:
  <h2>Unnumbered Promotional cards</h2>           ← EN
  <h2>Japanese Unnumbered Promotional cards</h2>  ← we want this
    <h3>1996 - 2005</h3>
    <h3>2006</h3>
    <h3>2007</h3>
    ...

Everything after the 2nd H2 anchor is JP unnumbered. Split by the
year H3 headers and collect card anchors per year.

Card ids: {set_id}-{seq:03d} where set_id encodes the year bucket:
  JPP-U1996  1996-2005 combined bucket (Bulbapedia's own grouping)
  JPP-U2006  2006-only
  JPP-U2007  2007-only
  … through JPP-U{Y}

We deliberately shove multi-year into JPP-U1996 rather than split
per-year because Bulbapedia only exposes the combined block — no
per-year sub-headers exist in the 1996-2005 range.
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

log = logging.getLogger("import_unn_jp")

BASE = "https://bulbapedia.bulbagarden.net"
PAGE = "Unnumbered_Promotional_cards_(TCG)"

_H2_RE = re.compile(
    r'<h2[^>]*>.*?<span class="mw-headline"[^>]*id="([^"]+)"[^>]*>([^<]+)</span>',
    re.DOTALL,
)
_H3_RE = re.compile(
    r'<h3[^>]*>.*?<span class="mw-headline"[^>]*id="([^"]+)"[^>]*>([^<]+)</span>',
    re.DOTALL,
)
_ANCHOR_RE = re.compile(r'href="(/wiki/[A-Za-z0-9%\'_\-]+_\([^)]+\))"')
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


def _slice_jp_section(html: str) -> str:
    """Return substring after the 'Japanese Unnumbered Promotional cards' H2."""
    for m in _H2_RE.finditer(html):
        if "japanese" in m.group(2).lower():
            return html[m.end():]
    return ""


def _split_by_year(section_html: str) -> dict[str, str]:
    """Return {year_label: sub_html}. First segment may be pre-year prefatory
    text; skip it."""
    marks = [(m.start(), m.group(2).strip()) for m in _H3_RE.finditer(section_html)]
    buckets: dict[str, str] = {}
    for i, (start, label) in enumerate(marks):
        end = marks[i + 1][0] if i + 1 < len(marks) else len(section_html)
        buckets[label] = section_html[start:end]
    return buckets


def _first_year(label: str) -> str | None:
    """`'1996 - 2005'` → `'1996'`,  `'2006'` → `'2006'`."""
    m = re.search(r"(\d{4})", label)
    return m.group(1) if m else None


async def _extract_page_data(c: httpx.AsyncClient, href: str) -> dict:
    html = await _fetch(c, BASE + href)
    if not html:
        return {}
    m = _CARDIMG_RE.search(html)
    img = None
    if m:
        src = m.group(2)
        img = re.sub(
            r"/thumb/((?:[^/]+/){2}[^/]+\.(?:jpg|png))/\d+px-[^/]+$", r"/\1", src
        )
    m = re.search(r"<h1[^>]*>\s*<span[^>]*>([^<]+)</span>", html)
    en_name = m.group(1).strip() if m else None
    return {"en_name": en_name, "image_small": img}


async def run(dry: bool) -> None:
    await init_db()

    headers = {"User-Agent": "PullList-Catalog/1.0 (+https://pulllist.org)"}
    total_seeded = 0
    total_skipped = 0

    async with httpx.AsyncClient(headers=headers, follow_redirects=True) as c:
        html = await _fetch(c, f"{BASE}/wiki/{PAGE}")
        if not html:
            log.error("failed to fetch main page")
            return
        jp = _slice_jp_section(html)
        if not jp:
            log.error("could not find Japanese H2 section")
            return
        buckets = _split_by_year(jp)
        log.info(f"Year buckets: {list(buckets.keys())}")

        for year_label, chunk in buckets.items():
            year = _first_year(year_label)
            if not year:
                continue
            set_id = f"JPP-U{year}"
            # 1996-2005 lives in a subpage; fetch it separately.
            if year == "1996":
                sub = await _fetch(c, f"{BASE}/wiki/{PAGE}/1996-2005")
                if sub:
                    chunk = sub
            raw = _ANCHOR_RE.findall(chunk)
            anchors = [
                a for a in dict.fromkeys(raw)
                # Skip generic energy links (Fire_Energy_(TCG) etc.)
                if not re.search(r"_Energy_\(TCG\)$", a)
                and not a.endswith("_(TCG)")
            ]
            log.info(f"[{set_id}] {year_label}  →  {len(anchors)} anchors")

            async with SessionLocal() as db:
                if not await db.get(Set, set_id):
                    db.add(Set(
                        id=set_id, language="ja", series="Promos",
                        name=f"Unnumbered Promos ({year_label})",
                        name_en=f"Unnumbered Promos ({year_label})",
                    ))
                    await db.commit()

            for i, href in enumerate(anchors, 1):
                card_id = f"{set_id}-{i:03d}"
                async with SessionLocal() as db:
                    if await db.get(Card, card_id):
                        total_skipped += 1
                        continue
                data = await _extract_page_data(c, href)
                if not data:
                    continue
                if dry:
                    log.info(f"  + {card_id} name={data.get('en_name')!r}")
                    continue
                async with SessionLocal() as db:
                    db.add(Card(
                        id=card_id,
                        set_id=set_id,
                        language="ja",
                        name=data.get("en_name") or f"{set_id}-{i}",
                        number=f"{i:03d}",
                        number_int=i,
                        image_small=data.get("image_small"),
                    ))
                    await db.commit()
                total_seeded += 1

    log.info(f"\n=== Summary ===")
    log.info(f"  seeded_cards: {total_seeded}")
    log.info(f"  skipped_existing: {total_skipped}")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    asyncio.run(run(args.dry_run))


if __name__ == "__main__":
    main()
