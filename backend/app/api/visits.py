"""Visit tracking — public POST endpoint that the Next.js route
handler hits on every page view. Admin aggregate endpoints live in
`app.api.admin`.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user_optional
from app.database import get_db
from app.models import User, VisitLog


router = APIRouter(prefix="/visits", tags=["visits"])


_VALID_DEVICE = {"mobile", "desktop", "tablet", "bot"}


class VisitIn(BaseModel):
    session_id: str = Field(..., min_length=8, max_length=64)
    path: str = Field(..., min_length=1, max_length=512)
    country: str | None = Field(None, max_length=2)
    region: str | None = Field(None, max_length=64)
    city: str | None = Field(None, max_length=96)
    referrer: str | None = Field(None, max_length=512)
    device: str | None = Field(None, max_length=16)


@router.post("", status_code=status.HTTP_204_NO_CONTENT)
async def log_visit(
    payload: VisitIn,
    user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Record a page view. The frontend's /api/track-visit route handler
    hydrates the geo fields from Vercel's edge headers before forwarding
    here, so the backend just persists the row.
    """
    device = payload.device if payload.device in _VALID_DEVICE else None
    country = (payload.country or "").upper()[:2] or None

    row = VisitLog(
        user_id=user.id if user else None,
        session_id=payload.session_id,
        path=payload.path[:512],
        country=country,
        region=payload.region,
        city=payload.city,
        referrer=payload.referrer,
        device=device,
        created_at=datetime.utcnow(),
    )
    db.add(row)
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=500, detail="visit write failed")
