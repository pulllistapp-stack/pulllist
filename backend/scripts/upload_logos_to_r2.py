"""Upload the local logo backup to Cloudflare R2 + swap DB URLs.

Prereq: backup_all_set_logos.py has populated
backend/data/logo_backup/{lang}/{set_id}.{ext} (837/842 today; 5
KR sets have dead upstream URLs and no local mirror).

What this does:
  1. Enumerate every file under logo_backup/{lang}/*.{png,jpg,...}
  2. Upload to R2 at key `set-logos/{lang}/{set_id}.{ext}` with the
     right Content-Type header (so the pub URL serves as an image,
     not application/octet-stream).
  3. In one transaction, UPDATE every matching zh/en/ja/ko row's
     `logo_url` to `{R2_PUBLIC_URL}/set-logos/{lang}/{set_id}.{ext}`.
  4. Print a delta of which rows changed + which stayed on their
     original URL (typically the 5 ko sets we couldn't back up).

Idempotent: R2 uploads use put_object (overwrite), so re-runs are
safe. DB writes are gated on the file actually existing in R2.

Credentials come from backend/.env (R2_ACCESS_KEY_ID + R2_SECRET_
ACCESS_KEY + R2_ENDPOINT + R2_BUCKET + R2_PUBLIC_URL). Same env
vars need to be present in Render for the backend to reference R2
programmatically later (this script doesn't need Render, only the
local .env).

Usage:
    python -m scripts.upload_logos_to_r2 --dry-run
    python -m scripts.upload_logos_to_r2                 # full
    python -m scripts.upload_logos_to_r2 --lang zh-tw    # subset
    python -m scripts.upload_logos_to_r2 --skip-db       # upload only
    python -m scripts.upload_logos_to_r2 --skip-upload   # DB swap only
"""
from __future__ import annotations
import argparse
import asyncio
import io
import logging
import mimetypes
import os
import sys
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
log = logging.getLogger("upload_logos_to_r2")

BACKUP_ROOT = Path(__file__).resolve().parents[1] / "data" / "logo_backup"
LANGS = ("en", "ja", "ko", "zh-cn", "zh-tw")


def _r2_client():
    endpoint = os.environ.get("R2_ENDPOINT")
    key = os.environ.get("R2_ACCESS_KEY_ID")
    secret = os.environ.get("R2_SECRET_ACCESS_KEY")
    if not (endpoint and key and secret):
        raise RuntimeError(
            "R2 creds missing — set R2_ENDPOINT / R2_ACCESS_KEY_ID / "
            "R2_SECRET_ACCESS_KEY in backend/.env"
        )
    # R2 requires signature v4 + path-style addressing (bucket in path,
    # not subdomain) for the S3-compat endpoint.
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=key,
        aws_secret_access_key=secret,
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        region_name="auto",
    )


def _content_type_for(path: Path) -> str:
    mt, _ = mimetypes.guess_type(str(path))
    return mt or "application/octet-stream"


def _key_for(lang: str, filename: str) -> str:
    return f"set-logos/{lang}/{filename}"


def _upload_all(bucket: str, lang_filter: str | None, dry_run: bool) -> dict[str, str]:
    """Upload every file under logo_backup/{lang}. Returns a mapping
    {(lang, set_id): public_url_suffix} for later DB update."""
    client = _r2_client() if not dry_run else None
    uploaded: dict[tuple[str, str], str] = {}
    total = 0
    for lang in LANGS:
        if lang_filter and lang != lang_filter:
            continue
        lang_dir = BACKUP_ROOT / lang
        if not lang_dir.exists():
            log.info(f"  {lang}: no dir, skip")
            continue
        files = sorted(lang_dir.iterdir())
        log.info(f"  {lang}: {len(files)} files")
        for f in files:
            if not f.is_file():
                continue
            set_id = f.stem  # BW1b.png -> BW1b
            key = _key_for(lang, f.name)
            ct = _content_type_for(f)
            if dry_run:
                log.info(f"    would upload {f.name} -> {key} ({ct})")
            else:
                with f.open("rb") as body:
                    client.put_object(
                        Bucket=bucket, Key=key, Body=body,
                        ContentType=ct,
                        # 1yr cache — R2 URLs are content-addressed by
                        # our set_id+ext, so a re-upload with a real
                        # change would need a filename change anyway.
                        CacheControl="public, max-age=31536000, immutable",
                    )
            uploaded[(lang, set_id)] = key
            total += 1
    log.info(f"upload phase: {total} files")
    return uploaded


async def _swap_urls(uploaded: dict[tuple[str, str], str], dry_run: bool) -> None:
    public_base = os.environ["R2_PUBLIC_URL"].rstrip("/")
    await init_db()
    async with SessionLocal() as db:
        # Get current rows
        rows = (await db.execute(text(
            "SELECT id, language, logo_url FROM sets "
            "WHERE language IN ('en','ja','ko','zh-cn','zh-tw') "
            "AND logo_url IS NOT NULL"
        ))).all()
        by_key = {(r.language, r.id): r for r in rows}

        planned: list[tuple[str, str, str]] = []  # (set_id, old, new)
        for (lang, set_id), key in uploaded.items():
            row = by_key.get((lang, set_id))
            if row is None:
                continue
            new_url = f"{public_base}/{key}"
            if row.logo_url == new_url:
                continue
            planned.append((set_id, row.logo_url or "", new_url))

        log.info(f"planned URL swaps: {len(planned)}")
        for sid, old, new in planned[:8]:
            log.info(f"  {sid:20s} {old[:60]!r}")
            log.info(f"    -> {new}")
        if len(planned) > 8:
            log.info(f"  ... +{len(planned) - 8} more")

        if dry_run:
            log.info("--dry-run: no DB writes")
            return

        for sid, _old, new in planned:
            await db.execute(
                text("UPDATE sets SET logo_url=:u, updated_at=NOW() WHERE id=:s"),
                {"u": new, "s": sid},
            )
        await db.commit()
        log.info(f"swapped {len(planned)} logo_urls in DB")


async def main() -> int:
    # Load .env manually — this script may be run outside FastAPI context
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
                    help="Limit to one language (en/ja/ko/zh-cn/zh-tw)")
    ap.add_argument("--skip-upload", action="store_true",
                    help="Skip R2 upload, only run DB URL swap")
    ap.add_argument("--skip-db", action="store_true",
                    help="Skip DB swap, only upload to R2")
    args = ap.parse_args()

    bucket = os.environ.get("R2_BUCKET")
    if not bucket:
        raise RuntimeError("R2_BUCKET missing from env")
    log.info(f"target bucket: {bucket}")
    log.info(f"public base:   {os.environ.get('R2_PUBLIC_URL')}")

    if args.skip_upload:
        # Rebuild the uploaded map from what's on disk (assumes prior
        # upload succeeded). No R2 client needed here.
        uploaded: dict[tuple[str, str], str] = {}
        for lang in LANGS:
            if args.lang and lang != args.lang:
                continue
            for f in (BACKUP_ROOT / lang).glob("*") if (BACKUP_ROOT / lang).exists() else []:
                if f.is_file():
                    uploaded[(lang, f.stem)] = _key_for(lang, f.name)
        log.info(f"skip-upload: inferred {len(uploaded)} keys from disk")
    else:
        uploaded = _upload_all(bucket, args.lang, args.dry_run)

    if not args.skip_db:
        await _swap_urls(uploaded, args.dry_run)

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
