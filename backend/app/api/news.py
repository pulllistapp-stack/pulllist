"""News view-count tracking.

The /news posts themselves are Markdown files in the frontend repo;
this router only holds the running view tally for each slug so we
can display 'X views' on the listing + rank popular posts later.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import NewsView

router = APIRouter(prefix="/news", tags=["news"])

_SLUG_MAX_LEN = 128


def _validate_slug(slug: str) -> str:
    if not slug or len(slug) > _SLUG_MAX_LEN:
        raise HTTPException(status_code=400, detail="invalid slug")
    # Posts are authored by us (Markdown files in repo) so we control
    # the slug space. The validation here is just a sanity floor — we
    # never want a path traversal or wildly long string in our table.
    if any(c in slug for c in ("/", "\\", "..", "\x00")):
        raise HTTPException(status_code=400, detail="invalid slug")
    return slug


def _upsert_increment(dialect_name: str):
    """ON CONFLICT DO UPDATE that increments the counter — dialect dispatch
    so the script also works against sqlite in tests."""
    if dialect_name == "postgresql":
        return insert(NewsView)
    return sqlite_insert(NewsView)


@router.get("/views")
async def list_views(db: AsyncSession = Depends(get_db)) -> dict[str, int]:
    """Bulk fetch — used by the listing page to show counts inline."""
    rows = (await db.execute(select(NewsView.slug, NewsView.view_count))).all()
    return {slug: count for slug, count in rows}


@router.get("/views/{slug}")
async def get_view(slug: str, db: AsyncSession = Depends(get_db)) -> dict[str, int]:
    slug = _validate_slug(slug)
    row = await db.get(NewsView, slug)
    return {"slug": slug, "view_count": row.view_count if row else 0}


@router.post("/views/{slug}")
async def increment_view(
    slug: str, db: AsyncSession = Depends(get_db)
) -> dict[str, int]:
    """Increment the counter on first detail-page mount.

    No auth, no rate limit beyond what Cloudflare / Render apply at the
    edge. Anonymous + cheap by design — a single client refreshing pads
    the count slightly, which is the same tradeoff most blogs accept.
    Re-running view-deduping at SQL-time would need IP storage we'd
    rather not collect.
    """
    slug = _validate_slug(slug)
    stmt = _upsert_increment(db.bind.dialect.name).values(slug=slug, view_count=1)
    stmt = stmt.on_conflict_do_update(
        index_elements=["slug"],
        set_={"view_count": NewsView.view_count + 1},
    )
    await db.execute(stmt)
    await db.commit()
    row = await db.get(NewsView, slug)
    return {"slug": slug, "view_count": row.view_count if row else 1}
