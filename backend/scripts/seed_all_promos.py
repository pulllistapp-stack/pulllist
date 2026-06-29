"""Batch-seed every TCGCSV promo group LO listed.

One-shot ingestion of the full catalog of US/WoTC Pokémon TCG promo
sets. Each set is independent; if one fails (e.g. TCGCSV transient
500) the rest still run. Re-runnable — each per-set seed is idempotent
via seed_promo_group.seed().

Run:
    python -m scripts.seed_all_promos             # everything
    python -m scripts.seed_all_promos --dry-run   # report only
    python -m scripts.seed_all_promos --only smp,svp   # subset

Adding a new set: append to PROMO_SETS below with the TCGCSV
group_id + your chosen short slug + display name + series + release
date. TCGCSV group ids come from
https://tcgcsv.com/tcgplayer/3/groups (filter by name).
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import TypedDict

os.environ.setdefault("DEBUG", "false")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.seed_promo_group import seed as seed_one  # noqa: E402

log = logging.getLogger("seed_all_promos")


class PromoSet(TypedDict):
    group_id: int
    set_id: str
    set_name: str
    series: str | None
    release_date: str | None


# All promo sets from LO's TCGplayer URL. set_id chosen to be short +
# memorable; collisions across promo eras avoided by appending the era
# code (e.g. xyp for XY Promos vs np for Nintendo Promos vs wotcp for
# WoTC Promo — TCGplayer reuses the "PR" abbreviation across eras).
PROMO_SETS: list[PromoSet] = [
    # Already seeded — kept here so --only mep re-runs work and the
    # canonical id stays documented.
    {"group_id": 24451, "set_id": "mep", "set_name": "ME: Mega Evolution Promo",
     "series": "Mega Evolution", "release_date": "2025-09-26"},

    # Modern era
    {"group_id": 22872, "set_id": "svp", "set_name": "SV: Scarlet & Violet Promo Cards",
     "series": "Scarlet & Violet", "release_date": "2023-03-31"},
    {"group_id": 2545, "set_id": "swsd", "set_name": "SWSH: Sword & Shield Promo Cards",
     "series": "Sword & Shield", "release_date": "2019-11-15"},
    {"group_id": 1861, "set_id": "smp", "set_name": "SM Promos",
     "series": "Sun & Moon", "release_date": "2016-12-14"},
    {"group_id": 1451, "set_id": "xyp", "set_name": "XY Promos",
     "series": "XY", "release_date": "2013-12-16"},
    {"group_id": 1407, "set_id": "bwp", "set_name": "Black and White Promos",
     "series": "Black & White", "release_date": "2011-04-25"},
    {"group_id": 1453, "set_id": "hgssp", "set_name": "HGSS Promos",
     "series": "HeartGold & SoulSilver", "release_date": "2010-02-01"},
    {"group_id": 1421, "set_id": "dpp", "set_name": "Diamond and Pearl Promos",
     "series": "Diamond & Pearl", "release_date": "2007-05-01"},
    {"group_id": 1455, "set_id": "bop", "set_name": "Best of Promos",
     "series": "e-Card", "release_date": "2002-12-01"},
    {"group_id": 1418, "set_id": "wotcp", "set_name": "WoTC Promo",
     "series": "WoTC Black Star", "release_date": "1999-07-01"},

    # Cross-era specials
    {"group_id": 24529, "set_id": "pptp",
     "set_name": "Player Placement Trainer Promos",
     "series": "Tournament", "release_date": "2026-01-02"},
    {"group_id": 2332, "set_id": "ppp",
     "set_name": "Professor Program Promos",
     "series": "Organized Play", "release_date": None},
    {"group_id": 2205, "set_id": "pwcp",
     "set_name": "Pikachu World Collection Promos",
     "series": "Special", "release_date": None},
    {"group_id": 1938, "set_id": "aap",
     "set_name": "Alternate Art Promos",
     "series": "Special", "release_date": None},
    {"group_id": 1423, "set_id": "np", "set_name": "Nintendo Promos",
     "series": "Special", "release_date": None},

    # Vintage / niche
    {"group_id": 2214, "set_id": "kwbp", "set_name": "Kids WB Promos",
     "series": "Crossover", "release_date": "2004-07-02"},
    {"group_id": 2155, "set_id": "ccp", "set_name": "Countdown Calendar Promos",
     "series": "Special", "release_date": "2008-10-01"},
    {"group_id": 2175, "set_id": "bkp", "set_name": "Burger King Promos",
     "series": "Crossover", "release_date": None},

    # McDonald's — one set per year + 25th anniv
    {"group_id": 2782, "set_id": "md25anniv",
     "set_name": "McDonald's 25th Anniversary Promos",
     "series": "McDonald's", "release_date": "2021-02-09"},
    {"group_id": 24163, "set_id": "md24", "set_name": "McDonald's Promos 2024",
     "series": "McDonald's", "release_date": "2024-01-21"},
    {"group_id": 23306, "set_id": "md23", "set_name": "McDonald's Promos 2023",
     "series": "McDonald's", "release_date": "2023-09-12"},
    {"group_id": 3150, "set_id": "md22", "set_name": "McDonald's Promos 2022",
     "series": "McDonald's", "release_date": "2022-08-03"},
    {"group_id": 2555, "set_id": "md19", "set_name": "McDonald's Promos 2019",
     "series": "McDonald's", "release_date": "2019-10-01"},
    {"group_id": 2364, "set_id": "md18", "set_name": "McDonald's Promos 2018",
     "series": "McDonald's", "release_date": "2018-11-02"},
    {"group_id": 2148, "set_id": "md17", "set_name": "McDonald's Promos 2017",
     "series": "McDonald's", "release_date": "2017-11-07"},
    {"group_id": 3087, "set_id": "md16", "set_name": "McDonald's Promos 2016",
     "series": "McDonald's", "release_date": "2016-08-05"},
    {"group_id": 1694, "set_id": "md15", "set_name": "McDonald's Promos 2015",
     "series": "McDonald's", "release_date": "2015-11-23"},
    {"group_id": 1692, "set_id": "md14", "set_name": "McDonald's Promos 2014",
     "series": "McDonald's", "release_date": "2014-05-23"},
    {"group_id": 1427, "set_id": "md12", "set_name": "McDonald's Promos 2012",
     "series": "McDonald's", "release_date": "2012-06-15"},
    {"group_id": 1401, "set_id": "md11", "set_name": "McDonald's Promos 2011",
     "series": "McDonald's", "release_date": "2011-06-17"},
]


async def main(only: set[str] | None, dry_run: bool) -> None:
    sets = (
        [s for s in PROMO_SETS if s["set_id"] in only]
        if only
        else PROMO_SETS
    )
    log.info("seeding %d promo sets (dry_run=%s)", len(sets), dry_run)

    succeeded: list[str] = []
    failed: list[tuple[str, str]] = []

    for idx, conf in enumerate(sets, 1):
        sid = conf["set_id"]
        log.info(
            "\n=== [%d/%d] %s (group %d) ===",
            idx,
            len(sets),
            conf["set_name"],
            conf["group_id"],
        )
        try:
            await seed_one(
                group_id=conf["group_id"],
                set_id=sid,
                set_name=conf["set_name"],
                series=conf["series"],
                release_date=conf["release_date"],
                dry_run=dry_run,
            )
            succeeded.append(sid)
        except Exception as e:
            log.error("FAILED %s: %s", sid, e)
            failed.append((sid, str(e)))

    log.info("\n=== ALL DONE ===")
    log.info("succeeded (%d): %s", len(succeeded), ", ".join(succeeded))
    if failed:
        log.warning("failed (%d):", len(failed))
        for sid, err in failed:
            log.warning("  %s — %s", sid, err)


def cli() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--only",
        default=None,
        help="Comma-separated set_ids to run (default: all)",
    )
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    only = set(args.only.split(",")) if args.only else None
    asyncio.run(main(only, args.dry_run))


if __name__ == "__main__":
    cli()
