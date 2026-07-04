"""Apply hand-curated image URLs for JPP-U* Unnumbered Promo cards.

For each entry in backend/data/jpp_unn_manual_images.json where the
value is a non-empty URL string, this script:
  - Downloads the URL
  - Saves it locally under frontend/public/jp-unn/{card_id}.{ext}
  - Updates cards.image_small / image_large / updated_at

Idempotent: if the local file already exists AND the DB image_small
already points to it, the entry is skipped. Otherwise the file is
re-downloaded and the DB row repointed (useful when swapping in a
better scan for the same card_id).

Usage:
    cd backend
    python -m scripts.import_jpp_unn_manual_urls
    python -m scripts.import_jpp_unn_manual_urls --dry-run
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote

import httpx
from sqlalchemy import text

from app.database import SessionLocal, init_db

log = logging.getLogger("import_jpp_unn_manual_urls")

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
MIRROR_DIR = REPO_ROOT / "frontend" / "public" / "jp-unn"
MANUAL_FILE = Path(__file__).resolve().parent.parent / "data" / "jpp_unn_manual_images.json"


def _load_manual_map() -> dict[str, str]:
    if not MANUAL_FILE.exists():
        log.error(f"Manual file not found: {MANUAL_FILE}")
        return {}
    with MANUAL_FILE.open("r", encoding="utf-8") as f:
        raw = json.load(f)
    out: dict[str, str] = {}
    for k, v in raw.items():
        if k.startswith("_"):
            continue  # comment fields
        if not isinstance(v, str) or not v.strip():
            continue
        if not re.match(r"^https?://", v.strip()):
            log.warning(f"Skip {k}: value is not a URL: {v!r}")
            continue
        out[k] = v.strip()
    return out


def _guess_ext(url: str, content_type: str | None) -> str:
    filename = unquote(url.rsplit("/", 1)[-1].split("?")[0])
    ext = Path(filename).suffix.lower()
    if ext in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
        return ".jpg" if ext == ".jpeg" else ext
    if content_type:
        ct = content_type.lower()
        if "png" in ct:
            return ".png"
        if "webp" in ct:
            return ".webp"
        if "gif" in ct:
            return ".gif"
        if "jpeg" in ct or "jpg" in ct:
            return ".jpg"
    return ".jpg"


async def run(dry: bool) -> None:
    await init_db()
    MIRROR_DIR.mkdir(parents=True, exist_ok=True)

    manual = _load_manual_map()
    log.info(f"Manual URLs to process: {len(manual)}")
    if not manual:
        log.info("Nothing to do — add URL entries to jpp_unn_manual_images.json")
        return

    async with SessionLocal() as db:
        rows = (await db.execute(text(
            "SELECT id, image_small FROM cards WHERE id = ANY(:ids)"
        ), {"ids": list(manual.keys())})).all()
    existing = {r.id: r.image_small for r in rows}
    missing_ids = set(manual) - set(existing)
    if missing_ids:
        log.warning(f"Not found in DB (skipped): {sorted(missing_ids)}")

    stats = {"downloaded": 0, "skipped_same_url": 0, "failed": 0, "not_in_db": len(missing_ids)}
    updates: list[tuple[str, str]] = []

    async with httpx.AsyncClient(
        headers={"User-Agent": "PullList-ManualImport/1.0 (+https://pulllist.org)"},
        follow_redirects=True,
    ) as client:
        for card_id, url in manual.items():
            if card_id not in existing:
                continue
            try:
                r = await client.get(url, timeout=25)
            except httpx.HTTPError as e:
                log.warning(f"  ! {card_id}: {e}")
                stats["failed"] += 1
                continue
            if r.status_code != 200 or len(r.content) < 500:
                log.warning(f"  ! {card_id}: HTTP {r.status_code} bytes={len(r.content)}")
                stats["failed"] += 1
                continue

            ext = _guess_ext(url, r.headers.get("content-type"))
            dest = MIRROR_DIR / f"{card_id}{ext}"
            local_rel = f"/jp-unn/{card_id}{ext}"

            if existing[card_id] == local_rel and dest.exists():
                stats["skipped_same_url"] += 1
                log.info(f"  = {card_id}: already at {local_rel}")
                continue

            log.info(f"  + {card_id} <- {url}  ({len(r.content)} bytes -> {local_rel})")
            if dry:
                continue

            dest.write_bytes(r.content)
            stats["downloaded"] += 1
            updates.append((card_id, local_rel))

    if updates and not dry:
        async with SessionLocal() as db:
            for cid, path in updates:
                await db.execute(
                    text("""UPDATE cards
                            SET image_small=:p, image_large=:p, updated_at=:now
                            WHERE id=:i"""),
                    {"p": path, "now": datetime.utcnow(), "i": cid},
                )
            await db.commit()
        log.info(f"DB rows updated: {len(updates)}")

    log.info("=== Summary ===")
    for k, v in stats.items():
        log.info(f"  {k}: {v}")
    if dry:
        log.info("MODE: DRY-RUN — no writes")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    asyncio.run(run(args.dry_run))


if __name__ == "__main__":
    main()
