"""Mirror every set logo (EN + JP + KR + CN + TW) to a local folder.

Belt-and-suspenders backup before the planned Cloudflare R2
migration. The catalog leans on a lot of third-party CDNs whose
availability we don't control — koca.shop, hobbyxstore, weserv,
naver phinf, tcgdex, limitless, bulbagarden, pokemon.com, etc. If
any single host goes 410 (as pokemonkorea.co.kr did recently) we
lose that slice of the browser tiles until re-scrape. This backup
gives us a local copy of every currently-valid logo so R2 upload
can pull from disk instead of racing external hosts.

Layout:
    backend/data/logo_backup/{language}/{set_id}.{ext}

Language folder = the DB `language` column value verbatim
(en / ja / ko / zh-cn / zh-tw). Extension is derived from the URL
path (defaults to .png if the URL has no obvious extension — many
proxy URLs like weserv/koca don't advertise one). Idempotent:
existing files are skipped unless --refresh.

Uses subprocess-wrapped curl. urllib and httpx have both bit us
elsewhere in this session (HTTP/1.1 quirks, edge 500s); curl
consistently negotiates HTTP/2 and follows redirects cleanly.

Usage:
    python -m scripts.backup_all_set_logos --dry-run
    python -m scripts.backup_all_set_logos
    python -m scripts.backup_all_set_logos --lang ko --refresh
    python -m scripts.backup_all_set_logos --concurrency 8
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
log = logging.getLogger("backup_all_set_logos")

# repo/backend/data/logo_backup
BACKUP_ROOT = Path(__file__).resolve().parents[1] / "data" / "logo_backup"

_EXT_RE = re.compile(r"\.(png|jpg|jpeg|webp|gif|svg)(?:$|\?)", re.I)


def _extract_ext(url: str) -> str:
    """Return an extension like '.png' from either the URL path or,
    for weserv-style proxies, the wrapped `url=` param."""
    parsed = urlparse(url)
    m = _EXT_RE.search(parsed.path)
    if m:
        return "." + m.group(1).lower().replace("jpeg", "jpg")
    # weserv wraps the real URL in ?url=<encoded>
    qs = parse_qs(parsed.query)
    if "url" in qs:
        inner = unquote(qs["url"][0])
        m = _EXT_RE.search(inner)
        if m:
            return "." + m.group(1).lower().replace("jpeg", "jpg")
    return ".png"


async def _download_one(url: str, out_path: Path) -> tuple[bool, str]:
    if out_path.exists() and out_path.stat().st_size > 0:
        return True, "skip-exists"

    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = out_path.with_suffix(out_path.suffix + ".tmp")

    def _run() -> subprocess.CompletedProcess:
        return subprocess.run(
            ["curl", "-sSL", "-A", "Mozilla/5.0", "--max-time", "20",
             "-o", str(tmp_path), url],
            capture_output=True, text=True, timeout=30,
        )

    try:
        result = await asyncio.to_thread(_run)
    except subprocess.TimeoutExpired:
        if tmp_path.exists():
            tmp_path.unlink()
        return False, "curl-timeout"

    if result.returncode != 0 or not tmp_path.exists():
        if tmp_path.exists():
            tmp_path.unlink()
        return False, f"curl-fail rc={result.returncode} {result.stderr[:80]}"

    size = tmp_path.stat().st_size
    if size < 200:
        # Suspiciously tiny — probably an error page/redirect, not an image.
        # Peek at first bytes.
        head = tmp_path.read_bytes()[:120]
        tmp_path.unlink()
        return False, f"tiny {size}B head={head!r}"

    tmp_path.replace(out_path)
    return True, f"{size}B"


async def _list_targets(lang_filter: str | None) -> list[tuple[str, str, str]]:
    async with SessionLocal() as db:
        sql = ("SELECT id, language, logo_url FROM sets "
               "WHERE logo_url IS NOT NULL AND logo_url <> '' "
               "AND language IN ('en','ja','ko','zh-cn','zh-tw')")
        params: dict = {}
        if lang_filter:
            sql += " AND language = :lang"
            params["lang"] = lang_filter
        sql += " ORDER BY language, id"
        rows = (await db.execute(text(sql), params)).all()
    return [(r.id, r.language, r.logo_url) for r in rows]


async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--lang", default=None,
                    help="Limit to one language (en/ja/ko/zh-cn/zh-tw)")
    ap.add_argument("--refresh", action="store_true",
                    help="Re-download files that already exist on disk")
    ap.add_argument("--concurrency", type=int, default=10)
    args = ap.parse_args()

    await init_db()
    targets = await _list_targets(args.lang)
    log.info(f"planning backup of {len(targets)} logos to {BACKUP_ROOT}")

    by_lang: dict[str, int] = {}
    for _sid, lang, _url in targets:
        by_lang[lang] = by_lang.get(lang, 0) + 1
    for lang, n in sorted(by_lang.items()):
        log.info(f"  {lang}: {n}")

    if args.dry_run:
        log.info("--dry-run: nothing downloaded")
        return 0

    if args.refresh:
        log.info("--refresh: overwriting existing files")

    sem = asyncio.Semaphore(args.concurrency)
    counts = {"ok": 0, "skip": 0, "fail": 0}
    failures: list[tuple[str, str, str, str]] = []

    async def _do(sid: str, lang: str, url: str):
        ext = _extract_ext(url)
        out = BACKUP_ROOT / lang / f"{sid}{ext}"
        if args.refresh and out.exists():
            out.unlink()
        async with sem:
            ok, why = await _download_one(url, out)
        if ok:
            if why == "skip-exists":
                counts["skip"] += 1
            else:
                counts["ok"] += 1
            log.info(f"  [{lang}] {sid:22s} {why}")
        else:
            counts["fail"] += 1
            failures.append((sid, lang, url, why))
            log.warning(f"  [{lang}] {sid:22s} FAIL {why}")

    await asyncio.gather(*(_do(sid, lang, url) for sid, lang, url in targets))

    log.info("=== summary ===")
    log.info(f"  downloaded: {counts['ok']}")
    log.info(f"  skipped (already on disk): {counts['skip']}")
    log.info(f"  failed: {counts['fail']}")
    if failures:
        log.info("=== failures ===")
        for sid, lang, url, why in failures:
            log.info(f"  [{lang}] {sid}  {why}  url={url[:100]}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
