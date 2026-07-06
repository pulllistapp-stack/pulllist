"""Convert lingering EN-style rarity labels on JP cards to the JP
native codes (C / U / R / RR / RRR / AR / SR / SAR / HR / UR).

After the Bulbapedia sweep landed 8,974 JP cards on JP codes, ~7,493
JP cards still carried the old pokemontcg.io labels ("Rare Secret",
"Ultra Rare", "Illustration Rare", …) because their sets weren't in
the scrape's slug dictionary. Those labels do have a defensible JP
equivalent, so re-map them so the sidebar's JP taxonomy actually
shows them.

Mapping:
    Common                     → C
    Uncommon                   → U
    Rare                       → R
    Rare Holo                  → R    (holo isn't its own JP tier)
    Rare Holo 1st Edition      → R
    Double Rare                → RR
    Triple Rare                → RRR
    Special Rare               → SR
    Illustration Rare          → AR
    Special Illustration Rare  → SAR
    Ultra Rare                 → UR
    Rare Ultra                 → UR
    Rare Secret                → UR   (JP UR = gold-bordered secret)
    Rare Rainbow               → UR   (rainbow foil = UR in JP)
    Hyper Rare                 → HR
    Shiny Rare                 → SSR
    Shiny Ultra Rare           → SSR
    Character Holo Rare        → CHR
    Character Super Rare       → CSR
    Rare Holo EX               → RR
    Rare Holo GX               → RR
    Rare Holo V                → RR
    Rare Holo VMAX             → RRR
    Rare Holo VSTAR            → RRR
    Rare Holo ex               → RR
    Rare ACE                   → ACE

Left alone (no clean JP counterpart; frontend Misc bucket for these):
    Amazing Rare, Radiant Rare, LEGEND, Rare BREAK, Rare Prism Star,
    Rare Shining, Rare Holo ☆, Rare Holo LV.X, Rare Prime,
    ACE SPEC Rare, Promo (already JP-compatible),
    Classic Collection, Mega Hyper Rare.

Idempotent. Only touches language='ja' rows.
"""
from __future__ import annotations

import argparse
import asyncio
import logging

from sqlalchemy import text

from app.database import SessionLocal, init_db

log = logging.getLogger("remap_jp_en_rarity_labels")


_EN_TO_JP: dict[str, str] = {
    "Common": "C",
    "Uncommon": "U",
    "Rare": "R",
    "Rare Holo": "R",
    "Rare Holo 1st Edition": "R",
    "Double Rare": "RR",
    "Triple Rare": "RRR",
    "Special Rare": "SR",
    "Illustration Rare": "AR",
    "Special Illustration Rare": "SAR",
    "Ultra Rare": "UR",
    "Rare Ultra": "UR",
    "Rare Secret": "UR",
    "Rare Rainbow": "UR",
    "Hyper Rare": "HR",
    "Shiny Rare": "SSR",
    "Shiny Ultra Rare": "SSR",
    "Character Holo Rare": "CHR",
    "Character Super Rare": "CSR",
    "Rare Holo EX": "RR",
    "Rare Holo GX": "RR",
    "Rare Holo V": "RR",
    "Rare Holo VMAX": "RRR",
    "Rare Holo VSTAR": "RRR",
    "Rare Holo ex": "RR",
    "Rare ACE": "ACE",
}


async def run(dry: bool) -> None:
    await init_db()

    async with SessionLocal() as db:
        rows = (await db.execute(text("""
            SELECT id, rarity FROM cards
            WHERE language = 'ja' AND rarity = ANY(:from_labels)
        """), {"from_labels": list(_EN_TO_JP.keys())})).all()

    from collections import Counter
    dist = Counter(r.rarity for r in rows)
    log.info(f"Targets: {len(rows)} JP cards with EN-style rarity")
    for label, n in dist.most_common():
        log.info(f"  {n:5d}  {label}  →  {_EN_TO_JP[label]}")

    if not rows or dry:
        if dry:
            log.info("MODE: DRY-RUN — no writes")
        return

    async with SessionLocal() as db:
        for label, jp_code in _EN_TO_JP.items():
            r = await db.execute(
                text("""
                    UPDATE cards SET rarity = :jp, updated_at = NOW()
                    WHERE language = 'ja' AND rarity = :en
                """),
                {"jp": jp_code, "en": label},
            )
            if r.rowcount:
                log.info(f"  applied {r.rowcount:5d}  {label} → {jp_code}")
        await db.commit()


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
    )
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    asyncio.run(run(args.dry_run))


if __name__ == "__main__":
    main()
