"""One-shot migration — copy the welcome markdown post into the DB.

After Phase 2 the frontend reads news posts from the DB rather than
the filesystem. This script seeds whatever's already in
frontend/content/news/ so the public page isn't empty on cutover.

Safe to re-run: rows are upserted by slug.

Also flips is_admin=true on the LO user account when the script is
called with --grant-admin <email>.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import re
import sys
from pathlib import Path

os.environ.setdefault("DEBUG", "false")
logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(message)s")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select, text, update
from app.database import SessionLocal, engine, init_db  # noqa: E402
from app.models import NewsPost, User  # noqa: E402


async def ensure_is_admin_column() -> None:
    """init_db only runs CREATE TABLE IF NOT EXISTS. The is_admin /
    deleted_at columns were added to an existing users table, so we
    patch them in explicitly."""
    async with engine.begin() as conn:
        await conn.execute(text(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_admin BOOLEAN NOT NULL DEFAULT FALSE"
        ))
        await conn.execute(text(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP NULL"
        ))

engine.echo = False
log = logging.getLogger("migrate_markdown_news")
log.setLevel(logging.INFO)

CONTENT_DIR = Path(__file__).resolve().parents[2] / "frontend" / "content" / "news"


_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    meta_block = m.group(1)
    body = text[m.end():]
    meta: dict[str, str] = {}
    for line in meta_block.splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        meta[key.strip()] = value.strip().strip('"').strip("'")
    return meta, body


async def upsert_markdown_posts() -> int:
    if not CONTENT_DIR.exists():
        log.info("no markdown source dir, skipping")
        return 0
    files = sorted(CONTENT_DIR.glob("*.md"))
    if not files:
        log.info("no markdown files to migrate")
        return 0

    count = 0
    async with SessionLocal() as db:
        for f in files:
            meta, body = _parse_frontmatter(f.read_text(encoding="utf-8"))
            slug = meta.get("slug") or f.stem
            existing = await db.get(NewsPost, slug)
            payload = dict(
                title=meta.get("title", slug),
                body=body.strip(),
                excerpt=meta.get("excerpt") or None,
                region=meta.get("region", "all"),
                category=meta.get("category") or None,
                thumbnail_url=meta.get("thumbnail") or None,
                author=meta.get("author") or None,
                published_at=meta.get("publishedAt", "2026-06-21"),
                reading_time=int(meta["readingTime"]) if meta.get("readingTime") else None,
            )
            if existing:
                for k, v in payload.items():
                    setattr(existing, k, v)
                log.info(f"  updated {slug}")
            else:
                db.add(NewsPost(slug=slug, **payload))
                log.info(f"  inserted {slug}")
            count += 1
        await db.commit()
    return count


async def grant_admin(email: str) -> None:
    async with SessionLocal() as db:
        result = await db.execute(
            update(User).where(User.email == email).values(is_admin=True)
        )
        await db.commit()
        if result.rowcount:
            log.info(f"  granted admin to {email}")
        else:
            log.warning(f"  no user with email {email!r} — sign up first")


async def main(grant_admin_email: str | None) -> None:
    await init_db()
    await ensure_is_admin_column()
    count = await upsert_markdown_posts()
    log.info(f"migrated {count} markdown posts")
    if grant_admin_email:
        await grant_admin(grant_admin_email)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--grant-admin",
        help="Set is_admin=true on the user with this email (must already exist).",
    )
    args = parser.parse_args()
    asyncio.run(main(args.grant_admin))
