"""Import the full Japanese Pokémon TCG catalog from TCGdex.

Pulls every JP set + card from https://api.tcgdex.net/v2/ja and stores
them in our DB with `language='ja'`. TCGdex IDs (SV3, SV5K-001) are
preserved as-is so JP rows can't collide with our pokemontcg.io-style
EN ids (sv3, sv3-1).

Usage:
    python -m scripts.import_jp_catalog                  # full catalog
    python -m scripts.import_jp_catalog --set SV5K       # one set
    python -m scripts.import_jp_catalog --refresh        # re-pull existing
    python -m scripts.import_jp_catalog --sets-only      # skip card fetch
"""
from __future__ import annotations

import argparse
import asyncio
import logging
from datetime import date, datetime

import httpx
from sqlalchemy import select

from app.database import SessionLocal, init_db
from app.models import Card, Set

TCGDEX_BASE = "https://api.tcgdex.net/v2/ja"
log = logging.getLogger("import_jp_catalog")

# Sized image variants on assets.tcgdex.net. The base path the API
# returns is `https://assets.tcgdex.net/ja/SV/SV5K/001`; we append
# `/low.webp` for thumbnails and `/high.webp` for the detail view.
IMAGE_SMALL_SUFFIX = "/low.webp"
IMAGE_LARGE_SUFFIX = "/high.webp"


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def _coerce_int(value) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _image_urls(base: str | None) -> tuple[str | None, str | None]:
    if not base:
        return None, None
    return base + IMAGE_SMALL_SUFFIX, base + IMAGE_LARGE_SUFFIX


async def _upsert_set(db, raw: dict, processed: set[str]) -> Set | None:
    set_id = raw["id"]
    # Defend against duplicate detail responses in the same batch. The
    # TCGdex /ja/sets index has known dupes (sv1a x9, etc.); we dedupe
    # at the index level but a defensive skip here guarantees we never
    # call db.add() twice for the same primary key inside one session.
    if set_id in processed:
        return None
    processed.add(set_id)
    row = await db.get(Set, set_id)
    if row is not None and row.language != "ja":
        # Cross-language ID collision (e.g. lowercase JP set "sv1a" vs
        # pokemontcg.io's English "sv1a"). Refuse to touch the row -
        # silently overwriting EN data is worse than missing a JP set.
        # Long-term we'll re-import these under a prefixed id.
        log.warning(
            f"  ! skip {set_id}: existing row is language={row.language!r}, refusing to overwrite"
        )
        return None
    if row is None:
        row = Set(id=set_id, language="ja")
        db.add(row)
    cardcount = raw.get("cardCount") or {}
    serie = raw.get("serie") or {}
    row.name = raw.get("name", "")
    # Mirror into name_local too so downstream UI that prefers the
    # "native" name field doesn't have to special-case JP.
    row.name_local = raw.get("name")
    row.series = serie.get("name")
    row.printed_total = _coerce_int(cardcount.get("official"))
    row.total = _coerce_int(cardcount.get("total"))
    row.release_date = _parse_date(raw.get("releaseDate"))
    # Don't clobber a logo/symbol we mirrored ourselves (Bulbapedia, card-binder,
    # manual). TCGdex returns null for these on most JP sets, and overwriting
    # with None wipes the mirrors. Only update when the API actually has one.
    if raw.get("logo"):
        row.logo_url = raw["logo"] + ".webp"
    if raw.get("symbol"):
        row.symbol_url = raw["symbol"] + ".webp"
    row.language = "ja"
    return row


async def _upsert_card(db, raw: dict, set_id: str) -> Card | None:
    card_id = raw["id"]
    row = await db.get(Card, card_id)
    if row is not None and row.language != "ja":
        # Same protection as _upsert_set - never overwrite an EN row
        # because of a case-equal-id collision.
        log.warning(
            f"  ! skip card {card_id}: existing row is language={row.language!r}"
        )
        return None
    if row is None:
        row = Card(id=card_id, language="ja", set_id=set_id)
        db.add(row)
    img_small, img_large = _image_urls(raw.get("image"))
    pricing = raw.get("pricing") or {}
    cardmarket = pricing.get("cardmarket")

    name = raw.get("name", "")
    row.name = name
    row.name_local = name  # JP catalog: native name == display name
    row.supertype = raw.get("category")
    row.types = raw.get("types")
    row.rarity = raw.get("rarity")
    row.number = raw.get("localId")
    row.number_int = _coerce_int(raw.get("localId"))
    row.hp = str(raw.get("hp")) if raw.get("hp") is not None else None
    row.hp_int = _coerce_int(raw.get("hp"))
    row.artist = raw.get("illustrator")
    row.national_pokedex_numbers = raw.get("dexId")
    row.image_small = img_small
    row.image_large = img_large
    row.cardmarket_prices = cardmarket
    row.set_id = set_id
    row.language = "ja"
    return row


async def _fetch_json(client: httpx.AsyncClient, url: str) -> dict | list | None:
    try:
        r = await client.get(url, timeout=20)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPError as e:
        log.warning(f"  ! HTTP {url}: {e}")
        return None


async def run(only_set: str | None, refresh: bool, sets_only: bool) -> None:
    await init_db()

    async with httpx.AsyncClient() as client:
        index = await _fetch_json(client, f"{TCGDEX_BASE}/sets")
        if not isinstance(index, list):
            log.error("Failed to fetch JP set index.")
            return
        raw_count = len(index)

        # TCGdex's /ja/sets index returns duplicates (XY5a x2, sv1a x8, ...).
        # Importing both copies would trip the sets.id primary key. Keep
        # the first occurrence of each id; per-set detail is identical
        # across duplicates so picking either is fine.
        seen: set[str] = set()
        unique = []
        for s in index:
            sid = s.get("id")
            if not sid or sid in seen:
                continue
            seen.add(sid)
            unique.append(s)
        index = unique
        log.info(f"Fetched {raw_count} JP sets from index ({raw_count - len(index)} duplicates removed -> {len(index)} unique).")

        if only_set:
            index = [s for s in index if s.get("id") == only_set]
            if not index:
                log.error(f"Set {only_set} not in TCGdex index.")
                return

        sem = asyncio.Semaphore(8)

        async def get_set_detail(s: dict) -> dict | None:
            async with sem:
                return await _fetch_json(client, f"{TCGDEX_BASE}/sets/{s['id']}")

        details = await asyncio.gather(*[get_set_detail(s) for s in index])
        details = [d for d in details if d]
        log.info(f"Fetched details for {len(details)} sets.")

        # Upsert sets first so card FKs resolve.
        processed_set_ids: set[str] = set()
        async with SessionLocal() as db:
            for d in details:
                await _upsert_set(db, d, processed_set_ids)
            await db.commit()
        log.info(f"Upserted {len(processed_set_ids)} JP sets.")

        if sets_only:
            return

        # Cards. The set-detail payload includes a thin `cards` array with
        # only id+name+image+localId, so we have to hit the per-card
        # endpoint for full detail (hp, rarity, types, etc.).
        async with SessionLocal() as db:
            existing_ids: set[str] = set()
            if not refresh:
                rows = (await db.execute(
                    select(Card.id).where(Card.language == "ja")
                )).all()
                existing_ids = {r[0] for r in rows}
                if existing_ids:
                    log.info(f"  {len(existing_ids):,} JP cards already in DB - will skip unless --refresh.")

        for i, d in enumerate(details, 1):
            set_id = d["id"]
            thin_cards = d.get("cards") or []
            to_fetch = [
                c for c in thin_cards
                if refresh or c["id"] not in existing_ids
            ]
            if not to_fetch:
                log.info(f"  [{i}/{len(details)}] {set_id:10s} all cards already cached, skipping.")
                continue

            log.info(f"  [{i}/{len(details)}] {set_id:10s} {d.get('name','')[:25]:25s} fetching {len(to_fetch)} cards…")

            async def fetch_card(cid: str) -> dict | None:
                async with sem:
                    return await _fetch_json(client, f"{TCGDEX_BASE}/cards/{cid}")

            details_chunk = await asyncio.gather(*[fetch_card(c["id"]) for c in to_fetch])

            async with SessionLocal() as db:
                written = 0
                for raw in details_chunk:
                    if raw is None:
                        continue
                    await _upsert_card(db, raw, set_id)
                    existing_ids.add(raw["id"])
                    written += 1
                await db.commit()
            log.info(f"    -> wrote {written} cards")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--set", dest="only_set", help="Import only this TCGdex set id (e.g. SV5K)")
    parser.add_argument("--refresh", action="store_true", help="Re-fetch cards already in DB")
    parser.add_argument("--sets-only", action="store_true", help="Sets first; defer card fetch")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    asyncio.run(run(args.only_set, args.refresh, args.sets_only))


if __name__ == "__main__":
    main()
