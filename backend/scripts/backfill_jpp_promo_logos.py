"""Backfill logo_url for JPP-* JP promo sets by reusing the EN Black
Star Promo logo of the matching era.

The JP catalog has 8+ JPP-* sets (JPP-SV, JPP-S, JPP-SM, JPP-XY,
JPP-BW, JPP-DP, JPP-DPt, JPP-P etc.) that share the same series
(プロモカード / Promos) and each corresponds one-to-one to an EN
Black Star Promo era. pokemontcg.io hosts a canonical star logo
per EN era (svp, smp, xyp, bwp, dpp, basep, swshp). Same visual
identity — same Pokemon Black Star Promo star + era ribbon.

Rather than mirror to /public we just point at the CDN URL; the
images.pokemontcg.io host is already whitelisted in
next.config.mjs so <Image> renders it directly.

Idempotent — re-runs skip rows that already have the mapped URL.
"""
from __future__ import annotations

import argparse
import asyncio
import logging

from sqlalchemy import text

from app.database import SessionLocal, init_db

log = logging.getLogger("backfill_jpp_promo_logos")


# JP promo set → EN Black Star Promo id (whose logo we borrow).
JPP_TO_EN_PROMO: dict[str, str] = {
    "JPP-SV":  "svp",       # Scarlet & Violet Black Star Promos
    "JPP-S":   "swshp",     # SWSH Black Star Promos
    "JPP-SM":  "smp",       # SM Black Star Promos
    "JPP-XY":  "xyp",       # XY Black Star Promos
    "JPP-BW":  "bwp",       # BW Black Star Promos
    "JPP-DP":  "dpp",       # DP Black Star Promos
    "JPP-DPt": "dpp",       # DP-Pt era, reuse DPP star (same lineage)
    "JPP-P":   "basep",     # WoTC-era Wizards Black Star Promos
}


async def run(dry: bool) -> None:
    await init_db()
    async with SessionLocal() as db:
        rows = (await db.execute(text("""
            SELECT id, name, logo_url FROM sets
            WHERE language='ja' AND id LIKE 'JPP-%'
            ORDER BY id
        """))).all()

        log.info(f"Found {len(rows)} JPP-* sets")
        updated = 0
        for sid, name, cur in rows:
            en_id = JPP_TO_EN_PROMO.get(sid)
            if not en_id:
                log.info(f"  {sid:10s} skip (no era mapping) — {name}")
                continue
            new_url = f"https://images.pokemontcg.io/{en_id}/logo.png"
            if cur == new_url:
                log.info(f"  {sid:10s} already set → {new_url}")
                continue
            log.info(f"  {sid:10s} → {new_url}  (was {cur})")
            updated += 1
            if not dry:
                await db.execute(text("""
                    UPDATE sets SET logo_url = :u WHERE id = :i AND language='ja'
                """), {"u": new_url, "i": sid})
        if not dry:
            await db.commit()

    log.info(f"\n=== Summary ===")
    log.info(f"  updated: {updated}")
    if dry:
        log.info("  MODE: DRY-RUN — no writes")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    asyncio.run(run(args.dry_run))


if __name__ == "__main__":
    main()
