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

# collectory.cc sits behind Cloudflare and 403s the default httpx UA
# from datacenter IPs (GitHub Actions runners), so we lean on a full
# browser header set to look like a Korean user's Chrome hitting the
# site's own SPA. Same headers also work locally, so no code branch.
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://collectory.cc/",
    "Origin": "https://collectory.cc",
}

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
    """Fetch every card in a collectory set. The `/cards?set_id=…`
    filter is silently broken on the API side (returns unfiltered
    global results — verified 2026-07-19), so we hit the nested
    `/sets/{id}/cards` endpoint instead which does honor the scope
    and returns the whole set in one payload (no pagination needed;
    largest set observed is 356 cards)."""
    d = await _fetch_json(client, f"/sets/{collectory_set_id}/cards")
    return d.get("cards", []) if isinstance(d, dict) else []


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
) -> tuple[str, str, float] | None:
    """Pick a KR set to attach this collectory set's cards under.
    Returns (our_ko_set_id, matched_name, score) or None.

    Score guides the winner-take-all pass in `_pick_best_matches`: a
    set_code_ja direct hit scores 1.0; fuzzy name matches use their
    SequenceMatcher ratio. Only ≥0.85 fuzzy hits are kept — the loose
    0.7 threshold produced too many collisions across localized
    reprints ("포켓몬 카드 151", "포켓몬 카드 151 (중판)", "151" all
    matching the same ko-SV2a row and dumping 3× the card rows)."""
    scj = (coll_set.get("set_code_ja") or "").strip()
    if scj and scj in ko_index:
        our_id, our_name = ko_index[scj]
        return (our_id, our_name, 1.0)

    coll_name = _norm_name(coll_set.get("name_ko"))
    if not coll_name:
        return None
    best: tuple[str, str] | None = None
    best_score = 0.0
    for _tcg_id, (our_id, our_name) in ko_index.items():
        ratio = SequenceMatcher(None, coll_name, _norm_name(our_name)).ratio()
        if ratio > best_score:
            best_score = ratio
            best = (our_id, our_name)
    if best_score >= 0.85 and best is not None:
        return (best[0], best[1], best_score)
    return None


def _pick_best_matches(
    coll_sets: list[dict], ko_index: dict[str, tuple[str, str]]
) -> dict[str, dict]:
    """Winner-take-all: for each of our ko-* set ids, pick exactly one
    collectory set (highest score; tie-break on card_count desc).
    Returns {our_ko_set_id: collectory_set_dict}. This is the fix for
    the mid-run PK collisions we saw when multiple collectory sets
    ('151', '포켓몬 카드 151', '포켓몬 카드 151 (중판)') all
    matched ko-SV2a and their cards fought for `ko-SV2a-001`."""
    # First pass: for each collectory set, compute its (target, score)
    all_matches: list[tuple[str, float, int, dict]] = []
    for cs in coll_sets:
        if (cs.get("card_count") or 0) == 0:
            continue
        m = _match_collectory_set(cs, ko_index)
        if m is None:
            continue
        our_id, _our_name, score = m
        all_matches.append((our_id, score, cs.get("card_count") or 0, cs))
    # Group by our_id, keep best (score desc, card_count desc)
    best_per: dict[str, tuple[float, int, dict]] = {}
    for our_id, score, cc, cs in all_matches:
        prev = best_per.get(our_id)
        if prev is None or (score, cc) > (prev[0], prev[1]):
            best_per[our_id] = (score, cc, cs)
    return {our_id: cs for our_id, (_s, _cc, cs) in best_per.items()}


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

    async with httpx.AsyncClient(headers=HEADERS) as client:
        # Index our existing KR sets
        async with SessionLocal() as db:
            ko_index = await _build_ko_set_index(db)
        log.info(f"KR sets in DB (available as attach targets): {len(ko_index)}")

        # Pull collectory set catalog
        coll_payload = await _fetch_json(client, "/sets")
        coll_sets = coll_payload.get("sets", coll_payload if isinstance(coll_payload, list) else [])
        log.info(f"collectory.cc sets: {len(coll_sets)}")
        stats["collectory_sets_seen"] = sum(
            1 for cs in coll_sets if (cs.get("card_count") or 0) > 0
        )

        # Winner-take-all: one collectory set per ko-* target. Prevents
        # duplicate-key crashes we saw when several collectory reprints
        # of the same physical expansion all matched the same ko-*
        # set and their cards competed for the same primary keys.
        best_matches = _pick_best_matches(coll_sets, ko_index)
        log.info(f"unique ko-* -> collectory matches: {len(best_matches)}")

        # Track which match came from set_code_ja (score=1.0) vs fuzzy
        for our_id, cs in best_matches.items():
            if (cs.get("set_code_ja") or "").strip() == _strip_tcgdex_prefix(our_id):
                stats["sets_matched_via_code"] += 1
            else:
                stats["sets_matched_via_name"] += 1
        stats["sets_unmatched"] = stats["collectory_sets_seen"] - (
            stats["sets_matched_via_code"] + stats["sets_matched_via_name"]
        )

        target_ko_ids: set[str] | None = {only_set} if only_set else None

        for our_id, cs in best_matches.items():
            if target_ko_ids and our_id not in target_ko_ids:
                continue

            _our_id_confirm, our_name = ko_index.get(our_id, (our_id, ""))
            matched_by = "code" if (cs.get("set_code_ja") or "").strip() == _strip_tcgdex_prefix(our_id) else "name"

            log.info(
                f"  match: collectory[{cs.get('set_code_ja') or (cs.get('name_ko') or '')[:20]}] -> "
                f"{our_id} '{our_name[:30]}' via {matched_by}"
            )

            # Fetch this collectory set's full card list via the
            # scoped endpoint (the /cards?set_id= filter is silently
            # broken — see _list_all_cards_for_set for context).
            coll_id = cs.get("id")
            try:
                cards = await _list_all_cards_for_set(client, coll_id)
            except Exception as e:
                log.warning(f"  ! fetch failed for {coll_id}: {e}")
                continue

            # In-session dedupe: collectory occasionally lists the
            # same card twice within a set (variant printings, promo
            # reprints that carry the same number/069). Silently
            # collapse to first-seen so the batch commit doesn't
            # explode on a duplicate PK.
            seen_card_ids: set[str] = set()
            local_added = local_updated = 0
            async with SessionLocal() as db:
                for c in cards:
                    stats["cards_seen"] += 1
                    if dry_run:
                        continue
                    stripped = _strip_tcgdex_prefix(our_id)
                    num_raw = str(c.get("card_number") or "").strip()
                    if not num_raw:
                        stats["cards_skipped"] += 1
                        continue
                    cid = f"ko-{stripped}-{num_raw}"
                    if cid in seen_card_ids:
                        stats["cards_skipped"] += 1
                        continue
                    seen_card_ids.add(cid)
                    result, _ = await _upsert_kr_card(db, c, our_id, cs)
                    stats[f"cards_{result}"] += 1
                    if result == "added":
                        local_added += 1
                    elif result == "updated":
                        local_updated += 1
                if not dry_run:
                    await db.commit()
            log.info(
                f"    -> {len(cards)} cards from collectory ({len(seen_card_ids)} unique); "
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
