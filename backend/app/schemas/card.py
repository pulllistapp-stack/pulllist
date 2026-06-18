from pydantic import BaseModel, ConfigDict


class CardBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    supertype: str | None = None
    subtypes: list[str] | None = None
    types: list[str] | None = None
    hp: str | None = None
    rarity: str | None = None
    number: str | None = None
    artist: str | None = None
    flavor_text: str | None = None
    national_pokedex_numbers: list[int] | None = None

    image_small: str | None = None
    image_large: str | None = None

    tcgplayer_url: str | None = None
    tcgplayer_product_id: int | None = None
    tcgplayer_prices: dict | None = None
    cardmarket_url: str | None = None
    cardmarket_prices: dict | None = None
    market_price_usd: float | None = None

    set_id: str
    set_name: str | None = None
    set_printed_total: int | None = None
    set_ptcgo_code: str | None = None


class CardRead(CardBase):
    pass


class CardList(BaseModel):
    items: list[CardRead]
    total: int
    page: int
    page_size: int
