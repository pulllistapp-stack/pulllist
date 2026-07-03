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
from pathlib import Path
from urllib.parse import quote, urlparse

import httpx

from app.database import SessionLocal, init_db
from app.models import Set

# We mirror the images into the Next.js public folder so the frontend
# can serve them from its own origin. Bulbapedia sits behind Cloudflare
# with `Cross-Origin-Resource-Policy: same-origin` and a browser-UA
# challenge, so direct hotlinking from pulllist.org yields 403 even
# though server-to-server fetches return the bytes fine.
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
MIRROR_DIR = REPO_ROOT / "frontend" / "public" / "set-logos"

log = logging.getLogger("import_bulbapedia_logos")

WIKI_API = "https://bulbapedia.bulbagarden.net/w/api.php"
USER_AGENT = "PullList-Catalog/1.0 (https://pulllist.org; hello@pulllist.org)"

# Hand-curated TCGdex JP set id -> Bulbapedia page title. Covering the
# most-trafficked JP sets first; expand the table as we surface more.
# The Bulbapedia page name is what `?action=parse&page=...` accepts.
JP_SET_TO_BULBAPEDIA: dict[str, str] = {
    # Mega Evolution era (2025-2026)
    "M5":     "Abyss Eye (TCG)",
    "M4":     "Ninja Spinner (TCG)",
    "M3":     "Nihil Zero (TCG)",
    "M2a":    "MEGA Dream ex (TCG)",
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

# Direct image URL overrides for sets where Bulbapedia has no logo file
# uploaded. Drop a remote URL here, the script will download + mirror it
# under /public/set-logos/{set_id}.png. Useful for the modern JP sets
# whose Bulbapedia pages don't link a logo image (SV6, SV7a, SV8, SV8a,
# SV9, SV9a, SV10, S7D, S6K, S11a, SV2a, etc.).
#
# LO usage: when you find a logo image anywhere - pokemon-card.com,
# Twitter, a Reddit thread, a forum post - copy the image URL and add
# it here. The script handles the rest.
MANUAL_LOGO_URLS: dict[str, str] = {
    # card-binder.com collection thumbnails - clean, transparent webp logos
    # they uploaded for their JP set product pages. Mirroring to our own
    # /public/set-logos/ so we're not hotlinking their Shopify CDN.
    "SV9a":  "https://card-binder.com/cdn/shop/collections/Pokemon-TCG-Japan-Hot-Air-Heat-Wave-Arena-Logo_e4b93fa3-3e7e-43e5-8848-312ca721e511.webp",
    "SV10":  "https://card-binder.com/cdn/shop/collections/Glory-of-Team-Rocket.logo.413.webp",
    "SV9":   "https://card-binder.com/cdn/shop/collections/Pokemon-TCG-Japan-Battle-Partners-Logo_796f4586-33eb-40dd-bfdc-764a26dcc638.webp",
    "SV8a":  "https://card-binder.com/cdn/shop/collections/Pokemon-TCG-Japan-Terastal-Festival-ex-Logo_c23e1b7b-26bf-4f5a-af55-cfee69ff78d6.webp",
    "SV8":   "https://card-binder.com/cdn/shop/collections/Pokemon-TCG-Japan-Super-Electric-Breaker-Logo_5555e9c7-9a7d-49c6-927c-93874d6d3c2f.webp",
    "SV7a":  "https://card-binder.com/cdn/shop/collections/Pokemon-TCG-Japan-Paradise-Dragona-Logo_516d307a-a500-406c-811c-8fa370a9478b.webp",
    "SV6":   "https://card-binder.com/cdn/shop/collections/Pokemon-TCG-Japan-Mask-of-Change-Logo_bfce4f9b-a8b4-43f6-bcef-db3eab7d4431.webp",
    "SV2a":  "https://card-binder.com/cdn/shop/collections/Pokemon-TCG-Japan-151-Logo_038a8b53-aca5-42aa-9781-6b03e63614b0.webp",
    "S11a":  "https://card-binder.com/cdn/shop/collections/Incandescent-Arcana.logo.webp",
    "S7D":   "https://card-binder.com/cdn/shop/collections/Perfect-Skyscraper.logo.webp",
    "S6K":   "https://card-binder.com/cdn/shop/collections/Pokemon-Jet-Black-Spirit-Booster-Box-Japanese-s6K.webp",
    "S10b":  "https://card-binder.com/cdn/shop/collections/Pokemon_Go_97f5456a-f502-4f3d-b8f5-fc3f91511bfe.webp",
}


def _is_jp_logo_filename(name: str) -> bool:
    """Heuristic: Bulbapedia uploads JP set logos as e.g. M2_Logo_JP.png,
    SV5 Logo JP.png. Match either underscore or space separator. We want
    the JP variant, not English/Korean/etc."""
    if not (name.lower().endswith(".png") or name.lower().endswith(".jpg") or name.lower().endswith(".jpeg")):
        return False
    # "Logo JP" with space or underscore separator, JP must end a word
    return bool(re.search(r"Logo[_\s]+JP\b", name, re.IGNORECASE))


def _is_any_logo_filename(name: str) -> bool:
    if not (name.lower().endswith(".png") or name.lower().endswith(".jpg") or name.lower().endswith(".jpeg")):
        return False
    return "Logo" in name


async def _page_images(client: httpx.AsyncClient, page: str) -> list[str]:
    """Use action=query (not parse) because parse doesn't follow redirects,
    and most JP TCG pages on Bulbapedia redirect to their EN counterpart
    where both _JP and _EN logos are linked."""
    r = await client.get(
        WIKI_API,
        params={
            "action": "query",
            "titles": page,
            "prop": "images",
            "imlimit": 100,
            "redirects": 1,
            "format": "json",
        },
        timeout=20,
    )
    r.raise_for_status()
    body = r.json()
    pages = body.get("query", {}).get("pages", {})
    images: list[str] = []
    for _, pdata in pages.items():
        for im in pdata.get("images", []):
            title = im.get("title", "")
            # title comes as "File:SV5 Logo JP.png" - drop the namespace.
            images.append(title.removeprefix("File:"))
    return images


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


async def _download_image(client: httpx.AsyncClient, url: str, dest: Path) -> bool:
    """Stream a Bulbapedia image to disk. Returns True on success."""
    try:
        r = await client.get(url, timeout=30)
        r.raise_for_status()
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(r.content)
        return True
    except httpx.HTTPError as e:
        log.warning(f"  ! download {url}: {e}")
        return False


async def run(dry: bool) -> None:
    await init_db()

    headers = {"User-Agent": USER_AGENT}
    found: dict[str, tuple[str, str]] = {}  # set_id -> (remote_url, local_path)
    misses: list[str] = []

    if not dry:
        MIRROR_DIR.mkdir(parents=True, exist_ok=True)

    async with httpx.AsyncClient(headers=headers) as client:
        # ── Pass 0: manual URL overrides ─────────────────────────────
        # LO drops a logo image URL into MANUAL_LOGO_URLS for any set
        # Bulbapedia doesn't host. We download + mirror those first so
        # they take precedence and skip the API path entirely.
        for set_id, url in MANUAL_LOGO_URLS.items():
            ext = Path(urlparse(url).path).suffix or ".png"
            local_rel = f"/set-logos/{set_id}{ext}"
            local_abs = MIRROR_DIR / f"{set_id}{ext}"
            if dry:
                log.info(f"  ↻ {set_id:8s} MANUAL {url[:60]} (would save to {local_rel})")
                found[set_id] = (url, local_rel)
                continue
            ok = await _download_image(client, url, local_abs)
            if ok:
                log.info(f"  ↻ {set_id:8s} MANUAL -> {local_rel} ({local_abs.stat().st_size:,} bytes)")
                found[set_id] = (url, local_rel)
            else:
                misses.append(set_id)

        for set_id, page in JP_SET_TO_BULBAPEDIA.items():
            if set_id in MANUAL_LOGO_URLS:
                continue  # already handled in pass 0
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
                jp_logos = [i for i in imgs if _is_any_logo_filename(i)]
            if not jp_logos:
                log.warning(f"  ! {set_id:8s} '{page}' — no logo files on page ({len(imgs)} images total)")
                misses.append(set_id)
                continue

            # When a page hosts multiple JP logos (e.g. Mega Brave/Symphonia
            # combined article has M1L, M1S and M1 logos all linked),
            # prefer the file whose name leads with this set's id so M1S
            # gets M1S_Logo_JP.png rather than the M1L one it happens to
            # find first.
            id_prefixed = [
                i for i in jp_logos
                if re.match(rf"^{re.escape(set_id)}[_\s]", i, re.IGNORECASE)
            ]
            if id_prefixed:
                jp_logos = id_prefixed

            chosen = jp_logos[0]
            url = await _file_url(client, chosen)
            if not url:
                log.warning(f"  ! {set_id:8s} could not resolve {chosen}")
                misses.append(set_id)
                continue

            # Mirror to /frontend/public/set-logos/{set_id}.{ext} since
            # Bulbapedia's CDN refuses cross-origin loads from browsers.
            ext = Path(urlparse(url).path).suffix or ".png"
            local_rel = f"/set-logos/{set_id}{ext}"
            local_abs = MIRROR_DIR / f"{set_id}{ext}"

            if dry:
                log.info(f"  ✓ {set_id:8s} {page:38s} -> {chosen} (would save to {local_rel})")
            else:
                ok = await _download_image(client, url, local_abs)
                if not ok:
                    misses.append(set_id)
                    continue
                log.info(f"  ✓ {set_id:8s} {page:38s} -> {local_rel} ({local_abs.stat().st_size:,} bytes)")

            found[set_id] = (url, local_rel)

    if dry:
        log.info(f"\n  MODE: DRY RUN — {len(found)} matched, {len(misses)} missed")
        return

    async with SessionLocal() as db:
        for set_id, (_, local_rel) in found.items():
            row = await db.get(Set, set_id)
            if row is None:
                log.warning(f"  ! {set_id} no longer in DB, skipping")
                continue
            row.logo_url = local_rel
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
