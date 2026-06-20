"""Seed virtual Set rows for each Japanese promotional-card era.

TCGdex's JP catalog has effectively no promo coverage. Bulbapedia has
comprehensive list pages, one per era ("SV-P Promotional cards (TCG)",
"S-P Promotional cards (TCG)", etc.). Phase 1 of the promo work: create
a Set row per era so individual promo cards (Phase 2) have a parent
to attach to and the UI (Phase 3) can group them under a "Promos"
heading next to the regular expansion series.

Set ids are prefixed `JPP-` so they can't collide with any TCGdex /
pokemontcg.io id (no real catalog uses that prefix).

Usage:
    python -m scripts.seed_promo_eras
    python -m scripts.seed_promo_eras --dry-run
"""
from __future__ import annotations

import argparse
import asyncio
import logging
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select

from app.database import SessionLocal, init_db
from app.models import Set

log = logging.getLogger("seed_promo_eras")


@dataclass
class PromoEra:
    id: str
    name: str
    name_en: str
    series: str
    bulbapedia_page: str
    release_start: date | None
    sort_order: int  # newer first when sorted


# Hand-curated, era-by-era. The release_start is approximate (start of
# the corresponding mainline era), used for sorting alongside regular
# sets. name carries the JP label, name_en the canonical English-side
# heading.
PROMO_ERAS: list[PromoEra] = [
    # Most recent first (sort_order = -release_year so we can stable-sort)
    PromoEra("JPP-SV",  "プロモ・SV-P",   "SV-P Promotional Cards",  "プロモカード",
             "SV-P Promotional cards (TCG)",  date(2023, 1, 20), -2023),
    PromoEra("JPP-S",   "プロモ・S-P",    "S-P Promotional Cards",   "プロモカード",
             "S-P Promotional cards (TCG)",   date(2020, 1, 31), -2020),
    PromoEra("JPP-SM",  "プロモ・SM-P",   "SM-P Promotional Cards",  "プロモカード",
             "SM-P Promotional cards (TCG)",  date(2016, 12, 9), -2016),
    PromoEra("JPP-XY",  "プロモ・XY-P",   "XY-P Promotional Cards",  "プロモカード",
             "XY-P Promotional cards (TCG)",  date(2013, 10, 12), -2013),
    PromoEra("JPP-BW",  "プロモ・BW-P",   "BW-P Promotional Cards",  "プロモカード",
             "BW-P Promotional cards (TCG)",  date(2010, 12, 17), -2010),
    PromoEra("JPP-L",   "プロモ・L-P",    "L-P Promotional Cards",   "プロモカード",
             "L-P Promotional cards (TCG)",   date(2009, 10, 9), -2009),
    PromoEra("JPP-DPt", "プロモ・DPt-P",  "DPt-P Promotional Cards", "プロモカード",
             "DPt-P Promotional cards (TCG)", date(2008, 9, 13), -2008),
    PromoEra("JPP-DP",  "プロモ・DP-P",   "DP-P Promotional Cards",  "プロモカード",
             "DP-P Promotional cards (TCG)",  date(2006, 11, 25), -2006),
    PromoEra("JPP-PCG", "プロモ・PCG-P",  "PCG-P Promotional Cards", "プロモカード",
             "PCG-P Promotional cards (TCG)", date(2004, 11, 27), -2004),
    PromoEra("JPP-ADV", "プロモ・ADV-P",  "ADV-P Promotional Cards", "プロモカード",
             "ADV-P Promotional cards (TCG)", date(2002, 10, 11), -2002),
    PromoEra("JPP-PPP", "プロモ・PPP-P",  "PPP Promotional Cards",   "プロモカード",
             "PPP Promotional cards (TCG)",   date(2001, 6, 1), -2001),
    PromoEra("JPP-P",   "プロモ・P",      "P Promotional Cards",     "プロモカード",
             "P Promotional cards (TCG)",     date(1996, 10, 20), -1996),
    # Special collections - separate from the main era P-sets
    PromoEra("JPP-WC",  "ワールドコレクション", "World Collection (Promos)", "プロモカード",
             "World Collection (TCG)",        date(2010, 1, 1), -2010),
    PromoEra("JPP-SI",  "サザンアイランド",   "Southern Islands",        "プロモカード",
             "Southern Islands (TCG)",        date(1999, 1, 1), -1999),
    PromoEra("JPP-VM",  "自販機カード",     "Vending Machine Cards",   "プロモカード",
             "Vending Machine cards (TCG)",   date(1998, 6, 1), -1998),
    PromoEra("JPP-PKC", "ピカチュウフレンズ",  "Pikachu's New Friends",   "プロモカード",
             "Pikachu's New Friends (TCG)",   date(2001, 1, 1), -2001),
    PromoEra("JPP-MCD", "マクドナルド・ポケモンe", "McDonald's Pokemon-e",   "プロモカード",
             "McDonald's Pokémon-e Minimum Pack (TCG)", date(2002, 6, 1), -2002),
]


async def run(dry: bool) -> None:
    await init_db()

    async with SessionLocal() as db:
        existing_ids = {
            row[0] for row in (
                await db.execute(select(Set.id).where(Set.language == "ja"))
            ).all()
        }

        created = 0
        updated = 0

        for era in PROMO_ERAS:
            row = await db.get(Set, era.id)
            if row is None:
                row = Set(
                    id=era.id,
                    name=era.name,
                    name_local=era.name,
                    name_en=era.name_en,
                    series=era.series,
                    language="ja",
                    release_date=era.release_start,
                )
                db.add(row)
                created += 1
                action = "create"
            else:
                row.name = era.name
                row.name_local = era.name
                row.name_en = era.name_en
                row.series = era.series
                row.release_date = era.release_start
                updated += 1
                action = "update"

            log.info(f"  [{action}] {era.id:8s} {era.name:18s} <- {era.bulbapedia_page}")

        if dry:
            log.info("\n  MODE: DRY RUN — no writes")
        else:
            await db.commit()

        log.info(f"\n=== Summary ===")
        log.info(f"  created : {created}")
        log.info(f"  updated : {updated}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    asyncio.run(run(args.dry_run))


if __name__ == "__main__":
    main()
