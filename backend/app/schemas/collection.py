from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class CollectionItemCreate(BaseModel):
    card_id: str
    qty: int = Field(default=1, ge=1, le=999)
    condition: str = Field(default="NM", pattern="^(NM|LP|MP|HP|DMG)$")
    is_graded: bool = False
    grade: str | None = None
    acquired_at: date | None = None
    notes: str | None = Field(default=None, max_length=500)


class CollectionItemUpdate(BaseModel):
    qty: int | None = Field(default=None, ge=1, le=999)
    condition: str | None = Field(default=None, pattern="^(NM|LP|MP|HP|DMG)$")
    is_graded: bool | None = None
    grade: str | None = None
    acquired_at: date | None = None
    notes: str | None = Field(default=None, max_length=500)


class CollectionItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    card_id: str
    qty: int
    condition: str
    is_graded: bool
    grade: str | None = None
    acquired_at: date | None = None
    notes: str | None = None
    created_at: datetime


class CollectionItemDetail(CollectionItemRead):
    """Item enriched with card/set info for collection listings."""

    card_name: str
    card_number: str | None
    image_small: str | None
    rarity: str | None
    market_price_usd: float | None
    set_id: str
    set_name: str


class SetCompletion(BaseModel):
    set_id: str
    set_name: str
    total_cards: int
    owned_unique: int
    owned_total_qty: int
    completion_pct: float
    estimated_value_usd: float
