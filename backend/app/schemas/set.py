from datetime import date

from pydantic import BaseModel, ConfigDict


class SetBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
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
