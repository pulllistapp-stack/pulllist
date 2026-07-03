"""Import JP Unnumbered Promo cards via row-level table parsing.

Bulbapedia's `Unnumbered_Promotional_cards_(TCG)` main page + the
`/1996-2005` subpage list every card in a <tr> row with:
  col 0  number ("—" or specific)
  col 1  image placeholder (hidden; Bulbapedia hasn't uploaded scans
         to this listing table for most entries)
  col 2  card link + variant tags in [brackets]
  col 3  energy type icon
  col 4  rarity
  col 5+ description (issue/date/promo channel)

Anchor targets often redirect (Pikachu_(CoroCoro_promo) → the shared
Wizards_Promo_1 page), and the target page carries multiple images
across reprint variants. Rather than trust first-image on the target
page, we:

  1. Parse every card row into structured (name, variant, description).
  2. Follow the anchor redirect to get a canonical URL — dedupe on it.
  3. On the target page, only accept an image whose filename ENCODES
     a JP-only promo tag (Toyota, Playmat, CoroCoro, FanBook, JRPromo,
     PhoneCard, CardFile, Snap, Asobikata, Trophy). Reprints (Wizards
     Promo, XY Promo, Portuguese) get rejected. If nothing qualifies,
     image_small stays NULL — a "no image" placeholder is better than
     the wrong card's image.

Cards land in year-bucketed sets: JPP-U1996 (holds 1996-2005 lump,
matching Bulbapedia's own grouping) plus JPP-U{Y} for 2006-2024.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import re
import unicodedata
from urllib.parse import unquote

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
_ROW_RE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.DOTALL)
# Card link: <a href="/wiki/PATH" ... title="..."> pokemon name </a>
_CARD_LINK_RE = re.compile(
    r'<a href="(/wiki/[^"#]+)"[^>]*(?:class="mw-redirect")?[^>]*title="([^"]+)"[^>]*>([^<]+)</a>'
)
_BRACKET_TAG_RE = re.compile(r"\[([^\]]+)\]")

# Filename patterns that are trustworthy JP promo files
_JP_FILE_KEYS = [
    "CoroCoro", "Corocoro", "Toyota", "Playmat", "FanBook", "Fan_Book",
    "CardFile", "Card_File", "JR_Promo", "JRPromo", "Snap", "PhoneCard",
    "Phone_Card", "Asobikata", "Trophy", "GrandParty", "Grand_Party",
    "BestPhoto", "NintendoDistribution", "MovieCommemoration",
    "Movie_Commemoration", "TropicalMega", "Tropical_Mega",
    "KidsAnniversary", "Kids_Anniversary", "Old_Maid", "OldMaid",
    "IllustratorContest", "Illustrator", "Gym_Challenge_Master_Key",
    "GymChallengeMasterKey", "Battle_Master", "BattleMaster",
]
# Reprint / wrong-variant filenames to reject
_REJECT_FILE_KEYS = [
    "WizardsPromo", "Wizards_Promo", "XYPromo", "XY_Promo",
    "Portuguese", "German", "Spanish", "French", "Italian", "Korean",
    "TCG_Card_Back", "CardBack", "TCG1_", "TCG2_", "Project_",
    "Portal_", "Bulbapedia_", "Poke_dollar", "Coin_",
]

_INFOBOX_IMG_RE = re.compile(
    r'<a href="/wiki/File:([^"]+\.(?:jpg|png))"[^>]*class="mw-file-description"[^>]*>'
    r'\s*<img[^>]+src="([^"]+)"[^>]+class="mw-file-element"',
    re.IGNORECASE,
)


async def _fetch_full(c: httpx.AsyncClient, url: str) -> tuple[int, str, str]:
    try:
        r = await c.get(url, timeout=25, follow_redirects=True)
    except httpx.HTTPError:
        return 0, "", url
    return r.status_code, r.text, str(r.url)


def _slice_jp_section(html: str) -> str:
    for m in _H2_RE.finditer(html):
        if "japanese" in m.group(2).lower():
            return html[m.end():]
    return ""


def _split_by_year(section_html: str) -> dict[str, str]:
    marks = [(m.start(), m.group(2).strip()) for m in _H3_RE.finditer(section_html)]
    return {label: section_html[start:(marks[i + 1][0] if i + 1 < len(marks) else len(section_html))]
            for i, (start, label) in enumerate(marks)}


def _first_year(label: str) -> str | None:
    m = re.search(r"(\d{4})", label)
    return m.group(1) if m else None


def _parse_row(row_html: str) -> dict | None:
    """Extract (anchor, name_base, variant_tag, description) from a table row."""
    # Card link column
    m = _CARD_LINK_RE.search(row_html)
    if not m:
        return None
    href = m.group(1)
    pokemon = m.group(3).strip()
    # anchor after the link may carry [brackets]
    after = row_html[m.end():]
    variant_m = _BRACKET_TAG_RE.search(after[:300])
    variant = variant_m.group(1).strip() if variant_m else None
    # Description column (last <td> tends to hold text)
    tds = re.findall(r"<td[^>]*>(.*?)</td>", row_html, re.DOTALL)
    desc = None
    for td in reversed(tds):
        text_only = re.sub(r"<[^>]+>", " ", td)
        text_only = re.sub(r"\s+", " ", text_only).strip()
        if text_only and text_only not in {"—", "-"} and len(text_only) > 4:
            desc = text_only[:180]
            break
    return {"href": href, "pokemon": pokemon, "variant": variant, "description": desc}


def _slug(name: str) -> str:
    """Turn 'No.1 Trainer' or 'Pokémon Illustrator' into a canonical
    lowercase alnum string to compare against filenames."""
    s = unicodedata.normalize("NFKD", name)
    s = re.sub(r"[^A-Za-z0-9]", "", s)
    return s.lower()


def _pick_image(html: str, row_name: str, row_desc: str | None) -> str | None:
    """Pick a card image from the target page.

    Rules (strictest first — a hit at rule N skips N+1):
      1. filename starts with row Pokémon/name AND filename encodes a
         JP-promo tag that ALSO appears in the row description
         (e.g. row says "CoroCoro Comic" and file is
         PikachuCoroCoroPromo.jpg — high confidence match).
      2. filename starts with row Pokémon/name AND encodes any JP tag.
         Only picked if there's exactly one such file (no ambiguity).
      3. otherwise NULL — better to show a placeholder than the wrong
         card's image.
    """
    row_slug = _slug(row_name.split("[")[0])
    if not row_slug:
        return None
    # Build a list of candidate substrings to look for in the filename.
    # Bulbapedia's naming inconsistently keeps or drops role suffixes
    # (Trophy Cards are stored as "TropicalMegaBattleNo1" — no "Trainer"),
    # so trim well-known suffixes and also allow the individual word slugs.
    prefixes = {row_slug}
    for suffix in ("trainer", "pikachu", "trophy"):
        if row_slug.endswith(suffix) and len(row_slug) > len(suffix) + 2:
            prefixes.add(row_slug[: -len(suffix)])
    # Also individual meaningful tokens (kept from _slug — no spaces)
    for tok in re.findall(r"[a-z0-9]+", " ".join(re.findall(r"[A-Za-z0-9]+", row_name.split("[")[0])).lower()):
        if len(tok) >= 3:
            prefixes.add(tok)
    prefix_list = sorted(prefixes, key=lambda p: -len(p))
    desc_lower = (row_desc or "").lower()

    strict_hit = None
    ambig_candidates = []

    for filename, src in _INFOBOX_IMG_RE.findall(html):
        f_lower = filename.lower()
        if any(k.lower() in f_lower for k in _REJECT_FILE_KEYS):
            continue
        f_slug = _slug(unquote(filename))
        if not any(p in f_slug for p in prefix_list):
            continue

        # Which JP tags fire on this filename?
        tags_in_file = [k for k in _JP_FILE_KEYS if k.lower() in f_lower]
        if not tags_in_file:
            continue

        # Rule 1 — a matching tag also appears in row description
        for tag in tags_in_file:
            token = re.sub(r"[_%]", "", tag).lower()
            if token in re.sub(r"\s+", "", desc_lower):
                strict_hit = src
                break
        if strict_hit:
            break

        ambig_candidates.append(src)

    # Second-chance: exactly one candidate AND the row describes a
    # promo channel that credibly maps to a JP file. This rescues cases
    # like Pokémon Illustrator (file: PokémonIllustratorCoroCoroPromo,
    # desc: "Illust Artist Contest" — neither is literally "CoroCoro"
    # but the file is uniquely the right card).
    _DESC_CHANNEL_HINTS = (
        "coro", "corocoro", "snap", "playmat", "fan book", "fanbook",
        "card file", "cardfile", "jr ", "phone", "fan club", "fanclub",
        "illustrator", "trophy", "mega battle", "megabattle", "tropical",
        "contest", "ancient mew", "movie", "toyota", "asobikata", "old maid",
        "battle master", "kids", "world", "issue insert",
    )
    if not strict_hit and len(ambig_candidates) == 1:
        if any(hint in desc_lower for hint in _DESC_CHANNEL_HINTS):
            strict_hit = ambig_candidates[0]

    src = strict_hit
    if not src:
        return None
    return re.sub(
        r"/thumb/((?:[^/]+/){2}[^/]+\.(?:jpg|png))/\d+px-[^/]+$", r"/\1", src
    )


async def run(dry: bool) -> None:
    await init_db()
    headers = {"User-Agent": "PullList-Catalog/1.0 (+https://pulllist.org)"}
    stats = {"rows": 0, "unique": 0, "with_image": 0, "seeded": 0, "skipped": 0}

    async with httpx.AsyncClient(headers=headers, follow_redirects=True) as c:
        # Fetch the main page + subpage
        _, main_html, _ = await _fetch_full(c, f"{BASE}/wiki/{PAGE}")
        jp_section = _slice_jp_section(main_html)
        buckets = _split_by_year(jp_section)

        for year_label, chunk in buckets.items():
            year = _first_year(year_label)
            if not year:
                continue
            set_id = f"JPP-U{year}"
            # 1996-2005 lump on a subpage
            if year == "1996":
                _, sub_html, _ = await _fetch_full(c, f"{BASE}/wiki/{PAGE}/1996-2005")
                if sub_html:
                    chunk = sub_html

            rows = _ROW_RE.findall(chunk)
            parsed = []
            for row in rows:
                p = _parse_row(row)
                if not p:
                    continue
                stats["rows"] += 1
                parsed.append(p)
            log.info(f"[{set_id}] {year_label} → {len(parsed)} rows parsed")

            # Dedupe by canonical (post-redirect) URL
            seen_urls = set()
            deduped = []
            for p in parsed:
                # Resolve redirect
                status, html, final_url = await _fetch_full(c, BASE + p["href"])
                if status != 200:
                    continue
                if final_url in seen_urls:
                    continue
                seen_urls.add(final_url)
                p["_html"] = html
                p["_final_url"] = final_url
                deduped.append(p)
            stats["unique"] += len(deduped)
            log.info(f"[{set_id}]   {len(deduped)} unique after redirect dedupe")

            # Seed set
            async with SessionLocal() as db:
                if not await db.get(Set, set_id):
                    db.add(Set(
                        id=set_id, language="ja", series="Promos",
                        name=f"Unnumbered Promos ({year_label})",
                        name_en=f"Unnumbered Promos ({year_label})",
                    ))
                    await db.commit()

            for i, p in enumerate(deduped, 1):
                card_id = f"{set_id}-{i:03d}"
                async with SessionLocal() as db:
                    if await db.get(Card, card_id):
                        stats["skipped"] += 1
                        continue
                img = _pick_image(p["_html"], p["pokemon"], p.get("description"))
                if img:
                    stats["with_image"] += 1
                display_name = p["pokemon"]
                if p["variant"]:
                    display_name = f"{p['pokemon']} [{p['variant']}]"
                if dry:
                    log.info(f"  + {card_id} name={display_name!r} img={bool(img)}")
                    continue
                async with SessionLocal() as db:
                    db.add(Card(
                        id=card_id,
                        set_id=set_id,
                        language="ja",
                        name=display_name,
                        flavor_text=p.get("description"),
                        number=f"{i:03d}",
                        number_int=i,
                        image_small=img,
                    ))
                    await db.commit()
                stats["seeded"] += 1

    log.info(f"\n=== Summary ===")
    for k, v in stats.items():
        log.info(f"  {k}: {v}")


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
