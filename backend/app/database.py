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
