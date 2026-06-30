"""Download every externally-hosted JP card image to a local folder.

Acts as a permanent archive against the day Bulbapedia / learn-book /
nazonobasho rotates filenames or goes down. Doesn't touch the DB —
image_small still points at the live URL. The local copy is your
insurance: when a source dies, you have the bytes and can re-host
(Cloudflare R2, Vercel /public, anywhere) and bulk-rewrite image_small.

Layout on disk:
  {OUT_ROOT}/
    PMCG1/
      001.jpg
      002.jpg
      ...
    E1/
      001.jpg
      ...

Default OUT_ROOT is C:\\Users\\Jinwon\\Desktop\\PokeRadar\\backups\\jp_images
— override with --out.

Usage:
    python -m scripts.download_jp_images_local           # full sweep
    python -m scripts.download_jp_images_local --dry-run
    python -m scripts.download_jp_images_local --set PCG9
    python -m scripts.download_jp_images_local --skip-existing  # default
"""
from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path

import httpx
from sqlalchemy import text

from app.database import SessionLocal, init_db

log = logging.getLogger("download_jp_images_local")

DEFAULT_OUT = Path(r"C:\Users\Jinwon\Desktop\PokeRadar\backups\jp_images")

# Hosts we want to archive. External-only — skip the in-house URLs
# (TCGdex, Limitless, etc.) since those have their own SLA.
ARCHIVE_HOSTS = (
    "archives.bulbagarden.net",  # PMCG/E1/VS1/web1
    "learn-book.com",            # PCG1-9
    "nazonobasho.com",           # E1-E5 JP native
)

SEM = 8


def _ext_from_url(url: str) -> str:
    """Return .jpg / .png / .webp from URL, defaulting to .jpg."""
    lower = url.lower()
    for ext in (".jpg", ".jpeg", ".png", ".webp"):
        if ext in lower:
            return ext
    return ".jpg"


async def _download_one(c: httpx.AsyncClient, url: str, dest: Path) -> tuple[bool, str]:
    if dest.exists() and dest.stat().st_size > 0:
        return True, "exists"
    try:
        r = await c.get(url, timeout=30)
    except httpx.HTTPError as e:
        return False, f"fetch: {e}"
    if r.status_code != 200:
        return False, f"HTTP {r.status_code}"
    if len(r.content) < 500:
        return False, f"too small ({len(r.content)} bytes)"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(r.content)
    return True, "downloaded"


async def run(out_root: Path, only: str | None, dry: bool) -> None:
    await init_db()

    host_pattern = "(" + "|".join(ARCHIVE_HOSTS) + ")"
    sql = """
        SELECT id, set_id, number, image_small
        FROM cards
        WHERE language='ja'
          AND image_small IS NOT NULL
          AND image_small ~ :hostpat
    """
    params = {"hostpat": host_pattern}
    if only:
        sql += " AND set_id = :sid"
        params["sid"] = only

    async with SessionLocal() as db:
        rows = (await db.execute(text(sql), params)).all()

    log.info(f"Targets: {len(rows)} JP cards with externally-hosted images")
    log.info(f"Out root: {out_root}")
    if dry:
        log.info("MODE: DRY-RUN — listing first 5:")
        for cid, sid, num, url in rows[:5]:
            log.info(f"  {sid}/{num or '?'}{_ext_from_url(url)}  ←  {url}")
        return

    sem = asyncio.Semaphore(SEM)
    done = exists = failed = 0

    async def task(cid: str, sid: str, num: str | None, url: str):
        nonlocal done, exists, failed
        # Use 3-digit zero-pad if number is numeric, else card_id suffix
        try:
            label = f"{int(num):03d}" if num and num.isdigit() else (num or cid)
        except (ValueError, TypeError):
            label = num or cid
        dest = out_root / sid / f"{label}{_ext_from_url(url)}"
        async with sem:
            ok, msg = await _download_one(c, url, dest)
        if ok and msg == "exists":
            exists += 1
        elif ok:
            done += 1
        else:
            failed += 1
            log.warning(f"  ! {sid}/{label}: {msg}")

    async with httpx.AsyncClient(
        headers={"User-Agent": "PullList-Archive/1.0"}, follow_redirects=True
    ) as c:
        await asyncio.gather(*[task(*r) for r in rows])

    log.info("\n=== Summary ===")
    log.info(f"  downloaded:    {done}")
    log.info(f"  already cached: {exists}")
    log.info(f"  failed:         {failed}")
    log.info(f"  total on disk:  {sum(1 for _ in out_root.rglob('*.jpg'))}")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, default=DEFAULT_OUT, help="Destination root")
    p.add_argument("--set", dest="only", help="One set id (e.g. PCG9)")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    asyncio.run(run(args.out, args.only, args.dry_run))


if __name__ == "__main__":
    main()
