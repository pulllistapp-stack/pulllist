"""Seed a TCGCSV promo group into our Sets / Cards tables.

Why we need this:
    pokemontcg.io's promo coverage is patchy — newer US-promo sets
    like "ME: Mega Evolution Promo" (MEP) don't show up, so the scan
    flow OCRs the card correctly but mis-matches against the closest
    regular set instead. TCGCSV mirrors TCGplayer's full product list
    including promos, so this script reads any TCGCSV group and
    upserts our catalog directly.

What it handles:
    - Card-number extraction from messy product names
      ("Mega Lucario ex - 033", "Drifloon - (Cosmos Holo) 005",
       "N's Zekrom - 031 (Pokemon Center Exclusive)")
    - Pokemon Center exclusive variants — same Pokémon, same number,
      different productId / price / image. We give them a `-pkc`
      suffix on card_id and keep "(Pokemon Center Exclusive)" in the
      display name so collectors can tell them apart.
    - Cosmos Holo + other parenthetical variants — same pattern
      ("-cosmos", etc.) so each priced TCGplayer product becomes a
      distinct PullList card.
    - Idempotent — re-running upserts; existing rows keep their
      collection / wishlist FKs.

Usage examples:
    # MEP (ME: Mega Evolution Promo)
    python -m scripts.seed_promo_group --group-id 24451 \\
        --set-id mep --set-name "ME: Mega Evolution Promo" \\
        --series "Mega Evolution" --release-date 2025-09-26

    # SVP (SV Black Star Promos)
    python -m scripts.seed_promo_group --group-id 22872 \\
        --set-id svp --set-name "SV: Scarlet & Violet Promo Cards" \\
        --series "Scarlet & Violet" --release-date 2023-03-31

    # Dry run (no DB writes)
    python -m scripts.seed_promo_group --group-id 24451 \\
        --set-id mep --set-name "ME: Mega Evolution Promo" --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import re
import sys
from datetime import date, datetime
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("DEBUG", "false")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

from app.database import SessionLocal, init_db  # noqa: E402
from app.models import Card, Set  # noqa: E402

log = logging.getLogger("seed_promo_group")

TCGCSV = "https://tcgcsv.com/tcgplayer/3"
USER_AGENT = "PullList/1.0 (https://pulllist.org; bot)"

# Variant suffix in parentheses → card_id suffix + readable label.
_VARIANT_MAP: list[tuple[re.Pattern[str], str, str]] = [
    (re.compile(r"pokemon center", re.IGNORECASE), "pkc", "Pokemon Center Exclusive"),
    (re.compile(r"pokémon center", re.IGNORECASE), "pkc", "Pokémon Center Exclusive"),
    (re.compile(r"cosmos holo", re.IGNORECASE), "cosmos", "Cosmos Holo"),
    (re.compile(r"reverse holo", re.IGNORECASE), "reverse", "Reverse Holo"),
    (re.compile(r"non[- ]holo", re.IGNORECASE), "nonholo", "Non-Holo"),
    (re.compile(r"prerelease", re.IGNORECASE), "prerelease", "Prerelease"),
    (re.compile(r"staff", re.IGNORECASE), "staff", "Staff"),
]

# Match a 3-digit card number anywhere in the title (handles "- 005",
# "- (Cosmos Holo) 005", "- 005 (Cosmos Holo)").
_NUMBER_RE = re.compile(r"\b(\d{1,3})\b")


def _parse_product(name: str) -> tuple[str, str | None, str | None, str | None]:
    """Return (clean_name, number, variant_id, variant_label).

    clean_name: card name with the number-tail removed but the
                variant suffix preserved for display.
    number:     3-digit card number string, or None if unparseable.
    variant_id: short tag for card_id suffix ('pkc', 'cosmos', None).
    variant_label: human-readable variant suffix to retain in the
                display name (None when no variant).
    """
    # Split on " - " separator if present; pre-separator chunk is the
    # base name + "Card Name", post-separator carries number + variant.
    base, _, tail = name.partition(" - ")
    if not tail:
        # Some products skip the " - " (rare) — fall back to scanning
        # the whole name.
        tail = base
        base = base

    number_match = _NUMBER_RE.search(tail)
    number = number_match.group(1).zfill(3) if number_match else None

    variant_id: str | None = None
    variant_label: str | None = None
    # Variant suffixes can appear in either parens OR square brackets:
    #   "Riolu - 010 (Pokemon Center Exclusive)" → paren-style
    #   "Meganium - 001 [Staff]"                  → bracket-style
    # Scan both shapes.
    bracket_matches = re.findall(r"\(([^)]+)\)|\[([^\]]+)\]", tail)
    for paren, bracket in bracket_matches:
        candidate = paren or bracket
        for pat, vid, vlabel in _VARIANT_MAP:
            if pat.search(candidate):
                variant_id = vid
                variant_label = vlabel
                break
        if variant_id:
            break

    # Display name: keep variant suffix (so the UI tells them apart)
    # but drop the " - NNN" / standalone number / "(Cosmos Holo)" bare
    # parts unless they're the variant label we want to keep.
    display = base.strip()
    if variant_label:
        display = f"{display} ({variant_label})"
    return display, number, variant_id, variant_label


def _extended(extended: list[dict], key: str) -> str | None:
    for entry in extended or []:
        if entry.get("name") == key:
            return entry.get("value")
    return None


async def fetch_products(group_id: int) -> list[dict]:
    async with httpx.AsyncClient(
        timeout=60.0, headers={"User-Agent": USER_AGENT}
    ) as c:
        r = await c.get(f"{TCGCSV}/{group_id}/products")
        r.raise_for_status()
        data = r.json()
        return data.get("results", [])


async def seed(
    *,
    group_id: int,
    set_id: str,
    set_name: str,
    series: str | None,
    release_date: str | None,
    dry_run: bool,
) -> None:
    await init_db()
    products = await fetch_products(group_id)
    log.info("fetched %d products from TCGCSV group %d", len(products), group_id)

    set_release: date | None = None
    if release_date:
        set_release = date.fromisoformat(release_date)

    stats = {
        "set_created_or_existed": 0,
        "cards_inserted": 0,
        "cards_updated": 0,
        "cards_skipped_no_number": 0,
        "variants_detected": 0,
        "id_collisions_resolved": 0,
    }
    # Track card_ids we've already used in THIS batch so we can
    # disambiguate collisions our variant regex didn't catch (some
    # TCGplayer SKUs share a number with no parseable suffix — e.g.
    # marketplace fulfilment variants).
    used_ids: set[str] = set()

    async with SessionLocal() as db:
        # Upsert the Set row
        existing_set = await db.get(Set, set_id)
        if existing_set is None:
            if not dry_run:
                db.add(
                    Set(
                        id=set_id,
                        name=set_name,
                        series=series,
                        release_date=set_release,
                        language="en",
                        printed_total=None,
                        total=len(products),
                    )
                )
                await db.commit()
            log.info("inserted Set id=%s name=%s", set_id, set_name)
        else:
            log.info("Set %s already exists; cards will upsert", set_id)
        stats["set_created_or_existed"] = 1

        for p in products:
            product_id = p.get("productId")
            raw_name = p.get("name", "")
            display, number, variant_id, variant_label = _parse_product(raw_name)

            if number is None:
                log.warning("skip (no number): %s", raw_name)
                stats["cards_skipped_no_number"] += 1
                continue

            card_id = f"{set_id}-{number}"
            if variant_id:
                card_id = f"{card_id}-{variant_id}"
                stats["variants_detected"] += 1

            # In-batch uniqueness guard. If two TCGplayer products parse
            # to the same id (variant suffix we didn't recognise, weird
            # SKU split, etc.) tag the second one with the productId so
            # both rows survive. Better than failing the whole batch.
            if card_id in used_ids:
                card_id = f"{card_id}-{product_id}"
                stats["id_collisions_resolved"] += 1
            used_ids.add(card_id)

            rarity = _extended(p.get("extendedData") or [], "Rarity") or "Promo"
            hp_str = _extended(p.get("extendedData") or [], "HP")
            hp_int = None
            if hp_str:
                try:
                    hp_int = int(hp_str)
                except ValueError:
                    hp_int = None
            card_type = _extended(p.get("extendedData") or [], "Card Type")

            image_url = p.get("imageUrl")
            image_small = image_url
            image_large = (
                image_url.replace("_200w.jpg", "_400w.jpg") if image_url else None
            )
            tcg_url = p.get("url")

            existing = await db.get(Card, card_id)
            if existing is None:
                if not dry_run:
                    db.add(
                        Card(
                            id=card_id,
                            name=display,
                            supertype="Pokémon" if hp_int else None,
                            rarity=rarity,
                            number=number,
                            number_int=int(number) if number.isdigit() else None,
                            hp=hp_str,
                            hp_int=hp_int,
                            types=[card_type] if card_type else None,
                            image_small=image_small,
                            image_large=image_large,
                            tcgplayer_url=tcg_url,
                            tcgplayer_product_id=product_id,
                            set_id=set_id,
                            language="en",
                            created_at=datetime.utcnow(),
                            updated_at=datetime.utcnow(),
                        )
                    )
                stats["cards_inserted"] += 1
                log.info(
                    "  + %s  %s  (productId=%s)", card_id, display, product_id
                )
            else:
                # Idempotent update — refresh metadata that may have
                # changed (image URL revision, new rarity classification)
                # but never overwrite collection FKs (those live on
                # CollectionItem.card_id and aren't on this row).
                if not dry_run:
                    existing.name = display
                    existing.rarity = rarity
                    existing.number = number
                    existing.number_int = (
                        int(number) if number.isdigit() else None
                    )
                    existing.image_small = image_small
                    existing.image_large = image_large
                    existing.tcgplayer_url = tcg_url
                    existing.tcgplayer_product_id = product_id
                    existing.updated_at = datetime.utcnow()
                stats["cards_updated"] += 1

        if not dry_run:
            await db.commit()

    log.info("=== summary ===")
    for k, v in stats.items():
        log.info("  %s: %s", k, v)
    log.info("  dry_run: %s", dry_run)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--group-id", type=int, required=True)
    parser.add_argument("--set-id", required=True, help="Our PullList set id, e.g. 'mep'")
    parser.add_argument("--set-name", required=True)
    parser.add_argument("--series", default=None)
    parser.add_argument("--release-date", default=None, help="YYYY-MM-DD")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    asyncio.run(
        seed(
            group_id=args.group_id,
            set_id=args.set_id,
            set_name=args.set_name,
            series=args.series,
            release_date=args.release_date,
            dry_run=args.dry_run,
        )
    )


if __name__ == "__main__":
    main()
