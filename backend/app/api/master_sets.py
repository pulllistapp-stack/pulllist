"""Master-set routes — set-completion tracking with base + master modes.

A user creates one MasterSet row per set they want to complete. The row
itself carries only preferences (binder size, display mode, sort); the
card list and progress are computed on read against `collection_items`
so the moment a card is added, progress moves.

Two completion definitions coexist per row:
    * base   — one slot per Card in the set
    * master — one slot per (Card, TCGplayer variant) — reverse holos,
               holofoils, unlimited, etc. counted separately from the
               base print. Variant enumeration comes from Card.
               tcgplayer_prices JSON keys (the same source the collection
               modal already uses for variant picking).

EN-only for now — the endpoint refuses non-`en` sets so we don't display
a half-populated Master target for JP catalogs that haven't been
variant-indexed. Trivial to lift when JP variant data lands.
"""

import secrets
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import and_, delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models import Card, CollectionItem, MasterSet, Set, User


def _new_share_token() -> str:
    """18 bytes → ~24-char URL-safe base64 (~144 bits entropy). Matches
    the sharing.py token shape so both surfaces feel identical."""
    return secrets.token_urlsafe(18)


router = APIRouter(prefix="/master-sets", tags=["master-sets"])


ALLOWED_BINDER_SIZES = {"3x3", "4x3", "4x4"}
ALLOWED_DISPLAY_MODES = {"base", "master"}
ALLOWED_SORT_MODES = {"number", "rarity"}


class MasterSetCreate(BaseModel):
    set_id: str = Field(..., max_length=64)
    binder_size: str = Field("3x3")
    display_mode: str = Field("base")
    sort_mode: str = Field("number")


class MasterSetUpdate(BaseModel):
    binder_size: str | None = None
    display_mode: str | None = None
    sort_mode: str | None = None


class MasterSetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    set_id: str
    set_name: str
    set_logo_url: str | None
    set_release_date: str | None
    binder_size: str
    display_mode: str
    sort_mode: str
    total_base: int
    """Card rows in the set (base target)."""
    owned_base: int
    """Distinct Card ids in the set the user owns at least one copy of."""
    total_master: int
    """Sum of variant counts across the set. Reverse holo + normal count
    as 2, hits with a single print count as 1."""
    owned_master: int
    """Distinct (card_id, variant) pairs the user owns from the set."""
    cover_image_url: str | None = None
    """User-uploaded cover image as a data: URL. Null → default mascot."""
    share_token: str | None = None
    """Public share token; null → not shared. Only surfaced to the row owner."""
    created_at: datetime
    updated_at: datetime


class BinderSlot(BaseModel):
    card_id: str
    number: str | None
    number_int: int | None
    name: str
    rarity: str | None
    image_small: str | None
    variant: str
    """'base' for the numbered card row; TCGplayer variant key
    ('normal' / 'holofoil' / 'reverseHolofoil' / ...) for master-mode
    extras. The frontend uses this to render tiny variant badges on
    reverse-holo / holo slots without an extra join."""
    owned: bool


class BinderView(BaseModel):
    master_set: MasterSetRead
    slots: list[BinderSlot]


def _validate_prefs(
    binder_size: str | None,
    display_mode: str | None,
    sort_mode: str | None,
) -> None:
    if binder_size is not None and binder_size not in ALLOWED_BINDER_SIZES:
        raise HTTPException(400, f"binder_size must be one of {ALLOWED_BINDER_SIZES}")
    if display_mode is not None and display_mode not in ALLOWED_DISPLAY_MODES:
        raise HTTPException(400, f"display_mode must be one of {ALLOWED_DISPLAY_MODES}")
    if sort_mode is not None and sort_mode not in ALLOWED_SORT_MODES:
        raise HTTPException(400, f"sort_mode must be one of {ALLOWED_SORT_MODES}")


def _variants_for(card: Card) -> list[str]:
    """TCGplayer variant keys we treat as separate Master-mode slots.

    Only accept dict payloads; legacy string / list rows are rare (a
    handful of very old promo imports) and we treat them as base-only —
    one slot, `normal`. When the card has no pricing at all we fall
    back to the same single 'normal' slot so an empty pricing row
    doesn't drop the card from the Master target entirely.
    """
    prices = card.tcgplayer_prices
    if isinstance(prices, dict) and prices:
        return list(prices.keys())
    return ["normal"]


async def _progress(
    db: AsyncSession, user_id: str, set_id: str
) -> tuple[int, int, int, int]:
    """Return (total_base, owned_base, total_master, owned_master)."""
    total_base_stmt = select(func.count()).select_from(Card).where(Card.set_id == set_id)
    total_base = (await db.execute(total_base_stmt)).scalar_one()

    owned_base_stmt = (
        select(func.count(func.distinct(CollectionItem.card_id)))
        .join(Card, CollectionItem.card_id == Card.id)
        .where(Card.set_id == set_id, CollectionItem.user_id == user_id)
    )
    owned_base = (await db.execute(owned_base_stmt)).scalar_one() or 0

    # Master target: walk every card, sum len(variants). Cheap — even
    # a 250-card set is one indexed query returning ~250 rows.
    variants_stmt = select(Card.id, Card.tcgplayer_prices).where(Card.set_id == set_id)
    card_variants: dict[str, list[str]] = {}
    for cid, prices in (await db.execute(variants_stmt)).all():
        if isinstance(prices, dict) and prices:
            card_variants[cid] = list(prices.keys())
        else:
            card_variants[cid] = ["normal"]
    total_master = sum(len(v) for v in card_variants.values())

    # Owned master: distinct (card_id, variant) pairs the user has,
    # intersected against the set's card_variants map to drop stray
    # collection rows with unusual variant strings.
    owned_variants_stmt = (
        select(CollectionItem.card_id, CollectionItem.variant)
        .join(Card, CollectionItem.card_id == Card.id)
        .where(Card.set_id == set_id, CollectionItem.user_id == user_id)
        .distinct()
    )
    owned_master = 0
    for cid, variant in (await db.execute(owned_variants_stmt)).all():
        allowed = card_variants.get(cid, ["normal"])
        if variant in allowed:
            owned_master += 1
    return total_base, owned_base, total_master, owned_master


async def _row_to_read(
    db: AsyncSession,
    row: MasterSet,
    s: Set,
    *,
    include_cover: bool = True,
) -> MasterSetRead:
    """Build the response DTO. `include_cover=False` on list endpoints
    keeps the response light — cover data URLs can be ~600KB each and
    a user with 10 binders would blow up the list payload otherwise."""
    tb, ob, tm, om = await _progress(db, row.user_id, row.set_id)
    return MasterSetRead(
        id=row.id,
        set_id=row.set_id,
        set_name=s.name,
        set_logo_url=s.logo_url,
        set_release_date=s.release_date.isoformat() if s.release_date else None,
        binder_size=row.binder_size,
        display_mode=row.display_mode,
        sort_mode=row.sort_mode,
        total_base=tb,
        owned_base=ob,
        total_master=tm,
        owned_master=om,
        cover_image_url=row.cover_image_url if include_cover else None,
        share_token=row.share_token,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.get("/for-card/{card_id}", response_model=list[MasterSetRead])
async def list_master_sets_containing_card(
    card_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[MasterSetRead]:
    """Return the caller's master sets that include this card. Since
    master sets are unique on (user, set) and each Card belongs to
    exactly one set, this returns 0 or 1 rows. Kept as a list for
    forward-compat in case cards ever span sets."""
    card = await db.get(Card, card_id)
    if card is None:
        raise HTTPException(404, "Card not found")

    stmt = (
        select(MasterSet, Set)
        .join(Set, MasterSet.set_id == Set.id)
        .where(MasterSet.user_id == user.id, MasterSet.set_id == card.set_id)
    )
    rows = (await db.execute(stmt)).all()
    return [
        await _row_to_read(db, ms, s, include_cover=False) for ms, s in rows
    ]


@router.get("", response_model=list[MasterSetRead])
async def list_master_sets(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[MasterSetRead]:
    """Every master set the caller has, newest first."""
    stmt = (
        select(MasterSet, Set)
        .join(Set, MasterSet.set_id == Set.id)
        .where(MasterSet.user_id == user.id)
        .order_by(MasterSet.created_at.desc())
    )
    rows = (await db.execute(stmt)).all()
    return [
        await _row_to_read(db, ms, s, include_cover=False) for ms, s in rows
    ]


@router.post("", response_model=MasterSetRead, status_code=status.HTTP_201_CREATED)
async def create_master_set(
    payload: MasterSetCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MasterSetRead:
    _validate_prefs(payload.binder_size, payload.display_mode, payload.sort_mode)

    s = (await db.execute(select(Set).where(Set.id == payload.set_id))).scalar_one_or_none()
    if s is None:
        raise HTTPException(404, "Set not found")
    if (s.language or "en") != "en":
        raise HTTPException(400, "Master sets are EN-only for now")

    row = MasterSet(
        user_id=user.id,
        set_id=payload.set_id,
        binder_size=payload.binder_size,
        display_mode=payload.display_mode,
        sort_mode=payload.sort_mode,
    )
    db.add(row)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "You already have a master set for this set")
    await db.refresh(row)
    return await _row_to_read(db, row, s)


@router.patch("/{master_set_id}", response_model=MasterSetRead)
async def update_master_set(
    master_set_id: int,
    payload: MasterSetUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MasterSetRead:
    _validate_prefs(payload.binder_size, payload.display_mode, payload.sort_mode)
    row = (
        await db.execute(
            select(MasterSet).where(
                MasterSet.id == master_set_id, MasterSet.user_id == user.id
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(404, "Master set not found")

    if payload.binder_size is not None:
        row.binder_size = payload.binder_size
    if payload.display_mode is not None:
        row.display_mode = payload.display_mode
    if payload.sort_mode is not None:
        row.sort_mode = payload.sort_mode
    await db.commit()
    await db.refresh(row)

    s = (await db.execute(select(Set).where(Set.id == row.set_id))).scalar_one()
    return await _row_to_read(db, row, s)


@router.delete("/{master_set_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_master_set(
    master_set_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(
        delete(MasterSet).where(
            MasterSet.id == master_set_id, MasterSet.user_id == user.id
        )
    )
    if result.rowcount == 0:
        raise HTTPException(404, "Master set not found")
    await db.commit()


@router.get("/{master_set_id}", response_model=BinderView)
async def get_binder_view(
    master_set_id: int,
    mode: str | None = None,
    sort: str | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BinderView:
    """Return the row + a flat slot list ready for grid rendering.

    `mode` / `sort` are transient overrides — they let the client flip
    Base ↔ Master and number ↔ rarity without a PATCH round-trip.
    Omit to fall back to the row's persisted preferences.
    """
    _validate_prefs(None, mode, sort)
    row = (
        await db.execute(
            select(MasterSet).where(
                MasterSet.id == master_set_id, MasterSet.user_id == user.id
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(404, "Master set not found")

    effective_mode = mode or row.display_mode
    effective_sort = sort or row.sort_mode

    s = (await db.execute(select(Set).where(Set.id == row.set_id))).scalar_one()
    head = await _row_to_read(db, row, s)

    order_by = (
        (Card.number_int.asc().nullslast(), Card.number.asc())
        if effective_sort == "number"
        else (Card.rarity.asc().nullslast(), Card.number_int.asc().nullslast())
    )
    cards = (
        await db.execute(
            select(Card).where(Card.set_id == row.set_id).order_by(*order_by)
        )
    ).scalars().all()

    owned_pairs: set[tuple[str, str]] = {
        (cid, variant)
        for cid, variant in (
            await db.execute(
                select(CollectionItem.card_id, CollectionItem.variant)
                .join(Card, CollectionItem.card_id == Card.id)
                .where(Card.set_id == row.set_id, CollectionItem.user_id == user.id)
                .distinct()
            )
        ).all()
    }
    owned_card_ids = {cid for cid, _ in owned_pairs}

    slots: list[BinderSlot] = []
    for c in cards:
        if effective_mode == "base":
            slots.append(
                BinderSlot(
                    card_id=c.id,
                    number=c.number,
                    number_int=c.number_int,
                    name=c.name,
                    rarity=c.rarity,
                    image_small=c.image_small,
                    variant="base",
                    owned=c.id in owned_card_ids,
                )
            )
        else:
            for v in _variants_for(c):
                slots.append(
                    BinderSlot(
                        card_id=c.id,
                        number=c.number,
                        number_int=c.number_int,
                        name=c.name,
                        rarity=c.rarity,
                        image_small=c.image_small,
                        variant=v,
                        owned=(c.id, v) in owned_pairs,
                    )
                )

    return BinderView(master_set=head, slots=slots)


# ── Cover image ─────────────────────────────────────────────────────
# Stored inline as a data: URL — frontend resizes to ~800x1200 JPEG
# before submit so payloads stay under a soft cap. Replacing the row's
# value is a UPDATE, so there are no orphan blobs to clean up if the
# user swaps covers (LO's requirement — "storage 안 차게").

_COVER_MAX_BYTES = 800_000
"""~600KB base64 = ~800KB of Text — comfortable ceiling for Neon rows
without ballooning list-endpoint responses. Frontend enforces a stricter
target (700KB), this is the last-line-of-defence server-side."""


class CoverUploadIn(BaseModel):
    image_data_url: str = Field(..., min_length=32)
    """data:image/{jpeg|png|webp};base64,... — validated for prefix +
    length. We don't inspect the payload bytes — the frontend does the
    resize + format work."""


@router.put("/{master_set_id}/cover", response_model=MasterSetRead)
async def set_master_set_cover(
    master_set_id: int,
    payload: CoverUploadIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MasterSetRead:
    if not payload.image_data_url.startswith("data:image/"):
        raise HTTPException(400, "cover must be a data:image/… URL")
    if len(payload.image_data_url) > _COVER_MAX_BYTES:
        raise HTTPException(
            413,
            f"cover exceeds {_COVER_MAX_BYTES // 1000}KB — "
            "resize / recompress before uploading",
        )

    row = (
        await db.execute(
            select(MasterSet).where(
                MasterSet.id == master_set_id, MasterSet.user_id == user.id
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(404, "Master set not found")

    row.cover_image_url = payload.image_data_url
    await db.commit()
    await db.refresh(row)

    s = (await db.execute(select(Set).where(Set.id == row.set_id))).scalar_one()
    return await _row_to_read(db, row, s)


@router.delete("/{master_set_id}/cover", response_model=MasterSetRead)
async def clear_master_set_cover(
    master_set_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MasterSetRead:
    row = (
        await db.execute(
            select(MasterSet).where(
                MasterSet.id == master_set_id, MasterSet.user_id == user.id
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(404, "Master set not found")

    row.cover_image_url = None
    await db.commit()
    await db.refresh(row)

    s = (await db.execute(select(Set).where(Set.id == row.set_id))).scalar_one()
    return await _row_to_read(db, row, s)


# ── Share ───────────────────────────────────────────────────────────
# Read-only public view at /p/masters/{token}. Owner mints the token
# once; deleting it revokes access. Same shape as the portfolio share
# in app/api/sharing.py so the two surfaces feel consistent.


@router.post("/{master_set_id}/share", response_model=MasterSetRead)
async def enable_master_set_share(
    master_set_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MasterSetRead:
    """Mint a share token if one doesn't already exist (idempotent).
    Returning the existing token on repeat calls avoids yanking a URL
    that friends already have."""
    row = (
        await db.execute(
            select(MasterSet).where(
                MasterSet.id == master_set_id, MasterSet.user_id == user.id
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(404, "Master set not found")

    if not row.share_token:
        row.share_token = _new_share_token()
        await db.commit()
        await db.refresh(row)

    s = (await db.execute(select(Set).where(Set.id == row.set_id))).scalar_one()
    return await _row_to_read(db, row, s)


@router.delete("/{master_set_id}/share", response_model=MasterSetRead)
async def revoke_master_set_share(
    master_set_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MasterSetRead:
    """Nulls the share token. Anyone with the old URL gets a 404."""
    row = (
        await db.execute(
            select(MasterSet).where(
                MasterSet.id == master_set_id, MasterSet.user_id == user.id
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(404, "Master set not found")

    row.share_token = None
    await db.commit()
    await db.refresh(row)

    s = (await db.execute(select(Set).where(Set.id == row.set_id))).scalar_one()
    return await _row_to_read(db, row, s)


@router.get("/public/{token}", response_model=BinderView)
async def get_public_binder_view(
    token: str,
    db: AsyncSession = Depends(get_db),
) -> BinderView:
    """Anonymous read-only binder view. Progress numbers reflect the
    OWNER's collection, not the viewer's. Same slot structure as the
    authenticated getBinderView so the frontend can reuse BinderSpread."""
    row = (
        await db.execute(
            select(MasterSet).where(MasterSet.share_token == token)
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(404, "Shared binder not found")

    s = (await db.execute(select(Set).where(Set.id == row.set_id))).scalar_one()
    head = await _row_to_read(db, row, s)
    # Hide the share token in the public payload — no reason to echo it
    # back to non-owners.
    head.share_token = None

    order_by = (
        (Card.number_int.asc().nullslast(), Card.number.asc())
        if row.sort_mode == "number"
        else (Card.rarity.asc().nullslast(), Card.number_int.asc().nullslast())
    )
    cards = (
        await db.execute(
            select(Card).where(Card.set_id == row.set_id).order_by(*order_by)
        )
    ).scalars().all()

    owned_pairs: set[tuple[str, str]] = {
        (cid, variant)
        for cid, variant in (
            await db.execute(
                select(CollectionItem.card_id, CollectionItem.variant)
                .join(Card, CollectionItem.card_id == Card.id)
                .where(
                    Card.set_id == row.set_id,
                    CollectionItem.user_id == row.user_id,
                )
                .distinct()
            )
        ).all()
    }
    owned_card_ids = {cid for cid, _ in owned_pairs}

    slots: list[BinderSlot] = []
    for c in cards:
        if row.display_mode == "base":
            slots.append(
                BinderSlot(
                    card_id=c.id,
                    number=c.number,
                    number_int=c.number_int,
                    name=c.name,
                    rarity=c.rarity,
                    image_small=c.image_small,
                    variant="base",
                    owned=c.id in owned_card_ids,
                )
            )
        else:
            for v in _variants_for(c):
                slots.append(
                    BinderSlot(
                        card_id=c.id,
                        number=c.number,
                        number_int=c.number_int,
                        name=c.name,
                        rarity=c.rarity,
                        image_small=c.image_small,
                        variant=v,
                        owned=(c.id, v) in owned_pairs,
                    )
                )

    return BinderView(master_set=head, slots=slots)
