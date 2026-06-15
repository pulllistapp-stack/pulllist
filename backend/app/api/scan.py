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
from app.database import get_db
from app.models import Card, Set, User

log = logging.getLogger("scan")
router = APIRouter(prefix="/cards", tags=["cards"])


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

Examine the card carefully and return:

1. card_name: The exact English card name with modifiers — "Charizard ex",
   "Mega Charizard X ex", "Cinccino ex", "Pikachu VMAX", etc.

2. card_number: The card number from the bottom — "125" or "125/094" or "4/102".
   Return what you can read.

3. set_name: The set name if visible from the logo/symbol or set text.

4. confidence:
   - "high" — you can clearly read the name AND the number
   - "medium" — name clear but number partially obscured, or vice versa
   - "low" — significant guesswork

5. notes: Brief details that help match — rarity (Common/Rare/Ultra/Special
   Illustration Rare/Hyper/Mega Hyper), variant (full art, alt art,
   illustration rare), artist signature, anything unique about this print.

If unclear, give your best guess with low confidence rather than refusing.
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
            output_config={
                "format": {
                    "type": "json_schema",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "card_name": {"type": ["string", "null"]},
                            "card_number": {"type": ["string", "null"]},
                            "set_name": {"type": ["string", "null"]},
                            "confidence": {
                                "type": "string",
                                "enum": ["high", "medium", "low"],
                            },
                            "notes": {"type": ["string", "null"]},
                        },
                        "required": [
                            "card_name",
                            "card_number",
                            "set_name",
                            "confidence",
                            "notes",
                        ],
                        "additionalProperties": False,
                    },
                }
            },
        )
    except anthropic.APIError as e:
        log.error("Claude vision call failed: %s", e)
        raise HTTPException(status_code=502, detail=f"Vision API error: {e}")
    except Exception as e:
        log.error("Unexpected scan error: %s", e)
        raise HTTPException(status_code=500, detail=f"Unexpected: {e}")

    # Extract structured output from the first text block
    import json as _json

    text_block = next(
        (b for b in response.content if getattr(b, "type", None) == "text"), None
    )
    if not text_block:
        raise HTTPException(status_code=502, detail="Vision API returned no text")
    try:
        parsed = _json.loads(text_block.text)
        identification = ScanIdentification(**parsed)
    except Exception as e:
        log.error("Failed to parse Claude response: %s | raw: %s", e, text_block.text)
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
