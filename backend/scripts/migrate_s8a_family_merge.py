"""One-shot merge of the 25th Anniversary set family into S8a.

Previously we split the TCGCSV s8a category into three PullList sets
(S8a, S8a-P, S8a-G) to match distinct printed numbering. LO decided
that's the wrong UX — from a collector's POV the 25th Anniversary
release is a single product line (matches how TCG Republic groups
it), so all three collapse into S8a.

To keep card ids unique after the merge we namespace the two
sub-sets' numbers with a letter prefix:
    base cards     stay as number "1".."30"          (id S8a-1..S8a-30)
    promo pack     re-numbered "P1".."P25"           (id S8a-P1..S8a-P25)
    golden box     re-numbered "G1".."G15"           (id S8a-G1..S8a-G15)

Card ``number_int`` is offset (100+N for promo, 200+N for golden)
so sort-by-number still puts base first, then promos, then golden —
without the string-sort quirk that would land "P10" before "P2".

FK safety: the S8a-P / S8a-G cards were just imported minutes ago
by ``import_jp_group_cards`` in the same session — no user has
collected or wishlisted them yet, so a plain DELETE is safe. If
that assumption changes (e.g. this migration is re-run months
later after user activity), the CASCADE from cards.set_id → sets
will still enforce integrity, but any collection/wishlist rows
would need re-linking to the new S8a-P{N} ids first.

Idempotent — only acts if the two sub-sets still exist. The
following ``import_jp_group_cards`` step in the workflow then
re-imports those groups directly into S8a with the prefixes.

Usage:
    python -m scripts.migrate_s8a_family_merge --dry-run
    python -m scripts.migrate_s8a_family_merge
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal, init_db  # noqa: E402


log = logging.getLogger("migrate_s8a_family_merge")


_SUB_SETS = ("S8a-P", "S8a-G")


async def run(dry_run: bool) -> None:
    await init_db()

    async with SessionLocal() as db:
        # Report what's currently split out so the log makes the
        # "before" state explicit.
        for sid in _SUB_SETS:
            n_cards = (await db.execute(
                text("SELECT COUNT(*) FROM cards WHERE set_id = :s"),
                {"s": sid},
            )).scalar()
            n_prods = (await db.execute(
                text("SELECT COUNT(*) FROM products WHERE set_id = :s"),
                {"s": sid},
            )).scalar()
            log.info(f"{sid}: {n_cards} cards, {n_prods} sealed products")

        s8a_before = (await db.execute(
            text("SELECT total, printed_total FROM sets WHERE id = 'S8a'")
        )).first()
        if s8a_before:
            log.info(
                f"S8a before: total={s8a_before.total} "
                f"printed_total={s8a_before.printed_total}"
            )

        if dry_run:
            log.info("MODE: DRY-RUN — no writes")
            return

        # 1. Sealed products retain the same TCGCSV product ids; just
        # rehome their FK. Idempotent — repeated runs update to same
        # value, no-op after the first pass.
        r = await db.execute(
            text(
                "UPDATE products SET set_id = 'S8a' "
                "WHERE set_id = ANY(:subs)"
            ),
            {"subs": list(_SUB_SETS)},
        )
        log.info(f"products moved to S8a: {r.rowcount}")

        # 2. Drop the sub-set cards. See docstring re: FK safety —
        # only safe because the cards were freshly imported and
        # haven't been referenced by user collection/wishlist tables.
        r = await db.execute(
            text("DELETE FROM cards WHERE set_id = ANY(:subs)"),
            {"subs": list(_SUB_SETS)},
        )
        log.info(f"cards deleted (will be re-imported with prefix): {r.rowcount}")

        # 3. Drop the sub-set rows themselves.
        r = await db.execute(
            text("DELETE FROM sets WHERE id = ANY(:subs)"),
            {"subs": list(_SUB_SETS)},
        )
        log.info(f"sets deleted: {r.rowcount}")

        # 4. Bump the unified S8a total to cover all three printings
        # (30 base + 25 promo + 15 golden).
        r = await db.execute(
            text("UPDATE sets SET total = 70 WHERE id = 'S8a'")
        )
        log.info(f"S8a total updated to 70: {r.rowcount}")

        # 5. Promote S8a from STUB → MAIN. The set was tagged STUB when
        # only the shell row existed (no cards seeded). Now that the
        # import pass filled it with 70 cards + 4 sealed products,
        # STUB is wrong — and the JP set browser (/sets?region=ja)
        # hides STUB rows, which meant /sets/S8a was unreachable
        # through the UI even though the detail page worked.
        r = await db.execute(
            text(
                "UPDATE sets SET set_type = 'MAIN' "
                "WHERE id = 'S8a' AND set_type = 'STUB'"
            )
        )
        log.info(f"S8a set_type STUB→MAIN: {r.rowcount}")

        await db.commit()


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    asyncio.run(run(args.dry_run))


if __name__ == "__main__":
    main()
