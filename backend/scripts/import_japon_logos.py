"""Mirror JP-specific set logos from japon-collection.com.

Our Bulbapedia mirror reused English equivalent logos for JP sets that
got bundled differently in English (3 JP sets → 1 EN "Battle Styles"
release, so all three shared the BATTLE STYLES logo). japon-collection
hosts the actual JP-specific logos at a predictable URL pattern:

    https://www.japon-collection.com/images/logos/logo_pokemon_{slug}_{id}.png

…where `slug` is the English name normalised (lowercase, spaces →
underscores, punctuation stripped) and `id` is our lowercase set id.

Underlying art is still TPCi IP — same legal basis as Bulbapedia and
every other source — but japon-collection has no explicit NC clause,
which removes one of two friction points. Attribution still belongs in
/about.

Usage:
    python -m scripts.import_japon_logos               # all visible JP sets
    python -m scripts.import_japon_logos --dry-run     # report only
    python -m scripts.import_japon_logos --set S6H     # one set
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

log = logging.getLogger("import_japon_logos")

BASE = "https://www.japon-collection.com/images/logos"
MIRROR_DIR = Path(__file__).resolve().parent.parent.parent / "frontend" / "public" / "set-logos"


# Hand-curated overrides for cases where slug-from-name_en doesn't hit.
# Verified by probing the site directly. Each value is (slug, id_override
# or None to use default). The id_override is needed when japon-collection
# transposed a character (S5I -> s5l, etc).
SLUG_OVERRIDES: dict[str, tuple[str, str | None]] = {
    # SwSh era — sets that share the EN logo on Bulbapedia, fixed here
    "S5a":  ("peerless_fighters", None),     # site uses "peerless" not "matchless"
    "S5I":  ("single_strike_master", "s5l"), # typo on site: s5L not s5I
    "S3":   ("infinity_zone", None),
    "S1W":  ("sword", None),
    "S4a":  ("shiny_star_v", ""),            # no id suffix on this one
    "S7D":  ("skyscraping_perfection", None),
    "S8b":  ("high_class_pack_vmax_climax", None),
    "S10b": ("pokemon_go", None),            # name_en is empty on this row
}


def _name_to_slug(name_en: str) -> str:
    """`'Single Strike Master'` -> `'single_strike_master'`."""
    s = name_en.lower()
    s = re.sub(r"[^a-z0-9\s]", "", s)
    s = re.sub(r"\s+", "_", s).strip("_")
    return s


def _candidate_attempts(set_id: str, name_en: str | None) -> list[tuple[str, str]]:
    """Returns (slug, id_suffix) pairs to try in order. Empty id_suffix
    means try the suffix-less filename `logo_pokemon_{slug}.png`."""
    out: list[tuple[str, str]] = []
    if set_id in SLUG_OVERRIDES:
        slug, override = SLUG_OVERRIDES[set_id]
        if override is None:
            out.append((slug, set_id.lower()))
        else:
            out.append((slug, override))
    if name_en:
        s = _name_to_slug(name_en)
        out.append((s, set_id.lower()))
        # Try without "_ex" suffix
        if "_ex" in s:
            out.append((s.replace("_ex", ""), set_id.lower()))
        # Try suffix-less filename
        out.append((s, ""))
    # Dedupe preserving order
    seen = set()
    deduped = []
    for pair in out:
        if pair[0] and pair not in seen:
            seen.add(pair)
            deduped.append(pair)
    return deduped


async def _try_fetch(
    client: httpx.AsyncClient, slug: str, id_suffix: str
) -> tuple[str | None, bytes | None]:
    if id_suffix:
        url = f"{BASE}/logo_pokemon_{slug}_{id_suffix}.png"
    else:
        url = f"{BASE}/logo_pokemon_{slug}.png"
    try:
        r = await client.get(url, timeout=15)
    except httpx.HTTPError:
        return None, None
    if r.status_code != 200:
        return None, None
    return url, r.content


async def run(only: str | None, dry: bool) -> None:
    await init_db()

    async with SessionLocal() as db:
        if only:
            rows = (
                await db.execute(
                    text("SELECT id, name, name_en FROM sets WHERE id=:i"),
                    {"i": only},
                )
            ).all()
        else:
            rows = (
                await db.execute(
                    text(
                        """SELECT id, name, name_en FROM sets
                           WHERE language='ja' AND logo_url LIKE '/set-logos/%'
                           ORDER BY id"""
                    )
                )
            ).all()

    log.info(f"Targets: {len(rows)} JP sets.")
    MIRROR_DIR.mkdir(parents=True, exist_ok=True)

    hit, miss = [], []
    async with httpx.AsyncClient(headers={"User-Agent": "PullList-Catalog/1.0"}) as c:
        for set_id, jp_name, name_en in rows:
            attempts = _candidate_attempts(set_id, name_en)
            if not attempts:
                miss.append((set_id, jp_name, "no candidate slugs"))
                continue
            url, payload, tried_slug = None, None, None
            for slug, id_suffix in attempts:
                url, payload = await _try_fetch(c, slug, id_suffix)
                if url:
                    tried_slug = f"{slug} (id={id_suffix or 'NONE'})"
                    break
            if not url:
                miss.append((set_id, jp_name, f"tried {len(attempts)} variants"))
                continue
            hit.append((set_id, tried_slug, url, len(payload)))
            if not dry:
                # Mirror locally. Overwrite the Bulbapedia file in place
                # so the DB path /set-logos/{ID}.png keeps resolving.
                dest = MIRROR_DIR / f"{set_id}.png"
                dest.write_bytes(payload)

    log.info(f"\n=== Summary ===")
    log.info(f"  hits:   {len(hit)}/{len(rows)}")
    log.info(f"  misses: {len(miss)}")
    if hit:
        log.info("\n--- Hits ---")
        for set_id, slug, url, size in hit:
            log.info(f"  {set_id:8s} <- {slug:30s} ({size:,} bytes)")
    if miss:
        log.info("\n--- Misses (need manual mapping) ---")
        for set_id, jp_name, reason in miss:
            log.info(f"  {set_id:8s} {jp_name[:25]:25s} -- {reason}")
    if dry:
        log.info("\n  MODE: DRY-RUN — no files written")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--set", dest="only", help="One set id (e.g. S6H)")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    asyncio.run(run(args.only, args.dry_run))


if __name__ == "__main__":
    main()
