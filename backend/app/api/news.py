"""News content + view-count API.

Posts live in the DB so LO can write from the browser (/admin/news).
Public endpoints under /news/posts read them, admin-only endpoints
under the same prefix create/update/delete. View counter sits beside
the posts table.
"""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_admin
from app.database import get_db
from app.models import NewsPost, NewsView, User

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


# ────────────── Posts (content) ──────────────


class PostIn(BaseModel):
    slug: str = Field(min_length=1, max_length=128)
    title: str = Field(min_length=1, max_length=256)
    body: str = Field(min_length=1)
    excerpt: str | None = Field(default=None, max_length=512)
    region: str = Field(default="all", pattern="^(all|kr|ja|us)$")
    category: str | None = Field(default=None, max_length=64)
    thumbnail_url: str | None = Field(default=None, max_length=512)
    author: str | None = Field(default=None, max_length=64)
    published_at: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    reading_time: int | None = Field(default=None, ge=1, le=120)


class PostOut(PostIn):
    pass


def _post_to_dict(p: NewsPost) -> dict:
    return {
        "slug": p.slug,
        "title": p.title,
        "body": p.body,
        "excerpt": p.excerpt,
        "region": p.region,
        "category": p.category,
        "thumbnail_url": p.thumbnail_url,
        "author": p.author,
        "published_at": p.published_at,
        "reading_time": p.reading_time,
    }


@router.get("/posts")
async def list_posts(
    region: str | None = None, db: AsyncSession = Depends(get_db)
) -> list[dict]:
    stmt = select(NewsPost).order_by(NewsPost.published_at.desc())
    if region and region != "all":
        # 'all'-region posts surface in every region tab; specific-region
        # posts surface only in that tab.
        stmt = stmt.where(NewsPost.region.in_([region, "all"]))
    rows = (await db.execute(stmt)).scalars().all()
    return [_post_to_dict(p) for p in rows]


@router.get("/posts/{slug}")
async def get_post(slug: str, db: AsyncSession = Depends(get_db)) -> dict:
    slug = _validate_slug(slug)
    p = await db.get(NewsPost, slug)
    if not p:
        raise HTTPException(status_code=404, detail="post not found")
    return _post_to_dict(p)


@router.post("/posts", status_code=201)
async def create_post(
    payload: PostIn,
    admin: Annotated[User, Depends(get_current_admin)],
    db: AsyncSession = Depends(get_db),
) -> dict:
    slug = _validate_slug(payload.slug)
    existing = await db.get(NewsPost, slug)
    if existing:
        raise HTTPException(status_code=409, detail="slug already exists")
    post = NewsPost(
        slug=slug,
        title=payload.title,
        body=payload.body,
        excerpt=payload.excerpt,
        region=payload.region,
        category=payload.category,
        thumbnail_url=payload.thumbnail_url,
        author=payload.author or admin.name,
        published_at=payload.published_at,
        reading_time=payload.reading_time,
    )
    db.add(post)
    await db.commit()
    return _post_to_dict(post)


@router.put("/posts/{slug}")
async def update_post(
    slug: str,
    payload: PostIn,
    admin: Annotated[User, Depends(get_current_admin)],  # noqa: ARG001
    db: AsyncSession = Depends(get_db),
) -> dict:
    slug = _validate_slug(slug)
    post = await db.get(NewsPost, slug)
    if not post:
        raise HTTPException(status_code=404, detail="post not found")
    # Slug rename: if payload.slug differs, this is effectively a slug
    # change. Cheapest path is to require the URL slug to match the body;
    # a real rename means delete + create.
    if payload.slug != slug:
        raise HTTPException(
            status_code=400,
            detail="slug rename not supported; delete + create instead",
        )
    post.title = payload.title
    post.body = payload.body
    post.excerpt = payload.excerpt
    post.region = payload.region
    post.category = payload.category
    post.thumbnail_url = payload.thumbnail_url
    if payload.author:
        post.author = payload.author
    post.published_at = payload.published_at
    post.reading_time = payload.reading_time
    await db.commit()
    return _post_to_dict(post)


@router.delete("/posts/{slug}", status_code=204)
async def delete_post(
    slug: str,
    admin: Annotated[User, Depends(get_current_admin)],  # noqa: ARG001
    db: AsyncSession = Depends(get_db),
) -> None:
    slug = _validate_slug(slug)
    post = await db.get(NewsPost, slug)
    if post:
        await db.delete(post)
        # Carry the view counter along — slug is unique to the post.
        view = await db.get(NewsView, slug)
        if view:
            await db.delete(view)
        await db.commit()


# ────────────── View counter ──────────────


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
