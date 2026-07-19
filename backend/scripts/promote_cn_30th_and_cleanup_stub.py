"""Two-part cleanup for the CN 30th Celebration entries:

1. DELETE the stub `me30-cn` (30th Celebration CN) row seeded in
   90a3f7a — it was going to hold the CN worldwide-sync slot but
   the CN catalog already carries `zhcn-c-b09b95caa5` for the same
   campaign, with 9 real cards + a logo already populated.

2. PROMOTE `zhcn-c-b09b95caa5` into the 30th Celebration series so
   the browse-by-series pill on /sets groups it alongside the EN /
   JP 30th rows instead of leaving it under 'Other'. LO's ask:
   'CN 버전은 이미 OTHER에 30th 있으니 거기 집중 (…) OTHER 에 있는걸
   위로 올리고' — the existing row is the canonical CN 30th
   presence; the stub was noise.

Both operations idempotent — re-running skips missing / already-
promoted rows.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import delete, select

from app.database import SessionLocal, init_db
from app.models.set import Set


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("cleanup_cn_30th")


STUB_ID = "me30-cn"
CANONICAL_ID = "zhcn-c-b09b95caa5"
TARGET_SERIES = "30th Celebration"


async def run(dry_run: bool) -> None:
    await init_db()

    async with SessionLocal() as db:
        # ── Step 1: delete stub ────────────────────────────────
        stub = await db.get(Set, STUB_ID)
        if stub is None:
            log.info(f"[skip-delete] {STUB_ID} — already absent")
        else:
            log.info(
                f"[delete] {STUB_ID} — {stub.name}"
                f" (release={stub.release_date}, cards=n/a)"
            )
            if not dry_run:
                await db.execute(delete(Set).where(Set.id == STUB_ID))

        # ── Step 2: promote canonical ─────────────────────────
        canonical = await db.get(Set, CANONICAL_ID)
        if canonical is None:
            log.warning(
                f"[warn] canonical CN 30th row {CANONICAL_ID} not found — "
                "no series promotion applied"
            )
        elif canonical.series == TARGET_SERIES:
            log.info(
                f"[skip-promote] {CANONICAL_ID} already carries "
                f"series='{TARGET_SERIES}'"
            )
        else:
            log.info(
                f"[promote] {CANONICAL_ID} — {canonical.name}: "
                f"series {canonical.series!r} → {TARGET_SERIES!r}"
            )
            if not dry_run:
                canonical.series = TARGET_SERIES

        if not dry_run:
            await db.commit()

        log.info(f"\ndry_run: {dry_run}")


def main() -> None:
    import argparse

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(run(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
