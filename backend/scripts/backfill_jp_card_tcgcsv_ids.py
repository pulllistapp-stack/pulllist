"""Populate tcgplayer_product_id + tcgplayer_group_id on JP cards.

LO wants first-time prices on every JP card in the catalog so the
UI stops showing '$?' placeholders. TCGCSV's Pokemon Japan category
(85) carries prices for ~448 groups; our JP catalog has ~316 sets
with ~21k cards. Once each card row carries a tcgplayer_product_id
the daily sync (sync_tcgcsv_daily.py — patched to loop cat 3 + 85)
does the rest.

Algorithm per JP set:
  1. Resolve target TCGCSV group id via:
       - existing set_id ↔ group_id table (loaded from
         ingest_jp_sealed._TCGCSV_ALIASES + _GROUP_ID_OVERRIDES)
       - fallback: TCGCSV group abbreviation == our set_id
         (case-insensitive)
  2. Fetch the group's products, filter to cards
     (extendedData has 'Number' or 'HP' or 'Attack 1' etc.)
  3. Match each of our set's cards by CARD NUMBER against the
     TCGCSV product list. Our JP catalog stores JP names ('ストラ
     イク') while TCGCSV JP category stores English names
     ('Scyther') so name matching returns zero. Numbers are
     language-invariant and unique within a set, so they're the
     reliable join key. Parses TCGCSV's 'NNN/YYY' extendedData
     Number into an int for cross-comparison with our number_int.
  4. Save tcgplayer_product_id + tcgplayer_url on the card row.

Only fires for cards where tcgplayer_product_id IS NULL — never
overwrites an existing mapping.

Usage:
    python -m scripts.backfill_jp_card_tcgcsv_ids --dry-run
    python -m scripts.backfill_jp_card_tcgcsv_ids
    python -m scripts.backfill_jp_card_tcgcsv_ids --set SVHK
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import re
import sys
from collections import defaultdict
from pathlib import Path

import httpx
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal, init_db  # noqa: E402
from scripts.ingest_jp_sealed import (  # noqa: E402
    _TCGCSV_ALIASES,
    _GROUP_ID_OVERRIDES,
)


log = logging.getLogger("backfill_jp_card_tcgcsv_ids")


TCGCSV_BASE = "https://tcgcsv.com/tcgplayer/85"
UA = "PullList-Catalog/1.0 (+https://pulllist.org)"


# Any of these in TCGCSV extendedData marks a product as a card.
_CARD_ATTR_KEYS = {
    "Number", "HP", "CardType", "Attack 1", "Attack 2", "Retreat Cost",
    "Stage", "Weakness", "Resistance", "Rarity", "Flavor Text",
}


# TCGCSV's Number field looks like "003/068" or "005a/068" or just
# "SM-P 27". We only want the leading integer — that's what our
# number_int stores. Regex takes the first digit run in the string.
_LEADING_INT_RE = re.compile(r"(\d+)")


def _extract_number(raw: str | None) -> int | None:
    if not raw:
        return None
    m = _LEADING_INT_RE.search(raw)
    if not m:
        return None
    try:
        return int(m.group(1))
    except ValueError:
        return None


async def _fetch_json(client: httpx.AsyncClient, path: str) -> list[dict]:
    r = await client.get(f"{TCGCSV_BASE}/{path}", timeout=45)
    r.raise_for_status()
    payload = r.json()
    if isinstance(payload, dict):
        return payload.get("results") or []
    return payload or []


async def _load_group_index(client: httpx.AsyncClient) -> dict[str, int]:
    """Return {abbreviation.lower(): groupId} for all TCGCSV JP groups.
    Layered with hand-curated aliases (from ingest_jp_sealed) so our
    JP set ids that don't literally match a TCGCSV abbreviation still
    resolve."""
    groups = await _fetch_json(client, "groups")
    idx: dict[str, int] = {}
    for g in groups:
        abbr = (g.get("abbreviation") or "").strip().lower()
        if abbr and abbr not in idx:
            idx[abbr] = int(g["groupId"])
    # Layer aliases (tcgcsv_abbr → our_set_id): reverse-map so lookup
    # keyed on our set_id lower still resolves.
    for tcg_abbr, our_id in _TCGCSV_ALIASES.items():
        gid = idx.get(tcg_abbr)
        if gid is not None:
            idx[our_id.lower()] = gid
    return idx


def _resolve_group_id(
    set_id: str, group_index: dict[str, int]
) -> int | None:
    # 1. TCGCSV-group-id explicit overrides (Pt Arceus decks are
    # keyed on group_id in ingest_jp_sealed, not abbr, so we invert
    # that mapping here).
    for gid, mapped_set in _GROUP_ID_OVERRIDES.items():
        if mapped_set.lower() == set_id.lower():
            return gid
    # 2. Direct match on abbreviation (case-insensitive).
    return group_index.get(set_id.lower())


async def _fetch_group_cards(
    client: httpx.AsyncClient, group_id: int
) -> list[dict]:
    """Return only the card products from a TCGCSV group (drops sealed)."""
    products = await _fetch_json(client, f"{group_id}/products")
    cards: list[dict] = []
    for p in products:
        ext = p.get("extendedData") or []
        if any(e.get("name") in _CARD_ATTR_KEYS for e in ext):
            cards.append(p)
    return cards


async def run(only_set: str | None, dry_run: bool) -> None:
    await init_db()

    async with SessionLocal() as db:
        sql = (
            "SELECT id FROM sets WHERE language = 'ja'"
        )
        params: dict = {}
        if only_set:
            sql += " AND id = :s"
            params["s"] = only_set
        set_rows = (await db.execute(text(sql), params)).all()
    set_ids = [r.id for r in set_rows]
    log.info(f"JP sets to probe: {len(set_ids)}")

    stats = {
        "sets_seen": 0,
        "sets_no_group": 0,
        "sets_matched": 0,
        "cards_seen": 0,
        "cards_matched": 0,
        "cards_written": 0,
        "cards_already": 0,
    }

    async with httpx.AsyncClient(headers={"User-Agent": UA}) as client:
        group_index = await _load_group_index(client)
        log.info(f"TCGCSV JP groups indexed: {len(group_index)}")

        for set_id in set_ids:
            stats["sets_seen"] += 1
            gid = _resolve_group_id(set_id, group_index)
            if gid is None:
                stats["sets_no_group"] += 1
                continue
            stats["sets_matched"] += 1

            try:
                cards = await _fetch_group_cards(client, gid)
            except Exception as exc:
                log.warning(f"  ! {set_id} gid={gid} fetch failed: {exc}")
                continue

            # Build number_int → TCGCSV product info map. Numbers are
            # language-invariant and unique per printed set, which is
            # the only reliable join key when TCGCSV stores EN names
            # (Scyther) and our JP catalog stores JP names (ストラ
            # イク). First-seen wins if a group lists variants under
            # the same number — the daily sync's per-variant
            # tcgplayer_prices JSON captures the rest.
            tcg_by_num: dict[int, tuple[int, str]] = {}
            for p in cards:
                ext = {e.get("name"): e.get("value") for e in (p.get("extendedData") or [])}
                num = _extract_number(ext.get("Number"))
                pid = p.get("productId")
                if num is not None and pid is not None:
                    tcg_by_num.setdefault(num, (int(pid), p.get("name") or ""))

            async with SessionLocal() as db:
                rows = (await db.execute(
                    text(
                        "SELECT id, name, number_int, tcgplayer_product_id "
                        "FROM cards WHERE set_id = :s"
                    ),
                    {"s": set_id},
                )).all()

            local_stats = defaultdict(int)
            # Build a batch of updates first, then commit per-SET in
            # one transaction. Per-row commit on 15k rows blew past
            # the 45-min workflow timeout — per-set (30-80 rows each)
            # is ~200x faster and still gives fine-grained recovery
            # if a run gets cancelled midway.
            pending: list[tuple[str, int]] = []
            for r in rows:
                stats["cards_seen"] += 1
                if r.tcgplayer_product_id is not None:
                    stats["cards_already"] += 1
                    local_stats["already"] += 1
                    continue
                if r.number_int is None:
                    continue
                hit = tcg_by_num.get(r.number_int)
                if hit is None:
                    continue
                pid, _ = hit
                stats["cards_matched"] += 1
                local_stats["matched"] += 1
                pending.append((r.id, pid))

            if pending and not dry_run:
                async with SessionLocal() as db:
                    for cid, pid in pending:
                        w = await db.execute(
                            text(
                                "UPDATE cards SET "
                                "  tcgplayer_product_id = :pid, "
                                "  tcgplayer_url = :url "
                                "WHERE id = :id AND tcgplayer_product_id IS NULL"
                            ),
                            {
                                "pid": pid,
                                "url": f"https://www.tcgplayer.com/product/{pid}",
                                "id": cid,
                            },
                        )
                        if w.rowcount:
                            stats["cards_written"] += 1
                            local_stats["written"] += 1
                    await db.commit()

            log.info(
                f"  {set_id:12s} gid={gid:>6d}  "
                f"cards={len(rows):>4}  matched={local_stats['matched']:>4}  "
                f"written={local_stats['written']:>4}  "
                f"already={local_stats['already']:>4}"
            )

    log.info("=== JP tcg_pid backfill ===")
    for k, v in stats.items():
        log.info(f"  {k}: {v}")
    if dry_run:
        log.info("MODE: DRY-RUN — no writes")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--set", dest="only_set", help="Limit to one set id")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    asyncio.run(run(args.only_set, args.dry_run))


if __name__ == "__main__":
    main()
