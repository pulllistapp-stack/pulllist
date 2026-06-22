"""Add `status` + `source_url` columns to news_posts plus an index on
source_url. Idempotent — safe to re-run.

Why:
    The newsbot (backend/newsbot/) posts articles as drafts so LO can
    review before they hit the public /news feed. Existing rows
    grandfather to status='published'. The bot keys dedupe off the
    upstream URL via source_url; the index keeps the lookup O(log n).
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

log = logging.getLogger("migrate_news_status_source")


STATEMENTS = (
    "ALTER TABLE news_posts ADD COLUMN IF NOT EXISTS status VARCHAR(16) "
    "NOT NULL DEFAULT 'published'",
    "ALTER TABLE news_posts ADD COLUMN IF NOT EXISTS source_url VARCHAR(512)",
    "CREATE INDEX IF NOT EXISTS idx_news_posts_source_url "
    "ON news_posts (source_url)",
)


async def main() -> None:
    async with engine.begin() as conn:
        for stmt in STATEMENTS:
            log.info("running: %s", stmt)
            await conn.execute(text(stmt))
    log.info("done")


if __name__ == "__main__":
    asyncio.run(main())
