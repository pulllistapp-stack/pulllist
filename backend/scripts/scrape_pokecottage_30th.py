"""Scrape every image asset pokecottage.com hosts for the 30th
Anniversary card list page and mirror them into LO's local backup
directory.

pokecottage.com/sets/30th-anniversary-card-list/ serves 27 webp
assets from Squarespace's CDN:
    - 4 "Pokemon 30th Anniversary Card List{N}.webp" collage sheets
      (the actual revealed card art, laid out grid-per-image)
    - 16 "30th Anniversary Celebration Product List{N}.webp" product
      shots (ETBs, blisters, tins, bundles, etc.)
    - Plus a handful of orphaned ETB / binder / booster bundle
      individual shots

Individual cards aren't independently addressable — they're baked
into the collage sheets. This script's job is just to grab all 27
files and stash them locally so we can slice them up later, use
them as set-page hero art, or feed them back into the reveal card
lookups.

Layout:
    PullList_ImageBackup/set-previews/me30/{sanitized_filename}
    PullList_ImageBackup/set-previews/me30/_manifest.json

Idempotent — files already on disk are skipped. Same shape as
backup_en_card_images.py so the delete/re-run story is consistent.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import re
import time
import urllib.parse as up
from pathlib import Path

import httpx


PAGE = "https://pokecottage.com/sets/30th-anniversary-card-list/"
DEST_DEFAULT = Path(r"C:\Users\Jinwon\Desktop\PullList_ImageBackup\set-previews\me30")

BROWSER_HDRS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": PAGE,
}


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("scrape_pokecottage_30th")


def _sanitize(url: str) -> str:
    """Turn a Squarespace-CDN URL into a Windows-safe filename.
    Keeps only the basename before any query string, unquotes '+',
    and strips characters Windows won't allow in filenames."""
    tail = url.rsplit("/", 1)[-1].split("?")[0]
    tail = up.unquote(tail)
    tail = tail.replace("+", " ")
    tail = re.sub(r'[<>:"|?*\x00-\x1f]', "", tail)
    return tail.strip()[:180]


async def main(dest: Path, dry_run: bool) -> None:
    dest.mkdir(parents=True, exist_ok=True)

    async with httpx.AsyncClient(
        timeout=45, headers=BROWSER_HDRS, follow_redirects=True
    ) as c:
        log.info("fetching listing page")
        r = await c.get(PAGE)
        r.raise_for_status()
        html = r.text

        # Grab EVERY Squarespace CDN reference regardless of tag or
        # attribute — the individual-card jpg/webp files (30C+victini+
        # 013.jpg etc.) live inside lightbox / gallery structures the
        # narrower attribute-scoped regex misses. Filter out favicons +
        # non-image assets after the fact.
        raw_urls = re.findall(
            r'(https://images\.squarespace-cdn\.com/[^\s"\'<>]+)',
            html,
        )
        # Drop query strings for dedup; keep the first version's URL.
        seen: dict[str, str] = {}
        for u in raw_urls:
            base = u.split("?")[0]
            if base not in seen:
                seen[base] = u
        urls = [
            u for u in seen.values()
            if not any(skip in u.lower() for skip in ("favicon", ".ico"))
            and re.search(r"\.(?:webp|png|jpg|jpeg)(?:\?|$)", u, re.IGNORECASE)
        ]
        log.info("found %d distinct Squarespace CDN URLs", len(urls))

        stats = {"downloaded": 0, "skipped": 0, "failed": 0, "bytes": 0}
        started = time.time()
        rows: list[dict] = []

        for i, url in enumerate(urls, 1):
            fname = _sanitize(url)
            path = dest / fname
            if path.exists():
                stats["skipped"] += 1
                log.info("  [%d/%d] skip (exists): %s", i, len(urls), fname)
                rows.append({"url": url, "path": str(path), "status": "skipped"})
                continue

            try:
                r2 = await c.get(url)
                if r2.status_code != 200 or not r2.content:
                    stats["failed"] += 1
                    log.warning(
                        "  [%d/%d] HTTP %s: %s",
                        i, len(urls), r2.status_code, fname,
                    )
                    rows.append({"url": url, "status": "failed", "http": r2.status_code})
                    continue
                if not dry_run:
                    path.write_bytes(r2.content)
                stats["downloaded"] += 1
                stats["bytes"] += len(r2.content)
                log.info(
                    "  [%d/%d] %s (%d bytes)",
                    i, len(urls), fname, len(r2.content),
                )
                rows.append({
                    "url": url,
                    "path": str(path),
                    "bytes": len(r2.content),
                    "status": "downloaded",
                })
            except httpx.HTTPError as e:
                stats["failed"] += 1
                log.warning("  [%d/%d] error: %s", i, len(urls), e)
                rows.append({"url": url, "status": "error", "error": str(e)})

        manifest = {
            "source_page": PAGE,
            "downloaded_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "elapsed_seconds": round(time.time() - started, 1),
            "total_mb": round(stats["bytes"] / 1024 / 1024, 2),
            "counts": stats,
            "files": rows,
        }
        if not dry_run:
            (dest / "_manifest.json").write_text(
                json.dumps(manifest, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

    log.info("=== summary ===")
    for k, v in stats.items():
        log.info("  %s: %s", k, v)
    log.info("  dest: %s", dest)
    log.info("  dry_run: %s", dry_run)


def cli() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dest", type=Path, default=DEST_DEFAULT)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    asyncio.run(main(args.dest, args.dry_run))


if __name__ == "__main__":
    cli()
