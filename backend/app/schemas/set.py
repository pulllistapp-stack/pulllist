from datetime import date

from pydantic import BaseModel, ConfigDict


class SetBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    name_ko: str | None = None
    """Korean translation of the set name. Frontend swaps to this when the
    user toggles UI language to KR. Null for sets we haven't mapped yet."""
    series: str | None = None
    printed_total: int | None = None
    total: int | None = None
    ptcgo_code: str | None = None
    release_date: date | None = None
    symbol_url: str | None = None
    logo_url: str | None = None


class SetRead(SetBase):
    pass


class SetWithCardCount(SetBase):
    card_count: int
    total_value_usd: float | None = None
    """Sum of market_price_usd across all cards in the set (None if no prices)."""
    owned_unique: int | None = None
    """Distinct cards from this set in the requesting user's collection. None if anonymous."""
