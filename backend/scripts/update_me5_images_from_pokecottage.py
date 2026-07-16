"""Backfill me5 (Pitch Black) card images from Pokecottage's CDN.

Pitch Black releases 2026-07-17 (2 days out at time of writing) and
pokemontcg.io usually doesn't have artwork indexed for 1-2 weeks
post-release, leaving our /sets/me5 grid completely image-less on
launch day. Pokecottage published the full 120-card visual list
ahead of release and their CDN serves each card at a deterministic
URL — this script walks that list, wraps each URL through the
`images.weserv.nl` proxy to sidestep hot-link 403s, and writes it
to `cards.image_small` / `cards.image_large` for the matching
me5-XXX row.

Matched by card number (integer). Cards we've seeded but Pokecottage
doesn't list (or vice versa) get logged and skipped.

Usage:
    python -m scripts.update_me5_images_from_pokecottage
    python -m scripts.update_me5_images_from_pokecottage --dry-run
    python -m scripts.update_me5_images_from_pokecottage --overwrite  # replace existing images too
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.database import SessionLocal, init_db
from app.models import Card


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("update_me5_images")


# Full Pitch Black card list from Pokecottage
# (https://pokecottage.com/sets/pitch-black-card-list). Each tuple is
# (card_number, image_filename). The filename is appended to
# POKECOTTAGE_CDN_BASE to form the source URL, which we then wrap in
# the weserv proxy so DB-referenced images don't hit hot-link 403.
POKECOTTAGE_CDN_BASE = (
    "https://pokecottagecdn.com/mastersets/images/cards/"
)

PITCH_BLACK_CARDS: list[tuple[int, str]] = [
    (1, "2026-07-17__me5__1__Tropius__Standard.webp"),
    (2, "2026-07-17__me5__2__Grubbin__Standard.webp"),
    (3, "2026-07-17__me5__3__Fomantis__Standard.webp"),
    (4, "2026-07-17__me5__4__Lurantis_ex__Holo.webp"),
    (5, "2026-07-17__me5__5__Poltchageist__Standard.webp"),
    (6, "2026-07-17__me5__6__Sinistcha__Standard.webp"),
    (7, "2026-07-17__me5__7__Heatran__Holo.webp"),
    (8, "2026-07-17__me5__8__Mega_Delphox_ex__Holo.webp"),
    (9, "2026-07-17__me5__9__Sizzlipede__Standard.webp"),
    (10, "2026-07-17__me5__10__Centiskorch__Standard.webp"),
    (11, "2026-07-17__me5__11__Charcadet__Standard.webp"),
    (12, "2026-07-17__me5__12__Armarouge__Holo.webp"),
    (13, "2026-07-17__me5__13__Goldeen__Standard.webp"),
    (14, "2026-07-17__me5__14__Seaking__Standard.webp"),
    (15, "2026-07-17__me5__15__Wailmer__Standard.webp"),
    (16, "2026-07-17__me5__16__Wailord_ex__Holo.webp"),
    (17, "2026-07-17__me5__17__Relicanth__Standard.webp"),
    (18, "2026-07-17__me5__18__Popplio__Standard.webp"),
    (19, "2026-07-17__me5__19__Brionne__Standard.webp"),
    (20, "2026-07-17__me5__20__Primarina__Holo.webp"),
    (21, "2026-07-17__me5__21__Finizen__Standard.webp"),
    (22, "2026-07-17__me5__22__Palafin__Standard.webp"),
    (23, "2026-07-17__me5__23__Electrike__Standard.webp"),
    (24, "2026-07-17__me5__24__Manectric__Standard.webp"),
    (25, "2026-07-17__me5__25__Charjabug__Standard.webp"),
    (26, "2026-07-17__me5__26__Vikavolt__Standard.webp"),
    (27, "2026-07-17__me5__27__Mega_Zeraora_ex__Holo.webp"),
    (28, "2026-07-17__me5__28__Miraidon__Holo.webp"),
    (29, "2026-07-17__me5__29__Slowpoke__Standard.webp"),
    (30, "2026-07-17__me5__30__Slowbro__Standard.webp"),
    (31, "2026-07-17__me5__31__Mega_Slowbro_ex__Holo.webp"),
    (32, "2026-07-17__me5__32__Jynx__Standard.webp"),
    (33, "2026-07-17__me5__33__Shuppet__Standard.webp"),
    (34, "2026-07-17__me5__34__Banette__Standard.webp"),
    (35, "2026-07-17__me5__35__Spiritomb__Holo.webp"),
    (36, "2026-07-17__me5__36__Litwick__Standard.webp"),
    (37, "2026-07-17__me5__37__Lampent__Standard.webp"),
    (38, "2026-07-17__me5__38__Mega_Chandelure_ex__Holo.webp"),
    (39, "2026-07-17__me5__39__Dhelmise__Standard.webp"),
    (40, "2026-07-17__me5__40__Marshadow__Standard.webp"),
    (41, "2026-07-17__me5__41__Annihilape__Standard.webp"),
    (42, "2026-07-17__me5__42__Mankey__Standard.webp"),
    (43, "2026-07-17__me5__43__Primeape__Standard.webp"),
    (44, "2026-07-17__me5__44__Cranidos__Standard.webp"),
    (45, "2026-07-17__me5__45__Rampardos_ex__Holo.webp"),
    (46, "2026-07-17__me5__46__Drilbur__Standard.webp"),
    (47, "2026-07-17__me5__47__Koraidon__Holo.webp"),
    (48, "2026-07-17__me5__48__Mega_Darkrai_ex__Holo.webp"),
    (49, "2026-07-17__me5__49__Vullaby__Standard.webp"),
    (50, "2026-07-17__me5__50__Mandibuzz__Standard.webp"),
    (51, "2026-07-17__me5__51__Inkay__Standard.webp"),
    (52, "2026-07-17__me5__52__Malamar__Standard.webp"),
    (53, "2026-07-17__me5__53__Nickit__Standard.webp"),
    (54, "2026-07-17__me5__54__Thievul__Standard.webp"),
    (55, "2026-07-17__me5__55__Morpeko_ex__Holo.webp"),
    (56, "2026-07-17__me5__56__Zarude__Holo.webp"),
    (57, "2026-07-17__me5__57__Maschiff__Standard.webp"),
    (58, "2026-07-17__me5__58__Mabosstiff__Standard.webp"),
    (59, "2026-07-17__me5__59__Chi-Yu__Holo.webp"),
    (60, "2026-07-17__me5__60__Skarmory__Standard.webp"),
    (61, "2026-07-17__me5__61__Shieldon__Standard.webp"),
    (62, "2026-07-17__me5__62__Bastiodon__Holo.webp"),
    (63, "2026-07-17__me5__63__Bronzor__Standard.webp"),
    (64, "2026-07-17__me5__64__Bronzong__Standard.webp"),
    (65, "2026-07-17__me5__65__Mega_Excadrill_ex__Holo.webp"),
    (66, "2026-07-17__me5__66__Pikipek__Standard.webp"),
    (67, "2026-07-17__me5__67__Trumbeak__Standard.webp"),
    (68, "2026-07-17__me5__68__Toucannon__Standard.webp"),
    (69, "2026-07-17__me5__69__Type_Null__Standard.webp"),
    (70, "2026-07-17__me5__70__Silvally__Holo.webp"),
    (71, "2026-07-17__me5__71__Bombirdier__Standard.webp"),
    (72, "2026-07-17__me5__72__Antique_Armor_Fossil__Standard.webp"),
    (73, "2026-07-17__me5__73__Antique_Skull_Fossil__Standard.webp"),
    (74, "2026-07-17__me5__74__Backtrack_Badge__Standard.webp"),
    (75, "2026-07-17__me5__75__Dark_Bell__Standard.webp"),
    (76, "2026-07-17__me5__76__Fossil_Quarry__Standard.webp"),
    (77, "2026-07-17__me5__77__Gladion_s_Final_Battle__Standard.webp"),
    (78, "2026-07-17__me5__78__Gwynn__Standard.webp"),
    (79, "2026-07-17__me5__79__Jett__Standard.webp"),
    (80, "2026-07-17__me5__80__Misty_s_Vitality__Standard.webp"),
    (81, "2026-07-17__me5__81__Rust_Syndicate_Grunt__Standard.webp"),
    (82, "2026-07-17__me5__82__Tremendous_Bomb__Standard.webp"),
    (83, "2026-07-17__me5__83__Shadowy_Darkness_Energy__Holo.webp"),
    (84, "2026-07-17__me5__84__Voltaic_Lightning_Energy__Holo.webp"),
    (85, "2026-07-17__me5__85__Fomantis__Holo.webp"),
    (86, "2026-07-17__me5__86__Armarouge__Holo.webp"),
    (87, "2026-07-17__me5__87__Goldeen__Holo.webp"),
    (88, "2026-07-17__me5__88__Primarina__Holo.webp"),
    (89, "2026-07-17__me5__89__Manectric__Holo.webp"),
    (90, "2026-07-17__me5__90__Slowbro__Holo.webp"),
    (91, "2026-07-17__me5__91__Dhelmise__Holo.webp"),
    (92, "2026-07-17__me5__92__Thievul__Holo.webp"),
    (93, "2026-07-17__me5__93__Bastiodon__Holo.webp"),
    (94, "2026-07-17__me5__94__Toucannon__Holo.webp"),
    (95, "2026-07-17__me5__95__Silvally__Holo.webp"),
    (96, "2026-07-17__me5__96__Lurantis_ex__Holo.webp"),
    (97, "2026-07-17__me5__97__Wailord_ex__Holo.webp"),
    (98, "2026-07-17__me5__98__Mega_Zeraora_ex__Holo.webp"),
    (99, "2026-07-17__me5__99__Mega_Chandelure_ex__Holo.webp"),
    (100, "2026-07-17__me5__100__Rampardos_ex__Holo.webp"),
    (101, "2026-07-17__me5__101__Mega_Darkrai_ex__Holo.webp"),
    (102, "2026-07-17__me5__102__Morpeko_ex__Holo.webp"),
    (103, "2026-07-17__me5__103__Mega_Excadrill_ex__Holo.webp"),
    (104, "2026-07-17__me5__104__Brave_Bangle__Holo.webp"),
    (105, "2026-07-17__me5__105__Crushing_Hammer__Holo.webp"),
    (106, "2026-07-17__me5__106__Dark_Bell__Holo.webp"),
    (107, "2026-07-17__me5__107__Energy_Switch__Holo.webp"),
    (108, "2026-07-17__me5__108__Gladion_s_Final_Battle__Holo.webp"),
    (109, "2026-07-17__me5__109__Gwynn__Holo.webp"),
    (110, "2026-07-17__me5__110__Iron_Defender__Holo.webp"),
    (111, "2026-07-17__me5__111__Misty_s_Vitality__Holo.webp"),
    (112, "2026-07-17__me5__112__Rust_Syndicate_Grunt__Holo.webp"),
    (113, "2026-07-17__me5__113__Tremendous_Bomb__Holo.webp"),
    (114, "2026-07-17__me5__114__Mega_Zeraora_ex__Holo.webp"),
    (115, "2026-07-17__me5__115__Mega_Chandelure_ex__Holo.webp"),
    (116, "2026-07-17__me5__116__Mega_Darkrai_ex__Holo.webp"),
    (117, "2026-07-17__me5__117__Morpeko_ex__Holo.webp"),
    (118, "2026-07-17__me5__118__Gladion_s_Final_Battle__Holo.webp"),
    (119, "2026-07-17__me5__119__Gwynn__Holo.webp"),
    (120, "2026-07-17__me5__120__Mega_Darkrai_ex__Holo.webp"),
]


def _weserv_wrap(url: str) -> str:
    """Wrap a source image URL in the weserv proxy so browser requests
    for it don't hit the source CDN's hot-link protection. Same
    treatment we apply everywhere else per project convention (see
    memory: project-pulllist-weserv-images)."""
    encoded = urllib.parse.quote(url, safe="")
    return f"https://images.weserv.nl/?url={encoded}&output=webp"


async def run(dry_run: bool, overwrite: bool) -> None:
    await init_db()

    # Build lookup: card_number (int) → weserv-wrapped image URL
    by_number: dict[int, str] = {}
    for num, filename in PITCH_BLACK_CARDS:
        src = POKECOTTAGE_CDN_BASE + filename
        by_number[num] = _weserv_wrap(src)

    updates = 0
    skipped_existing = 0
    unmatched = []

    async with SessionLocal() as db:
        stmt = select(Card).where(Card.set_id == "me5")
        rows = list((await db.execute(stmt)).scalars())
        log.info(f"me5 has {len(rows)} card rows; Pokecottage list has {len(by_number)}")

        for card in rows:
            # Card number in DB may be "1" or "01" or "001" — normalize
            # by stripping leading zeros and parsing as int.
            try:
                num_int = int((card.number or "").split("/")[0].lstrip("0") or "0")
            except ValueError:
                unmatched.append((card.id, card.number, "unparseable-number"))
                continue

            src_url = by_number.get(num_int)
            if not src_url:
                unmatched.append((card.id, card.number, "not-in-pokecottage-list"))
                continue

            if not overwrite and card.image_small and card.image_large:
                skipped_existing += 1
                continue

            if not dry_run:
                card.image_small = src_url
                card.image_large = src_url
            updates += 1

        if not dry_run:
            await db.commit()

    log.info(f"=== summary ===")
    log.info(f"  updated: {updates}")
    log.info(f"  skipped (existing image, no --overwrite): {skipped_existing}")
    log.info(f"  unmatched: {len(unmatched)}")
    for cid, num, reason in unmatched[:20]:
        log.info(f"    - {cid} #{num!r}: {reason}")
    log.info(f"  dry_run: {dry_run}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace image_small / image_large even when already populated.",
    )
    args = parser.parse_args()
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(run(dry_run=args.dry_run, overwrite=args.overwrite))


if __name__ == "__main__":
    main()
