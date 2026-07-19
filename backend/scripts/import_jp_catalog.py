"""Import a full non-EN Pokémon TCG catalog from TCGdex.

Pulls every set + card for the requested language from TCGdex and
stores them in our DB with `Set.language`/`Card.language` set to the
same code. TCGdex IDs (SV3, SV5K-001, CSM1cC) are preserved as-is so
non-EN rows can't collide with our pokemontcg.io-style EN ids
(sv3, sv3-1).

Originally shipped as `import_jp_catalog.py` when JP was the only
non-EN catalog. Now parametrized on `--lang` — same script drives
JP (ja), KR (ko), CN Simplified (zh-cn), and any future TCGdex
locale. Filename kept for backward compatibility with existing docs
and inline references; runs default to `--lang ja` when omitted.

Usage:
    python -m scripts.import_jp_catalog                       # JP (default)
    python -m scripts.import_jp_catalog --lang ko             # KR full catalog
    python -m scripts.import_jp_catalog --lang zh-cn          # CN Simplified
    python -m scripts.import_jp_catalog --lang ko --set SM1M  # one KR set
    python -m scripts.import_jp_catalog --refresh             # re-pull existing
    python -m scripts.import_jp_catalog --sets-only           # skip card fetch
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

TCGDEX_ROOT = "https://api.tcgdex.net/v2"
log = logging.getLogger("import_tcgdex_catalog")

# Supported locales — anything TCGdex serves and our DB understands.
# 'en' is intentionally omitted: EN catalog lives on pokemontcg.io and
# is imported by a separate pipeline. Hitting TCGdex for EN would
# introduce a divergent source of truth for the same rows.
SUPPORTED_LANGS = ("ja", "ko", "zh-cn", "zh-tw")

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


# TCGdex's JP rarity labels use inconsistent casing ("Double rare",
# "Illustration rare") and a few non-pokemontcg.io spellings ("Holo Rare",
# "Secret Rare"). The frontend filter groups (FilterSidebar) and the
# rarity-tier color map (lib/rarity.ts) both key off pokemontcg.io's
# canonical names, so we normalize on the way in.
_RARITY_REMAP: dict[str, str] = {
    "Holo Rare": "Rare Holo",
    "Double rare": "Double Rare",
    "Illustration rare": "Illustration Rare",
    "Special illustration rare": "Special Illustration Rare",
    "Shiny rare": "Shiny Rare",
    "Secret Rare": "Rare Secret",
}


def _normalize_rarity(value: str | None) -> str | None:
    if not value:
        return None
    # TCGdex sometimes returns the string "None"; treat it as missing.
    if value == "None":
        return None
    return _RARITY_REMAP.get(value, value)


async def _upsert_set(db, raw: dict, processed: set[str], lang: str) -> Set | None:
    set_id = raw["id"]
    # Defend against duplicate detail responses in the same batch. The
    # TCGdex /{lang}/sets index has known dupes (sv1a x9 on ja, etc.); we
    # dedupe at the index level but a defensive skip here guarantees we
    # never call db.add() twice for the same primary key inside one
    # session.
    if set_id in processed:
        return None
    processed.add(set_id)
    row = await db.get(Set, set_id)
    if row is not None and row.language != lang:
        # Cross-language ID collision (e.g. lowercase JP set "sv1a" vs
        # pokemontcg.io's English "sv1a", or KR "SM1M" landing on JP
        # "SM1M" if we ever share ids). Refuse to touch the row -
        # silently overwriting another catalog's data is worse than
        # missing a set. Long-term such sets need a prefixed id.
        log.warning(
            f"  ! skip {set_id}: existing row is language={row.language!r}, refusing to overwrite (importing lang={lang!r})"
        )
        return None
    if row is None:
        row = Set(id=set_id, language=lang)
        db.add(row)
    cardcount = raw.get("cardCount") or {}
    serie = raw.get("serie") or {}
    row.name = raw.get("name", "")
    # Mirror into name_local too so downstream UI that prefers the
    # "native" name field doesn't have to special-case each locale.
    row.name_local = raw.get("name")
    row.series = serie.get("name")
    row.printed_total = _coerce_int(cardcount.get("official"))
    row.total = _coerce_int(cardcount.get("total"))
    row.release_date = _parse_date(raw.get("releaseDate"))
    # Don't clobber a logo/symbol we mirrored ourselves (Bulbapedia,
    # card-binder, manual). TCGdex returns null for these on many JP
    # sets, and overwriting with None wipes the mirrors. Only update
    # when the API actually has one.
    if raw.get("logo"):
        row.logo_url = raw["logo"] + ".webp"
    if raw.get("symbol"):
        row.symbol_url = raw["symbol"] + ".webp"
    row.language = lang
    return row


async def _upsert_card(db, raw: dict, set_id: str, lang: str) -> Card | None:
    card_id = raw["id"]
    row = await db.get(Card, card_id)
    if row is not None and row.language != lang:
        # Same protection as _upsert_set - never overwrite another
        # catalog's row because of a case-equal-id collision.
        log.warning(
            f"  ! skip card {card_id}: existing row is language={row.language!r} (importing lang={lang!r})"
        )
        return None
    if row is None:
        row = Card(id=card_id, language=lang, set_id=set_id)
        db.add(row)
    img_small, img_large = _image_urls(raw.get("image"))
    pricing = raw.get("pricing") or {}
    cardmarket = pricing.get("cardmarket")

    name = raw.get("name", "")
    row.name = name
    row.name_local = name  # native locale name == display name for all TCGdex locales
    row.supertype = raw.get("category")
    row.types = raw.get("types")
    row.rarity = _normalize_rarity(raw.get("rarity"))
    row.number = raw.get("localId")
    row.number_int = _coerce_int(raw.get("localId"))
    row.hp = str(raw.get("hp")) if raw.get("hp") is not None else None
    row.hp_int = _coerce_int(raw.get("hp"))
    row.artist = raw.get("illustrator")
    # TCGdex occasionally returns dex ids as floats (e.g. 384.1 to flag a
    # delta-species variant of #384 Rayquaza). Our schema is list[int]
    # and the API serializer rejects floats — coerce to int here so the
    # decimal annotation never reaches the column.
    raw_dex = raw.get("dexId") or []
    row.national_pokedex_numbers = [int(n) for n in raw_dex] or None
    row.image_small = img_small
    row.image_large = img_large
    row.cardmarket_prices = cardmarket
    row.set_id = set_id
    row.language = lang
    return row


async def _fetch_json(client: httpx.AsyncClient, url: str) -> dict | list | None:
    try:
        r = await client.get(url, timeout=20)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPError as e:
        log.warning(f"  ! HTTP {url}: {e}")
        return None


async def run(
    only_set: str | None,
    refresh: bool,
    sets_only: bool,
    lang: str,
) -> None:
    await init_db()

    base = f"{TCGDEX_ROOT}/{lang}"
    lang_label = lang.upper()

    async with httpx.AsyncClient() as client:
        index = await _fetch_json(client, f"{base}/sets")
        if not isinstance(index, list):
            log.error(f"Failed to fetch {lang_label} set index.")
            return
        raw_count = len(index)

        # TCGdex's set index returns duplicates on some locales (JP:
        # XY5a x2, sv1a x8; KR/CN: fewer or none, but the dedupe is
        # cheap enough to always run). Importing both copies would trip
        # the sets.id primary key. Keep the first occurrence of each id;
        # per-set detail is identical across duplicates so either wins.
        seen: set[str] = set()
        unique = []
        for s in index:
            sid = s.get("id")
            if not sid or sid in seen:
                continue
            seen.add(sid)
            unique.append(s)
        index = unique
        log.info(
            f"Fetched {raw_count} {lang_label} sets from index "
            f"({raw_count - len(index)} duplicates removed -> {len(index)} unique)."
        )

        if only_set:
            index = [s for s in index if s.get("id") == only_set]
            if not index:
                log.error(f"Set {only_set} not in TCGdex {lang_label} index.")
                return

        sem = asyncio.Semaphore(8)

        async def get_set_detail(s: dict) -> dict | None:
            async with sem:
                return await _fetch_json(client, f"{base}/sets/{s['id']}")

        details = await asyncio.gather(*[get_set_detail(s) for s in index])
        details = [d for d in details if d]
        log.info(f"Fetched details for {len(details)} sets.")

        # Upsert sets first so card FKs resolve.
        processed_set_ids: set[str] = set()
        async with SessionLocal() as db:
            for d in details:
                await _upsert_set(db, d, processed_set_ids, lang)
            await db.commit()
        log.info(f"Upserted {len(processed_set_ids)} {lang_label} sets.")

        if sets_only:
            return

        # Cards. The set-detail payload includes a thin `cards` array
        # with only id+name+image+localId, so we have to hit the per-
        # card endpoint for full detail (hp, rarity, types, etc.).
        async with SessionLocal() as db:
            existing_ids: set[str] = set()
            if not refresh:
                rows = (await db.execute(
                    select(Card.id).where(Card.language == lang)
                )).all()
                existing_ids = {r[0] for r in rows}
                if existing_ids:
                    log.info(
                        f"  {len(existing_ids):,} {lang_label} cards already "
                        f"in DB - will skip unless --refresh."
                    )

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

            log.info(
                f"  [{i}/{len(details)}] {set_id:10s} {d.get('name','')[:25]:25s} "
                f"fetching {len(to_fetch)} cards…"
            )

            async def fetch_card(cid: str) -> dict | None:
                async with sem:
                    return await _fetch_json(client, f"{base}/cards/{cid}")

            details_chunk = await asyncio.gather(*[fetch_card(c["id"]) for c in to_fetch])

            async with SessionLocal() as db:
                written = 0
                for raw in details_chunk:
                    if raw is None:
                        continue
                    await _upsert_card(db, raw, set_id, lang)
                    existing_ids.add(raw["id"])
                    written += 1
                await db.commit()
            log.info(f"    -> wrote {written} cards")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--set", dest="only_set", help="Import only this TCGdex set id (e.g. SV5K)")
    parser.add_argument("--refresh", action="store_true", help="Re-fetch cards already in DB")
    parser.add_argument("--sets-only", action="store_true", help="Sets first; defer card fetch")
    parser.add_argument(
        "--lang",
        default="ja",
        choices=SUPPORTED_LANGS,
        help=(
            "TCGdex locale to import (default: ja). Populates "
            "Set.language / Card.language on inserted rows."
        ),
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    asyncio.run(run(args.only_set, args.refresh, args.sets_only, args.lang))


if __name__ == "__main__":
    main()
