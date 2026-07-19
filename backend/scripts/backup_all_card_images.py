"""Mirror every card image (JP + KR + CN + TW) to a local folder.

EN is already backed up separately in
`C:\\Users\\Jinwon\\Desktop\\PullList_ImageBackup\\en\\` (17GB, ~41k
files, small+large per card). Skipping EN here — the eventual R2
upload script reads from both roots.

For JP the `image_small` and `image_large` URLs are usually
different (differ=19,335 of 21k), so both are downloaded. For
KR/CN/TW the two columns hold the same URL, so we only fetch
image_large (and later serve both DB columns from the same file).

Layout:
    backend/data/card_backup/{lang}/{set_id}/{card_id}_small.{ext}
    backend/data/card_backup/{lang}/{set_id}/{card_id}_large.{ext}

Idempotent — existing files are skipped unless --refresh.
Failures logged per-row; script exits 0 even if some fail (the
sources we scrape from have flaky uptime and a 0.5% miss rate is
normal).

Uses subprocess-wrapped curl — same shape as backup_all_set_logos.py.
Concurrent via asyncio semaphore (default 10, tune with --concurrency).

Usage:
    python -m scripts.backup_all_card_images --dry-run
    python -m scripts.backup_all_card_images                  # JP+KR+CN+TW
    python -m scripts.backup_all_card_images --lang zh-tw     # smallest first
    python -m scripts.backup_all_card_images --concurrency 15
"""
from __future__ import annotations
import argparse
import asyncio
import io
import logging
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse, parse_qs, unquote

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402
from app.database import SessionLocal, init_db  # noqa: E402

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("backup_all_card_images")

BACKUP_ROOT = Path(__file__).resolve().parents[1] / "data" / "card_backup"

# EN is already backed up outside the repo — skip it here.
DEFAULT_LANGS = ("ja", "ko", "zh-cn", "zh-tw")

_EXT_RE = re.compile(r"\.(png|jpg|jpeg|webp|gif)(?:$|\?)", re.I)


def _extract_ext(url: str) -> str:
    parsed = urlparse(url)
    m = _EXT_RE.search(parsed.path)
    if m:
        return "." + m.group(1).lower().replace("jpeg", "jpg")
    qs = parse_qs(parsed.query)
    if "url" in qs:
        inner = unquote(qs["url"][0])
        m = _EXT_RE.search(inner)
        if m:
            return "." + m.group(1).lower().replace("jpeg", "jpg")
    return ".jpg"


def _sanitize_set_id(s: str) -> str:
    """Some set IDs have chars invalid on Windows filesystems (mostly
    fine for our zh-tw/zh-cn/ko/ja IDs, but defensive)."""
    return re.sub(r'[<>:"|?*\x00-\x1f]', "_", s)


async def _download(url: str, out_path: Path) -> tuple[bool, str]:
    if out_path.exists() and out_path.stat().st_size > 0:
        return True, "skip-exists"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(out_path.suffix + ".tmp")

    def _run() -> subprocess.CompletedProcess:
        return subprocess.run(
            ["curl", "-sSL", "-A", "Mozilla/5.0", "--max-time", "20",
             "-o", str(tmp), url],
            capture_output=True, text=True, timeout=30,
        )

    try:
        result = await asyncio.to_thread(_run)
    except subprocess.TimeoutExpired:
        if tmp.exists():
            tmp.unlink()
        return False, "curl-timeout"

    if result.returncode != 0 or not tmp.exists():
        if tmp.exists():
            tmp.unlink()
        return False, f"curl-fail rc={result.returncode}"

    size = tmp.stat().st_size
    if size < 200:
        head = tmp.read_bytes()[:120]
        tmp.unlink()
        return False, f"tiny {size}B head={head[:60]!r}"

    tmp.replace(out_path)
    return True, f"{size}B"


async def _list_targets(langs: tuple[str, ...],
                        set_filter: str | None) -> list[tuple[str, str, str, str, str]]:
    """Return list of (card_id, language, set_id, image_small, image_large)."""
    async with SessionLocal() as db:
        placeholders = ", ".join(f":lang{i}" for i in range(len(langs)))
        sql = (f"SELECT id, language, set_id, image_small, image_large "
               f"FROM cards "
               f"WHERE language IN ({placeholders}) "
               f"AND image_small IS NOT NULL")
        params: dict = {f"lang{i}": l for i, l in enumerate(langs)}
        if set_filter:
            sql += " AND set_id = :sid"
            params["sid"] = set_filter
        sql += " ORDER BY language, set_id, id"
        rows = (await db.execute(text(sql), params)).all()
    return [(r.id, r.language, r.set_id, r.image_small, r.image_large or r.image_small)
            for r in rows]


async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--lang", default=None,
                    help="Limit to one language (defaults to ja/ko/zh-cn/zh-tw)")
    ap.add_argument("--set", dest="set_filter", default=None,
                    help="Limit to one set_id (for testing)")
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--concurrency", type=int, default=10)
    args = ap.parse_args()

    langs = (args.lang,) if args.lang else DEFAULT_LANGS
    await init_db()
    targets = await _list_targets(langs, args.set_filter)
    log.info(f"planning backup of {len(targets)} cards to {BACKUP_ROOT}")

    by_lang: dict[str, int] = {}
    for _cid, lang, _sid, _s, _l in targets:
        by_lang[lang] = by_lang.get(lang, 0) + 1
    for lang, n in sorted(by_lang.items()):
        log.info(f"  {lang}: {n}")

    if args.dry_run:
        log.info("--dry-run: nothing downloaded")
        return 0

    sem = asyncio.Semaphore(args.concurrency)
    counts = {"ok": 0, "skip": 0, "fail": 0}
    processed = 0
    lock = asyncio.Lock()

    async def _do(card_id: str, lang: str, set_id: str,
                  small_url: str, large_url: str):
        nonlocal processed
        safe_set = _sanitize_set_id(set_id)
        safe_card = _sanitize_set_id(card_id)
        # Save both when URLs differ; otherwise one _large is enough.
        wants = [("_large", large_url)]
        if small_url != large_url:
            wants.append(("_small", small_url))

        for suffix, url in wants:
            ext = _extract_ext(url)
            out = BACKUP_ROOT / lang / safe_set / f"{safe_card}{suffix}{ext}"
            if args.refresh and out.exists():
                out.unlink()
            async with sem:
                ok, why = await _download(url, out)
            if ok:
                if why == "skip-exists":
                    counts["skip"] += 1
                else:
                    counts["ok"] += 1
            else:
                counts["fail"] += 1
                log.warning(f"  [{lang}/{set_id}] {card_id}{suffix} FAIL {why}")

        async with lock:
            processed += 1
            if processed % 500 == 0:
                log.info(f"  progress: {processed}/{len(targets)} cards "
                         f"(ok={counts['ok']} skip={counts['skip']} fail={counts['fail']})")

    await asyncio.gather(*(
        _do(cid, lang, sid, s, l)
        for cid, lang, sid, s, l in targets
    ))

    log.info("=== summary ===")
    log.info(f"  downloaded: {counts['ok']}")
    log.info(f"  skipped (already on disk): {counts['skip']}")
    log.info(f"  failed: {counts['fail']}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
