"""Merge empty CN native shells into their same-date moved siblings.

Background (see cleanup_ko_c_locale_mixup.py + KR/CN Phase 1d):
  The zh-cn set catalog is currently split across two lineages:
  (a) `zhcn-c-*` (128 rows) — moved from the ko cleanup, carry cards +
      logos but the display `name` is English or Korean because that's
      what collectory recorded.
  (b) TCGdex short-prefix rows (e.g. `zhcn-CSV9.5C`, `zhcn-CBB3C`) —
      empty shells (0 cards, 0 logo) but carry the correct Simplified
      Chinese `name`, `name_local`, and `series` classification.

  When rendered in the CN catalog UI these look like separate sets even
  though same-date pairs are the same physical release. e.g.
  `zhcn-CSV9.5C` (太晶盛聚, 0 cards, series 朱&紫) and
  `zhcn-c-574b2fe05f` (Terastal Gathering, 258 cards, series OTHER) are
  the same set from two sources.

Strategy:
  For every empty (0-card) native row, find same-release_date moved
  rows. Promote the native's Chinese name/series onto the primary moved
  row of that date (the one with the most cards — the main booster —
  gets the full name; all moved on that date get the native's series).
  Delete the empty native after promotion.

  Non-empty natives (currently 8: SV7/SV7a/SV8/SV8a/SV9/SV9a/SV10 are
  Traditional Chinese mislabeled as zh-cn; CSMPiC is a real CN Battle
  Party Reward Pack) are skipped here — they need a separate track.

Safety:
  - Never touches rows outside language='zh-cn'.
  - Refuses to delete a native that has any cards / products.
  - Refuses to promote to a moved row that's not `zhcn-c-*`.
  - --dry-run prints planned changes without writing.
  - --only <substr> narrows to native IDs containing this substring
    (useful for spot-testing one pair).
  - Idempotent: a moved row that already has a Chinese `name_local`
    matching the native is left alone (only series update runs).
"""
from __future__ import annotations
import argparse
import asyncio
import io
import logging
import sys
from collections import defaultdict
from pathlib import Path

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402
from app.database import SessionLocal, init_db  # noqa: E402

logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


async def load_cn_rows(db):
    r = await db.execute(text("""
        SELECT id, name, name_local, name_en, series, release_date, logo_url,
               (SELECT COUNT(*) FROM cards WHERE set_id=s.id) AS n_cards
        FROM sets s WHERE language='zh-cn'
    """))
    return list(r.all())


async def has_products(db, sid: str) -> int:
    return (await db.execute(
        text("SELECT COUNT(*) FROM products WHERE set_id=:s"), {"s": sid}
    )).scalar_one()


def _chinese_ratio(s: str | None) -> float:
    if not s:
        return 0.0
    n = sum(1 for c in s if '一' <= c <= '鿿')
    return n / len(s)


# Chinese Simplified series name → English label. Applied inline in the
# `series` field (bilingual, matching the KR canonicalization pattern in
# cleanup_kr_classification.py) so browsers who read either script can
# recognize the era at a glance.
CN_SERIES_EN: dict[str, str] = {
    "朱&紫": "Scarlet & Violet",
    "剑&盾": "Sword & Shield",
    "太阳&月亮": "Sun & Moon",
    "XY BREAK": "XY BREAK",
    "XY": "XY",
    "黑白": "Black & White",
    "钻石与珍珠": "Diamond & Pearl",
    "宝石": "EX-era",
}


def _bilingual_series(cn: str | None) -> str | None:
    if not cn:
        return None
    if cn in ("Other", "其他"):
        return cn
    en = CN_SERIES_EN.get(cn)
    if not en or cn == en or en in cn:
        return cn
    return f"{cn} ({en})"


async def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--only", default=None,
                   help="Only process natives whose ID contains this substring")
    args = p.parse_args()

    await init_db()
    async with SessionLocal() as db:
        rows = await load_cn_rows(db)
        moved = [r for r in rows if r.id.startswith("zhcn-c-")]
        native = [r for r in rows if not r.id.startswith("zhcn-c-")]

        empty_natives = [n for n in native if n.n_cards == 0]
        nonempty_natives = [n for n in native if n.n_cards > 0]

        print(f"moved: {len(moved)}, empty natives: {len(empty_natives)}, "
              f"non-empty natives (skipped): {len(nonempty_natives)}")

        if args.only:
            empty_natives = [n for n in empty_natives if args.only.lower() in n.id.lower()]
            print(f"--only filter → {len(empty_natives)} natives")

        # Index natives by date. Multiple natives per date is common (e.g.
        # CSM2aC + csm2a on the same day — different TCGdex snapshots).
        natives_by_date: dict[object, list] = defaultdict(list)
        for n in empty_natives:
            if n.release_date:
                natives_by_date[n.release_date].append(n)

        moved_by_date: dict[object, list] = defaultdict(list)
        for m in moved:
            if m.release_date:
                moved_by_date[m.release_date].append(m)

        def pick_representative(nats: list) -> object:
            """Deterministic pick from same-date natives — most Chinese-
            dense name wins, ID as tiebreaker."""
            return max(nats, key=lambda n: (_chinese_ratio(n.name), n.id))

        planned_updates: list[tuple[str, str, dict, str]] = []
        planned_deletes: list[str] = []
        unmatched_native_dates = 0

        # Iterate per moved row so each is updated at most once
        for m in moved:
            nats = natives_by_date.get(m.release_date, [])
            if not nats:
                continue  # no native pairing → leave moved untouched
            candidates_sorted = sorted(
                moved_by_date[m.release_date], key=lambda x: -x.n_cards
            )
            is_primary = (m.id == candidates_sorted[0].id)
            rep = pick_representative(nats)

            fields: dict = {}
            reasons: list[str] = []

            # Series propagates to every moved on that date, with
            # bilingual formatting (matches KR canonicalization)
            new_series = _bilingual_series(rep.series)
            if new_series and (m.series or "") != new_series:
                fields["series"] = new_series
                reasons.append(f"series {m.series!r}→{new_series!r}")

            if is_primary:
                if rep.name and _chinese_ratio(m.name) < 0.3:
                    fields["name"] = rep.name
                    reasons.append(f"name {m.name!r}→{rep.name!r}")
                if rep.name_local and _chinese_ratio(m.name_local) < 0.3:
                    fields["name_local"] = rep.name_local
                    reasons.append(f"name_local +{rep.name_local!r}")
                # Preserve original English/Korean as subtitle
                if m.name and _chinese_ratio(m.name) < 0.3 and not m.name_en:
                    fields["name_en"] = m.name
                    reasons.append(f"name_en preserve {m.name!r}")

            if fields:
                planned_updates.append((m.id, rep.id, fields, "; ".join(reasons)))

        # Delete empty natives — those with a same-date moved got merged,
        # those without get orphan-deleted (nothing to save)
        for n in empty_natives:
            assert n.n_cards == 0, n.id
            products = await has_products(db, n.id)
            if products:
                print(f"  SKIP native {n.id} — has {products} products (unexpected)")
                continue
            if not moved_by_date.get(n.release_date):
                unmatched_native_dates += 1
            planned_deletes.append(n.id)

        print()
        print(f"planned updates:  {len(planned_updates)}")
        print(f"planned deletes:  {len(planned_deletes)}  "
              f"({unmatched_native_dates} unmatched, "
              f"{len(planned_deletes) - unmatched_native_dates} merged)")
        print()
        print("=== Sample updates (first 30) ===")
        for mid, nid, fields, reasons in planned_updates[:30]:
            print(f"  UPDATE {mid:22s} ← {nid:22s}  {reasons}")
        if len(planned_updates) > 30:
            print(f"  ... +{len(planned_updates) - 30} more updates")

        print()
        print("=== Sample deletes (first 20) ===")
        for nid in planned_deletes[:20]:
            print(f"  DELETE {nid}")
        if len(planned_deletes) > 20:
            print(f"  ... +{len(planned_deletes) - 20} more deletes")

        if args.dry_run:
            print()
            print("--dry-run: no changes committed")
            return 0

        # Execute
        for mid, _nid, fields, _reasons in planned_updates:
            set_clauses = ", ".join(f"{k} = :{k}" for k in fields)
            params = {**fields, "id": mid}
            await db.execute(
                text(f"UPDATE sets SET {set_clauses}, updated_at=NOW() WHERE id = :id"),
                params,
            )
        if planned_deletes:
            await db.execute(
                text("DELETE FROM sets WHERE id = ANY(:ids)"),
                {"ids": planned_deletes},
            )
        await db.commit()
        print()
        print(f"applied {len(planned_updates)} updates, deleted {len(planned_deletes)} natives")
        return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
