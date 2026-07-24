"""Backfill the ko-p-* promo sets with rich data from collectory.cc.

Companion to `import_kr_promos_namuwiki.py`. Namu gave us the text
catalog (names + numbers) but zero card images and no set logos —
collectory.cc's Korean fan-run archive carries scanned cardart + KR
names + logo for the 4 promo eras it covers:

  ko-p-xy   ← XY-P                   (216 cards)
  ko-p-sm   ← SM Black Star Promos   (251 cards)
  ko-p-ss   ← SWSH Black Star Promos (305 cards)
  ko-p-sv   ← SV-P                   (378 cards)

Collectory uses a different card-number convention than namu (e.g.
`XY01` vs `001/XY-P`) so cards in these 4 sets can't be merged into
the namu-imported rows by id. Instead we replace: delete the
namu-imported cards under the 4 target sets, then insert the fuller,
better-arted collectory dataset. Users searching by name still find
what they need; the physical printing is unchanged.

Card ids sanitize `/` → `_` (matches the 2026-07-20 slash-rename that
fixed Next.js routing). Card language is 'ko'. Rarity defaults to
"Promo" if collectory has no rarity signal on the row.

The remaining 3 eras (ko-p-base, ko-p-bw, ko-p-mega) stay on namu
data — collectory doesn't group those as promos.

Usage
-----
    python -m scripts.import_kr_promos_collectory --dry-run
    python -m scripts.import_kr_promos_collectory
    python -m scripts.import_kr_promos_collectory --era sv
    python -m scripts.import_kr_promos_collectory --skip-delete   # additive
"""
from __future__ import annotations

import argparse
import asyncio
import io
import logging
import sys
from pathlib import Path

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx  # noqa: E402
from sqlalchemy import select, text  # noqa: E402

from app.database import SessionLocal, init_db  # noqa: E402
from app.models import Card, Set  # noqa: E402


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("import_kr_promos_collectory")


COLLECTORY_BASE = "https://collectory.cc/api"

# Same header set as import_kr_from_collectory.py. Collectory sits
# behind Cloudflare and 403s bare httpx UAs on datacenter IPs.
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


# Hand-verified against `/api/sets` — verified 2026-07-22.
# One entry per era we can source from collectory; base / bw / mega
# have no promo-grouped counterpart there and stay on namu data.
ERA_TO_UUID: dict[str, str] = {
    "xy": "bc2389e4-47c2-4150-a711-47574472d6e1",  # XY-P (216)
    "sm": "523eb016-c84e-4c52-8aea-3a5f0a22d18f",  # SM Black Star Promos (251)
    "ss": "4a2071be-6aaf-4bb8-98b9-8c61eb24d3fb",  # SWSH Black Star Promos (305)
    "sv": "305842f8-b171-47cd-a03c-e8edfc15a771",  # SV-P (378)
}


# Rarity map lifted from import_kr_from_collectory.py — same collectory
# vocab, same canonical EN labels we use elsewhere.
_RARITY_MAP = {
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


def _rarity_norm(raw: str | None) -> str:
    if not raw:
        return "Promo"
    return _RARITY_MAP.get(raw.upper(), raw)


def _sanitize_number(raw: str) -> str:
    """Card ids can't contain '/' — Next.js `/cards/[cardId]` routing
    parses slashes as path separators. Match the 2026-07-20 rename that
    already normalised the 29k collectory-imported KR/CN rows to `_`."""
    return raw.replace("/", "_").strip()


def _coerce_int(value) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _number_int_from(raw: str) -> int | None:
    """Best-effort integer parse: `001/XY-P` → 1, `XY01` → 1, `SWSH010`
    → 10. Walk the string and grab the first run of digits — that
    matches how the trending / sort-by-number queries expect data."""
    buf = []
    for ch in raw:
        if ch.isdigit():
            buf.append(ch)
        elif buf:
            break
    return int("".join(buf)) if buf else None


async def _fetch_json(client: httpx.AsyncClient, path: str) -> dict:
    r = await client.get(f"{COLLECTORY_BASE}{path}", timeout=30)
    r.raise_for_status()
    return r.json()


async def _fetch_sets_index(client) -> dict[str, dict]:
    """Grab the whole /sets response and index by uuid. Collectory's
    per-set endpoint (`/sets/{uuid}`) returns 405 Method Not Allowed
    — only the list and the `/sets/{uuid}/cards` nested route work."""
    payload = await _fetch_json(client, "/sets")
    sets = payload.get("sets", payload if isinstance(payload, list) else [])
    return {cs.get("id"): cs for cs in sets if cs.get("id")}


async def _fetch_cards(client, uuid: str) -> list[dict]:
    """`/sets/{uuid}/cards` returns the full list; no pagination.
    `/cards?set_id=…` is broken on the API side (returns unfiltered
    global results — see import_kr_from_collectory.py for the note)."""
    d = await _fetch_json(client, f"/sets/{uuid}/cards")
    return d.get("cards", []) if isinstance(d, dict) else []


async def _replace_era(
    db, era: str, coll_set: dict, coll_cards: list[dict],
    skip_delete: bool,
) -> tuple[int, int, int]:
    """Wipe the target set's existing cards (namu-imported, no images)
    and insert the collectory dataset. Also refreshes the set's logo
    from collectory's image_url. Returns (deleted, inserted, skipped)."""
    target_set_id = f"ko-p-{era}"

    # 1) Refresh set logo + name_ko from collectory metadata.
    row = await db.get(Set, target_set_id)
    if row is None:
        log.warning("  target set %s not present in DB — skip", target_set_id)
        return (0, 0, 0)
    if coll_set.get("image_url"):
        row.logo_url = coll_set["image_url"]
    if coll_set.get("name_ko"):
        # Keep our "포켓몬 카드 게임 프로모 (…)" prefix as `name`,
        # but overlay collectory's native title on name_local so users
        # who prefer collectory's naming see it there.
        row.name_local = coll_set["name_ko"]
    # Refresh the total-card counts so /sets/[id] header and Master/
    # Full-set split reflect collectory's larger catalog rather than
    # the stale namu figure this row was originally seeded with.
    row.total = len(coll_cards)
    row.printed_total = len(coll_cards)

    # 2) Bulk-delete existing cards under this set (namu-imported).
    #    Guarded by --skip-delete so a manual rerun can layer in
    #    without wiping.
    deleted = 0
    if not skip_delete:
        del_stmt = text(
            "DELETE FROM cards WHERE set_id = :sid AND language = 'ko'"
        )
        res = await db.execute(del_stmt, {"sid": target_set_id})
        deleted = res.rowcount or 0

    # 3) Insert collectory rows.
    inserted = 0
    skipped = 0
    seen_ids: set[str] = set()
    for c in coll_cards:
        num_raw = str(c.get("card_number") or "").strip()
        if not num_raw:
            skipped += 1
            continue
        num_slug = _sanitize_number(num_raw)
        card_id = f"{target_set_id}-{num_slug}"
        if card_id in seen_ids:
            skipped += 1
            continue
        seen_ids.add(card_id)

        img = (c.get("cdn_image_url") or c.get("image_url") or None)
        name_ko = c.get("name_ko") or c.get("name") or ""
        if not name_ko:
            skipped += 1
            continue

        # If we did NOT run the wipe step, an existing row with this
        # id might already sit there. UPSERT semantics: check + update.
        existing = await db.get(Card, card_id)
        if existing is not None:
            existing.name = name_ko
            existing.name_local = name_ko
            existing.number = num_raw
            existing.number_int = _number_int_from(num_raw)
            existing.image_small = img
            existing.image_large = img
            existing.rarity = _rarity_norm(c.get("rarity"))
            existing.artist = c.get("illustrator")
            existing.set_id = target_set_id
            existing.language = "ko"
        else:
            db.add(Card(
                id=card_id,
                name=name_ko,
                name_local=name_ko,
                number=num_raw,
                number_int=_number_int_from(num_raw),
                image_small=img,
                image_large=img,
                rarity=_rarity_norm(c.get("rarity")),
                artist=c.get("illustrator"),
                set_id=target_set_id,
                language="ko",
            ))
        inserted += 1

    return (deleted, inserted, skipped)


async def run(era_filter: str | None, dry_run: bool, skip_delete: bool) -> None:
    await init_db()
    total = {"deleted": 0, "inserted": 0, "skipped": 0}
    async with httpx.AsyncClient(headers=HEADERS) as client:
        try:
            sets_index = await _fetch_sets_index(client)
            log.info("indexed %d collectory sets", len(sets_index))
        except httpx.HTTPError as e:
            log.error("failed to fetch /sets index: %s", e)
            return
        for era, uuid in ERA_TO_UUID.items():
            if era_filter and era != era_filter:
                continue
            log.info("=== era %s (collectory %s) ===", era, uuid[:8])
            coll_set = sets_index.get(uuid)
            if coll_set is None:
                log.warning("  uuid %s not present in /sets response — skip", uuid)
                continue
            try:
                coll_cards = await _fetch_cards(client, uuid)
            except httpx.HTTPError as e:
                log.warning("  fetch failed: %s", e)
                continue
            log.info(
                "  collectory: %s (%d cards, logo=%s)",
                coll_set.get("name_ko") or coll_set.get("name_en") or "—",
                len(coll_cards),
                "yes" if coll_set.get("image_url") else "no",
            )

            async with SessionLocal() as db:
                deleted, inserted, skipped = await _replace_era(
                    db, era, coll_set, coll_cards, skip_delete,
                )
                if dry_run:
                    log.info("  DRY-RUN — rolling back "
                             "(would delete=%d, insert=%d, skip=%d)",
                             deleted, inserted, skipped)
                    await db.rollback()
                else:
                    await db.commit()
                    log.info("  LIVE — committed "
                             "(deleted=%d, inserted=%d, skipped=%d)",
                             deleted, inserted, skipped)
                total["deleted"] += deleted
                total["inserted"] += inserted
                total["skipped"] += skipped

    log.info("=== summary ===")
    for k, v in total.items():
        log.info("  %-10s %d", k, v)
    if dry_run:
        log.info("MODE: DRY-RUN — no writes")
    else:
        log.info("MODE: LIVE — committed")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dry-run", action="store_true",
                   help="Rollback each era's txn instead of committing.")
    p.add_argument("--era", choices=list(ERA_TO_UUID.keys()),
                   help="Limit to one era (xy|sm|ss|sv).")
    p.add_argument("--skip-delete", action="store_true",
                   help="Don't wipe existing cards under the target sets — "
                        "additive upsert only. Use for reruns.")
    args = p.parse_args()
    asyncio.run(run(args.era, args.dry_run, args.skip_delete))


if __name__ == "__main__":
    main()
