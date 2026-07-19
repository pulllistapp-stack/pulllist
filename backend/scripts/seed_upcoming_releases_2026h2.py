"""Seed Pokemon TCG sets releasing between Aug 2026 and Jan 2027 so
the /drops Release Calendar shows them under Upcoming.

Data source: PokeBeach + Pokecottage + PokeGuardian confirmations
gathered 2026-07-19. Non-Japanese English localized sets (e.g. Delta
Reign = Storm Emeralda's EN cut) get their own row with the EN release
date. Each row carries release_date + language + series so the
calendar can group by month and filter by region.

Card counts (printed_total) are left NULL for now — those get filled
by the daily TCGCSV sync once the group appears (usually 4-6 weeks
before street date). Same for logo_url; the calendar renders a name-
only row until then.

Idempotent — re-running only adds sets whose id is missing.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.database import SessionLocal, init_db
from app.models.set import Set


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("seed_upcoming")


UPCOMING: list[dict] = [
    # ── EN main ────────────────────────────────────────────────
    {
        "id": "fpic-s3",
        "name": "First Partner Illustration Collection Series 3",
        "language": "en",
        "series": "First Partner",
        "release_date": "2026-08-07",
        "set_type": "PROMO_NEW",
        "set_subtype": "SPECIAL",
    },
    {
        "id": "me6",
        "name": "Delta Reign",
        "language": "en",
        "series": "Mega Evolution",
        "release_date": "2026-11-06",
        "set_type": "MAIN",
        "set_subtype": None,
    },
    # ── JP main ────────────────────────────────────────────────
    {
        "id": "m6",
        "name": "Storm Emeralda",
        "language": "ja",
        "series": "Mega Evolution",
        "release_date": "2026-07-31",
        "set_type": "MAIN",
        "set_subtype": None,
    },
    {
        "id": "m6a",
        "name": "30th Celebration (JP)",
        "language": "ja",
        "series": "30th Celebration",
        "release_date": "2026-09-16",
        "set_type": "MAIN",
        "set_subtype": None,
    },
    {
        "id": "m7",
        "name": "Aura Seeker",
        "language": "ja",
        "series": "Mega Evolution",
        "release_date": "2026-11-27",
        "set_type": "MAIN",
        "set_subtype": None,
    },
    # ── JP special deck sets ──────────────────────────────────
    {
        "id": "m7-sds",
        "name": "Special Deck Set: Mega Feraligatr / Dragonite / Gengar ex",
        "language": "ja",
        "series": "Mega Evolution",
        "release_date": "2026-11-13",
        "set_type": "DECK",
        "set_subtype": "BOX",
    },
    # ── JP 30th Celebration Card Sets (9-pack per-gen minis) ──
    # These are 9 physical products all released the same day, each
    # keyed to a Pokemon generation. Row per generation so the
    # calendar counts them accurately and future card ingests can
    # attach to the right SKU. Numbers roughly follow the JP
    # regional set numbering (gen 1 → Kanto, etc.).
    *[
        {
            "id": f"m30cs-{i}",
            "name": f"30th Celebration Card Set — Gen {i}",
            "language": "ja",
            "series": "30th Celebration",
            "release_date": "2026-10-16",
            "set_type": "PROMO_NEW",
            "set_subtype": "SPECIAL",
        }
        for i in range(1, 10)
    ],
]


async def run(dry_run: bool) -> None:
    await init_db()

    async with SessionLocal() as db:
        existing_ids = {
            r
            for (r,) in (
                await db.execute(
                    select(Set.id).where(Set.id.in_([u["id"] for u in UPCOMING]))
                )
            ).all()
        }
        log.info(f"already-present ids: {sorted(existing_ids)}")

        added = 0
        skipped = 0
        for spec in UPCOMING:
            if spec["id"] in existing_ids:
                log.info(f"  [skip] {spec['id']:<12} {spec['name']}")
                skipped += 1
                continue

            row = Set(
                id=spec["id"],
                name=spec["name"],
                language=spec["language"],
                series=spec.get("series"),
                release_date=(
                    date.fromisoformat(spec["release_date"])
                    if spec.get("release_date")
                    else None
                ),
                set_type=spec.get("set_type"),
                set_subtype=spec.get("set_subtype"),
                # printed_total / logo_url / symbol_url stay NULL until
                # the daily TCGCSV sync fills them once the group goes
                # live upstream (usually 4-6 weeks before street date).
                printed_total=None,
                logo_url=None,
                symbol_url=None,
            )
            log.info(
                f"  [add ] {spec['id']:<12} {spec['language']:<3} "
                f"{spec['release_date']}  {spec['name']}"
            )
            if not dry_run:
                db.add(row)
                added += 1

        if not dry_run:
            await db.commit()

        log.info(f"\n=== summary ===")
        log.info(f"  added:   {added}")
        log.info(f"  skipped: {skipped}")
        log.info(f"  dry_run: {dry_run}")


def main() -> None:
    import argparse

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(run(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
