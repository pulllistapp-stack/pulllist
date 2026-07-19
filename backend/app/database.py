from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


class Base(DeclarativeBase):
    pass


engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    future=True,
)

SessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session


async def init_db() -> None:
    from app.models import (  # noqa: F401
        card,
        collection,
        news_post,
        news_view,
        portfolio,
        processed_url,
        refresh_token,
        set as set_model,
        snapshot,
        user,
        wishlist,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # metadata.create_all only creates missing tables — it never
        # ALTER TABLEs existing ones. Any new column on a pre-existing
        # table has to be added by hand. Postgres 9.6+ 'IF NOT EXISTS'
        # makes each ALTER idempotent so we can call it on every boot.
        # Add new lines here as models grow columns; grouping them in
        # one block keeps the migration story readable in one place.
        from sqlalchemy import text
        await conn.execute(text(
            "ALTER TABLE newsbot_processed_urls "
            "ADD COLUMN IF NOT EXISTS title_tokens TEXT"
        ))
        # Partial index for the DISTINCT ON latest-raw-eBay-median lookup
        # used by (1) nightly TCGCSV sync's consensus blend, (2) unified
        # Refresh endpoint, (3) backfill_consensus_market_price. Without
        # it the planner falls back to a full scan of the base ix_snapshot_
        # card_date and filters in-memory, which scales badly as
        # card_price_snapshots grows past ~500k rows. Partial predicate
        # matches every downstream query exactly so the planner picks it
        # every time. IF NOT EXISTS keeps boot idempotent.
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_snapshot_ebay_raw_card_time "
            "ON card_price_snapshots (card_id, snapshot_at DESC) "
            "WHERE source = 'ebay' AND grade = 'raw' "
            "AND market_price_usd IS NOT NULL"
        ))
