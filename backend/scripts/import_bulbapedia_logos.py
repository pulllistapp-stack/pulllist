"""Fetch JP set logos from Bulbapedia and save URLs into Set.logo_url.

TCGdex's /ja API returns logo: null for every JP set we import, which
left the catalog grid full of placeholders. Bulbapedia has high-res
JP set logos hand-uploaded by the community on the page for each
expansion. This script walks a curated TCGdex-set-id -> Bulbapedia-
page-title mapping, hits the MediaWiki API to extract the JP logo
filename, resolves the actual image URL via imageinfo, and writes
that into Set.logo_url so the existing SetCard component picks it
up automatically.

We point Set.logo_url at archives.bulbagarden.net directly rather
than mirroring to /public — saves us a CDN expense and is what
Bulbapedia's image host is set up to serve. Add the hostname to
next.config's remotePatterns so Next.js Image accepts it.

Bulbapedia content is CC-BY-NC-SA 2.5; we credit them on /about.

Usage:
    python -m scripts.import_bulbapedia_logos
    python -m scripts.import_bulbapedia_logos --dry-run
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import re
from urllib.parse import quote

import httpx

from app.database import SessionLocal, init_db
from app.models import Set

log = logging.getLogger("import_bulbapedia_logos")

WIKI_API = "https://bulbapedia.bulbagarden.net/w/api.php"
USER_AGENT = "PullList-Catalog/1.0 (https://pulllist.org; hello@pulllist.org)"

# Hand-curated TCGdex JP set id -> Bulbapedia page title. Covering the
# most-trafficked JP sets first; expand the table as we surface more.
# The Bulbapedia page name is what `?action=parse&page=...` accepts.
JP_SET_TO_BULBAPEDIA: dict[str, str] = {
    # Mega Evolution era (2025-2026)
    "M3":     "Nihil Zero (TCG)",
    "M2":     "Inferno X (TCG)",
    "M1L":    "Mega Brave (TCG)",
    "M1S":    "Mega Symphonia (TCG)",
    # Scarlet & Violet era (JP)
    "SV11B":  "Black Bolt (TCG)",
    "SV11W":  "White Flare (TCG)",
    "SV10":   "Glory of Team Rocket (TCG)",
    "SV9a":   "Heat Wave Arena (TCG)",
    "SV9":    "Battle Partners (TCG)",
    "SV8a":   "Terastal Festival ex (TCG)",
    "SV8":    "Super-Electric Breaker (TCG)",
    "SV7a":   "Paradise Dragona (TCG)",
    "SV7":    "Stellar Miracle (TCG)",
    "SV6a":   "Night Wanderer (TCG)",
    "SV6":    "Mask of Change (TCG)",
    "SV5a":   "Crimson Haze (TCG)",
    "SV5M":   "Cyber Judge (TCG)",
    "SV5K":   "Wild Force (TCG)",
    "SV4a":   "Shiny Treasure ex (TCG)",
    "SV4M":   "Future Flash (TCG)",
    "SV4K":   "Ancient Roar (TCG)",
    "SV3a":   "Raging Surf (TCG)",
    "SV3":    "Ruler of the Black Flame (TCG)",
    "SV2a":   "Pokemon Card 151 (TCG)",
    "SV2D":   "Clay Burst (TCG)",
    "SV2P":   "Snow Hazard (TCG)",
    "SV1V":   "Violet ex (TCG)",
    "SV1S":   "Scarlet ex (TCG)",
    "SV1a":   "Triplet Beat (TCG)",
    # Sword & Shield era (JP, popular only)
    "S12a":   "VSTAR Universe (TCG)",
    "S12":    "Paradigm Trigger (TCG)",
    "S11a":   "Incandescent Arcana (TCG)",
    "S11":    "Lost Abyss (TCG)",
    "S10a":   "Dark Phantasma (TCG)",
    "S10":    "Pokemon GO (TCG)",
    "S10D":   "Time Gazer (TCG)",
    "S10P":   "Space Juggler (TCG)",
    "S9a":    "Battle Region (TCG)",
    "S9":     "Star Birth (TCG)",
    "S8a":    "25th Anniversary Collection (TCG)",
    "S8b":    "VMAX Climax (TCG)",
    "S8":     "Fusion Arts (TCG)",
    "S7R":    "Blue Sky Stream (TCG)",
    "S7D":    "Towering Perfection (TCG)",
    "S6a":    "Eevee Heroes (TCG)",
    "S6H":    "Silver Lance (TCG)",
    "S6K":    "Jet-Black Poltergeist (TCG)",
    "S5a":    "Matchless Fighters (TCG)",
    "S5R":    "Rapid Strike Master (TCG)",
    "S5I":    "Single Strike Master (TCG)",
    "S4a":    "Shiny Star V (TCG)",
    "S4":     "Amazing Volt Tackle (TCG)",
    "S3a":    "Legendary Heartbeat (TCG)",
    "S3":     "Infinity Zone (TCG)",
    "S2a":    "Explosive Walker (TCG)",
    "S2":     "Rebellion Crash (TCG)",
    "S1a":    "VMAX Rising (TCG)",
    "S1W":    "Sword (TCG)",
    "S1H":    "Shield (TCG)",
}


def _is_jp_logo_filename(name: str) -> bool:
    """Heuristic: Bulbapedia uploads JP set logos as e.g. M2_Logo_JP.png,
    SV9a_Logo_JP.png. We want the JP-suffix variant, not English."""
    return bool(re.search(r"Logo[_\s].*?JP", name, re.IGNORECASE)) and (
        ".png" in name.lower() or ".jpg" in name.lower() or ".jpeg" in name.lower()
    )


async def _page_images(client: httpx.AsyncClient, page: str) -> list[str]:
    r = await client.get(
        WIKI_API,
        params={"action": "parse", "page": page, "prop": "images", "format": "json"},
        timeout=20,
    )
    r.raise_for_status()
    body = r.json()
    if "error" in body:
        return []
    return list(body.get("parse", {}).get("images", []))


async def _file_url(client: httpx.AsyncClient, filename: str) -> str | None:
    """Resolve a File:Name.png -> its actual archives.bulbagarden.net URL."""
    r = await client.get(
        WIKI_API,
        params={
            "action": "query",
            "titles": f"File:{filename}",
            "prop": "imageinfo",
            "iiprop": "url|size",
            "format": "json",
        },
        timeout=20,
    )
    r.raise_for_status()
    pages = r.json().get("query", {}).get("pages", {})
    for _, pdata in pages.items():
        for ii in pdata.get("imageinfo", []):
            url = ii.get("url")
            if url:
                return url
    return None


async def run(dry: bool) -> None:
    await init_db()

    headers = {"User-Agent": USER_AGENT}
    found: dict[str, str] = {}
    misses: list[str] = []

    async with httpx.AsyncClient(headers=headers) as client:
        for set_id, page in JP_SET_TO_BULBAPEDIA.items():
            try:
                imgs = await _page_images(client, page)
            except httpx.HTTPError as e:
                log.warning(f"  ! {set_id:8s} page fetch failed: {e}")
                misses.append(set_id)
                continue

            jp_logos = [i for i in imgs if _is_jp_logo_filename(i)]
            if not jp_logos:
                # Fallback: any Logo file (some pages only have the EN logo
                # uploaded, which is still better than the blank placeholder).
                jp_logos = [i for i in imgs if "Logo" in i and (
                    ".png" in i.lower() or ".jpg" in i.lower()
                )]
            if not jp_logos:
                log.warning(f"  ! {set_id:8s} '{page}' — no logo files on page")
                misses.append(set_id)
                continue

            chosen = jp_logos[0]
            url = await _file_url(client, chosen)
            if not url:
                log.warning(f"  ! {set_id:8s} could not resolve {chosen}")
                misses.append(set_id)
                continue

            log.info(f"  ✓ {set_id:8s} {page:38s} -> {chosen} ({url})")
            found[set_id] = url

    if dry:
        log.info(f"\n  MODE: DRY RUN — {len(found)} matched, {len(misses)} missed")
        return

    async with SessionLocal() as db:
        for set_id, url in found.items():
            row = await db.get(Set, set_id)
            if row is None:
                log.warning(f"  ! {set_id} no longer in DB, skipping")
                continue
            row.logo_url = url
        await db.commit()

    log.info(f"\n=== Summary ===")
    log.info(f"  Matched + updated   : {len(found)}")
    log.info(f"  Misses              : {len(misses)}")
    if misses:
        log.info(f"  {misses}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing.")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    asyncio.run(run(args.dry_run))


if __name__ == "__main__":
    main()
