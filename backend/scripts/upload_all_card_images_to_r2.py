"""Upload every locally-backed-up card image to Cloudflare R2 and
swap the DB `cards.image_small` / `image_large` columns.

Reads from two source roots:
  A. C:\\Users\\Jinwon\\Desktop\\PullList_ImageBackup\\en\\{set (name)}\\
     — LO's separately-maintained EN backup, 41k files, `{card_id}_
     {small|large}.{ext}` inside per-set folders whose names have
     the pretty English set name in parentheses.
  B. backend/data/card_backup/{lang}/{set_id}/{card_id}_{small|large}.{ext}
     — fresh JP/KR/CN/TW backup + the EN me5/me30 gap fill, all
     with clean {set_id}/ folder names.

Upload target: `card-images/{lang}/{set_id}/{card_id}_{small|large}.{ext}`
in the same R2 bucket that holds set logos (pulllist-setslogosbackup).
R2 free tier is 10GB and this pushes us to ~23.6GB → ~$0.20/mo
Standard-class overage. LO already accepted this on the plan.

DB swap: for every uploaded (card_id, suffix) pair, UPDATE the
corresponding column. If _large exists but _small doesn't, both
columns get the _large URL (matches how KR/CN/TW rows already
store the same URL in both columns).

Idempotent. Concurrency defaults to 12 for the upload phase.

Usage:
    python -m scripts.upload_all_card_images_to_r2 --dry-run
    python -m scripts.upload_all_card_images_to_r2                   # full
    python -m scripts.upload_all_card_images_to_r2 --lang en         # subset
    python -m scripts.upload_all_card_images_to_r2 --skip-upload     # DB only
"""
from __future__ import annotations
import argparse
import asyncio
import io
import logging
import mimetypes
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import boto3  # noqa: E402
from botocore.config import Config  # noqa: E402
from sqlalchemy import text  # noqa: E402
from app.database import SessionLocal, init_db  # noqa: E402

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("upload_all_card_images_to_r2")

PULLLIST_EN_ROOT = Path(r"C:\Users\Jinwon\Desktop\PullList_ImageBackup\en")
CARD_BACKUP_ROOT = Path(__file__).resolve().parents[1] / "data" / "card_backup"

# `{set_id} (Set Name)` — capture just the set_id chunk before the
# opening paren.
_EN_SET_DIR_RE = re.compile(r"^([^\s(]+)")
# `{card_id}_small.jpg` / `_large.png` etc.
_CARD_FILENAME_RE = re.compile(r"^(.+)_(small|large)\.(png|jpg|jpeg|webp|gif)$", re.I)


def _r2_client():
    endpoint = os.environ["R2_ENDPOINT"]
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
        config=Config(signature_version="s3v4",
                      s3={"addressing_style": "path"}),
        region_name="auto",
    )


def _content_type(path: Path) -> str:
    mt, _ = mimetypes.guess_type(str(path))
    return mt or "application/octet-stream"


def _en_set_id_from_dirname(name: str) -> str | None:
    m = _EN_SET_DIR_RE.match(name)
    return m.group(1) if m else None


def _iter_pulllist_en() -> list[tuple[str, str, str, str, Path]]:
    """Return [(lang, set_id, card_id, suffix, path), ...] for
    PullList_ImageBackup/en/*/*.jpg."""
    out: list[tuple[str, str, str, str, Path]] = []
    if not PULLLIST_EN_ROOT.exists():
        return out
    for set_dir in PULLLIST_EN_ROOT.iterdir():
        if not set_dir.is_dir():
            continue
        set_id = _en_set_id_from_dirname(set_dir.name)
        if not set_id:
            continue
        for f in set_dir.iterdir():
            if not f.is_file():
                continue
            m = _CARD_FILENAME_RE.match(f.name)
            if not m:
                continue
            card_id, suffix, ext = m.group(1), m.group(2).lower(), m.group(3).lower()
            out.append(("en", set_id, card_id, suffix, f))
    return out


def _iter_card_backup() -> list[tuple[str, str, str, str, Path]]:
    out: list[tuple[str, str, str, str, Path]] = []
    if not CARD_BACKUP_ROOT.exists():
        return out
    for lang_dir in CARD_BACKUP_ROOT.iterdir():
        if not lang_dir.is_dir():
            continue
        lang = lang_dir.name
        for set_dir in lang_dir.iterdir():
            if not set_dir.is_dir():
                continue
            set_id = set_dir.name
            for f in set_dir.iterdir():
                if not f.is_file():
                    continue
                m = _CARD_FILENAME_RE.match(f.name)
                if not m:
                    continue
                card_id, suffix, ext = m.group(1), m.group(2).lower(), m.group(3).lower()
                out.append((lang, set_id, card_id, suffix, f))
    return out


def _r2_key(lang: str, set_id: str, card_id: str, suffix: str, ext: str) -> str:
    return f"card-images/{lang}/{set_id}/{card_id}_{suffix}.{ext}"


async def _upload_all(bucket: str, targets: list[tuple[str, str, str, str, Path]],
                      dry_run: bool, concurrency: int
                      ) -> dict[tuple[str, str], dict[str, str]]:
    """Upload every target file. Returns {(lang, card_id): {suffix: key}}
    so the DB-swap phase can look up which small/large URL each card
    has available."""
    client = None if dry_run else _r2_client()
    sem = asyncio.Semaphore(concurrency)
    uploaded: dict[tuple[str, str], dict[str, str]] = defaultdict(dict)
    counts = {"ok": 0, "fail": 0}
    processed = 0
    total = len(targets)
    lock = asyncio.Lock()

    async def _one(lang: str, set_id: str, card_id: str,
                   suffix: str, path: Path):
        nonlocal processed
        ext = path.suffix.lstrip(".").lower().replace("jpeg", "jpg")
        key = _r2_key(lang, set_id, card_id, suffix, ext)
        if dry_run:
            async with lock:
                uploaded[(lang, card_id)][suffix] = key
                processed += 1
                if processed % 5000 == 0:
                    log.info(f"  planned {processed}/{total}")
            return
        try:
            def _put():
                with path.open("rb") as body:
                    client.put_object(
                        Bucket=bucket, Key=key, Body=body,
                        ContentType=_content_type(path),
                        CacheControl="public, max-age=31536000, immutable",
                    )
            async with sem:
                await asyncio.to_thread(_put)
            uploaded[(lang, card_id)][suffix] = key
            async with lock:
                counts["ok"] += 1
                processed += 1
                if processed % 500 == 0:
                    log.info(f"  progress: {processed}/{total} "
                             f"(ok={counts['ok']} fail={counts['fail']})")
        except Exception as e:
            async with lock:
                counts["fail"] += 1
                processed += 1
            log.warning(f"  FAIL {key}: {e}")

    await asyncio.gather(*(
        _one(l, s, c, suf, p) for (l, s, c, suf, p) in targets
    ))
    log.info(f"upload phase: {counts}")
    return uploaded


async def _swap_urls(uploaded: dict[tuple[str, str], dict[str, str]],
                     dry_run: bool):
    public_base = os.environ["R2_PUBLIC_URL"].rstrip("/")
    await init_db()
    async with SessionLocal() as db:
        # Fetch every card we might touch
        card_ids = [cid for (_lang, cid) in uploaded.keys()]
        if not card_ids:
            log.info("no rows to swap")
            return
        # Chunk WHERE IN to avoid parameter limits
        planned: list[tuple[str, str, str]] = []
        CHUNK = 1000
        for i in range(0, len(card_ids), CHUNK):
            batch = card_ids[i:i + CHUNK]
            rows = (await db.execute(
                text("SELECT id, language, image_small, image_large "
                     "FROM cards WHERE id = ANY(:ids)"),
                {"ids": batch},
            )).all()
            for row in rows:
                have = uploaded.get((row.language, row.id))
                if not have:
                    continue
                large_key = have.get("large")
                small_key = have.get("small") or have.get("large")
                if large_key:
                    new_large = f"{public_base}/{large_key}"
                    new_small = f"{public_base}/{small_key}"
                    if row.image_large != new_large or row.image_small != new_small:
                        planned.append((row.id, new_small, new_large))

        log.info(f"planned DB swaps: {len(planned)}")
        for sid, sm, lg in planned[:5]:
            log.info(f"  {sid:35s} small={sm[:60]!r}")
            log.info(f"    large={lg}")

        if dry_run:
            log.info("--dry-run: no DB writes")
            return

        # Batched UPDATE — 74k sequential UPDATE-per-row timed out
        # the Render Postgres connection ("connection was closed in
        # the middle of operation"). Bulk via UNNEST arrays keeps
        # round-trip count small and works cleanly with asyncpg.
        CHUNK = 500
        total_written = 0
        for i in range(0, len(planned), CHUNK):
            batch = planned[i:i + CHUNK]
            await db.execute(text("""
                UPDATE cards
                   SET image_small = v.small,
                       image_large = v.large,
                       updated_at = NOW()
                  FROM (SELECT UNNEST(CAST(:ids AS varchar[])) AS id,
                               UNNEST(CAST(:smalls AS varchar[])) AS small,
                               UNNEST(CAST(:larges AS varchar[])) AS large) v
                 WHERE cards.id = v.id
            """), {
                "ids": [row[0] for row in batch],
                "smalls": [row[1] for row in batch],
                "larges": [row[2] for row in batch],
            })
            await db.commit()  # commit per batch — resilient to reconnect
            total_written += len(batch)
            if (i // CHUNK) % 10 == 0:
                log.info(f"  swapped {total_written}/{len(planned)}")
        log.info(f"swapped {total_written} cards.image_small/large in DB")


async def main() -> int:
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--lang", default=None,
                    help="Filter to one language (en/ja/ko/zh-cn/zh-tw)")
    ap.add_argument("--skip-upload", action="store_true")
    ap.add_argument("--skip-db", action="store_true")
    ap.add_argument("--concurrency", type=int, default=12)
    args = ap.parse_args()

    bucket = os.environ["R2_BUCKET"]
    log.info(f"bucket: {bucket}")
    log.info(f"public: {os.environ.get('R2_PUBLIC_URL')}")

    # Enumerate both source roots
    targets = _iter_pulllist_en() + _iter_card_backup()
    if args.lang:
        targets = [t for t in targets if t[0] == args.lang]
    # Dedupe: prefer PullList_ImageBackup version if both roots have
    # the same file (unlikely — different set dir naming — but safe).
    seen: set[tuple[str, str, str, str]] = set()
    deduped = []
    for t in targets:
        key = (t[0], t[1], t[2], t[3])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(t)
    targets = deduped

    log.info(f"total upload targets: {len(targets)}")
    by_lang: dict[str, int] = {}
    for lang, *_ in targets:
        by_lang[lang] = by_lang.get(lang, 0) + 1
    for lang, n in sorted(by_lang.items()):
        log.info(f"  {lang}: {n}")

    if args.skip_upload:
        # Rebuild uploaded map from the target list (assume prior run)
        uploaded: dict[tuple[str, str], dict[str, str]] = defaultdict(dict)
        for lang, set_id, card_id, suffix, path in targets:
            ext = path.suffix.lstrip(".").lower().replace("jpeg", "jpg")
            uploaded[(lang, card_id)][suffix] = _r2_key(lang, set_id, card_id, suffix, ext)
        log.info(f"skip-upload: inferred {sum(len(v) for v in uploaded.values())} keys")
    else:
        uploaded = await _upload_all(bucket, targets, args.dry_run, args.concurrency)

    if not args.skip_db:
        await _swap_urls(uploaded, args.dry_run)

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
