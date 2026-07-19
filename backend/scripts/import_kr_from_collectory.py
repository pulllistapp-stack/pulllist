"""Import KR card details from collectory.cc into existing KR sets.

Context
-------
`import_jp_catalog --lang ko` (TCGdex) imports 91 KR sets with clean
JP-shared ids (`ko-SV3`, `ko-CS3a`, ...) but TCGdex's KR endpoint
returns *empty* card arrays for most of them — the set metadata is
there, the cards aren't. As a result the KR catalog surfaces set
tiles that open to blank card pages.

collectory.cc (a Korean fan-run archive) has native KR card data
for essentially every KR-printed set: JP-shared code (`set_code_ja`),
Korean name (`name_ko`), Korean-scanned CDN images (`cdn_image_url`),
card number, rarity, and KRW pricing. This script bridges the two:
match each collectory set to one of our `ko-{tcgdex_id}` rows via
its `set_code_ja` (or fall back to fuzzy name match), then upsert
that set's cards under the same `ko-{tcgdex_id}` FK so the existing
TCGdex-side URLs keep working with real card content.

Idempotent. Existing cards get their fields refreshed; new cards get
added. Never touches JP / EN / CN rows.

Usage
-----
    python -m scripts.import_kr_from_collectory              # full sync
    python -m scripts.import_kr_from_collectory --dry-run    # probe
    python -m scripts.import_kr_from_collectory --set ko-SV3 # one set
"""
from __future__ import annotations

import argparse
import asyncio
import logging
from datetime import date, datetime
from difflib import SequenceMatcher
from typing import Any

import httpx
from sqlalchemy import select, text

from app.database import SessionLocal, init_db
from app.models import Card, Set


COLLECTORY_BASE = "https://collectory.cc/api"
UA = "PullList-Catalog/1.0 (+https://pulllist.org)"

log = logging.getLogger("import_kr_from_collectory")


# TCGdex uses JP set ids as its canonical set code for KR too, so our
# ko-{id} rows use ids like ko-SV3, ko-SM1M. Collectory's `set_code_ja`
# is that exact same code. Direct match resolves ~67 of 500 collectory
# sets (only the newer ones have set_code_ja filled in), so we fall
# back to fuzzy name matching for the rest.
def _strip_tcgdex_prefix(set_id: str) -> str:
    """`ko-SV3` -> `SV3`. Passthrough for anything without a prefix."""
    for p in ("ko-", "zhcn-", "zhtw-"):
        if set_id.startswith(p):
            return set_id[len(p):]
    return set_id


def _norm_name(s: str | None) -> str:
    """Lowercase + strip whitespace/punct for fuzzy name compare."""
    if not s:
        return ""
    return "".join(c for c in s.lower() if c.isalnum())


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


def _rarity_norm(raw: str | None) -> str | None:
    """collectory rarity vocab is short codes (C/U/R/RR/SR/PROMO/...).
    Map to our EN-canonical labels; unknown codes pass through so we
    keep the raw signal instead of dropping it. Add cases here as we
    see new codes surface in the wild."""
    if not raw:
        return None
    m = {
        "C": "Common",
        "U": "Uncommon",
        "R": "Rare",
        "RR": "Double Rare",
        "RRR": "Triple Rare",
        "SR": "Special Illustration Rare",
        "SAR": "Special Illustration Rare",
        "AR": "Illustration Rare",
        "UR": "Hyper Rare",
        "HR": "Hyper Rare",
        "CHR": "Character Rare",
        "CSR": "Character Super Rare",
        "PROMO": "Promo",
        "N": "Basic Energy",
    }
    return m.get(raw.upper(), raw)


async def _fetch_json(client: httpx.AsyncClient, path: str, params: dict | None = None) -> Any:
    r = await client.get(f"{COLLECTORY_BASE}{path}", params=params, timeout=30)
    r.raise_for_status()
    return r.json()


async def _list_all_cards_for_set(
    client: httpx.AsyncClient, collectory_set_id: str
) -> list[dict]:
    """collectory `/api/cards?set_id=...` returns paginated results with
    a soft page size cap; loop until we've seen every card in the set."""
    all_cards: list[dict] = []
    page = 1
    while True:
        d = await _fetch_json(
            client,
            "/cards",
            params={"set_id": collectory_set_id, "page": page, "limit": 200},
        )
        cards = d.get("cards", [])
        if not cards:
            break
        all_cards.extend(cards)
        # Break when we've collected the set's full count. `total` in
        # the response is the global card count (not the filtered one),
        # so we can't rely on it. Instead stop when a page returns
        # fewer than the requested limit.
        if len(cards) < 200:
            break
        page += 1
        if page > 50:  # hard safety cap
            break
    return all_cards


async def _build_ko_set_index(db) -> dict[str, tuple[str, str]]:
    """Return {tcgdex_id_no_prefix: (our_ko_set_id, our_name)} for
    every `language='ko'` set already in the DB. Keyed on the stripped
    id so a collectory set with `set_code_ja='SV3'` maps directly."""
    rows = (await db.execute(
        text("SELECT id, name FROM sets WHERE language = 'ko'")
    )).all()
    return {
        _strip_tcgdex_prefix(r.id): (r.id, r.name or "")
        for r in rows
    }


def _match_collectory_set(
    coll_set: dict, ko_index: dict[str, tuple[str, str]]
) -> tuple[str, str] | None:
    """Pick a KR set to attach this collectory set's cards under.
    Priority: (1) set_code_ja direct match, (2) fuzzy name match on
    name_ko above 0.7 similarity. Returns (our_ko_set_id, matched_name)
    or None if no confident match."""
    scj = (coll_set.get("set_code_ja") or "").strip()
    if scj and scj in ko_index:
        return ko_index[scj]
    # Fuzzy name match — collectory's name_ko vs our ko-set name.
    coll_name = _norm_name(coll_set.get("name_ko"))
    if not coll_name:
        return None
    best: tuple[str, str] | None = None
    best_score = 0.0
    for tcg_id, (our_id, our_name) in ko_index.items():
        ratio = SequenceMatcher(None, coll_name, _norm_name(our_name)).ratio()
        if ratio > best_score:
            best_score = ratio
            best = (our_id, our_name)
    if best_score >= 0.7:
        return best
    return None


async def _upsert_kr_card(
    db, coll_card: dict, our_set_id: str, coll_set: dict
) -> tuple[str, str]:
    """Write / refresh one KR card row. Card id is
    `ko-{our_set_stripped}-{card_number}` so we stay consistent with
    the TCGdex-side prefix scheme and don't collide with JP cards.
    Returns ('added' | 'updated' | 'unchanged', card_id)."""
    stripped = _strip_tcgdex_prefix(our_set_id)
    num_raw = str(coll_card.get("card_number") or "").strip()
    if not num_raw:
        return ("skipped", "")
    card_id = f"ko-{stripped}-{num_raw}"

    existing = await db.get(Card, card_id)
    if existing is not None and existing.language != "ko":
        log.warning(
            f"  ! skip card {card_id}: existing row language={existing.language!r}"
        )
        return ("skipped", card_id)

    # Prefer collectory's native KR scan (cdn.collectory.cc). Fall
    # back to whatever image_url they carry (often a JP TCGdex asset)
    # so the tile isn't blank.
    img = (
        coll_card.get("cdn_image_url")
        or coll_card.get("image_url")
        or None
    )
    fields = dict(
        name=coll_card.get("name_ko") or coll_card.get("name") or "",
        name_local=coll_card.get("name_ko"),
        supertype=(coll_card.get("card_type") or "").title() or None,
        rarity=_rarity_norm(coll_card.get("rarity")),
        number=num_raw,
        number_int=_coerce_int(num_raw.split("-")[0]) if num_raw else None,
        artist=coll_card.get("illustrator"),
        image_small=img,
        image_large=img,
        set_id=our_set_id,
        language="ko",
    )

    if existing is None:
        db.add(Card(id=card_id, **fields))
        return ("added", card_id)

    changed = False
    for k, v in fields.items():
        if getattr(existing, k) != v:
            setattr(existing, k, v)
            changed = True
    return (("updated" if changed else "unchanged"), card_id)


async def run(only_set: str | None, dry_run: bool) -> None:
    await init_db()

    stats = {
        "collectory_sets_seen": 0,
        "sets_matched_via_code": 0,
        "sets_matched_via_name": 0,
        "sets_unmatched": 0,
        "cards_seen": 0,
        "cards_added": 0,
        "cards_updated": 0,
        "cards_unchanged": 0,
        "cards_skipped": 0,
    }

    async with httpx.AsyncClient(headers={"User-Agent": UA}) as client:
        # Index our existing KR sets
        async with SessionLocal() as db:
            ko_index = await _build_ko_set_index(db)
        log.info(f"KR sets in DB (available as attach targets): {len(ko_index)}")

        # Pull collectory set catalog
        coll_payload = await _fetch_json(client, "/sets")
        coll_sets = coll_payload.get("sets", coll_payload if isinstance(coll_payload, list) else [])
        log.info(f"collectory.cc sets: {len(coll_sets)}")

        # Filter to sets that actually have cards + optionally an
        # only-set filter. If the only-set filter is one of ours
        # (`ko-SV3`), find its collectory counterpart(s); if it's
        # a raw collectory id, use that.
        target_ko_ids: set[str] | None = None
        if only_set:
            target_ko_ids = {only_set}

        for cs in coll_sets:
            if (cs.get("card_count") or 0) == 0:
                continue
            stats["collectory_sets_seen"] += 1
            match = _match_collectory_set(cs, ko_index)
            if match is None:
                stats["sets_unmatched"] += 1
                continue
            our_id, our_name = match

            if target_ko_ids and our_id not in target_ko_ids:
                continue

            matched_by = "code" if cs.get("set_code_ja") in ko_index else "name"
            if matched_by == "code":
                stats["sets_matched_via_code"] += 1
            else:
                stats["sets_matched_via_name"] += 1

            log.info(
                f"  match: collectory[{cs.get('set_code_ja') or cs.get('name_ko','')[:20]}] -> "
                f"{our_id} '{our_name[:30]}' via {matched_by}"
            )

            # Fetch this collectory set's full card list
            coll_id = cs.get("id")
            try:
                cards = await _list_all_cards_for_set(client, coll_id)
            except Exception as e:
                log.warning(f"  ! fetch failed for {coll_id}: {e}")
                continue

            local_added = local_updated = 0
            async with SessionLocal() as db:
                for c in cards:
                    stats["cards_seen"] += 1
                    if dry_run:
                        continue
                    result, _ = await _upsert_kr_card(db, c, our_id, cs)
                    stats[f"cards_{result}"] += 1
                    if result == "added":
                        local_added += 1
                    elif result == "updated":
                        local_updated += 1
                if not dry_run:
                    await db.commit()
            log.info(
                f"    -> {len(cards)} cards from collectory; "
                f"added={local_added} updated={local_updated}"
            )

    log.info("=== summary ===")
    for k, v in stats.items():
        log.info(f"  {k}: {v}")
    if dry_run:
        log.info("MODE: DRY-RUN — no writes")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--set", dest="only_set", help="Limit to one of our ko-* set ids")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
    )
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    asyncio.run(run(args.only_set, args.dry_run))


if __name__ == "__main__":
    main()
