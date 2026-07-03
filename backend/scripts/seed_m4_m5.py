"""Seed JP M4 (Ninja Spinner) + M5 (Abyss Eye) set rows.

TCGdex hasn't ingested these yet (both 404), but Limitless has them
indexed. scrape_limitless_jp.py needs the set rows to exist first,
so this seeds the minimal metadata (id / name / release / series
/ language) then hands off to Limitless for the cards.

Idempotent — re-runs are no-op.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date

from sqlalchemy import select

from app.database import SessionLocal, init_db
from app.models import Set

log = logging.getLogger("seed_m4_m5")


ROWS = [
    {
        "id": "M4",
        "name": "ニンジャスピナー",
        "name_en": "Ninja Spinner",
        "series": "ポケモンカードゲーム MEGA",
        "release_date": date(2026, 3, 13),
        "printed_total": 120,
        "total": 120,
        "language": "ja",
    },
    {
        "id": "M5",
        "name": "アビスアイ",
        "name_en": "Abyss Eye",
        "series": "ポケモンカードゲーム MEGA",
        "release_date": date(2026, 5, 22),
        "printed_total": 81,
        "total": 81,
        "language": "ja",
    },
]


async def run() -> None:
    await init_db()
    async with SessionLocal() as db:
        for row in ROWS:
            existing = await db.get(Set, row["id"])
            if existing:
                # Refresh name_en on re-run if stale
                if not existing.name_en:
                    existing.name_en = row["name_en"]
                log.info(f"  {row['id']}: already exists (name={existing.name!r})")
                continue
            db.add(Set(**row))
            log.info(f"  + {row['id']} {row['name']} ({row['name_en']}) — {row['printed_total']} cards, {row['release_date']}")
        await db.commit()
    log.info("Done.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    asyncio.run(run())
