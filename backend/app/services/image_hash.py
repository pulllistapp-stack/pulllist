"""Perceptual-hash helpers for the scan cache.

We hash incoming card images with pHash (64-bit perceptual hash) so the
cache survives small differences in re-scans (different angle, lighting,
crop). Exact pixel hashing would miss those completely.

Cache lookup uses Hamming distance — the number of differing bits between
two 64-bit hashes:
  - distance 0      : identical image
  - distance 1-5    : same card, different shot
  - distance 6-10   : maybe same card, maybe not
  - distance 11+    : different image

We accept distance ≤ MAX_HAMMING_DISTANCE as a cache hit.

Lookup is O(N) over recent rows. At our scale (<10k cache rows for the
first year) this is fast enough (~5ms). Past 100k rows we should switch
to a bigint column + ``bit_count((a # b)::bit(64))`` in SQL.
"""

from __future__ import annotations

import base64
import io
import logging
from datetime import datetime

import imagehash
from PIL import Image
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ScanCache


log = logging.getLogger("image_hash")

MAX_HAMMING_DISTANCE = 5
LOOKUP_WINDOW = 2000


def compute_phash(image_b64: str) -> str | None:
    """Return a 16-char hex pHash from base64-encoded image bytes.

    Returns None when the bytes don't decode to a valid image — caller
    should fall through to the Claude path in that case.
    """
    try:
        raw = base64.b64decode(image_b64, validate=False)
        img = Image.open(io.BytesIO(raw))
        # Force decode + RGB conversion so partially-corrupt images blow
        # up here rather than during hashing.
        img.load()
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        return str(imagehash.phash(img))  # 16 hex chars
    except Exception as e:
        log.warning("phash compute failed: %s", e)
        return None


def _hamming(a_hex: str, b_hex: str) -> int:
    """Hamming distance between two 16-char hex pHashes."""
    try:
        return bin(int(a_hex, 16) ^ int(b_hex, 16)).count("1")
    except ValueError:
        return 64  # treat malformed as max distance


async def find_cache_hit(
    db: AsyncSession,
    target_hash: str,
) -> ScanCache | None:
    """Look up the cache for any hash within MAX_HAMMING_DISTANCE of the
    incoming image. Newest-seen entries are checked first so viral cards
    short-circuit fast.

    Exact hits skip the distance loop entirely — most repeat scans of
    the same file land here.
    """
    exact = await db.get(ScanCache, target_hash)
    if exact is not None:
        return exact

    rows = (
        await db.execute(
            select(ScanCache)
            .order_by(ScanCache.last_seen.desc())
            .limit(LOOKUP_WINDOW)
        )
    ).scalars().all()

    for row in rows:
        if _hamming(target_hash, row.image_hash) <= MAX_HAMMING_DISTANCE:
            return row
    return None


async def write_cache(
    db: AsyncSession,
    image_hash: str,
    card_id: str,
    confidence: str | None,
) -> None:
    """Insert or refresh a cache entry. On duplicate hash, bumps
    hit_count + last_seen without re-pointing the card_id (the first
    successful identification wins; we don't want a flaky later read
    to overwrite a known-good answer)."""
    now = datetime.utcnow()
    dialect = db.bind.dialect.name
    insert_cls = pg_insert if dialect == "postgresql" else sqlite_insert
    stmt = (
        insert_cls(ScanCache)
        .values(
            image_hash=image_hash,
            card_id=card_id,
            confidence=confidence,
            hit_count=1,
            first_seen=now,
            last_seen=now,
        )
        .on_conflict_do_update(
            index_elements=["image_hash"],
            set_={
                "hit_count": ScanCache.hit_count + 1,
                "last_seen": now,
            },
        )
    )
    await db.execute(stmt)
    await db.commit()


async def bump_hit(db: AsyncSession, image_hash: str) -> None:
    """Cache-hit path: increment hit_count + refresh last_seen without
    re-inserting. Lighter than write_cache when we know the row already
    exists."""
    now = datetime.utcnow()
    await db.execute(
        update(ScanCache)
        .where(ScanCache.image_hash == image_hash)
        .values(hit_count=ScanCache.hit_count + 1, last_seen=now)
    )
    await db.commit()
