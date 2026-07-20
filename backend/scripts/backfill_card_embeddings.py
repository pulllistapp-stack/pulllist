"""Compute a MobileCLIP-S1 image embedding for every catalog card and
upload the packed matrix + id list to R2 so the bulk-scan endpoint can
find nearest-neighbour matches against a client-computed camera-frame
embedding.

Model choice: Xenova/mobileclip-s1 — the ONNX-exported version of
Apple's MobileCLIP-S1. 512-dim embeddings, ~15 MB weights, works on
CPU in tens of milliseconds per image. Same file the frontend loads
via transformers.js so an image hashed on either side lines up.

Outputs (to R2 bucket = settings.r2_bucket_embeddings):
  embeddings/card_embeddings.npy  — float32 [N, 512] numpy dump
  embeddings/card_ids.json        — list of card_id strings, same order
  embeddings/metadata.json        — model / dim / count / timestamp

Usage:
    python -m scripts.backfill_card_embeddings
    python -m scripts.backfill_card_embeddings --dry-run
    python -m scripts.backfill_card_embeddings --limit 200
    python -m scripts.backfill_card_embeddings --concurrency 24
"""

from __future__ import annotations

import argparse
import asyncio
import io
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
import numpy as np
from PIL import Image
from sqlalchemy import select

from app.config import settings
from app.database import SessionLocal, init_db
from app.models import Card
from app.services import r2


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("backfill_embeddings")


# OpenAI CLIP ViT-B/32 — 512-D image embeddings, ~150 MB weights,
# proven to run cross-platform. Backend: HF `transformers` +
# torch. Frontend (Day 2): `@xenova/transformers` loads the ONNX
# port at `Xenova/clip-vit-base-patch32` for byte-identical
# embeddings.
MODEL_ID = "openai/clip-vit-base-patch32"
EMBEDDING_DIM = 512

# Same retry / concurrency knobs as the pHash backfill — different
# CDNs, still a mix of Bulbapedia, TCGdex, weserv proxies.
HTTP_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
RETRIES = 2


# ────────── model loader ──────────

_model_cache: dict = {}


def load_model():
    """One-time load at start of the embed phase (not per image!).
    transformers + torch are ~1 GB, only pulled in by the backfill
    job — production backend never imports these."""
    if "model" in _model_cache:
        return _model_cache["model"], _model_cache["processor"]

    log.info("loading %s ...", MODEL_ID)
    import torch
    from transformers import CLIPImageProcessor, CLIPModel

    model = CLIPModel.from_pretrained(MODEL_ID)
    model.eval()
    processor = CLIPImageProcessor.from_pretrained(MODEL_ID)
    _model_cache["model"] = model
    _model_cache["processor"] = processor
    _model_cache["torch"] = torch
    log.info("model ready")
    return model, processor


def embed_image(img: Image.Image) -> np.ndarray:
    """Return a 512-D embedding for one PIL image."""
    return embed_batch([img])[0]


def embed_batch(images: list[Image.Image]) -> np.ndarray:
    """Batched forward pass — the whole point of the perf rewrite.
    CLIP-B/32 on CPU is ~4x faster in batches of 32 vs 1-at-a-time
    because the matmul kernels hit their sweet spot. Returns a
    numpy array shape [len(images), 512]."""
    model, processor = load_model()
    torch = _model_cache["torch"]
    rgb = [
        (img if img.mode == "RGB" else img.convert("RGB"))
        for img in images
    ]
    inputs = processor(images=rgb, return_tensors="pt")
    with torch.no_grad():
        features = model.get_image_features(pixel_values=inputs["pixel_values"])
    return features.numpy().astype(np.float32)


# ────────── image fetch (mirrors backfill_card_phashes) ──────────


async def _fetch_bytes(
    http: httpx.AsyncClient,
    url: str,
) -> bytes | None:
    for attempt in range(RETRIES + 1):
        try:
            resp = await http.get(url)
            if resp.status_code >= 500 and attempt < RETRIES:
                await asyncio.sleep(0.5 * (attempt + 1))
                continue
            resp.raise_for_status()
            return resp.content
        except (httpx.HTTPError, asyncio.TimeoutError):
            if attempt < RETRIES:
                await asyncio.sleep(0.5 * (attempt + 1))
                continue
        except Exception:
            break
    return None


async def _fetch_worker(
    queue: asyncio.Queue,
    http: httpx.AsyncClient,
    fetched: dict[str, bytes],
    counter: dict[str, int],
) -> None:
    while True:
        item = await queue.get()
        if item is None:
            queue.task_done()
            return
        card_id, url = item
        data = await _fetch_bytes(http, url)
        if data:
            fetched[card_id] = data
        else:
            counter["fetch_fail"] += 1
        counter["fetch_done"] += 1
        if counter["fetch_done"] % 200 == 0:
            log.info(
                "  fetch %d / %d (%d failed)",
                counter["fetch_done"],
                counter["fetch_total"],
                counter["fetch_fail"],
            )
        queue.task_done()


async def run(
    dry_run: bool,
    limit: int | None,
    concurrency: int,
) -> None:
    if not settings.r2_configured:
        raise SystemExit(
            "R2 credentials not configured — set R2_ACCOUNT_ID, "
            "R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY."
        )

    await init_db()

    async with SessionLocal() as db:
        stmt = select(Card.id, Card.image_small).where(
            Card.image_small.isnot(None)
        )
        if limit:
            stmt = stmt.limit(limit)
        rows = (await db.execute(stmt)).all()

    total = len(rows)
    log.info(
        "Backfill scope: %d cards (dry_run=%s, concurrency=%d)",
        total,
        dry_run,
        concurrency,
    )
    if dry_run or total == 0:
        return

    # ── phase 1: download every card image concurrently ──
    fetched: dict[str, bytes] = {}
    counter = {
        "fetch_done": 0,
        "fetch_fail": 0,
        "fetch_total": total,
    }
    queue: asyncio.Queue = asyncio.Queue()
    for cid, url in rows:
        queue.put_nowait((cid, url))
    for _ in range(concurrency):
        queue.put_nowait(None)

    limits = httpx.Limits(
        max_connections=concurrency,
        max_keepalive_connections=concurrency,
    )
    t0 = time.monotonic()
    async with httpx.AsyncClient(
        timeout=HTTP_TIMEOUT,
        limits=limits,
        headers={"User-Agent": "PullList-embedding-backfill/1.0"},
        follow_redirects=True,
    ) as http:
        workers = [
            asyncio.create_task(_fetch_worker(queue, http, fetched, counter))
            for _ in range(concurrency)
        ]
        await queue.join()
        for w in workers:
            w.cancel()
    log.info(
        "fetch complete: %d ok / %d failed in %.1fs",
        len(fetched),
        counter["fetch_fail"],
        time.monotonic() - t0,
    )

    # ── phase 2: embed in batches (CPU matmul sweet spot ~32) ──
    BATCH_SIZE = 32
    ids: list[str] = []
    vectors: list[np.ndarray] = []
    embed_fail = 0
    t1 = time.monotonic()

    # Pre-decode successful images. Bad decodes get counted as
    # embed_fail up front so the batch step sees only valid PILs.
    decoded: list[tuple[str, Image.Image]] = []
    for card_id, _url in rows:
        if card_id not in fetched:
            continue
        try:
            img = Image.open(io.BytesIO(fetched[card_id]))
            img.load()
            decoded.append((card_id, img))
        except Exception as e:
            embed_fail += 1
            log.warning("decode failed for %s: %s", card_id, e)

    processed = 0
    for start in range(0, len(decoded), BATCH_SIZE):
        chunk = decoded[start : start + BATCH_SIZE]
        chunk_ids = [c[0] for c in chunk]
        chunk_imgs = [c[1] for c in chunk]
        try:
            batch_vecs = embed_batch(chunk_imgs)
            for cid, vec in zip(chunk_ids, batch_vecs):
                ids.append(cid)
                vectors.append(vec)
        except Exception as e:
            # Whole-batch failure is rare (usually processor OOM).
            # Retry the batch one image at a time so a single bad
            # frame doesn't nuke the other 31.
            embed_fail += len(chunk_ids)
            log.warning(
                "batch failed (%s) — retrying individually", e
            )
            for cid, img in chunk:
                try:
                    vec = embed_batch([img])[0]
                    ids.append(cid)
                    vectors.append(vec)
                    embed_fail -= 1
                except Exception as e2:
                    log.warning("embed failed for %s: %s", cid, e2)
        processed += len(chunk)
        if (start // BATCH_SIZE) % 10 == 0 or processed >= len(decoded):
            elapsed = time.monotonic() - t1
            log.info(
                "  embed %d / %d (%.1f cards/s, %d failed)",
                processed,
                len(decoded),
                processed / max(elapsed, 1e-3),
                embed_fail,
            )
    log.info(
        "embed complete: %d ok / %d failed in %.1fs",
        len(vectors),
        embed_fail,
        time.monotonic() - t1,
    )

    if not vectors:
        raise SystemExit("no embeddings computed — aborting upload")

    # ── phase 3: pack + upload to R2 ──
    matrix = np.vstack(vectors).astype(np.float32)
    log.info("packed matrix: shape=%s dtype=%s", matrix.shape, matrix.dtype)

    buf = io.BytesIO()
    np.save(buf, matrix, allow_pickle=False)
    r2.upload_bytes(
        "embeddings/card_embeddings.npy",
        buf.getvalue(),
        content_type="application/octet-stream",
    )
    r2.upload_bytes(
        "embeddings/card_ids.json",
        json.dumps(ids).encode("utf-8"),
        content_type="application/json",
    )
    meta = {
        "model": MODEL_ID,
        "dim": int(matrix.shape[1]),
        "count": int(matrix.shape[0]),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "fetch_failed": counter["fetch_fail"],
        "embed_failed": embed_fail,
    }
    r2.upload_bytes(
        "embeddings/metadata.json",
        json.dumps(meta, indent=2).encode("utf-8"),
        content_type="application/json",
    )
    log.info("upload complete. metadata: %s", meta)


def _cli() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--concurrency", type=int, default=16)
    return p.parse_args()


if __name__ == "__main__":
    args = _cli()
    asyncio.run(
        run(
            dry_run=args.dry_run,
            limit=args.limit,
            concurrency=args.concurrency,
        )
    )
