from datetime import date

from pydantic import BaseModel, ConfigDict


class SetBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    name_ko: str | None = None
    """Korean translation of the set name. Frontend swaps to this when the
    user toggles UI language to KR. Null for sets we haven't mapped yet."""
    name_en: str | None = None
    """English equivalent of a JP-primary set name (e.g., 'Snow Hazard'
    for スノーハザード). Frontend renders 'JP (EN)' on JP catalog cards."""
    series: str | None = None
    printed_total: int | None = None
    total: int | None = None
    ptcgo_code: str | None = None
    release_date: date | None = None
    symbol_url: str | None = None
    logo_url: str | None = None
    set_type: str | None = None
    """Set categorization for browser grouping:
        MAIN / DECK / STUB / PROMO_LEGACY / PROMO_NEW. Only populated
        for JP sets right now (assigned by classify_jp_set_types.py).
        Null on EN/KR sets — frontend treats null as MAIN."""


class SetRead(SetBase):
    pass


class SetWithCardCount(SetBase):
    card_count: int
    total_value_usd: float | None = None
    """Sum of market_price_usd across all cards in the set. Sales-driven
    and noisier than mid; kept on the response for charts/back-compat."""
    total_value_mid_usd: float | None = None
    """Sum of every card's `mid_price_usd` — the TCGplayer midpoint
    listing price. This is the headline 'set value' the UI shows;
    avoids market's sales jitter and high's graded-slab inflation."""
    total_value_low_usd: float | None = None
    """Sum of every card's `low_price_usd` — the cheapest possible set
    completion if you bought every card at its current floor."""
    total_value_high_usd: float | None = None
    """Sum of every card's `high_price_usd` (rarity-ceiling capped) — the
    most expensive set completion. Pairs with `total_value_low_usd` to
    render a "$X – $Y" completion-cost band on the set card."""
    owned_unique: int | None = None
    """Distinct cards from this set in the requesting user's collection. None if anonymous."""
