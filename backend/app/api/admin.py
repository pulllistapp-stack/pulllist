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

from app.auth import get_current_admin
from app.database import get_db
from app.models import CollectionItem, User, WishlistItem

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
