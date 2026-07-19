"""Clean up ko-c-* rows that landed under the wrong locale.

Context
-------
`import_kr_from_collectory --include-new-sets` pulled every
unmatched collectory set into `language='ko'` (as `ko-c-<hash>`)
without checking that the underlying set was actually a Korean
release. Collectory's `/api/sets` mixes CN, US, JP, and scrydex-
sourced rows in with the KR ones, so ~63% of the 407 ko-c-* rows
we created belong somewhere else:

  KR      147   keep
  CN      128   move to zhcn-c-<hash> (language='zh-cn')
  US       99   delete (already in EN catalog via pokemontcg.io)
  JP       28   delete (already in JP catalog via TCGdex)
  SCRY      4   delete (scrydex is EN-sourced)
  UNKNOWN   1   report; leave alone unless --purge-unknown

Classification uses the CARD image CDN as the tell — the set's own
logo_url is unreliable (about half the sets store a random cover
card image or a scrydex logo even when the cards themselves are
KR-scanned). Voting on cards.image_small is stable across all
407 rows.

Scope guarantees
----------------
* Only touches sets with `id LIKE 'ko-c-%'` — the TCGdex-derived
  ko-{TCGDEX_ID} rows and everything under `language='en'` /
  `language='ja'` / `language='zh-cn'` is left untouched.
* Dry-run mode prints planned actions without touching the DB.
* Batches each set's card writes inside a per-set transaction so a
  fetch failure on one row doesn't unwind the rest.

Usage
-----
    python -m scripts.cleanup_ko_c_locale_mixup --dry-run
    python -m scripts.cleanup_ko_c_locale_mixup
"""
from __future__ import annotations

import argparse
import asyncio
import logging
from collections import Counter

from sqlalchemy import text

from app.database import SessionLocal, init_db


log = logging.getLogger("cleanup_ko_c_locale_mixup")


# Card-image CDN → region tag. Order doesn't matter (all patterns
# are prefix-matches, no overlap).
_REGION_PATTERNS: list[tuple[str, str]] = [
    ("KR",   "https://cdn.collectory.cc/cards/kr/"),
    ("CN",   "https://cdn.collectory.cc/cards/cn/"),
    ("US",   "https://cdn.collectory.cc/cards/us/"),
    ("JP",   "https://cdn.collectory.cc/cards/jp/"),
    ("SCRY", "https://images.scrydex.com/"),
    ("SCRY", "https://images.pokemontcg.io/"),
]


def _classify(image_small: str | None) -> str | None:
    if not image_small:
        return None
    for region, prefix in _REGION_PATTERNS:
        if image_small.startswith(prefix):
            return region
    return None


async def _majority_region(db, set_id: str) -> tuple[str | None, dict[str, int]]:
    """Return (winner, tally) — winner is the region with the most
    card images pointing at its CDN. None if the set has no cards or
    every card image is unclassified."""
    rows = (await db.execute(
        text("SELECT image_small FROM cards WHERE set_id = :s"),
        {"s": set_id},
    )).all()
    tally: Counter[str] = Counter()
    for (img,) in rows:
        r = _classify(img)
        if r is not None:
            tally[r] += 1
    if not tally:
        return None, {}
    return tally.most_common(1)[0][0], dict(tally)


async def _load_ko_c_sets(db) -> list[tuple[str, str]]:
    rows = (await db.execute(text(
        "SELECT id, name FROM sets WHERE language='ko' AND id LIKE 'ko-c-%'"
    ))).all()
    return [(r.id, r.name or "") for r in rows]


async def _move_to_cn(db, ko_id: str) -> str:
    """Rename ko-c-{hash} → zhcn-c-{hash}, move cards, flip language.
    Two writes: INSERT the new set row with copied metadata + UPDATE
    the cards' set_id + language + DELETE the old set. Wrapped in
    the caller's session so it commits atomically per set."""
    new_id = ko_id.replace("ko-c-", "zhcn-c-", 1)
    # Copy the row (Postgres INSERT ... SELECT is the atomic move).
    await db.execute(text("""
        INSERT INTO sets (
            id, name, series, printed_total, total, ptcgo_code,
            release_date, symbol_url, logo_url, language, name_local,
            name_en, name_ko, parent_set_id, set_subtype, set_type,
            created_at, updated_at
        )
        SELECT
            :new_id, name, series, printed_total, total, ptcgo_code,
            release_date, symbol_url, logo_url, 'zh-cn', name_local,
            name_en, name_ko, parent_set_id, set_subtype, set_type,
            created_at, NOW()
        FROM sets WHERE id = :old_id
        ON CONFLICT (id) DO NOTHING
    """), {"new_id": new_id, "old_id": ko_id})
    # Move cards (updates language too — the whole card row belongs
    # to a different catalog now).
    await db.execute(text(
        "UPDATE cards SET set_id = :new_id, language = 'zh-cn' "
        "WHERE set_id = :old_id"
    ), {"new_id": new_id, "old_id": ko_id})
    # Delete the old set row.
    await db.execute(text("DELETE FROM sets WHERE id = :old_id"), {"old_id": ko_id})
    return new_id


async def _delete_set(db, ko_id: str) -> None:
    """Delete a ko-c-* set and its cards outright. Guarded by the
    caller to ensure `ko_id` starts with the ko-c- prefix — will not
    fire on any other language's rows."""
    if not ko_id.startswith("ko-c-"):
        raise ValueError(f"refusing to delete non-ko-c- id: {ko_id!r}")
    await db.execute(text("DELETE FROM cards WHERE set_id = :s"), {"s": ko_id})
    await db.execute(text("DELETE FROM sets WHERE id = :s"), {"s": ko_id})


async def run(dry_run: bool) -> None:
    await init_db()

    stats = Counter()
    classified: list[tuple[str, str, str | None, dict[str, int]]] = []  # (id, name, region, tally)

    async with SessionLocal() as db:
        sets = await _load_ko_c_sets(db)
        log.info(f"ko-c-* sets to classify: {len(sets)}")
        for ko_id, name in sets:
            region, tally = await _majority_region(db, ko_id)
            classified.append((ko_id, name, region, tally))
            stats[region or "UNKNOWN"] += 1

    log.info("=== classification tally ===")
    for k, v in sorted(stats.items()):
        log.info(f"  {k}: {v}")

    if dry_run:
        log.info("DRY-RUN — no writes. First 5 CN moves:")
        cn = [c for c in classified if c[2] == "CN"][:5]
        for cid, cname, _r, tally in cn:
            log.info(f"  MOVE {cid} -> zhcn-c-{cid[5:]}  '{cname[:30]}'  {tally}")
        log.info("First 5 US deletes:")
        us = [c for c in classified if c[2] == "US"][:5]
        for cid, cname, _r, tally in us:
            log.info(f"  DELETE {cid}  '{cname[:30]}'  {tally}")
        log.info("First 5 JP deletes:")
        jp = [c for c in classified if c[2] == "JP"][:5]
        for cid, cname, _r, tally in jp:
            log.info(f"  DELETE {cid}  '{cname[:30]}'  {tally}")
        return

    # Execute — one transaction per set so a stumble on one row
    # doesn't unravel the whole cleanup pass.
    n_moved = n_deleted = 0
    for ko_id, name, region, _tally in classified:
        if region is None or region == "KR":
            continue  # keep in place
        try:
            async with SessionLocal() as db:
                if region == "CN":
                    new_id = await _move_to_cn(db, ko_id)
                    n_moved += 1
                    log.info(f"  moved  {ko_id} -> {new_id}  '{name[:30]}'")
                elif region in ("US", "JP", "SCRY"):
                    await _delete_set(db, ko_id)
                    n_deleted += 1
                    log.info(f"  deleted {ko_id}  ({region})  '{name[:30]}'")
                await db.commit()
        except Exception as e:
            log.warning(f"  ! {ko_id} failed: {e}")

    log.info(f"=== done: moved={n_moved}  deleted={n_deleted} ===")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
    )
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    asyncio.run(run(args.dry_run))


if __name__ == "__main__":
    main()
