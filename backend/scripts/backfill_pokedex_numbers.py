"""Backfill national_pokedex_numbers on JP / KR cards that came in without it.

Cards imported via TCGdex carry dexId out of the box, but our self-scraped
JP promo sets (JPP-XY, JPP-SwSh, JPP-SM, etc.) don't. With dex null the
cross-language search can't pair them with an EN query — searching
"Pikachu" misses every JP promo Pikachu even though we have them.

Fix: pull the Pokémon name index from PokéAPI (en / ja-Hrkt / ko names
for all 1025 dex entries), then for each card with dex IS NULL scan its
display name for the longest matching Pokémon name and set
national_pokedex_numbers = [dex]. Longest match wins so "Surfing Pikachu"
beats "Pichu", "ピカチュウex" beats "ピチュー", etc.

One-shot, idempotent. Safe to re-run.
"""

from __future__ import annotations

import asyncio
import logging
import re
import sys
from pathlib import Path

import httpx
from sqlalchemy import select, update

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal  # noqa: E402
from app.models import Card  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("backfill_dex")

POKEAPI_LIST = "https://pokeapi.co/api/v2/pokemon-species/?limit=1300"
POKEAPI_SPECIES = "https://pokeapi.co/api/v2/pokemon-species/{name}/"

# PokéAPI's language codes for the names we care about.
LANG_CODES = {"en", "ja-Hrkt", "ja", "ko"}


async def _fetch_json(client: httpx.AsyncClient, url: str) -> dict:
    r = await client.get(url, timeout=30.0)
    r.raise_for_status()
    return r.json()


async def build_name_index() -> dict[str, int]:
    """Returns name → dex_number. Multiple-language names all point at the
    same Pokémon's national dex id."""
    name_to_dex: dict[str, int] = {}
    async with httpx.AsyncClient() as client:
        log.info("fetching species list...")
        listing = await _fetch_json(client, POKEAPI_LIST)
        species_urls = [s["url"] for s in listing["results"]]
        log.info(f"  {len(species_urls)} species to walk")
        for i, url in enumerate(species_urls, 1):
            try:
                sp = await _fetch_json(client, url)
            except Exception as exc:
                log.warning(f"  ! skip {url}: {exc}")
                continue
            dex = sp.get("id")
            if not dex or dex > 1025:
                continue
            for nm in sp.get("names", []):
                lang = (nm.get("language") or {}).get("name")
                if lang not in LANG_CODES:
                    continue
                name = (nm.get("name") or "").strip()
                if not name:
                    continue
                # Don't let a shorter name overwrite a longer same-dex entry —
                # we want the most specific match anchor available.
                if name not in name_to_dex:
                    name_to_dex[name] = dex
            if i % 100 == 0:
                log.info(f"  ... {i}/{len(species_urls)}")
    return name_to_dex


def find_best_match(card_name: str, name_to_dex: dict[str, int]) -> int | None:
    """Longest substring match wins. Falls back to None if the card name
    doesn't contain any known Pokémon name (Trainer cards, basic Energy,
    fully-stylized promo titles like お公家さまと舞妓はん)."""
    candidates: list[tuple[int, int]] = []  # (length, dex)
    lower = card_name.lower()
    for name, dex in name_to_dex.items():
        target = name.lower() if not _is_cjk(name) else name
        haystack = lower if not _is_cjk(name) else card_name
        if target in haystack:
            candidates.append((len(name), dex))
    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0][1]


_CJK_RE = re.compile(r"[　-〿぀-ヿ㐀-䶿一-鿿＀-￯가-힯]")


def _is_cjk(s: str) -> bool:
    return bool(_CJK_RE.search(s))


async def backfill() -> None:
    name_to_dex = await build_name_index()
    log.info(f"name index built: {len(name_to_dex)} entries across en/ja/ko")

    async with SessionLocal() as session:
        stmt = select(Card.id, Card.name).where(
            Card.national_pokedex_numbers.is_(None),
            Card.name.isnot(None),
        )
        rows = (await session.execute(stmt)).all()
        log.info(f"{len(rows)} cards missing dex_numbers")

        matched = 0
        unmatched = 0
        BATCH = 200
        pending: list[tuple[str, int]] = []
        for card_id, name in rows:
            dex = find_best_match(name, name_to_dex)
            if dex is None:
                unmatched += 1
                continue
            pending.append((card_id, dex))
            matched += 1
            if len(pending) >= BATCH:
                await _flush(session, pending)
                pending.clear()
                log.info(f"  ... matched={matched} unmatched={unmatched}")
        if pending:
            await _flush(session, pending)
        await session.commit()
        log.info(f"DONE: matched={matched} unmatched={unmatched}")


async def _flush(session, pending: list[tuple[str, int]]) -> None:
    for card_id, dex in pending:
        await session.execute(
            update(Card)
            .where(Card.id == card_id)
            .values(national_pokedex_numbers=[dex])
        )


if __name__ == "__main__":
    asyncio.run(backfill())
