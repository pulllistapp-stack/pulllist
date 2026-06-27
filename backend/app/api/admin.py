"""Admin-only endpoints for managing users.

Every route in this router goes through `get_current_admin` so the JWT
must (a) belong to a real, non-deleted user and (b) carry is_admin=true.
Even if someone hits the URL directly with a normal user's token they
get a 403; the only privilege-elevation path is another admin
explicitly granting it via PATCH below.
"""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from datetime import datetime as _datetime

from app.auth import get_current_admin
from app.database import get_db
from app.models import Card, CardReport, CollectionItem, Set, User, WishlistItem

router = APIRouter(prefix="/admin", tags=["admin"])


class UserAdminToggle(BaseModel):
    is_admin: bool


def _serialize_user(u: User, card_count: int, wishlist_count: int) -> dict:
    return {
        "id": u.id,
        "email": u.email,
        "name": u.name,
        "avatar_url": u.avatar_url,
        "is_admin": u.is_admin,
        "deleted_at": u.deleted_at.isoformat() if u.deleted_at else None,
        "created_at": u.created_at.isoformat(),
        "card_count": card_count,
        "wishlist_count": wishlist_count,
    }


@router.get("/users")
async def list_users(
    admin: Annotated[User, Depends(get_current_admin)],  # noqa: ARG001
    q: str | None = Query(None, description="Search email / name (ILIKE)"),
    include_deleted: bool = False,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Paginated user list with collection + wishlist counts. Defaults to
    hiding soft-deleted users so the table reflects 'real' active members."""
    base_q = select(User).order_by(User.created_at.desc())
    if not include_deleted:
        base_q = base_q.where(User.deleted_at.is_(None))
    if q:
        pat = f"%{q}%"
        base_q = base_q.where(or_(User.email.ilike(pat), User.name.ilike(pat)))

    total = (
        await db.execute(select(func.count()).select_from(base_q.subquery()))
    ).scalar_one()

    page_q = base_q.offset((page - 1) * page_size).limit(page_size)
    users = (await db.execute(page_q)).scalars().all()
    if not users:
        return {"total": total, "page": page, "page_size": page_size, "items": []}

    user_ids = [u.id for u in users]

    # Per-user stats in two grouped queries — beats N+1 lookups.
    card_counts_q = (
        select(CollectionItem.user_id, func.count(CollectionItem.id))
        .where(CollectionItem.user_id.in_(user_ids))
        .group_by(CollectionItem.user_id)
    )
    card_counts: dict[str, int] = {
        uid: c for uid, c in (await db.execute(card_counts_q)).all()
    }
    wishlist_counts_q = (
        select(WishlistItem.user_id, func.count(WishlistItem.id))
        .where(WishlistItem.user_id.in_(user_ids))
        .group_by(WishlistItem.user_id)
    )
    wishlist_counts: dict[str, int] = {
        uid: c for uid, c in (await db.execute(wishlist_counts_q)).all()
    }

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            _serialize_user(
                u, card_counts.get(u.id, 0), wishlist_counts.get(u.id, 0)
            )
            for u in users
        ],
    }


@router.patch("/users/{user_id}/admin")
async def toggle_admin(
    user_id: str,
    payload: UserAdminToggle,
    admin: Annotated[User, Depends(get_current_admin)],
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Promote or demote a user. Guard: an admin can't demote themself —
    accidental self-lockout would leave the org with zero admins."""
    target = await db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if target.id == admin.id and payload.is_admin is False:
        raise HTTPException(
            status_code=400,
            detail="Admins can't remove their own admin role.",
        )
    target.is_admin = payload.is_admin
    await db.commit()
    return _serialize_user(target, 0, 0)


@router.delete("/users/{user_id}", status_code=204)
async def soft_delete_user(
    user_id: str,
    admin: Annotated[User, Depends(get_current_admin)],
    db: AsyncSession = Depends(get_db),
) -> None:
    """Soft delete — flip deleted_at so the user can no longer sign in,
    but collection/wishlist rows stay intact for any historical view we
    later want. Guard: admins can't delete themself (same lockout risk
    as demote)."""
    target = await db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if target.id == admin.id:
        raise HTTPException(
            status_code=400, detail="Admins can't delete their own account."
        )
    if target.deleted_at is None:
        target.deleted_at = datetime.utcnow()
        await db.commit()


@router.post("/users/{user_id}/restore")
async def restore_user(
    user_id: str,
    admin: Annotated[User, Depends(get_current_admin)],  # noqa: ARG001
    db: AsyncSession = Depends(get_db),
) -> dict:
    target = await db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    target.deleted_at = None
    await db.commit()
    return _serialize_user(target, 0, 0)


# ────────── Card reports (data-quality triage) ──────────


def _serialize_report(
    report: CardReport,
    card: Card | None,
    set_row: Set | None,
    reporter: User | None,
    resolver: User | None,
) -> dict:
    return {
        "id": report.id,
        "card_id": report.card_id,
        "card_name": card.name if card else None,
        "card_number": card.number if card else None,
        "card_image_small": card.image_small if card else None,
        "set_id": card.set_id if card else None,
        "set_name": set_row.name if set_row else None,
        "category": report.category,
        "comment": report.comment,
        "status": report.status,
        "created_at": report.created_at.isoformat(),
        "resolved_at": report.resolved_at.isoformat() if report.resolved_at else None,
        "resolution_note": report.resolution_note,
        "reporter": (
            {"id": reporter.id, "email": reporter.email, "name": reporter.name}
            if reporter
            else None
        ),
        "resolver": (
            {"id": resolver.id, "email": resolver.email, "name": resolver.name}
            if resolver
            else None
        ),
    }


@router.get("/card-reports")
async def list_card_reports(
    admin: Annotated[User, Depends(get_current_admin)],  # noqa: ARG001
    status_filter: str | None = Query(
        "open",
        alias="status",
        description="Filter by status. Pass '' or 'all' for everything.",
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List recent card reports for triage. Defaults to status=open so the
    inbox shows what needs attention; pass status=all to see history."""
    stmt = select(CardReport).order_by(CardReport.created_at.desc())
    show_all = status_filter in (None, "", "all")
    if not show_all:
        stmt = stmt.where(CardReport.status == status_filter)

    total_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(total_stmt)).scalar_one()

    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    reports = (await db.execute(stmt)).scalars().all()

    card_ids = {r.card_id for r in reports}
    user_ids = {r.user_id for r in reports if r.user_id} | {
        r.resolved_by for r in reports if r.resolved_by
    }

    cards: dict[str, Card] = {}
    sets: dict[str, Set] = {}
    if card_ids:
        rows = (
            await db.execute(select(Card).where(Card.id.in_(card_ids)))
        ).scalars()
        for c in rows:
            cards[c.id] = c
        set_rows = (
            await db.execute(
                select(Set).where(Set.id.in_({c.set_id for c in cards.values()}))
            )
        ).scalars()
        for s in set_rows:
            sets[s.id] = s

    users: dict[str, User] = {}
    if user_ids:
        for u in (
            await db.execute(select(User).where(User.id.in_(user_ids)))
        ).scalars():
            users[u.id] = u

    return {
        "items": [
            _serialize_report(
                r,
                cards.get(r.card_id),
                sets.get(cards[r.card_id].set_id) if r.card_id in cards else None,
                users.get(r.user_id) if r.user_id else None,
                users.get(r.resolved_by) if r.resolved_by else None,
            )
            for r in reports
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


class CardReportResolve(BaseModel):
    status: str  # 'resolved' / 'wontfix' / 'open' (re-open)
    resolution_note: str | None = None


@router.patch("/card-reports/{report_id}")
async def update_card_report(
    report_id: int,
    payload: CardReportResolve,
    admin: Annotated[User, Depends(get_current_admin)],
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Mark a report resolved/wontfix or re-open it. Stamps resolved_at +
    resolved_by when transitioning to a terminal status; clears them on
    re-open so the inbox count stays honest."""
    if payload.status not in ("open", "resolved", "wontfix"):
        raise HTTPException(
            status_code=400,
            detail="status must be one of open / resolved / wontfix",
        )

    report = await db.get(CardReport, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    report.status = payload.status
    report.resolution_note = payload.resolution_note
    if payload.status == "open":
        report.resolved_at = None
        report.resolved_by = None
    else:
        report.resolved_at = _datetime.utcnow()
        report.resolved_by = admin.id

    await db.commit()
    await db.refresh(report)

    card = await db.get(Card, report.card_id)
    set_row = await db.get(Set, card.set_id) if card else None
    reporter = await db.get(User, report.user_id) if report.user_id else None
    resolver = await db.get(User, report.resolved_by) if report.resolved_by else None

    return _serialize_report(report, card, set_row, reporter, resolver)
