from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


# TCGplayer's per-variant keys — all valid `variant` values.
_VARIANT_PATTERN = (
    r"^(normal|holofoil|reverseHolofoil|1stEdition|1stEditionHolofoil|"
    r"unlimited|unlimitedHolofoil)$"
)
_ACQUISITION_PATTERN = r"^(pull|trade|purchase|gift|other)$"


class CollectionItemCreate(BaseModel):
    card_id: str
    qty: int = Field(default=1, ge=1, le=999)
    variant: str = Field(default="normal", pattern=_VARIANT_PATTERN)
    condition: str = Field(default="NM", pattern="^(NM|LP|MP|HP|DMG)$")
    is_graded: bool = False
    grade: str | None = None
    acquired_at: date | None = None
    notes: str | None = Field(default=None, max_length=500)
    purchase_price_usd: float | None = Field(default=None, ge=0, le=1_000_000)
    acquisition_type: str | None = Field(default=None, pattern=_ACQUISITION_PATTERN)


class CollectionItemUpdate(BaseModel):
    qty: int | None = Field(default=None, ge=1, le=999)
    variant: str | None = Field(default=None, pattern=_VARIANT_PATTERN)
    condition: str | None = Field(default=None, pattern="^(NM|LP|MP|HP|DMG)$")
    is_graded: bool | None = None
    grade: str | None = None
    acquired_at: date | None = None
    notes: str | None = Field(default=None, max_length=500)
    purchase_price_usd: float | None = Field(default=None, ge=0, le=1_000_000)
    acquisition_type: str | None = Field(default=None, pattern=_ACQUISITION_PATTERN)


class CollectionItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    card_id: str
    qty: int
    variant: str = "normal"
    condition: str
    is_graded: bool
    grade: str | None = None
    acquired_at: date | None = None
    notes: str | None = None
    purchase_price_usd: float | None = None
    acquisition_type: str | None = None
    created_at: datetime


class CollectionItemDetail(CollectionItemRead):
    """Item enriched with card/set info for collection listings."""

    card_name: str
    card_number: str | None
    image_small: str | None
    # Hi-res card art — needed anywhere the row renders larger than a
    # thumbnail (slab frames, share cards). Nullable because JP/KR
    # catalogs sometimes only ship the small variant.
    image_large: str | None = None
    rarity: str | None
    market_price_usd: float | None
    # "graded" when market_price_usd came from a card_price_snapshots
    # graded-tier median (item is_graded + tier match); "raw" for
    # everything else including graded items where the tier hasn't
    # been scraped yet. The Vault uses this to show a tiny "PSA 10
    # median" badge on graded rows and a "no graded data — Refresh"
    # nudge when a graded item lands on raw fallback.
    price_source: str = "raw"
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
    # Full Set vs Master split — the base numbered run vs the whole set
    # including secrets / SIRs / hyper rares. `full_set_total` mirrors
    # Set.printed_total when available; falls back to `total_cards` when
    # the set doesn't declare a printed_total (rare — mostly promo sets).
    # `master_*` fields are aliases of the legacy `total_cards` /
    # `owned_unique` fields, kept alongside for consumers that want the
    # explicit naming without having to know the historical shape.
    full_set_total: int
    full_set_owned: int
    master_total: int
    master_owned: int
