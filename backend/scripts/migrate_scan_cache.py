"""Create `scan_cache` table for perceptual-hash card identification cache.

Idempotent — safe to re-run.
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
from app.models.scan_cache import ScanCache  # noqa: E402

log = logging.getLogger("migrate_scan_cache")


async def main() -> None:
    async with engine.begin() as conn:
        log.info("creating scan_cache table (if not exists)...")
        await conn.run_sync(
            lambda sync_conn: ScanCache.__table__.create(
                sync_conn, checkfirst=True
            )
        )
    log.info("done")


if __name__ == "__main__":
    asyncio.run(main())
