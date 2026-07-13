"""News content + view-count API.

Posts live in the DB so LO can write from the browser (/admin/news).
Public endpoints under /news/posts read them, admin-only endpoints
under the same prefix create/update/delete. View counter sits beside
the posts table.
"""

from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_admin, get_current_admin_optional
from app.database import get_db
from app.models import NewsPost, NewsView, ProcessedUrl, User

router = APIRouter(prefix="/news", tags=["news"])

_SLUG_MAX_LEN = 128

NewsStatus = Literal["draft", "published"]


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
    # Default to 'published' for legacy callers (the admin form pre-bot).
    # Newsbot always passes 'draft'.
    status: NewsStatus = "published"
    source_url: str | None = Field(default=None, max_length=512)


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
        "status": p.status,
        "source_url": p.source_url,
    }


@router.get("/posts")
async def list_posts(
    category: str | None = None,
    region: str | None = None,
    include_drafts: bool = Query(
        default=False,
        description="Admin-only. When true and caller is admin, returns drafts too.",
    ),
    admin: Annotated[User | None, Depends(get_current_admin_optional)] = None,
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    # published_at is a YYYY-MM-DD string — when the bot posts several
    # articles on the same day, every row's published_at is identical
    # and the result order falls back to whatever the DB feels like
    # (usually insertion order, which puts NEW posts at the bottom).
    # created_at is the real insertion timestamp; using it as the
    # tiebreaker keeps the feed strictly newest-first.
    stmt = select(NewsPost).order_by(
        NewsPost.published_at.desc(), NewsPost.created_at.desc()
    )
    if category and category != "all":
        # category filter is the primary axis the UI exposes — drops /
        # market / tcg / center / guide / news.
        stmt = stmt.where(NewsPost.category == category)
    if region and region != "all":
        # Region kept for forward flexibility (e.g. region-specific
        # event posts later). Not currently in the UI.
        stmt = stmt.where(NewsPost.region.in_([region, "all"]))
    # Drafts are admin-only. Anonymous + non-admin traffic only ever
    # sees published rows; flipping include_drafts as a non-admin is a
    # silent no-op (don't 403 — keeps the public endpoint forgiving).
    if not (admin and include_drafts):
        stmt = stmt.where(NewsPost.status == "published")
    rows = (await db.execute(stmt)).scalars().all()
    return [_post_to_dict(p) for p in rows]


@router.get("/posts/source-urls")
async def list_source_urls(
    admin: Annotated[User, Depends(get_current_admin)],  # noqa: ARG001
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Admin-only dedupe map for the newsbot — {source_url: slug} for
    every post that has a source_url set. Cheaper than fetching every
    row's body just to filter by URL."""
    rows = (
        await db.execute(
            select(NewsPost.source_url, NewsPost.slug).where(
                NewsPost.source_url.is_not(None)
            )
        )
    ).all()
    return {url: slug for url, slug in rows if url}


@router.get("/posts/processed-urls")
async def list_processed_urls(
    admin: Annotated[User, Depends(get_current_admin)],  # noqa: ARG001
    db: AsyncSession = Depends(get_db),
) -> dict[str, dict]:
    """Admin-only persistent dedupe log for the newsbot — every URL
    the bot has touched, regardless of whether the resulting post
    still exists. Returns {source_url: {outcome, title_tokens}} so
    the newsbot can dedupe both by URL AND by title-token similarity
    across runs (same-story-different-URL case). Used together with
    /posts/source-urls so dedupe survives post deletion."""
    rows = (
        await db.execute(
            select(
                ProcessedUrl.source_url,
                ProcessedUrl.outcome,
                ProcessedUrl.title_tokens,
            )
        )
    ).all()
    return {
        url: {"outcome": outcome, "title_tokens": tokens or ""}
        for url, outcome, tokens in rows
    }


class ProcessedUrlIn(BaseModel):
    source_url: str = Field(min_length=1, max_length=512)
    outcome: str = Field(min_length=1, max_length=32)
    # Optional so older newsbot builds still work. New builds pass
    # space-separated normalized content-word tokens for the title.
    title_tokens: str | None = Field(default=None, max_length=2048)


@router.post("/posts/processed-urls", status_code=204)
async def mark_processed_url(
    payload: ProcessedUrlIn,
    admin: Annotated[User, Depends(get_current_admin)],  # noqa: ARG001
    db: AsyncSession = Depends(get_db),
) -> None:
    """Append-only log of URLs the newsbot has processed. Idempotent
    on conflict (a URL re-touched in a future run is fine — we keep
    the original outcome and timestamp). Used for cost-safe dedupe
    that survives admin post deletion."""
    dialect = db.bind.dialect.name
    values = {"source_url": payload.source_url, "outcome": payload.outcome}
    if payload.title_tokens is not None:
        values["title_tokens"] = payload.title_tokens
    if dialect == "postgresql":
        stmt = insert(ProcessedUrl).values(**values).on_conflict_do_nothing(
            index_elements=["source_url"]
        )
    else:
        stmt = sqlite_insert(ProcessedUrl).values(**values).on_conflict_do_nothing(
            index_elements=["source_url"]
        )
    await db.execute(stmt)
    await db.commit()


@router.delete("/posts/processed-urls", status_code=204)
async def delete_processed_url(
    admin: Annotated[User, Depends(get_current_admin)],  # noqa: ARG001
    db: AsyncSession = Depends(get_db),
    source_url: str = Query(min_length=1, max_length=512),
) -> None:
    """Remove a single URL from the persistent dedupe log so the
    newsbot will pick it up again on the next run. Use when the
    earlier-published draft was bad (prompt was wrong, or quality was
    sub-par) and we want to regenerate from the same source under the
    fixed pipeline. Returns 204 whether the row existed or not —
    idempotent."""
    from sqlalchemy import delete as sql_delete
    await db.execute(
        sql_delete(ProcessedUrl).where(ProcessedUrl.source_url == source_url)
    )
    await db.commit()


@router.get("/posts/{slug}")
async def get_post(
    slug: str,
    admin: Annotated[User | None, Depends(get_current_admin_optional)] = None,
    db: AsyncSession = Depends(get_db),
) -> dict:
    slug = _validate_slug(slug)
    p = await db.get(NewsPost, slug)
    if not p:
        raise HTTPException(status_code=404, detail="post not found")
    if p.status == "draft" and not admin:
        # Hide draft existence from non-admins — same 404 as a missing
        # slug so the URL space doesn't leak which slugs are reserved
        # for unpublished work.
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
        status=payload.status,
        source_url=payload.source_url,
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
    post.status = payload.status
    post.source_url = payload.source_url
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
