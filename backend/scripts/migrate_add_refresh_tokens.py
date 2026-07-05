"""One-shot migration: create the `refresh_tokens` table.

Backs the Level-3 auth flow (short-lived access JWT + long-lived opaque
refresh token stored as sha256 hash). No ALTER on the existing `users`
table — this is additive only, so it's safe to deploy before the backend
code that uses it.

Idempotent: skips if the table already exists. Same treatment for the
active-session index.

Usage:
    python -m scripts.migrate_add_refresh_tokens --dry-run
    python -m scripts.migrate_add_refresh_tokens
"""
from __future__ import annotations

import argparse
import asyncio
import logging

from sqlalchemy import text

from app.database import SessionLocal, init_db

log = logging.getLogger("migrate_refresh_tokens")


CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS refresh_tokens (
    id            VARCHAR(36)  PRIMARY KEY,
    user_id       VARCHAR(36)  NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash    VARCHAR(64)  NOT NULL UNIQUE,
    created_at    TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at    TIMESTAMP    NOT NULL,
    revoked_at    TIMESTAMP,
    device_label  VARCHAR(120),
    last_used_at  TIMESTAMP
)
"""

# Two supporting indexes:
#   - user_id alone for CASCADE + "all my sessions" lookups
#   - (user_id, revoked_at) for the hot path — active-session filtering
CREATE_INDEXES_SQL = [
    "CREATE INDEX IF NOT EXISTS ix_refresh_tokens_user_id ON refresh_tokens (user_id)",
    "CREATE INDEX IF NOT EXISTS ix_refresh_tokens_token_hash ON refresh_tokens (token_hash)",
    "CREATE INDEX IF NOT EXISTS ix_refresh_tokens_user_active ON refresh_tokens (user_id, revoked_at)",
]


async def _table_exists(db, table: str) -> bool:
    r = await db.execute(
        text(
            """SELECT 1 FROM information_schema.tables
               WHERE table_name = :t"""
        ),
        {"t": table},
    )
    return r.first() is not None


async def run(dry_run: bool) -> None:
    await init_db()
    async with SessionLocal() as db:
        exists = await _table_exists(db, "refresh_tokens")

        if exists:
            log.info("refresh_tokens table already present — nothing to create.")
        else:
            log.info(
                "refresh_tokens table missing — %s create.",
                "would" if dry_run else "will",
            )

        if dry_run:
            log.info("---- DRY RUN — SQL that would execute ----")
            log.info(CREATE_TABLE_SQL.strip())
            for stmt in CREATE_INDEXES_SQL:
                log.info(stmt)
            log.info("---- END DRY RUN ----")
            return

        if not exists:
            log.info("Creating refresh_tokens table …")
            await db.execute(text(CREATE_TABLE_SQL))

        for stmt in CREATE_INDEXES_SQL:
            log.info("  %s", stmt)
            await db.execute(text(stmt))

        await db.commit()
        log.info("Migration complete.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log the SQL without executing it.",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
    )
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    asyncio.run(run(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
