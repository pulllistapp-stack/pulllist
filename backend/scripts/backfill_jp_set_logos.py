"""Backfill JP set logos from Bulbapedia.

For each no-logo JP set (MAIN + PROMO_LEGACY only — decks and new
promos excluded per LO), fetch the Bulbapedia set page, extract the
logo image URL from the infobox, download the full-resolution copy
locally, and update sets.logo_url.

Local target: frontend/public/set-logos/{set_id}.png
Served as: /set-logos/{set_id}.png (matches the existing convention
LO uses for the ME series).

Idempotent: skips sets that already have logo_url set. Won't clobber
existing files unless --force.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import re
from pathlib import Path

import httpx
from sqlalchemy import text

from app.database import SessionLocal, init_db

log = logging.getLogger("backfill_jp_set_logos")

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
LOGO_DIR = REPO_ROOT / "frontend" / "public" / "set-logos"

BULBAPEDIA = "https://bulbapedia.bulbagarden.net"
UA = "PullList-Catalog/1.0 (+https://pulllist.org; set-logo-backfill)"

# Hand-mapped Bulbapedia page slugs for each set. The default fallback
# derives a slug from name_en, but for JP sets whose EN Bulbapedia
# title differs from name_en (or where name_en is missing entirely)
# we override here.
_BULBAPEDIA_SLUGS: dict[str, str] = {
    # BW mainline
    "BW1b":  "Black_Collection_(TCG)",
    "BW1w":  "White_Collection_(TCG)",
    "BW2":   "Red_Collection_(TCG)",
    "BW3h":  "Hail_Blizzard_(TCG)",
    "BW3p":  "Psycho_Drive_(TCG)",
    "BW4":   "Dark_Rush_(TCG)",
    "BW5n":  "Dragon_Blade_(TCG)",
    "BW5z":  "Dragon_Blast_(TCG)",
    "BW6c":  "Cold_Flare_(TCG)",
    "BW6f":  "Freeze_Bolt_(TCG)",
    "BW7":   "Plasma_Gale_(TCG)",
    "BW8f":  "Spiral_Force_(TCG)",
    "BW8n":  "Raiden_Knuckle_(TCG)",
    "BW9":   "Megalo_Cannon_(TCG)",
    "SC":    "Shiny_Collection_(TCG)",

    # SM sub-sets (main expansions, not decks)
    "SM10a": "GG_End_(TCG)",
    "SM11":  "Miracle_Twin_(TCG)",
    "SM1p":  "Sun_%26_Moon_(TCG)",   # SM base — closest EN page
    "SM2p":  "To_Have_Seen_the_Battle_Rainbow_(TCG)",
    "SM3p":  "Shining_Legends_(TCG)",
    "SM4p":  "GX_Battle_Boost_(TCG)",
    "SM5p":  "Ultra_Force_(TCG)",

    # XY BREAK era
    "CP3":   "Pok%C3%A9Kyun_Collection_(TCG)",
    "CP4":   "Premium_Champion_Pack_(TCG)",
    "CP5":   "The_Best_of_XY_(TCG)",
    "CP6":   "Expansion_Pack_20th_Anniversary_(TCG)",
    "EBB":   "EX_Battle_Boost_(TCG)",
    "XY11b": "Fever-Burst_Fighter_(TCG)",
    "XY11r": "Cruel_Traitor_(TCG)",

    # XY era
    "XY":    "The_Best_of_XY_(TCG)",
    "XY1x":  "Collection_X_(TCG)",
    "XY1y":  "Collection_Y_(TCG)",
    "XY5g":  "Gaia_Volcano_(TCG)",
    "XY5t":  "Tidal_Storm_(TCG)",
    "XY8r":  "Red_Flash_(TCG)",

    # SV era
    "SV1a":  "Triplet_Beat_(TCG)",
    "SVF":   "Ruler_of_the_Black_Flame_(TCG)",
    "SVI":   "Scarlet_%26_Violet_(TCG)",
    "WAK":   "Wild_Force_(TCG)",

    # Legacy promo groups
    "JPP-SI":  "Southern_Islands_(TCG)",
    "JPP-VM1": "Vending_Series_(TCG)",
    "JPP-VM2": "Vending_Series_(TCG)",
    "JPP-VM3": "Vending_Series_(TCG)",

    # Vintage main sets
    "PCG1":  "Rulers_of_the_Heavens_(TCG)",
    "PCG4":  "Golden_Sky,_Silvery_Ocean_(TCG)",
    "PMCG1": "Base_Expansion_Pack_(TCG)",
    "E3":    "Wind_from_the_Sea_(TCG)",
    "VS1":   "Pok%C3%A9mon_VS_(TCG)",
    "web1":  "Pok%C3%A9mon_Web_(TCG)",
}


_LOGO_ANCHOR_RE = re.compile(
    # Match "Xxx_Logo.png", "XxxLogo.png", "Xxx_Logo_JP.png", any casing.
    r'<a\s+href="/wiki/File:([^"]+?(?:Logo|logo)(?:_JP|_EN)?\.(?:png|jpg))"',
    re.IGNORECASE,
)
_INFOBOX_IMG_RE = re.compile(
    r'<div[^>]*class="infobox-image"[^>]*>.*?'
    r'<img[^>]+src="([^"]+?\.(?:png|jpg))"',
    re.DOTALL | re.IGNORECASE,
)

# File names to reject even if they end in *_Logo.png — these are
# Bulbapedia meta project icons that appear at the top of many set
# pages, not the actual set logo.
_LOGO_REJECT = [
    "project_tcg", "project_ii", "bulbapedia", "bulbagarden",
    "wikieditor", "commons-logo",
]


def _is_rejected_logo(file_name: str) -> bool:
    n = file_name.lower()
    return any(bad in n for bad in _LOGO_REJECT)


async def _fetch_html(client: httpx.AsyncClient, url: str) -> str | None:
    try:
        r = await client.get(url, timeout=25)
    except httpx.HTTPError:
        return None
    if r.status_code != 200:
        return None
    return r.text


async def _resolve_file_url(
    client: httpx.AsyncClient, file_name: str
) -> str | None:
    """Given a File:Xxx.png reference, hit the File page and return
    the full-resolution image URL from archives.bulbagarden.net."""
    html = await _fetch_html(client, f"{BULBAPEDIA}/wiki/File:{file_name}")
    if not html:
        return None
    m = re.search(
        r'<a[^>]+href="(https?://archives\.bulbagarden\.net/media/upload/'
        r'(?!thumb/)[^"]+\.(?:png|jpg))"',
        html,
        re.IGNORECASE,
    )
    return m.group(1) if m else None


async def _find_logo_url(
    client: httpx.AsyncClient, slug: str
) -> tuple[str | None, str]:
    """Return (image_url, note). image_url is None if we couldn't find."""
    html = await _fetch_html(client, f"{BULBAPEDIA}/wiki/{slug}")
    if not html:
        return None, "page 404"

    # Prefer explicit File:*_Logo.png link, skipping meta project icons.
    all_matches = _LOGO_ANCHOR_RE.findall(html)
    matches = [m for m in all_matches if not _is_rejected_logo(m)]
    # Prefer JP variant if present
    picked = None
    for m in matches:
        if "_JP" in m or "Japan" in m:
            picked = m
            break
    if not picked and matches:
        picked = matches[0]

    if picked:
        url = await _resolve_file_url(client, picked)
        return url, f"logo:{picked}"

    # Fallback: infobox image (first image at top of page)
    m = _INFOBOX_IMG_RE.search(html)
    if m:
        src = m.group(1)
        if src.startswith("//"):
            src = "https:" + src
        # Strip /thumb/ variant
        src = re.sub(
            r"/thumb/((?:[^/]+/){2}[^/]+\.(?:png|jpg))/\d+px-[^/]+$",
            r"/\1",
            src,
        )
        return src, "infobox"

    return None, "no logo found on page"


async def _download(client: httpx.AsyncClient, url: str, dest: Path) -> bool:
    try:
        r = await client.get(url, timeout=30)
    except httpx.HTTPError as e:
        log.warning(f"  ! download: {e}")
        return False
    if r.status_code != 200 or len(r.content) < 500:
        log.warning(f"  ! HTTP {r.status_code} bytes={len(r.content)}")
        return False
    dest.write_bytes(r.content)
    return True


async def run(dry: bool, force: bool, only: str | None) -> None:
    await init_db()
    LOGO_DIR.mkdir(parents=True, exist_ok=True)

    async with SessionLocal() as db:
        q = """
          SELECT id, name, name_en, series FROM sets
          WHERE language='ja'
            AND set_type IN ('MAIN', 'PROMO_LEGACY')
            AND logo_url IS NULL
        """
        if only:
            q += f" AND id = '{only}'"
        rows = (await db.execute(text(q))).all()

    log.info(f"targets: {len(rows)} no-logo sets")

    stats = {"downloaded": 0, "skipped_on_disk": 0,
             "failed_page": 0, "failed_download": 0, "no_slug": 0}
    updates: list[tuple[str, str]] = []
    failures: list[tuple[str, str, str]] = []

    async with httpx.AsyncClient(
        headers={"User-Agent": UA}, follow_redirects=True
    ) as client:
        for row in rows:
            sid = row.id
            slug = _BULBAPEDIA_SLUGS.get(sid)
            if not slug and row.name_en:
                slug = (row.name_en.strip().replace(" ", "_") + "_(TCG)")
            if not slug:
                stats["no_slug"] += 1
                failures.append((sid, row.name or "", "no slug + no name_en"))
                continue

            dest = LOGO_DIR / f"{sid}.png"
            local_rel = f"/set-logos/{sid}.png"

            if not force and dest.exists() and dest.stat().st_size > 500:
                stats["skipped_on_disk"] += 1
                updates.append((sid, local_rel))
                continue

            img_url, note = await _find_logo_url(client, slug)
            if not img_url:
                stats["failed_page"] += 1
                failures.append((sid, slug, note))
                log.warning(f"  X {sid:12s} slug={slug!r} — {note}")
                continue

            log.info(f"  + {sid:12s} <- {img_url[-60:]}")
            if dry:
                continue

            ok = await _download(client, img_url, dest)
            if not ok:
                stats["failed_download"] += 1
                failures.append((sid, slug, "download failed"))
                continue

            stats["downloaded"] += 1
            updates.append((sid, local_rel))
            await asyncio.sleep(0.15)

    if updates and not dry:
        async with SessionLocal() as db:
            for sid, url in updates:
                await db.execute(
                    text("UPDATE sets SET logo_url=:u, updated_at=NOW() WHERE id=:i"),
                    {"u": url, "i": sid},
                )
            await db.commit()

    log.info("=== summary ===")
    for k, v in stats.items():
        log.info(f"  {k}: {v}")
    if updates:
        log.info(f"  DB rows repointed: {len(updates)}")
    log.info(f"=== unresolved ({len(failures)}) ===")
    for sid, slug, note in failures:
        log.info(f"  {sid:12s}  slug={slug[:40]:40s}  reason={note}")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--force", action="store_true")
    p.add_argument("--only", help="One set id, e.g. BW4")
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    asyncio.run(run(args.dry_run, args.force, args.only))


if __name__ == "__main__":
    main()
