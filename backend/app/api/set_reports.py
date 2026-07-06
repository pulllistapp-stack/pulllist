"""Public endpoint for submitting data-quality reports against a set.

Anonymous submissions allowed. Admin triage lives in app.api.admin.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user_optional
from app.database import get_db
from app.models import Set, SetReport, User


router = APIRouter(prefix="/sets", tags=["set_reports"])


VALID_CATEGORIES = {
    "missing_cards",
    "wrong_images",
    "wrong_metadata",
    "other",
}


class SetReportIn(BaseModel):
    category: str = Field(..., min_length=1, max_length=24)
    comment: str | None = Field(None, max_length=1000)


@router.post(
    "/{set_id}/reports",
    status_code=status.HTTP_201_CREATED,
    response_model=dict,
)
async def submit_set_report(
    set_id: str,
    payload: SetReportIn,
    user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Submit a data-quality report against a set.

    Categories: missing_cards / wrong_images / wrong_metadata / other.
    'other' requires a non-empty comment; the named categories treat
    the comment as optional extra context.
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

    s = await db.get(Set, set_id)
    if not s:
        raise HTTPException(status_code=404, detail="Set not found")

    report = SetReport(
        set_id=set_id,
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
