"""Backfill Card.tcgplayer_product_id via TCGCSV.

TCGplayer's public search page is a Single-Page App — the initial
HTML is a static CloudFront shell with no product list, so plain
httpx scraping returns zero matches (the JS-rendered grid hits a
private internal API client-side). TCGCSV (our daily price source,
tcgcsv.com) republishes TCGplayer's full product catalog as JSON
including the canonical productIds, so we resolve through it instead.

For each candidate card without a tcgplayer_product_id:
  1. Map the card's set to one or more TCGCSV group ids (hand-curated)
  2. Fetch products in those groups (cached per-group)
  3. Match by (normalised name, normalised number) → productId
  4. UPDATE Card.tcgplayer_product_id

Series 2 First Partner cards aren't indexed yet (TCGCSV lags TCGplayer's
catalogue by ~1-2 weeks for new sets); re-run later to pick them up.

Usage:
    # Default — fill missing ids for the manual fpic-* sets:
    python -m scripts.backfill_tcgplayer_product_id

    # Specific set:
    python -m scripts.backfill_tcgplayer_product_id --set-ids fpic-s1

    # Add extra TCGCSV groups to scan (comma-separated group ids):
    python -m scripts.backfill_tcgplayer_product_id --extra-groups 24722

    # Refresh (overwrite existing ids — rare, for stale rows):
    python -m scripts.backfill_tcgplayer_product_id --refresh

    # Dry-run (don't write, just log what would be set):
    python -m scripts.backfill_tcgplayer_product_id --dry-run
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
from sqlalchemy import select, update

from app.database import SessionLocal, init_db
from app.models import Card

log = logging.getLogger("backfill_tcgplayer_product_id")

TCGCSV_BASE = "https://tcgcsv.com/tcgplayer"
POKEMON_CATEGORY = "3"

# Hand-curated mapping from our internal set_id to the TCGCSV groupId
# that holds the singles for that set. TCGCSV groups TCGplayer's data
# by "set" as TCGplayer defines it, which doesn't always align with the
# product line LO/I assigned the cards under in our catalogue — e.g.
# the First Partner Illustration *Collection* (sealed boxes) lives in
# group 24584, but the individual promo cards (037–054) live in group
# 24451 "ME: Mega Evolution Promo" because that's where TCGplayer
# catalogues the singles.
#
# To add a new set: open https://tcgcsv.com/tcgplayer/3/groups and
# find the group whose listed products match the cards you're trying
# to resolve.
SET_TO_TCGCSV_GROUPS: dict[str, tuple[int, ...]] = {
    "fpic-s1": (24451,),  # ME: Mega Evolution Promo (037–045)
    "fpic-s2": (24451,),  # Series 2 promos will land here once TCGCSV indexes them
    "fpic-s3": (24451,),  # Series 3 (Aug 2026 release) ditto
}

_HEADERS = {
    "User-Agent": "PullList/1.0 (https://pulllist.org)",
    "Accept": "application/json",
}

# TCGCSV is a static-ish JSON API behind CloudFront — friendly, no
# documented rate cap. A small delay between group fetches stays
# polite without dragging the run out.
_THROTTLE_S = 0.3


_NAME_TRAIL_NUMBER_RE = re.compile(r"\s*[-–—]\s*\d+[a-z]*\s*$")


def _normalise_name(name: str) -> str:
    """Lowercase + strip diacritics + drop trailing ' - <number>' so
    TCGCSV's product naming convention ("Bulbasaur - 037") aligns with
    our DB's bare card name ("Bulbasaur"). 'Pokémon' also folds to
    'pokemon' for cross-source matching."""
    folded = (
        unicodedata.normalize("NFKD", name.lower())
        .encode("ascii", "ignore")
        .decode("ascii")
    )
    folded = _NAME_TRAIL_NUMBER_RE.sub("", folded)
    return re.sub(r"\s+", " ", folded).strip()


def _normalise_number(number: str | None) -> str | None:
    """TCGCSV stores card numbers as printed (e.g. '037'). Strip
    leading zeros for a tolerant compare path that also catches '37'
    style inputs. We try strict match first, fall back to this."""
    if not number:
        return None
    n = number.split("/")[0].strip()
    return n.lstrip("0") or "0"


async def fetch_products(
    client: httpx.AsyncClient, group_id: int
) -> list[dict[str, Any]]:
    url = f"{TCGCSV_BASE}/{POKEMON_CATEGORY}/{group_id}/products"
    r = await client.get(url, headers=_HEADERS, timeout=30.0)
    r.raise_for_status()
    payload = r.json()
    return payload.get("results", [])


def _extract_number(product: dict[str, Any]) -> str | None:
    """TCGCSV exposes the printed card number via extendedData entries
    of name=='Number'. Older / partial rows just have it absent. The
    extendedData list isn't keyed, so we walk it."""
    for ext in product.get("extendedData") or []:
        if (ext.get("name") or "").lower() == "number":
            value = ext.get("value")
            if isinstance(value, str):
                return value.strip()
    return None


async def backfill(
    set_ids: tuple[str, ...],
    extra_groups: tuple[int, ...],
    refresh: bool,
    dry_run: bool,
) -> None:
    await init_db()

    async with SessionLocal() as db:
        stmt = select(Card).where(Card.set_id.in_(set_ids))
        if not refresh:
            stmt = stmt.where(Card.tcgplayer_product_id.is_(None))
        cards = list((await db.execute(stmt)).scalars())

    log.info(
        f"Selected {len(cards)} card(s) across sets={list(set_ids)} "
        f"(refresh={refresh}, dry_run={dry_run})"
    )

    if not cards:
        log.info("Nothing to do.")
        return

    # Aggregate every group we'll need across all selected cards, plus
    # any explicit --extra-groups. Fetching each group once.
    needed_groups: set[int] = set(extra_groups)
    for c in cards:
        needed_groups.update(SET_TO_TCGCSV_GROUPS.get(c.set_id, ()))
    if not needed_groups:
        log.error(
            "No TCGCSV groups mapped for sets %s. Add an entry to "
            "SET_TO_TCGCSV_GROUPS or pass --extra-groups.",
            list(set_ids),
        )
        return
    log.info(f"Will fetch TCGCSV groups: {sorted(needed_groups)}")

    # (normalised_name, normalised_number) → productId
    # Strict (with-leading-zeros) and tolerant (zero-stripped) entries
    # are both written so a card stored as '37' or '037' resolves the
    # same way.
    lookup: dict[tuple[str, str], int] = {}
    async with httpx.AsyncClient() as client:
        for gid in sorted(needed_groups):
            try:
                products = await fetch_products(client, gid)
            except httpx.HTTPError as exc:
                log.warning(f"  ! group {gid} fetch failed: {exc}")
                continue
            added = 0
            for p in products:
                pid = p.get("productId")
                name = p.get("name")
                num = _extract_number(p)
                if not (isinstance(pid, int) and isinstance(name, str) and num):
                    continue
                key_name = _normalise_name(name)
                lookup[(key_name, num)] = pid
                stripped = _normalise_number(num)
                if stripped and stripped != num:
                    lookup[(key_name, stripped)] = pid
                added += 1
            log.info(f"  group {gid}: {added} products indexed")
            await asyncio.sleep(_THROTTLE_S)

    resolved: list[tuple[str, int]] = []
    misses: list[str] = []
    for card in cards:
        name_key = _normalise_name(card.name)
        num_key = _normalise_number(card.number)
        if not num_key:
            misses.append(card.id)
            log.info(f"{card.id} {card.name!r}: no card number to match")
            continue
        pid = lookup.get((name_key, num_key))
        if pid is None and card.number:
            # Fallback to printed-form match in case the stripping
            # disagrees with TCGCSV's storage form.
            pid = lookup.get((name_key, card.number.strip()))
        if pid is None:
            misses.append(card.id)
            log.info(
                f"{card.id:20s} {card.name!r:24s} #{card.number}: no TCGCSV match"
            )
        else:
            resolved.append((card.id, pid))
            log.info(
                f"{card.id:20s} {card.name!r:24s} #{card.number} → productId {pid}"
            )

    if dry_run:
        log.info(
            f"Dry run: would update {len(resolved)} row(s), "
            f"{len(misses)} miss(es)."
        )
        return

    if not resolved:
        log.info("No rows to write.")
        return

    async with SessionLocal() as db:
        for card_id, pid in resolved:
            await db.execute(
                update(Card)
                .where(Card.id == card_id)
                .values(tcgplayer_product_id=pid)
            )
        await db.commit()
    log.info(
        f"Wrote {len(resolved)} tcgplayer_product_id(s). "
        f"Misses: {len(misses)} (rerun later for sets still indexing on TCGCSV)"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--set-ids",
        default="fpic-s1,fpic-s2",
        help="Comma-separated set ids to backfill (default: fpic-s1,fpic-s2)",
    )
    parser.add_argument(
        "--extra-groups",
        default="",
        help="Comma-separated extra TCGCSV groupIds to scan (rarely needed)",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Re-resolve cards that already have a tcgplayer_product_id",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log what would be written without touching the DB",
    )
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    set_ids = tuple(s.strip() for s in args.set_ids.split(",") if s.strip())
    extra_groups = tuple(
        int(g.strip()) for g in args.extra_groups.split(",") if g.strip()
    )
    asyncio.run(
        backfill(
            set_ids=set_ids,
            extra_groups=extra_groups,
            refresh=args.refresh,
            dry_run=args.dry_run,
        )
    )


if __name__ == "__main__":
    main()
