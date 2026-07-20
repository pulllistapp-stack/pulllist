"""CNN image-embedding matcher for the bulk-scan flow.

Design:
  1. Backfill script (scripts/backfill_card_embeddings.py) computes a
     MobileCLIP-S1 embedding for every catalog card and uploads two
     files to R2:
       - embeddings/card_embeddings.npy  (float32, shape [N, 512])
       - embeddings/card_ids.json        (parallel list of card_ids)
       - embeddings/metadata.json        (model, dim, count, created_at)
  2. On first `/scan/embedding-match` request, the backend downloads
     both files, normalizes the matrix once (unit vectors), and
     caches it in memory. Server restart re-downloads.
  3. Match: caller sends a 512-dim vector, we return top-k
     cosine-similarity nearest neighbours.

Cosine similarity between two unit vectors == dot product, so once
the catalog is L2-normalized the query becomes one matrix multiply
against the whole catalog + argpartition — ~5-20 ms on 43 k rows.
"""

from __future__ import annotations

import io
import json
import logging
import threading
from dataclasses import dataclass
from typing import Any

import numpy as np

from app.services import r2


log = logging.getLogger("embedding_matcher")


EMBEDDINGS_KEY = "embeddings/card_embeddings.npy"
IDS_KEY = "embeddings/card_ids.json"
METADATA_KEY = "embeddings/metadata.json"


@dataclass
class EmbeddingCatalog:
    """Loaded, ready-to-search catalog."""

    # Shape [N, D], L2-normalized so dot product == cosine similarity.
    matrix: np.ndarray
    # Parallel with matrix rows.
    card_ids: list[str]
    # Free-form info from the backfill run — model name, dimensionality,
    # timestamp, source card count. Surfaced via a stats endpoint.
    metadata: dict[str, Any]

    @property
    def count(self) -> int:
        return len(self.card_ids)

    @property
    def dim(self) -> int:
        return int(self.matrix.shape[1]) if self.matrix.ndim == 2 else 0


_state: EmbeddingCatalog | None = None
_lock = threading.Lock()
_load_error: str | None = None


def get_catalog() -> EmbeddingCatalog | None:
    """Return the loaded catalog, or None if not loaded yet / errored."""
    return _state


def get_load_error() -> str | None:
    return _load_error


def ensure_loaded() -> EmbeddingCatalog:
    """Load-once from R2. Raises if the download / parse fails so the
    request handler can turn it into a clean HTTP 503."""
    global _state, _load_error
    if _state is not None:
        return _state
    with _lock:
        if _state is not None:
            return _state
        try:
            log.info("loading embedding catalog from R2...")
            emb_bytes = r2.download_bytes(EMBEDDINGS_KEY)
            ids_bytes = r2.download_bytes(IDS_KEY)
            meta_bytes = (
                r2.download_bytes(METADATA_KEY)
                if r2.head_exists(METADATA_KEY)
                else b"{}"
            )
            matrix = np.load(io.BytesIO(emb_bytes)).astype(np.float32)
            card_ids = json.loads(ids_bytes)
            metadata = json.loads(meta_bytes)
            if matrix.shape[0] != len(card_ids):
                raise ValueError(
                    f"embedding/id length mismatch: matrix rows={matrix.shape[0]}"
                    f" vs ids={len(card_ids)}"
                )
            # Normalize once so cosine similarity is a single dot product.
            norms = np.linalg.norm(matrix, axis=1, keepdims=True)
            norms[norms == 0] = 1.0
            matrix = matrix / norms
            _state = EmbeddingCatalog(
                matrix=matrix,
                card_ids=list(card_ids),
                metadata=metadata,
            )
            _load_error = None
            log.info(
                "embedding catalog loaded: %d cards × %d dim",
                _state.count,
                _state.dim,
            )
            return _state
        except Exception as e:
            _load_error = f"{type(e).__name__}: {e}"
            log.exception("embedding catalog load failed")
            raise


def reset() -> None:
    """Drop the cached catalog. Next request will re-download."""
    global _state, _load_error
    with _lock:
        _state = None
        _load_error = None


def search(query: np.ndarray, top_k: int = 5) -> list[tuple[str, float]]:
    """Return the top_k (card_id, cosine_similarity) matches for the
    supplied query vector. Query is normalized here; caller doesn't
    need to."""
    cat = ensure_loaded()
    if query.ndim != 1 or query.shape[0] != cat.dim:
        raise ValueError(
            f"query must be a 1-D vector of dim {cat.dim}, got shape {query.shape}"
        )
    q = query.astype(np.float32)
    n = np.linalg.norm(q)
    if n == 0:
        return []
    q = q / n
    sims = cat.matrix @ q  # (N,) cosine similarities
    k = min(top_k, cat.count)
    # argpartition — O(N) partial sort, then argsort on the top-k slice.
    idx = np.argpartition(-sims, k - 1)[:k]
    idx = idx[np.argsort(-sims[idx])]
    return [(cat.card_ids[int(i)], float(sims[int(i)])) for i in idx]
