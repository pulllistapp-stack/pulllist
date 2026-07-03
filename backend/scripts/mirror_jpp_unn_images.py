"""Download JPP-U* card images to frontend/public/jp-unn/ so we can serve
them ourselves. Bulbapedia archives 403s requests with an off-domain
Referer (Next.js Image proxy hits this too when it forwards the origin),
so mirroring is more reliable than any live proxy.

Skips files already on disk. Idempotent.
"""
from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path
from urllib.parse import unquote, quote

import httpx
from sqlalchemy import text

from app.database import SessionLocal, init_db

log = logging.getLogger("mirror_jpp_unn_images")

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
MIRROR_DIR = REPO_ROOT / "frontend" / "public" / "jp-unn"


async def run() -> None:
    await init_db()
    MIRROR_DIR.mkdir(parents=True, exist_ok=True)

    async with SessionLocal() as db:
        rows = (await db.execute(text("""
          SELECT id, image_small FROM cards
          WHERE set_id LIKE 'JPP-U%' AND language='ja'
            AND image_small IS NOT NULL
        """))).all()

    log.info(f"targets: {len(rows)} cards")
    updates: list[tuple[str, str]] = []
    downloaded = skipped = failed = 0

    async with httpx.AsyncClient(
        # No Referer header — Bulbapedia archives 403s off-domain refs.
        headers={"User-Agent": "PullList-Mirror/1.0"},
        follow_redirects=True,
    ) as c:
        for card_id, cur_url in rows:
            # Unwrap the weserv shim if it's already there.
            m = re.match(r"^https://images\.weserv\.nl/\?url=(.+)$", cur_url)
            src_url = unquote(m.group(1)) if m else cur_url

            filename = src_url.rsplit("/", 1)[-1]
            ext = Path(filename).suffix or ".jpg"
            dest = MIRROR_DIR / f"{card_id}{ext}"
            local_rel = f"/jp-unn/{card_id}{ext}"

            if dest.exists() and dest.stat().st_size > 0:
                skipped += 1
                if cur_url != local_rel:
                    updates.append((card_id, local_rel))
                continue

            try:
                r = await c.get(src_url, timeout=25)
            except httpx.HTTPError as e:
                log.warning(f"  ! {card_id}: {e}")
                failed += 1
                continue
            if r.status_code != 200 or len(r.content) < 500:
                log.warning(f"  ! {card_id}: HTTP {r.status_code} bytes={len(r.content)}")
                failed += 1
                continue

            dest.write_bytes(r.content)
            downloaded += 1
            updates.append((card_id, local_rel))

    if updates:
        async with SessionLocal() as db:
            for cid, path in updates:
                await db.execute(
                    text("UPDATE cards SET image_small=:p WHERE id=:i"),
                    {"p": path, "i": cid},
                )
            await db.commit()

    log.info(f"\n=== Summary ===")
    log.info(f"  downloaded: {downloaded}")
    log.info(f"  skipped (already on disk): {skipped}")
    log.info(f"  failed: {failed}")
    log.info(f"  DB rows repointed: {len(updates)}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    asyncio.run(run())
