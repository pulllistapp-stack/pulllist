"""Seed the JP set stubs required to attach the last 11 sealed
products that ``ingest_jp_sealed.py`` couldn't place.

After the 212-group base pass + 11-alias pass, 7 TCGCSV groups still
carried sealed SKUs (11 total) with no corresponding PullList set to
hang them on. This script creates those 6 missing sets as sealed-
focused stubs so a follow-up ``ingest_jp_sealed`` run can insert the
products. (The 7th group, ``svL``, is a pure alias — SV: Ceruledge
Stellar Starter Set already exists in DB as ``SVLS``.)

Set metadata is inline — no external fetch — so this stays a one-shot
seeding script. Cards attached to these groups are *not* imported
here; that's a separate ``ingest_jp_singles`` job if we later decide
to surface the ~137 promo/deck singles too.

Idempotent — ON CONFLICT DO NOTHING on primary key.

Usage:
    python -m scripts.seed_missing_jp_sealed_sets --dry-run
    python -m scripts.seed_missing_jp_sealed_sets
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from datetime import date
from pathlib import Path

from sqlalchemy.dialects.postgresql import insert as pg_insert

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal, init_db  # noqa: E402
from app.models.set import Set  # noqa: E402


log = logging.getLogger("seed_missing_jp_sealed_sets")


# Each dict is a Set row. Names come from the JP TCGCSV feed and
# Bulbapedia. printed_total/total left null on sealed-only stubs
# because we're not seeding the cards themselves in this pass.
_SETS: list[dict] = [
    {
        "id": "SBC",
        "name": "スペシャルBOX コレクション",
        "name_en": "Special Box Collections",
        "series": "スペシャル",
        "set_type": "PROMO_NEW",
        "set_subtype": "SPECIAL",
        "release_date": date(2020, 1, 1),
        "printed_total": None,
        "total": None,
        # Bucket set: 5 unrelated regional/movie/collab boxes released
        # 2020–2024 (Pokemon Center Tohoku / Hiroshima / Fukuoka,
        # Movie Koko Box, Pokemon Go Box). TCGCSV groups them all
        # under one supplemental group, so we mirror that shape.
    },
    {
        "id": "JPP-M",
        "name": "プロモ・M-P",
        "name_en": "MEGA Promotional Cards",
        "series": "メガエヴォリューション",
        "set_type": "PROMO_NEW",
        "set_subtype": None,
        "release_date": date(2025, 1, 1),
        "printed_total": None,
        "total": None,
        # Post-Aug 2025 MEGA-era promos (McDonald's Japan booster etc.).
        # 60+ promo card singles live on TCGCSV under this group but
        # aren't imported here.
    },
    {
        "id": "CLL",
        "name": "ポケモンカードゲーム クラシック リザードン",
        "name_en": "Pokemon Card Game Classic: Charizard",
        "series": "Classic",
        "set_type": "DECK",
        "set_subtype": "SPECIAL",
        "release_date": date(2023, 11, 10),
        "printed_total": 34,
        "total": 34,
        # Anniversary "Classic" set — a premium 3-deck reprint release
        # (Charizard / Blastoise / Venusaur). Only the Charizard variant
        # currently has a sealed SKU on TCGCSV, so we seed CLL alone;
        # CLV / CLF can be added when they get sealed listings.
    },
    {
        "id": "NPF1",
        "name": "ネオプレミアムファイル1",
        "name_en": "Neo Premium File 1",
        "series": "Neo",
        "set_type": "PROMO_LEGACY",
        "set_subtype": None,
        "release_date": date(2001, 3, 1),
        "printed_total": 9,
        "total": 9,
        # Vintage 2001 premium collector's file with 9 unnumbered
        # Neo-era promo cards. Sealed file is the collectible; the
        # cards go under it (not seeded here).
    },
    {
        "id": "PtA-GF",
        "name": "アルセウスLV.X デッキ 草・炎",
        "name_en": "Arceus LV.X Deck: Grass & Fire",
        "series": "プラチナ",
        "set_type": "DECK",
        "set_subtype": "DECK",
        "release_date": date(2009, 11, 20),
        "printed_total": 17,
        "total": 17,
    },
    {
        "id": "PtA-LP",
        "name": "アルセウスLV.X デッキ 雷・エスパー",
        "name_en": "Arceus LV.X Deck: Lightning & Psychic",
        "series": "プラチナ",
        "set_type": "DECK",
        "set_subtype": "DECK",
        "release_date": date(2009, 11, 20),
        "printed_total": 17,
        "total": 17,
    },
    {
        "id": "S8a-P",
        "name": "25thアニバーサリー プロモカードパック",
        "name_en": "25th Anniversary Promo Card Pack",
        "series": "ソード＆シールド",
        "set_type": "PROMO_NEW",
        "set_subtype": None,
        "release_date": date(2021, 10, 22),
        "printed_total": 25,
        "total": 25,
        # 25 classic-Pokemon reprint promos bundled with the s8a base
        # release. Separate numbering series (NNN/025) from the base
        # 25th Anniversary Collection (NNN/028). Common JP catalog
        # error is to fold both into a single set — we split them.
    },
    {
        "id": "S8a-G",
        "name": "25thアニバーサリー ゴールデンボックス",
        "name_en": "25th Anniversary Golden Box",
        "series": "ソード＆シールド",
        "set_type": "PROMO_NEW",
        "set_subtype": "BOX",
        "release_date": date(2021, 11, 27),
        "printed_total": 15,
        "total": 15,
        # 15-card golden-foil variant set from the s8a-G premium box.
        # Distinct SKU from the base collection; also gets its own
        # PullList set to keep the anniversary-family sealed products
        # attached to the right home.
    },
]


async def run(dry_run: bool) -> None:
    await init_db()

    log.info(f"Planning to seed {len(_SETS)} JP sets:")
    for s in _SETS:
        log.info(f"  {s['id']:10s} {s['set_type']:12s} {s['name_en']}")

    if dry_run:
        log.info("MODE: DRY-RUN — no writes")
        return

    async with SessionLocal() as db:
        # Use ON CONFLICT DO NOTHING so re-runs after an add are no-ops
        # rather than raising IntegrityError. Rows carry `language='ja'`
        # from the model's server_default.
        rows = [
            {**s, "language": "ja"}
            for s in _SETS
        ]
        stmt = pg_insert(Set).values(rows).on_conflict_do_nothing(
            index_elements=["id"]
        )
        result = await db.execute(stmt)
        await db.commit()
        log.info(f"inserted: {result.rowcount}")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    asyncio.run(run(args.dry_run))


if __name__ == "__main__":
    main()
