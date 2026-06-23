"""Add `purchase_price_usd` + `acquisition_type` columns to
`collection_items`. Idempotent — safe to re-run.

Why:
    The Portfolio add-modal exposes purchase price (for ROI tracking
    against current market price) and acquisition type
    (Pull / Trade / Purchase / Gift / Other). Both columns are nullable
    so existing rows backfill cleanly as 'unknown'.
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

from sqlalchemy import text  # noqa: E402

from app.database import engine  # noqa: E402

log = logging.getLogger("migrate_collection_purchase_fields")


STATEMENTS = (
    "ALTER TABLE collection_items "
    "ADD COLUMN IF NOT EXISTS purchase_price_usd DOUBLE PRECISION",
    "ALTER TABLE collection_items "
    "ADD COLUMN IF NOT EXISTS acquisition_type VARCHAR(16)",
)


async def main() -> None:
    async with engine.begin() as conn:
        for stmt in STATEMENTS:
            log.info("running: %s", stmt)
            await conn.execute(text(stmt))
    log.info("done")


if __name__ == "__main__":
    asyncio.run(main())
