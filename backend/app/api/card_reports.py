"""Public endpoint for submitting data-quality reports against a card.

Anonymous submissions allowed. Admin triage lives in app.api.admin.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user_optional
from app.database import get_db
from app.models import Card, CardReport, User


router = APIRouter(prefix="/cards", tags=["card_reports"])


VALID_CATEGORIES = {"wrong_price", "wrong_image", "wrong_name", "other"}


class CardReportIn(BaseModel):
    category: str = Field(..., min_length=1, max_length=24)
    comment: str | None = Field(None, max_length=1000)


@router.post(
    "/{card_id}/reports",
    status_code=status.HTTP_201_CREATED,
    response_model=dict,
)
async def submit_card_report(
    card_id: str,
    payload: CardReportIn,
    user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Submit a data-quality report against a card.

    Categories: wrong_price / wrong_image / wrong_name / other. The
    'other' category requires a non-empty comment; for the named
    categories the comment is optional context.
    """
    if payload.category not in VALID_CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail=(
                f"category must be one of {sorted(VALID_CATEGORIES)} — "
                f"got {payload.category!r}"
            ),
        )

    comment = (payload.comment or "").strip() or None
    if payload.category == "other" and not comment:
        raise HTTPException(
            status_code=400,
            detail="'other' category requires a comment.",
        )

    card = await db.get(Card, card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    report = CardReport(
        card_id=card_id,
        user_id=user.id if user else None,
        category=payload.category,
        comment=comment,
        status="open",
        created_at=datetime.utcnow(),
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)

    return {"id": report.id, "status": "open"}
