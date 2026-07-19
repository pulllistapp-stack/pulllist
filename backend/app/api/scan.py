"""Card scanning — Claude Vision API → DB match.

Flow:
  1. Client uploads base64-encoded JPEG of a card
  2. Claude Haiku 4.5 vision reads card name + number + set + rarity hint
  3. We fuzzy-match against our Card table and return top candidates
  4. Client confirms which candidate is correct → adds to collection

Model choice: claude-haiku-4-5 — Pokémon TCG cards have clear OCR-friendly
text and Haiku reads them reliably at ~$0.003 per scan. Sonnet 4.6 / Opus
4.8 don't add accuracy for this task but cost 3-15x more.

Auth: required (free tier rate-limits handled at the Pro-tier gate later;
for V1 we just log every scan in card_scan_logs for visibility).
"""

from __future__ import annotations

import logging
from typing import Literal

import anthropic
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.config import settings
from app.database import get_db
from app.models import Card, Set, User
from app.services.image_hash import (
    bump_hit,
    compute_phash,
    find_cache_hit,
    write_cache,
)

log = logging.getLogger("scan")
router = APIRouter(prefix="/cards", tags=["cards"])
# Bulk-scan pHash catalog lives under /scan/ to sidestep the
# /cards/{card_id} catch-all in the general cards router (a request to
# /cards/phash-catalog otherwise gets parsed as a card_id lookup and
# 404s before reaching us).
bulk_router = APIRouter(prefix="/scan", tags=["scan-bulk"])


# ────────── schemas ──────────


class ScanIdentification(BaseModel):
    """What Claude Vision extracted from the card image."""

    card_name: str | None = Field(
        None, description="Full English card name including modifiers like ex/VMAX/GX"
    )
    card_number: str | None = Field(
        None, description='Card number from bottom-left, e.g. "125" or "125/094"'
    )
    set_name: str | None = Field(None, description="Set name if visible")
    confidence: Literal["high", "medium", "low"]
    notes: str | None = Field(
        None,
        description="Rarity / variant / artist / anything that helps disambiguate",
    )


class ScanRequest(BaseModel):
    image_data: str = Field(
        ..., description="Base64-encoded image; data:URL prefix is also accepted"
    )
    media_type: str = Field("image/jpeg", description="Image MIME type")


class CardCandidate(BaseModel):
    id: str
    name: str
    number: str | None
    set_id: str
    set_name: str
    rarity: str | None
    image_small: str | None
    market_price_usd: float | None


class ScanResponse(BaseModel):
    identification: ScanIdentification
    candidates: list[CardCandidate]
    matched_card_id: str | None  # populated when confidence high AND we found 1+


SCAN_PROMPT = """You are identifying a Pokémon Trading Card Game card from an image.

Examine the card carefully and return ONLY a valid JSON object (no markdown, no
prose, no code fences) with exactly these keys:

{
  "card_name": "exact English card name with modifiers, e.g. 'Mega Charizard X ex', 'Cinccino ex', 'Pikachu VMAX'",
  "card_number": "card number from the bottom, e.g. '125' or '125/094' or '4/102'",
  "set_name": "set name if visible from logo/symbol/text, else null",
  "confidence": "high | medium | low",
  "notes": "brief disambiguating details: rarity (Common/Rare/Ultra/Special Illustration Rare/Hyper/Mega Hyper), variant (full art / alt art / illustration rare), artist signature, anything unique"
}

confidence levels:
- "high" — you can clearly read the name AND the number
- "medium" — name clear but number partially obscured, or vice versa
- "low" — significant guesswork

If a field is unreadable, return null for it (NOT an empty string).
Return ONLY the JSON object, nothing else.
"""


# ────────── endpoint ──────────


@router.post("/scan", response_model=ScanResponse)
async def scan_card(
    payload: ScanRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ScanResponse:
    """Identify a Pokémon TCG card from an uploaded image."""
    # Accept either raw base64 or a full data URL
    img = payload.image_data
    if img.startswith("data:"):
        try:
            _, img = img.split(",", 1)
        except ValueError:
            raise HTTPException(status_code=400, detail="Malformed data URL")

    if not img:
        raise HTTPException(status_code=400, detail="image_data is empty")

    media_type = payload.media_type or "image/jpeg"

    # ── pHash cache lookup ──────────────────────────────────────────────
    # Same image (or very close) scanned before → skip the Claude call.
    # The cache stores (image_hash → card_id) for successful identifications
    # at high/medium confidence. Low-confidence Claude calls aren't cached so
    # a shaky guess can't propagate.
    image_phash = compute_phash(img)
    if image_phash:
        hit = await find_cache_hit(db, image_phash)
        if hit is not None:
            cached_card = await db.get(Card, hit.card_id)
            if cached_card is not None:
                set_row = await db.get(Set, cached_card.set_id)
                set_name = set_row.name if set_row else cached_card.set_id
                candidate = CardCandidate(
                    id=cached_card.id,
                    name=cached_card.name,
                    number=cached_card.number,
                    set_id=cached_card.set_id,
                    set_name=set_name,
                    rarity=cached_card.rarity,
                    image_small=cached_card.image_small,
                    market_price_usd=float(cached_card.market_price_usd)
                    if cached_card.market_price_usd is not None
                    else None,
                )
                await bump_hit(db, hit.image_hash)
                log.info(
                    "User %s scan: cache hit %s → %s (hit_count now %d)",
                    user.id[:8],
                    hit.image_hash,
                    cached_card.id,
                    hit.hit_count + 1,
                )
                return ScanResponse(
                    identification=ScanIdentification(
                        card_name=cached_card.name,
                        card_number=cached_card.number,
                        set_name=set_name,
                        confidence="high",
                        notes="(cached from a previous scan)",
                    ),
                    candidates=[candidate],
                    matched_card_id=cached_card.id,
                )

    client = anthropic.AsyncAnthropic()
    try:
        response = await client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=512,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": img,
                            },
                        },
                        {
                            "type": "text",
                            "text": SCAN_PROMPT,
                        },
                    ],
                }
            ],
        )
    except anthropic.APIError as e:
        log.error("Claude vision call failed: %s", e)
        raise HTTPException(status_code=502, detail=f"Vision API error: {e}")
    except Exception as e:
        log.error("Unexpected scan error: %s", e)
        raise HTTPException(status_code=500, detail=f"Unexpected: {e}")

    # Extract JSON from the first text block. Claude sometimes wraps JSON in
    # markdown fences despite our instructions — strip them defensively.
    import json as _json
    import re as _re

    text_block = next(
        (b for b in response.content if getattr(b, "type", None) == "text"), None
    )
    if not text_block:
        raise HTTPException(status_code=502, detail="Vision API returned no text")

    raw = text_block.text.strip()
    # Strip ```json ... ``` or ``` ... ``` fences if present.
    fence = _re.match(r"^```(?:json)?\s*(.*?)\s*```$", raw, _re.DOTALL)
    if fence:
        raw = fence.group(1).strip()
    # Sometimes the model precedes JSON with a sentence; grab the first {...} block.
    brace = _re.search(r"\{.*\}", raw, _re.DOTALL)
    if brace:
        raw = brace.group(0)

    try:
        parsed = _json.loads(raw)
        identification = ScanIdentification(**parsed)
    except Exception as e:
        log.error(
            "Failed to parse Claude response: %s | raw: %s", e, text_block.text[:500]
        )
        raise HTTPException(
            status_code=502, detail="Vision API returned unparseable JSON"
        )

    candidates = await _match_card(db, identification)
    matched = (
        candidates[0].id
        if candidates and identification.confidence == "high"
        else None
    )

    log.info(
        "User %s scanned: %s #%s → %d candidates (matched=%s)",
        user.id[:8],
        identification.card_name,
        identification.card_number,
        len(candidates),
        matched,
    )

    # Cache successful high/medium-confidence identifications. Low/no-match
    # scans aren't cached — we don't want a shaky guess to short-circuit
    # the next scan of a different card that happens to look similar.
    if image_phash and matched and identification.confidence in ("high", "medium"):
        try:
            await write_cache(db, image_phash, matched, identification.confidence)
        except Exception as e:
            log.warning("scan cache write failed (non-fatal): %s", e)

    return ScanResponse(
        identification=identification,
        candidates=candidates,
        matched_card_id=matched,
    )


async def _match_card(
    db: AsyncSession, scan: ScanIdentification
) -> list[CardCandidate]:
    """Fuzzy-match the Claude identification to our Card table."""
    if not scan.card_name:
        return []

    name_pattern = f"%{scan.card_name.strip()}%"

    # Tier 1: name + number + set (tightest)
    stmt = (
        select(Card, Set.name)
        .join(Set, Card.set_id == Set.id)
        .where(Card.name.ilike(name_pattern))
    )

    if scan.card_number:
        num = scan.card_number.split("/")[0].strip()
        stmt = stmt.where(Card.number == num)

    if scan.set_name:
        stmt = stmt.where(Set.name.ilike(f"%{scan.set_name.strip()}%"))

    rows = (await db.execute(stmt.limit(5))).all()

    # Tier 2: relax to name + number only
    if not rows and scan.card_number:
        stmt2 = (
            select(Card, Set.name)
            .join(Set, Card.set_id == Set.id)
            .where(Card.name.ilike(name_pattern))
            .where(Card.number == scan.card_number.split("/")[0].strip())
            .limit(5)
        )
        rows = (await db.execute(stmt2)).all()

    # Tier 3: name only (last resort)
    if not rows:
        stmt3 = (
            select(Card, Set.name)
            .join(Set, Card.set_id == Set.id)
            .where(Card.name.ilike(name_pattern))
            .order_by(Card.market_price_usd.desc().nullslast())
            .limit(5)
        )
        rows = (await db.execute(stmt3)).all()

    return [
        CardCandidate(
            id=card.id,
            name=card.name,
            number=card.number,
            set_id=card.set_id,
            set_name=set_name,
            rarity=card.rarity,
            image_small=card.image_small,
            market_price_usd=float(card.market_price_usd)
            if card.market_price_usd is not None
            else None,
        )
        for card, set_name in rows
    ]


# ────────── Gemini alternative — same task, ~30x cheaper ──────────
#
# A/B path: identical request / response shape as /cards/scan so the
# frontend can route via a `?vision=gemini` query param and we can
# compare live accuracy without touching the default flow. If quality
# holds, this endpoint becomes the default and Claude sticks around
# as a fallback / for cases where Gemini's per-region key isn't set.


@router.post("/scan-gemini", response_model=ScanResponse)
async def scan_card_gemini(
    payload: ScanRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ScanResponse:
    """Identify a Pokémon TCG card using Google Gemini 2.0 Flash."""
    if not settings.gemini_api_key:
        raise HTTPException(
            status_code=501,
            detail="GEMINI_API_KEY not configured on the server",
        )

    # Base64 handling — identical to the Claude path so we can swap
    # providers on the client side by just changing the URL.
    img = payload.image_data
    if img.startswith("data:"):
        try:
            _, img = img.split(",", 1)
        except ValueError:
            raise HTTPException(status_code=400, detail="Malformed data URL")
    if not img:
        raise HTTPException(status_code=400, detail="image_data is empty")

    media_type = payload.media_type or "image/jpeg"

    # Shared pHash cache — a hit from a previous Claude scan of the
    # same image is just as valid for Gemini and vice-versa. Saves
    # duplicate API calls when the same photo gets scanned twice.
    image_phash = compute_phash(img)
    if image_phash:
        hit = await find_cache_hit(db, image_phash)
        if hit is not None:
            cached_card = await db.get(Card, hit.card_id)
            if cached_card is not None:
                set_row = await db.get(Set, cached_card.set_id)
                set_name = set_row.name if set_row else cached_card.set_id
                candidate = CardCandidate(
                    id=cached_card.id,
                    name=cached_card.name,
                    number=cached_card.number,
                    set_id=cached_card.set_id,
                    set_name=set_name,
                    rarity=cached_card.rarity,
                    image_small=cached_card.image_small,
                    market_price_usd=float(cached_card.market_price_usd)
                    if cached_card.market_price_usd is not None
                    else None,
                )
                await bump_hit(db, hit.image_hash)
                return ScanResponse(
                    identification=ScanIdentification(
                        card_name=cached_card.name,
                        card_number=cached_card.number,
                        set_name=set_name,
                        confidence="high",
                        notes="(cached from a previous scan)",
                    ),
                    candidates=[candidate],
                    matched_card_id=cached_card.id,
                )

    # Gemini call. google-genai is Google's newer unified SDK; the
    # async surface lives under client.aio.
    import base64 as _b64
    import json as _json
    import re as _re

    from google import genai
    from google.genai import types

    try:
        image_bytes = _b64.b64decode(img, validate=False)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Bad base64: {e}")

    client = genai.Client(api_key=settings.gemini_api_key)
    try:
        response = await client.aio.models.generate_content(
            model="gemini-2.0-flash",
            contents=[
                SCAN_PROMPT,
                types.Part.from_bytes(data=image_bytes, mime_type=media_type),
            ],
        )
    except Exception as e:
        log.error("Gemini call failed: %s", e)
        raise HTTPException(status_code=502, detail=f"Vision API error: {e}")

    raw = (response.text or "").strip()
    fence = _re.match(r"^```(?:json)?\s*(.*?)\s*```$", raw, _re.DOTALL)
    if fence:
        raw = fence.group(1).strip()
    brace = _re.search(r"\{.*\}", raw, _re.DOTALL)
    if brace:
        raw = brace.group(0)

    try:
        parsed = _json.loads(raw)
        identification = ScanIdentification(**parsed)
    except Exception as e:
        log.error(
            "Failed to parse Gemini response: %s | raw: %s", e, (response.text or "")[:500]
        )
        raise HTTPException(
            status_code=502, detail="Vision API returned unparseable JSON"
        )

    candidates = await _match_card(db, identification)
    matched = (
        candidates[0].id
        if candidates and identification.confidence == "high"
        else None
    )

    log.info(
        "User %s scanned (gemini): %s #%s → %d candidates (matched=%s)",
        user.id[:8],
        identification.card_name,
        identification.card_number,
        len(candidates),
        matched,
    )

    if image_phash and matched and identification.confidence in ("high", "medium"):
        try:
            await write_cache(db, image_phash, matched, identification.confidence)
        except Exception as e:
            log.warning("scan cache write failed (non-fatal): %s", e)

    return ScanResponse(
        identification=identification,
        candidates=candidates,
        matched_card_id=matched,
    )


# ────────── pHash catalog (bulk-scan client-side matching) ──────────


class PhashCatalogResponse(BaseModel):
    """A snapshot of every card's perceptual hash. Consumed by the client-
    side bulk scan loop so the camera can identify cards from a local
    hamming-distance lookup without a paid vision API call.

    Two parallel arrays keep the payload compact — one card_id list and
    one hash list, iterated in lockstep. At ~43 k rows this is ~2 MB raw
    (~500 KB gzipped) and lives behind long cache headers, so a phone
    downloads it once and reuses it for every subsequent session.
    """

    count: int
    generated_at: str
    ids: list[str]
    hashes: list[str]


# A pHash that repeats across many cards almost always signals a
# placeholder image (e.g. the Japanese card-back Bulbapedia URL
# 146 cards share) rather than genuine art overlap. Serving those
# to clients pulls "closest match" queries toward random cards for
# any low-content camera frame (empty hand, dark background). Drop
# any hash appearing more than this many times from the catalog.
DEGENERATE_CLUSTER_THRESHOLD = 10


@bulk_router.get("/phash-catalog", response_model=PhashCatalogResponse)
async def get_phash_catalog(
    db: AsyncSession = Depends(get_db),
) -> PhashCatalogResponse:
    """Return every card_id → image_phash mapping.

    Public: no auth required. The catalog is public data and clients
    (including the bulk scan feature) need it before any auth flow.
    Response is auto-gzipped by GZipMiddleware.

    Cache: 1 h in browser, 1 day at the edge. Regenerating pHashes is a
    manual backfill job, so real turnover is measured in weeks — an
    aggressive TTL is fine. Clients can bust via a URL query param when
    they know a resync landed.
    """
    from collections import Counter
    from datetime import datetime, timezone

    rows = (
        await db.execute(
            select(Card.id, Card.image_phash).where(Card.image_phash.isnot(None))
        )
    ).all()

    # First pass — count hash frequencies. Any hash beyond
    # DEGENERATE_CLUSTER_THRESHOLD is a shared placeholder and must
    # not be a valid match target.
    counts: Counter[str] = Counter(phash for _, phash in rows)

    ids: list[str] = []
    hashes: list[str] = []
    for card_id, phash in rows:
        if counts[phash] > DEGENERATE_CLUSTER_THRESHOLD:
            continue
        ids.append(card_id)
        hashes.append(phash)

    resp = PhashCatalogResponse(
        count=len(ids),
        generated_at=datetime.now(timezone.utc).isoformat(),
        ids=ids,
        hashes=hashes,
    )
    return resp


@bulk_router.get("/phash-catalog/stats")
async def get_phash_catalog_stats(
    db: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    """Quick health check — how many cards actually have a pHash yet.

    The client uses this before download to decide whether the bulk
    scan feature has enough coverage to be worth exposing (e.g. hide
    the toggle until >90 % of the catalog is hashed).
    """
    from sqlalchemy import func

    total = (
        await db.execute(select(func.count()).select_from(Card))
    ).scalar_one()
    with_hash = (
        await db.execute(
            select(func.count()).select_from(Card).where(
                Card.image_phash.isnot(None)
            )
        )
    ).scalar_one()
    with_image = (
        await db.execute(
            select(func.count()).select_from(Card).where(
                Card.image_small.isnot(None)
            )
        )
    ).scalar_one()
    return {
        "total_cards": int(total),
        "cards_with_image": int(with_image),
        "cards_with_phash": int(with_hash),
    }
