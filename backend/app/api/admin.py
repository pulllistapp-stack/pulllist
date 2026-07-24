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
from sqlalchemy import case, func, literal, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from datetime import datetime as _datetime, timedelta
from zoneinfo import ZoneInfo

from app.auth import get_current_admin
from app.database import get_db
from app.models import (
    Card,
    CardReport,
    CollectionItem,
    Set,
    SetReport,
    User,
    VisitLog,
    WishlistItem,
)

router = APIRouter(prefix="/admin", tags=["admin"])

# Admin dashboard "today" anchors to the operator's local calendar (ET),
# not the server's UTC clock — VisitLog.created_at is naive UTC, so we
# compute the ET midnight boundary and convert it back to naive UTC for
# the WHERE clause. Rolling windows (`utcnow() - timedelta`) stay
# UTC-based because they're duration-anchored, not calendar-anchored.
_ADMIN_TZ = ZoneInfo("America/New_York")


def _admin_today_start() -> _datetime:
    """Naive-UTC datetime for the current ET calendar-day boundary.

    VisitLog.created_at is stored as naive UTC (default=datetime.utcnow),
    so comparing rows to this value returns everything in the current ET
    calendar day.
    """
    et_now = _datetime.now(_ADMIN_TZ)
    et_midnight = et_now.replace(hour=0, minute=0, second=0, microsecond=0)
    return et_midnight.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)


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


# ────────── Set reports (data-quality triage — set-scoped) ──────────


def _serialize_set_report(
    report: SetReport,
    set_row: Set | None,
    reporter: User | None,
    resolver: User | None,
) -> dict:
    return {
        "id": report.id,
        "set_id": report.set_id,
        "set_name": set_row.name if set_row else None,
        "set_logo_url": set_row.logo_url if set_row else None,
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


@router.get("/set-reports")
async def list_set_reports(
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
    """Mirror of /card-reports scoped to SetReport rows. Same pagination
    + status filtering; each item hydrated with the set logo + name and
    the reporter / resolver contact info so the inbox reads at a glance."""
    stmt = select(SetReport).order_by(SetReport.created_at.desc())
    show_all = status_filter in (None, "", "all")
    if not show_all:
        stmt = stmt.where(SetReport.status == status_filter)

    total_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(total_stmt)).scalar_one()

    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    reports = (await db.execute(stmt)).scalars().all()

    set_ids = {r.set_id for r in reports}
    user_ids = {r.user_id for r in reports if r.user_id} | {
        r.resolved_by for r in reports if r.resolved_by
    }

    sets: dict[str, Set] = {}
    if set_ids:
        for s in (
            await db.execute(select(Set).where(Set.id.in_(set_ids)))
        ).scalars():
            sets[s.id] = s

    users: dict[str, User] = {}
    if user_ids:
        for u in (
            await db.execute(select(User).where(User.id.in_(user_ids)))
        ).scalars():
            users[u.id] = u

    return {
        "items": [
            _serialize_set_report(
                r,
                sets.get(r.set_id),
                users.get(r.user_id) if r.user_id else None,
                users.get(r.resolved_by) if r.resolved_by else None,
            )
            for r in reports
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.patch("/set-reports/{report_id}")
async def update_set_report(
    report_id: int,
    payload: CardReportResolve,
    admin: Annotated[User, Depends(get_current_admin)],
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Mark a set report resolved/wontfix or re-open. Same shape as the
    card-report resolver (reuses CardReportResolve for the payload)."""
    if payload.status not in ("open", "resolved", "wontfix"):
        raise HTTPException(
            status_code=400,
            detail="status must be one of open / resolved / wontfix",
        )

    report = await db.get(SetReport, report_id)
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

    set_row = await db.get(Set, report.set_id)
    reporter = await db.get(User, report.user_id) if report.user_id else None
    resolver = (
        await db.get(User, report.resolved_by) if report.resolved_by else None
    )

    return _serialize_set_report(report, set_row, reporter, resolver)


# ────────── Visit logs (traffic dashboard) ──────────


@router.get("/visits/summary")
async def visits_summary(
    admin: Annotated[User, Depends(get_current_admin)],  # noqa: ARG001
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Top-level traffic numbers for the admin dashboard:

      - today / yesterday / last-7d page views (raw count)
      - today / yesterday / last-7d unique visitors (distinct session_id)
      - today's country breakdown (top 10)
      - last-7d daily series (for a tiny sparkline)
    """
    # Day windows anchor to ET (LO's timezone) so "today" on the dashboard
    # matches the calendar day LO is actually reading it on.
    today_start = _admin_today_start()
    yest_start = today_start - timedelta(days=1)
    week_start = today_start - timedelta(days=6)  # inclusive 7-day window

    async def _count(window_start: _datetime, window_end: _datetime) -> int:
        stmt = select(func.count(VisitLog.id)).where(
            VisitLog.created_at >= window_start,
            VisitLog.created_at < window_end,
        )
        return int((await db.execute(stmt)).scalar() or 0)

    async def _unique(window_start: _datetime, window_end: _datetime) -> int:
        stmt = select(func.count(func.distinct(VisitLog.session_id))).where(
            VisitLog.created_at >= window_start,
            VisitLog.created_at < window_end,
        )
        return int((await db.execute(stmt)).scalar() or 0)

    today_views = await _count(today_start, today_start + timedelta(days=1))
    yest_views = await _count(yest_start, today_start)
    week_views = await _count(week_start, today_start + timedelta(days=1))

    today_uniques = await _unique(today_start, today_start + timedelta(days=1))
    yest_uniques = await _unique(yest_start, today_start)
    week_uniques = await _unique(week_start, today_start + timedelta(days=1))

    # Today's country breakdown
    country_stmt = (
        select(VisitLog.country, func.count(VisitLog.id))
        .where(VisitLog.created_at >= today_start)
        .group_by(VisitLog.country)
        .order_by(func.count(VisitLog.id).desc())
        .limit(10)
    )
    countries = [
        {"country": c or "??", "count": int(n)}
        for c, n in (await db.execute(country_stmt)).all()
    ]

    # 7-day daily series
    daily_stmt = (
        select(
            func.date(VisitLog.created_at).label("day"),
            func.count(VisitLog.id),
            func.count(func.distinct(VisitLog.session_id)),
        )
        .where(VisitLog.created_at >= week_start)
        .group_by("day")
        .order_by("day")
    )
    daily = [
        {"date": str(d), "views": int(v), "uniques": int(u)}
        for d, v, u in (await db.execute(daily_stmt)).all()
    ]

    return {
        "views": {"today": today_views, "yesterday": yest_views, "week": week_views},
        "uniques": {
            "today": today_uniques,
            "yesterday": yest_uniques,
            "week": week_uniques,
        },
        "countries_today": countries,
        "daily_7d": daily,
    }


@router.get("/visits/by-user")
async def visits_by_user(
    admin: Annotated[User, Depends(get_current_admin)],  # noqa: ARG001
    days: int = Query(1, ge=1, le=30, description="Window in days back from today."),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Per-logged-in-user visit counts within the window, plus their last
    seen timestamp + last seen country. Lets the admin spot unusual
    activity (e.g. a brand new account hitting 50 pages from CN today)."""
    today_start = _admin_today_start()
    window_start = today_start - timedelta(days=days - 1)

    stmt = (
        select(
            VisitLog.user_id,
            func.count(VisitLog.id).label("views"),
            func.max(VisitLog.created_at).label("last_seen"),
        )
        .where(
            VisitLog.created_at >= window_start,
            VisitLog.user_id.is_not(None),
        )
        .group_by(VisitLog.user_id)
        .order_by(func.count(VisitLog.id).desc())
    )
    rows = (await db.execute(stmt)).all()
    user_ids = [uid for uid, _, _ in rows]

    if not user_ids:
        return {"items": [], "days": days}

    users: dict[str, User] = {}
    for u in (
        await db.execute(select(User).where(User.id.in_(user_ids)))
    ).scalars():
        users[u.id] = u

    # last-seen country per user (most recent visit's country)
    last_country: dict[str, str | None] = {}
    last_country_stmt = (
        select(VisitLog.user_id, VisitLog.country)
        .where(
            VisitLog.user_id.in_(user_ids),
            VisitLog.created_at >= window_start,
        )
        .order_by(VisitLog.user_id, VisitLog.created_at.desc())
    )
    for uid, country in (await db.execute(last_country_stmt)).all():
        if uid not in last_country:
            last_country[uid] = country

    return {
        "days": days,
        "items": [
            {
                "user_id": uid,
                "email": users[uid].email if uid in users else None,
                "name": users[uid].name if uid in users else None,
                "is_admin": users[uid].is_admin if uid in users else False,
                "views": int(views),
                "last_seen": last_seen.isoformat() if last_seen else None,
                "last_country": last_country.get(uid),
            }
            for uid, views, last_seen in rows
            if uid in users
        ],
    }


# ────────── Visit tracking: extended views (2026-07) ──────────
# Recent stream, top pages, top referrers, anon session breakdown —
# the pieces the top-level summary doesn't cover. All accept a `days`
# window so the admin can pivot between "last 24h" and "last week".


def _serialize_visit(row: VisitLog, user: User | None) -> dict:
    return {
        "id": row.id,
        "created_at": row.created_at.isoformat(),
        "path": row.path,
        "referrer": row.referrer,
        "country": row.country,
        "region": row.region,
        "city": row.city,
        "device": row.device,
        "session_id": row.session_id,
        "is_anonymous": row.user_id is None,
        "user": (
            {"id": user.id, "email": user.email, "name": user.name}
            if user
            else None
        ),
    }


def _referrer_domain(raw: str | None) -> str:
    """Group referrers by hostname so top-referrers aggregates every
    google.com/search? deep link into one 'google.com' bucket.
    Missing / empty / literal 'direct' → 'direct'."""
    if not raw:
        return "direct"
    lower = raw.strip().lower()
    if not lower or lower == "direct":
        return "direct"
    for prefix in ("https://", "http://", "//"):
        if lower.startswith(prefix):
            lower = lower[len(prefix):]
            break
    for sep in ("/", "?", "#"):
        idx = lower.find(sep)
        if idx >= 0:
            lower = lower[:idx]
    if ":" in lower:
        lower = lower.split(":", 1)[0]
    return lower or "direct"


@router.get("/visits/recent")
async def visits_recent(
    admin: Annotated[User, Depends(get_current_admin)],  # noqa: ARG001
    limit: int = Query(100, ge=1, le=500),
    scope: str = Query(
        "all",
        description="all / anon / user",
        pattern="^(all|anon|user)$",
    ),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Raw stream of most recent visits — logged-in and anonymous mixed
    (or filtered via scope). Near-real-time activity scan."""
    stmt = select(VisitLog).order_by(VisitLog.created_at.desc()).limit(limit)
    if scope == "anon":
        stmt = stmt.where(VisitLog.user_id.is_(None))
    elif scope == "user":
        stmt = stmt.where(VisitLog.user_id.is_not(None))

    rows = (await db.execute(stmt)).scalars().all()

    user_ids = {r.user_id for r in rows if r.user_id}
    users: dict[str, User] = {}
    if user_ids:
        for u in (
            await db.execute(select(User).where(User.id.in_(user_ids)))
        ).scalars():
            users[u.id] = u

    return {
        "items": [
            _serialize_visit(r, users.get(r.user_id) if r.user_id else None)
            for r in rows
        ],
        "limit": limit,
        "scope": scope,
    }


@router.get("/visits/bots")
async def visits_bots(
    admin: Annotated[User, Depends(get_current_admin)],  # noqa: ARG001
    days: int = Query(7, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Bot traffic breakdown over the last N days.

    Groups by `bot_name` (set server-side from the User-Agent header —
    see app.services.bot_detect). Only rows with a recognized bot name
    are surfaced; human traffic and unknown UAs are excluded from this
    endpoint entirely.

    Response includes a coarse category tag ('search' / 'llm' / 'seo' /
    'social' / 'monitor' / 'other') so the dashboard can color-code the
    rows without duplicating the classification client-side.
    """
    window_start = _datetime.utcnow() - timedelta(days=days)

    stmt = (
        select(
            VisitLog.bot_name,
            func.count(VisitLog.id).label("views"),
            func.max(VisitLog.created_at).label("last_seen"),
        )
        .where(
            VisitLog.created_at >= window_start,
            VisitLog.bot_name.is_not(None),
        )
        .group_by(VisitLog.bot_name)
        .order_by(func.count(VisitLog.id).desc())
    )
    rows = (await db.execute(stmt)).all()

    return {
        "days": days,
        "items": [
            {
                "bot_name": name,
                "category": _bot_category(name),
                "views": int(views),
                "last_seen": last_seen.isoformat() if last_seen else None,
            }
            for name, views, last_seen in rows
        ],
    }


# Classification used by /admin/visits/bots. Keep in sync with the
# BOT_PATTERNS groupings in app.services.bot_detect. 'other' catches
# anything not explicitly listed (including the generic-bot fallback).
_BOT_CATEGORY: dict[str, str] = {
    # search engines
    "Googlebot": "search",
    "Googlebot-Image": "search",
    "Bingbot": "search",
    "DuckDuckBot": "search",
    "YandexBot": "search",
    "NaverBot": "search",
    "Applebot": "search",
    # LLM / AI answer
    "GPTBot": "llm",
    "ChatGPT-User": "llm",
    "OAI-SearchBot": "llm",
    "ClaudeBot": "llm",
    "anthropic-ai": "llm",
    "Google-Extended": "llm",
    "Applebot-Extended": "llm",
    "CCBot": "llm",
    "PerplexityBot": "llm",
    "Amazonbot": "llm",
    "Bytespider": "llm",
    "Diffbot": "llm",
    # 3rd-party SEO
    "AhrefsBot": "seo",
    "SemrushBot": "seo",
    "DotBot": "seo",
    "PetalBot": "seo",
    "DataForSeoBot": "seo",
    "MJ12bot": "seo",
    "BLEXBot": "seo",
    # social preview
    "facebookexternalhit": "social",
    "Twitterbot": "social",
    "Discordbot": "social",
    "Slackbot": "social",
    "TelegramBot": "social",
    "WhatsApp": "social",
    # monitoring
    "UptimeRobot": "monitor",
    "Pingdom": "monitor",
}


def _bot_category(name: str | None) -> str:
    return _BOT_CATEGORY.get(name or "", "other")


@router.get("/visits/top-paths")
async def visits_top_paths(
    admin: Annotated[User, Depends(get_current_admin)],  # noqa: ARG001
    days: int = Query(7, ge=1, le=90),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Most-viewed paths in the last N days. Views + unique-session
    counts side by side so the admin sees both raw hits and reach."""
    window_start = _datetime.utcnow() - timedelta(days=days)
    stmt = (
        select(
            VisitLog.path,
            func.count(VisitLog.id).label("views"),
            func.count(func.distinct(VisitLog.session_id)).label("uniques"),
        )
        .where(VisitLog.created_at >= window_start)
        .group_by(VisitLog.path)
        .order_by(func.count(VisitLog.id).desc())
        .limit(limit)
    )
    rows = (await db.execute(stmt)).all()
    return {
        "days": days,
        "items": [
            {"path": path, "views": int(views), "uniques": int(uniques)}
            for path, views, uniques in rows
        ],
    }


@router.get("/visits/top-referrers")
async def visits_top_referrers(
    admin: Annotated[User, Depends(get_current_admin)],  # noqa: ARG001
    days: int = Query(7, ge=1, le=90),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Aggregated by referrer HOSTNAME so google.com/... deep links
    collapse into one row. Sorted by unique-visitor count so a single
    scraper hammering doesn't dominate the list.

    Hostname normalization happens IN SQL — regexp_replace strips the
    scheme (https?:// or //), then trims everything from the first
    /?#: onward, then lower(). Matches _referrer_domain() behavior.
    Doing this in Python required pulling every visit row for the
    window (tens of thousands) into memory just to bucket them. SQL
    GROUP BY sends back only the top-N rows."""
    window_start = _datetime.utcnow() - timedelta(days=days)

    normalized = func.lower(
        func.regexp_replace(
            func.regexp_replace(VisitLog.referrer, r"^(https?://|//)", ""),
            r"[/?#:].*$",
            "",
        )
    )
    domain_expr = case(
        (
            or_(
                VisitLog.referrer.is_(None),
                func.trim(func.lower(VisitLog.referrer)) == "",
                func.trim(func.lower(VisitLog.referrer)) == "direct",
            ),
            literal("direct"),
        ),
        else_=normalized,
    ).label("domain")

    stmt = (
        select(
            domain_expr,
            func.count(VisitLog.id).label("views"),
            func.count(func.distinct(VisitLog.session_id)).label("uniques"),
        )
        .where(VisitLog.created_at >= window_start)
        .group_by(domain_expr)
        .order_by(
            func.count(func.distinct(VisitLog.session_id)).desc(),
            func.count(VisitLog.id).desc(),
        )
        .limit(limit)
    )
    rows = (await db.execute(stmt)).all()

    return {
        "days": days,
        "items": [
            {
                "domain": (domain or "direct"),
                "views": int(views),
                "uniques": int(uniques),
            }
            for domain, views, uniques in rows
        ],
    }


@router.get("/visits/anon-sessions")
async def visits_anon_sessions(
    admin: Annotated[User, Depends(get_current_admin)],  # noqa: ARG001
    days: int = Query(7, ge=1, le=90),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Per-anonymous-session breakdown: view count, first + last hit
    timestamps, entry path (earliest hit), country, device, entry
    referrer. Ordered by most recent activity so live sessions bubble
    to the top."""
    window_start = _datetime.utcnow() - timedelta(days=days)

    agg_stmt = (
        select(
            VisitLog.session_id,
            func.count(VisitLog.id).label("views"),
            func.min(VisitLog.created_at).label("first_seen"),
            func.max(VisitLog.created_at).label("last_seen"),
        )
        .where(
            VisitLog.created_at >= window_start,
            VisitLog.user_id.is_(None),
        )
        .group_by(VisitLog.session_id)
        .order_by(func.max(VisitLog.created_at).desc())
        .limit(limit)
    )
    agg_rows = (await db.execute(agg_stmt)).all()
    if not agg_rows:
        return {"days": days, "items": []}

    session_ids = [s for s, _, _, _ in agg_rows]

    # First hit per session — carries entry path / country / device /
    # entry referrer.
    entry_stmt = (
        select(
            VisitLog.session_id,
            VisitLog.path,
            VisitLog.country,
            VisitLog.city,
            VisitLog.device,
            VisitLog.referrer,
        )
        .where(
            VisitLog.session_id.in_(session_ids),
            VisitLog.user_id.is_(None),
        )
        .order_by(VisitLog.session_id, VisitLog.created_at.asc())
    )
    entry: dict[str, dict] = {}
    for sess, path, country, city, device, referrer in (
        await db.execute(entry_stmt)
    ).all():
        if sess not in entry:
            entry[sess] = {
                "entry_path": path,
                "country": country,
                "city": city,
                "device": device,
                "entry_referrer": _referrer_domain(referrer),
            }

    return {
        "days": days,
        "items": [
            {
                "session_id": sess,
                "views": int(views),
                "first_seen": first_seen.isoformat() if first_seen else None,
                "last_seen": last_seen.isoformat() if last_seen else None,
                **entry.get(sess, {}),
            }
            for sess, views, first_seen, last_seen in agg_rows
        ],
    }
