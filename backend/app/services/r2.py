"""Cloudflare R2 (S3-compatible) client for large binary artifacts
we don't want to bloat the Neon free-tier Postgres with — chiefly the
catalog image mirror and the on-device bulk-scan embedding index.

Credentials come from env; nothing here is safe to import at test-
collection time without them set, so the boto3 client is built
lazily on first use and cached.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import TYPE_CHECKING

from app.config import settings

if TYPE_CHECKING:
    from botocore.client import BaseClient


log = logging.getLogger("r2")


@lru_cache(maxsize=1)
def get_client() -> "BaseClient":
    """Return a cached S3 client pointed at Cloudflare R2. Callers
    should check settings.r2_configured first — this will still
    return a client if creds are empty (boto3 doesn't validate) but
    every subsequent call will 403."""
    import boto3
    from botocore.config import Config

    return boto3.client(
        "s3",
        endpoint_url=settings.r2_endpoint,
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
        # R2 uses `auto` for region name — any real AWS region string
        # just gets ignored.
        region_name="auto",
        config=Config(
            signature_version="s3v4",
            retries={"max_attempts": 3, "mode": "standard"},
        ),
    )


def download_bytes(key: str, bucket: str | None = None) -> bytes:
    """Fetch an object from R2 as raw bytes. Raises on failure."""
    b = bucket or settings.r2_bucket_embeddings
    if not settings.r2_configured:
        raise RuntimeError(
            "R2 credentials not configured (set R2_ACCOUNT_ID, "
            "R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY)."
        )
    log.info("R2 GET %s/%s", b, key)
    resp = get_client().get_object(Bucket=b, Key=key)
    return resp["Body"].read()


def upload_bytes(
    key: str,
    data: bytes,
    content_type: str = "application/octet-stream",
    bucket: str | None = None,
) -> None:
    """Write a byte payload to R2. Overwrites without warning."""
    b = bucket or settings.r2_bucket_embeddings
    if not settings.r2_configured:
        raise RuntimeError("R2 credentials not configured.")
    log.info("R2 PUT %s/%s (%d bytes)", b, key, len(data))
    get_client().put_object(
        Bucket=b,
        Key=key,
        Body=data,
        ContentType=content_type,
    )


def head_exists(key: str, bucket: str | None = None) -> bool:
    """Cheap existence check — HEAD instead of GET."""
    b = bucket or settings.r2_bucket_embeddings
    if not settings.r2_configured:
        return False
    try:
        get_client().head_object(Bucket=b, Key=key)
        return True
    except Exception:
        return False
