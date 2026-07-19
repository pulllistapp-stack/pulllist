"""Sort out KR set classification: dedupe, series naming, set_type.

Diagnosis after collectory + tcgdex + --include-new-sets landed:

  A. 14 empty CS* stubs — all named 트리플렛비트, all zero cards,
     TCGdex-metadata artifacts (real Triplet Beat = ko-SV1a which
     already carries 102 cards). Safe to delete.

  B. 9 dup pairs — TCGdex-side ko-{SM/S/sn}* plus a collectory
     ko-c-<hash> for the same physical set (풀메탈월, 챔피언로드,
     더블블레이즈, 얼터제네시스, 알로라의 달빛/햇빛, 플라스마 스파크,
     창공의 카리스마, GG엔드). Merge cards from ko-c-* into the
     canonical ko-SM* row (ids are our stable URL slug and match
     the JP catalog), then drop the ko-c-* row. When both rows
     hold cards with the same card_number, the ko-c-* copy is
     redundant — the collectory pass wrote a second row with the
     same {ko, name, image} content; skip those on move so no PK
     collision.

  C. Series field is inconsistent — same series shows up as either
     the JP-catalog English label ('Sword & Shield') or the KR
     TCGdex label ('검과 방패') depending on which import wrote the
     row last. Canonicalize to 'KR (English)' — verified against
     LO on 2026-07-19.

  D. set_type is NULL on all 243 KR sets, so the browser doesn't
     group starter decks / promos into their own DECK section like
     JP does. Apply the same name-pattern classifier the JP-side
     `classify_jp_set_types.py` uses, translated to the Korean
     names KR TCGdex ships ('스타터 덱', '덱 빌드 BOX', '프리미엄
     트레이너 박스', '25주년', 'BOX', 'V 스타트 덱' etc.).

Idempotent — running twice does nothing on top of a clean run.
Never touches en/ja/zh-* rows.

Usage:
    python -m scripts.cleanup_kr_classification --dry-run
    python -m scripts.cleanup_kr_classification
"""
from __future__ import annotations

import argparse
import asyncio
import logging
from collections import defaultdict

from sqlalchemy import text

from app.database import SessionLocal, init_db


log = logging.getLogger("cleanup_kr_classification")


# ─── C. Series canonicalization ──────────────────────────────────
# Map anything TCGdex/collectory could write for a given series
# down to the single canonical 'Korean (English)' label that KR
# users see in the series chip bar and set page. Left = raw value
# we've observed in the DB, right = canonical form.
_SERIES_MAP: dict[str, str] = {
    # Sword & Shield era
    "Sword & Shield": "검과 방패 (Sword & Shield)",
    "검과 방패":         "검과 방패 (Sword & Shield)",
    "소드&실드":          "검과 방패 (Sword & Shield)",
    # Sun & Moon era
    "Sun & Moon": "썬&문 (Sun & Moon)",
    "썬&문":       "썬&문 (Sun & Moon)",
    # Scarlet & Violet era
    "Scarlet & Violet": "스칼렛・바이올렛 (Scarlet & Violet)",
    "스칼렛・바이올렛":       "스칼렛・바이올렛 (Scarlet & Violet)",
    "scarlet-violet":   "스칼렛・바이올렛 (Scarlet & Violet)",
    # Mega Evolution (new 2026 era)
    "Mega Evolution": "메가에볼루션 (Mega Evolution)",
    "메가에볼루션":       "메가에볼루션 (Mega Evolution)",
    "MEGA":            "메가에볼루션 (Mega Evolution)",
    # XY / BW leave as-is — they're already single-form
    "XY": "XY",
    "Black & White": "블랙&화이트 (Black & White)",
    "블랙&화이트":         "블랙&화이트 (Black & White)",
    "BW": "블랙&화이트 (Black & White)",
    "Miscellaneous": "기타 (Misc)",
    "Other":        "기타 (Misc)",
    "OTHER":        "기타 (Misc)",
}


# ─── D. set_type classifier ──────────────────────────────────────
# Copies JP classifier's philosophy: DECK for starter decks / build
# boxes / trainer boxes / half decks, PROMO_* for promo sets, MAIN
# for the rest. Match on the Korean name string.
def _classify_set_type(name: str) -> str:
    n = name.lower()
    # DECK indicators — starter decks, build boxes, trainer boxes,
    # half decks, deck kits.
    _DECK_HINTS = (
        "스타트 덱", "스타터 덱", "스타터 세트", "스타트덱", "스타터",
        "덱 빌드 box", "덱빌드box", "빌드 box", "빌드box", "박스", "box",
        "프리미엄 트레이너", "트레이너 박스", "트레이너박스",
        "하프 덱", "하프덱", "배틀 강화", "배틀 이론", "배틀 파트너",
        "덱 kit", "덱키트", "덱 키트", "덱 세트", "덱세트",
        "챔피언 페스티벌", "챔피언스 페스티벌",
        "starter", "premium trainer", "battle deck",
    )
    if any(h in n for h in _DECK_HINTS):
        return "DECK"
    # 25th anniversary + special commemorative sets — MAIN for now
    # (they behave more like expansion packs than promos).
    return "MAIN"


# ─── A + B: dedupe surgery ──────────────────────────────────────
async def _list_empty_cs(db) -> list[str]:
    r = await db.execute(text(
        "SELECT id FROM sets s WHERE language='ko' AND id LIKE 'ko-CS%' "
        "AND (SELECT COUNT(*) FROM cards WHERE set_id=s.id) = 0"
    ))
    return [row.id for row in r.all()]


async def _list_dup_pairs(db) -> list[tuple[str, str, str]]:
    """Return [(name, canonical_tcgdex_id, ko_c_id)] pairs — cases
    where the same name appears on a TCGdex-derived ko-SM*/sn*/S*
    row AND a collectory ko-c-<hash> row. Skips the 트리플렛비트
    mega-cluster (handled by the empty-CS purge)."""
    r = await db.execute(text("""
        WITH grouped AS (
          SELECT name, array_agg(id ORDER BY id) as ids, COUNT(*) as n
          FROM sets WHERE language='ko' GROUP BY name
        )
        SELECT name, ids FROM grouped
        WHERE n = 2 AND name <> '트리플렛비트'
    """))
    pairs: list[tuple[str, str, str]] = []
    for row in r.all():
        ids = row.ids
        canon = [i for i in ids if not i.startswith("ko-c-")]
        cc    = [i for i in ids if i.startswith("ko-c-")]
        if len(canon) == 1 and len(cc) == 1:
            pairs.append((row.name, canon[0], cc[0]))
    return pairs


async def _merge_pair(db, name: str, canon_id: str, cc_id: str) -> tuple[int, int]:
    """Move cards from cc_id to canon_id. Return (moved, skipped_dup).
    Cards whose (canon_id, number) already exists are skipped — the
    collectory row is a redundant copy of the same physical card."""
    # Existing card numbers on the canonical side
    existing_numbers = {
        r.number for r in (await db.execute(
            text("SELECT number FROM cards WHERE set_id=:s"),
            {"s": canon_id},
        )).all()
    }
    # Candidates from the ko-c-* side
    ccs = (await db.execute(
        text("SELECT id, number FROM cards WHERE set_id=:s"),
        {"s": cc_id},
    )).all()
    moved = skipped = 0
    for row in ccs:
        if row.number in existing_numbers:
            # Duplicate content — delete the ko-c-* card row so the
            # empty set drop below succeeds.
            await db.execute(text("DELETE FROM cards WHERE id=:i"), {"i": row.id})
            skipped += 1
            continue
        # Reassign both set_id and the card's own storage id so the
        # id still reflects the set. new_id = canon_id + '-' + num
        stripped = canon_id[len("ko-"):]
        new_card_id = f"ko-{stripped}-{row.number}"
        # If somehow that id already exists (edge case: different
        # ko-c-* row with same {name, number}), skip.
        exists = (await db.execute(
            text("SELECT 1 FROM cards WHERE id=:i"), {"i": new_card_id},
        )).first()
        if exists:
            await db.execute(text("DELETE FROM cards WHERE id=:i"), {"i": row.id})
            skipped += 1
            continue
        await db.execute(text(
            "UPDATE cards SET id=:new, set_id=:s WHERE id=:old"
        ), {"new": new_card_id, "s": canon_id, "old": row.id})
        moved += 1
    return moved, skipped


async def run(dry_run: bool) -> None:
    await init_db()

    stats = defaultdict(int)

    # ── A: empty CS* stubs ──────────────────────────────────────
    async with SessionLocal() as db:
        empties = await _list_empty_cs(db)
    log.info(f"A: empty ko-CS* stubs to delete: {len(empties)}")
    if not dry_run:
        async with SessionLocal() as db:
            for sid in empties:
                if not sid.startswith("ko-CS"):
                    continue
                await db.execute(text("DELETE FROM sets WHERE id=:s"), {"s": sid})
                stats["A_stubs_deleted"] += 1
            await db.commit()

    # ── B: dup-pair merges ──────────────────────────────────────
    async with SessionLocal() as db:
        pairs = await _list_dup_pairs(db)
    log.info(f"B: dup pairs to merge: {len(pairs)}")
    for name, canon_id, cc_id in pairs:
        log.info(f"  pair '{name[:25]:25s}' canon={canon_id}  cc={cc_id}")
        if dry_run:
            continue
        async with SessionLocal() as db:
            moved, skipped = await _merge_pair(db, name, canon_id, cc_id)
            # Delete the now-empty ko-c-* set row.
            if cc_id.startswith("ko-c-"):
                await db.execute(text("DELETE FROM sets WHERE id=:s"), {"s": cc_id})
            await db.commit()
            stats["B_cards_moved"] += moved
            stats["B_cards_skipped_dup"] += skipped
            stats["B_cc_rows_deleted"] += 1

    # ── C: series canonicalization ──────────────────────────────
    log.info(f"C: canonicalizing series across {len(_SERIES_MAP)} known raw values")
    if not dry_run:
        async with SessionLocal() as db:
            for raw, canon in _SERIES_MAP.items():
                r = await db.execute(
                    text("UPDATE sets SET series=:c "
                         "WHERE language='ko' AND series=:r AND series <> :c"),
                    {"c": canon, "r": raw},
                )
                if r.rowcount:
                    stats[f"C_renamed[{raw[:20]}]"] = r.rowcount
            await db.commit()

    # ── D: set_type ─────────────────────────────────────────────
    async with SessionLocal() as db:
        rows = (await db.execute(text(
            "SELECT id, name FROM sets WHERE language='ko' AND set_type IS NULL"
        ))).all()
    log.info(f"D: sets needing set_type classification: {len(rows)}")
    if not dry_run:
        async with SessionLocal() as db:
            for row in rows:
                st = _classify_set_type(row.name or "")
                await db.execute(
                    text("UPDATE sets SET set_type=:t WHERE id=:s"),
                    {"t": st, "s": row.id},
                )
                stats[f"D_set_type[{st}]"] += 1
            await db.commit()

    log.info("=== summary ===")
    for k, v in sorted(stats.items()):
        log.info(f"  {k}: {v}")
    if dry_run:
        log.info("DRY-RUN — no writes")


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
