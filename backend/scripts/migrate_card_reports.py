"""Create `card_reports` table for user-submitted data-quality reports.

Idempotent — safe to re-run. Creates the table via SQLAlchemy's
``CardReport.__table__.create(checkfirst=True)`` so the column types,
indexes, and FKs match the model exactly.
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

os.environ.setdefault("DEBUG", "false")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import engine  # noqa: E402
from app.models.card_report import CardReport  # noqa: E402

log = logging.getLogger("migrate_card_reports")


async def main() -> None:
    async with engine.begin() as conn:
        log.info("creating card_reports table (if not exists)...")
        await conn.run_sync(
            lambda sync_conn: CardReport.__table__.create(
                sync_conn, checkfirst=True
            )
        )
    log.info("done")


if __name__ == "__main__":
    asyncio.run(main())
