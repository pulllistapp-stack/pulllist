"""Backfill missing JPP-U* card images from TCGCSV era-scoped promo groups.

JPP-U year buckets 2006-2024 cover 341 cards; only 126 have images
(from the earlier pokumon.com sweep). The remaining 215 cards need
another source.

Approach: JPP-U buckets are OUR concept (year groupings of loose
"unnumbered" promos), but the underlying cards live inside various
TCGCSV JP promo groups keyed by era:
    BW-P    24342   Black & White era (2011-2015)
    XY-P    23908   XY era (2013-2016)
    SM-P    23881   Sun & Moon era (2016-2019)
    S-P     23876   Sword & Shield era (2019-2022)
    SV-P    23779   Scarlet & Violet era (2022-2024)
    M-P     24423   MEGA era (2025+)
    L-P     24023   Legends era (2010-2011)
    DP-P    24137   Diamond & Pearl era (2006-2008)
    DPt-P   24136   Platinum era (2008-2010)
    PPP     24152   Pokémon Play Promo (2006-2010)
    Movie   24568   Japanese CD/Movie/Themed promos (any era)

Each JPP-U year maps to a small set of likely era groups; we scan
those for matching card names and pull the image. Fallback: try
every promo group if narrow scan misses.

Match strategy mirrors backfill_vending_from_tcgcsv:
  * strip trailing "(…)" from card name
  * lowercase + gender-symbol map + whitespace-collapse
  * first-seen product with an image wins

Idempotent — skips rows whose image_small already resolves to a
tcgplayer-cdn URL. Rows still on legacy /jp-unn/ local paths are
LEFT ALONE (those came from pokumon.com and are fine).

Usage:
    python -m scripts.backfill_jpp_u_from_tcgcsv --dry-run
    python -m scripts.backfill_jpp_u_from_tcgcsv
    python -m scripts.backfill_jpp_u_from_tcgcsv --only JPP-U2018
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import re
import sys
from pathlib import Path

import httpx
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal, init_db  # noqa: E402


log = logging.getLogger("backfill_jpp_u_from_tcgcsv")


TCGCSV_BASE = "https://tcgcsv.com/tcgplayer/85"
UA = "PullList-Catalog/1.0 (+https://pulllist.org)"


# Year bucket → ordered list of TCGCSV promo group ids to scan.
# First hit wins across all listed groups. A "Movie/CD" catch-all
# tail on every year handles cross-era themed promos.
_MOVIE_CD = 24568  # Japanese CD Promo (also carries movie promos)

_YEAR_TO_GROUPS: dict[str, list[int]] = {
    "JPP-U1996": [24152, 24137, _MOVIE_CD],                 # PPP + DP-P + Movie
    "JPP-U2006": [24152, 24137, _MOVIE_CD],
    "JPP-U2007": [24152, 24137, _MOVIE_CD],
    "JPP-U2008": [24152, 24137, 24136, _MOVIE_CD],          # + DPt-P
    "JPP-U2009": [24136, 24137, 24152, _MOVIE_CD],
    "JPP-U2010": [24136, 24023, 24137, _MOVIE_CD],          # + L-P
    "JPP-U2011": [24023, 24342, 24136, _MOVIE_CD],          # + BW-P
    "JPP-U2012": [24342, 24023, _MOVIE_CD],
    "JPP-U2013": [24342, 23908, _MOVIE_CD],                 # + XY-P
    "JPP-U2014": [23908, 24342, _MOVIE_CD],
    "JPP-U2015": [23908, 24342, _MOVIE_CD],
    "JPP-U2016": [23908, 23881, _MOVIE_CD],                 # + SM-P
    "JPP-U2017": [23881, 23908, _MOVIE_CD],
    "JPP-U2018": [23881, _MOVIE_CD],
    "JPP-U2019": [23881, 23876, _MOVIE_CD],                 # + S-P
    "JPP-U2020": [23876, 23881, _MOVIE_CD],
    "JPP-U2021": [23876, _MOVIE_CD],
    "JPP-U2022": [23876, 23779, _MOVIE_CD],                 # + SV-P
    "JPP-U2023": [23779, 23876, _MOVIE_CD],
    "JPP-U2024": [23779, _MOVIE_CD],
    "JPP-U2025": [24423, 23779, _MOVIE_CD],                 # + M-P
}


_PAREN_TAIL_RE = re.compile(r"\s*\([^)]*\)\s*$")
_BRACKET_TAIL_RE = re.compile(r"\s*\[[^\]]*\]\s*$")
_SYMBOL_MAP = str.maketrans({"♀": "f", "♂": "m", "é": "e", "É": "e"})

# TCGCSV JP catalog names cards as "Card Name - NNN/XX-P" (e.g.
# "Pikachu - 003/SM-P", "Snorlax GX - 001/SM-P"). Strip everything
# from the last " - " onwards, but only if the tail looks like a set
# number (digits then optional /suffix) to avoid clipping legitimate
# " - " in card names.
_SET_NUMBER_TAIL_RE = re.compile(
    r"\s+-\s+\d+[A-Za-z]?(?:\s*/\s*[\w\-]+)?\s*$"
)


def _strip_trailing_parens(name: str) -> str:
    """Peel any tail like ' (…)', ' […]' — Bulbapedia / TCGCSV / our
    own catalogs all use these interchangeably for variant tags."""
    prev = None
    out = name
    while prev != out:
        prev = out
        out = _PAREN_TAIL_RE.sub("", out)
        out = _BRACKET_TAIL_RE.sub("", out)
    return out


def _normalize_name(name: str) -> str:
    stripped = _SET_NUMBER_TAIL_RE.sub("", name)
    stripped = _strip_trailing_parens(stripped).strip()
    lowered = stripped.lower().translate(_SYMBOL_MAP)
    return re.sub(r"\s+", "", lowered)


async def _fetch_group_products(
    client: httpx.AsyncClient, gid: int
) -> dict[str, tuple[int, str]]:
    """Return {normalized_name: (productId, imageUrl)} for a group."""
    r = await client.get(f"{TCGCSV_BASE}/{gid}/products", timeout=45)
    r.raise_for_status()
    products = r.json().get("results") or []
    out: dict[str, tuple[int, str]] = {}
    for p in products:
        name = _normalize_name(p.get("name") or "")
        pid = p.get("productId")
        img = p.get("imageUrl")
        if name and pid is not None and img:
            out.setdefault(name, (int(pid), img))
    return out


async def run(only: str | None, dry_run: bool) -> None:
    await init_db()

    stats = {"scanned": 0, "matched": 0, "unmatched": 0, "written": 0}
    group_cache: dict[int, dict[str, tuple[int, str]]] = {}

    targets = [only] if only else list(_YEAR_TO_GROUPS.keys())

    async with httpx.AsyncClient(headers={"User-Agent": UA}) as client:
        for set_id in targets:
            group_ids = _YEAR_TO_GROUPS.get(set_id)
            if group_ids is None:
                log.warning(f"[{set_id}] no era mapping — skipping")
                continue

            async with SessionLocal() as db:
                rows = (await db.execute(
                    text("""
                        SELECT id, name, image_small FROM cards
                        WHERE set_id = :s AND (
                            image_small IS NULL
                            OR image_small = ''
                        )
                    """),
                    {"s": set_id},
                )).all()

            log.info(f"[{set_id}] cards needing image: {len(rows)}")

            # Preload all era groups for this bucket (dedup by cache).
            era_maps: list[dict[str, tuple[int, str]]] = []
            for gid in group_ids:
                if gid not in group_cache:
                    try:
                        group_cache[gid] = await _fetch_group_products(client, gid)
                    except Exception as e:
                        log.warning(f"  ! fetching group {gid}: {e}")
                        group_cache[gid] = {}
                era_maps.append(group_cache[gid])

            for r in rows:
                stats["scanned"] += 1
                key = _normalize_name(r.name or "")
                if not key:
                    stats["unmatched"] += 1
                    continue

                hit = None
                for em in era_maps:
                    if key in em:
                        hit = em[key]
                        break

                if hit is None:
                    stats["unmatched"] += 1
                    continue
                stats["matched"] += 1

                pid, img_small = hit
                img_large = img_small.replace("_200w", "_400w")

                if dry_run:
                    log.info(f"  [would] {r.id} → pid={pid} {img_small[:60]}")
                    continue

                async with SessionLocal() as db:
                    w = await db.execute(
                        text(
                            "UPDATE cards SET "
                            "  image_small = :s, "
                            "  image_large = :l, "
                            "  tcgplayer_product_id = :pid, "
                            "  tcgplayer_url = :url "
                            "WHERE id = :id"
                        ),
                        {
                            "s": img_small,
                            "l": img_large,
                            "pid": pid,
                            "url": f"https://www.tcgplayer.com/product/{pid}",
                            "id": r.id,
                        },
                    )
                    if w.rowcount:
                        stats["written"] += 1
                    await db.commit()

    log.info("=== JPP-U TCGCSV backfill ===")
    for k, v in stats.items():
        log.info(f"  {k}: {v}")
    if dry_run:
        log.info("MODE: DRY-RUN — no writes")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--only", help="Limit to a single JPP-U year bucket (e.g. JPP-U2018)")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    asyncio.run(run(args.only, args.dry_run))


if __name__ == "__main__":
    main()
