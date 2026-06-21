"""One-shot migration: add `variant` column to collection_items and wishlist_items.

Both tables now track per-variant ownership (normal vs reverseHolofoil
vs 1stEdition etc) so portfolio value is summed at each variant's own
market price rather than the variant-max we used to denormalize onto
cards.market_price_usd.

Existing rows get `variant='normal'` as default — every existing
collection / wishlist entry retroactively becomes a normal-variant
ownership record, which is the safest fallback (most cards a user
adds are the standard print).

Idempotent: skips if the column already exists.

Usage:
    python -m scripts.migrate_add_variant_column
"""
from __future__ import annotations

import asyncio
import logging

from sqlalchemy import text

from app.database import SessionLocal, init_db

log = logging.getLogger("migrate_variant")


async def _column_exists(db, table: str, column: str) -> bool:
    r = await db.execute(
        text(
            """SELECT 1 FROM information_schema.columns
               WHERE table_name=:t AND column_name=:c"""
        ),
        {"t": table, "c": column},
    )
    return r.first() is not None


async def _constraint_exists(db, name: str) -> bool:
    r = await db.execute(
        text(
            """SELECT 1 FROM pg_constraint WHERE conname=:n"""
        ),
        {"n": name},
    )
    return r.first() is not None


async def run() -> None:
    await init_db()
    async with SessionLocal() as db:
        # collection_items
        if not await _column_exists(db, "collection_items", "variant"):
            log.info("Adding collection_items.variant …")
            await db.execute(
                text(
                    "ALTER TABLE collection_items "
                    "ADD COLUMN variant VARCHAR(32) NOT NULL DEFAULT 'normal'"
                )
            )
            # Drop old unique constraint, recreate with variant included
            if await _constraint_exists(db, "uq_user_card_variant"):
                log.info("  rebuilding uq_user_card_variant to include variant column …")
                await db.execute(text("ALTER TABLE collection_items DROP CONSTRAINT uq_user_card_variant"))
                await db.execute(
                    text(
                        "ALTER TABLE collection_items "
                        "ADD CONSTRAINT uq_user_card_variant "
                        "UNIQUE (user_id, card_id, variant, condition, is_graded, grade)"
                    )
                )
        else:
            log.info("collection_items.variant already exists — skip")

        # wishlist_items
        if not await _column_exists(db, "wishlist_items", "variant"):
            log.info("Adding wishlist_items.variant …")
            await db.execute(
                text(
                    "ALTER TABLE wishlist_items "
                    "ADD COLUMN variant VARCHAR(32) NOT NULL DEFAULT 'normal'"
                )
            )
            if await _constraint_exists(db, "uq_user_wishlist_card"):
                log.info("  rebuilding uq_user_wishlist_card to include variant column …")
                await db.execute(text("ALTER TABLE wishlist_items DROP CONSTRAINT uq_user_wishlist_card"))
                await db.execute(
                    text(
                        "ALTER TABLE wishlist_items "
                        "ADD CONSTRAINT uq_user_wishlist_card "
                        "UNIQUE (user_id, card_id, variant)"
                    )
                )
        else:
            log.info("wishlist_items.variant already exists — skip")

        await db.commit()
        log.info("Migration complete.")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    asyncio.run(run())


if __name__ == "__main__":
    main()
