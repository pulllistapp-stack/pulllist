from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Card(Base):
    __tablename__ = "cards"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    supertype: Mapped[str | None] = mapped_column(String(64), nullable=True)
    subtypes: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    types: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    hp: Mapped[str | None] = mapped_column(String(16), nullable=True)
    hp_int: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    rarity: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    number_int: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    artist: Mapped[str | None] = mapped_column(String(255), nullable=True)
    flavor_text: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    national_pokedex_numbers: Mapped[list[int] | None] = mapped_column(JSON, nullable=True)

    image_small: Mapped[str | None] = mapped_column(String(512), nullable=True)
    image_large: Mapped[str | None] = mapped_column(String(512), nullable=True)

    tcgplayer_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    tcgplayer_prices: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    cardmarket_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    cardmarket_prices: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    market_price_usd: Mapped[float | None] = mapped_column(Float, nullable=True, index=True)

    set_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("sets.id", ondelete="CASCADE"), index=True
    )

    language: Mapped[str] = mapped_column(
        String(8), default="en", server_default="en", nullable=False, index=True
    )
    """ISO 639 lang code — 'en' / 'ja' / 'ko' / 'zh-CN' / 'zh-TW'."""

    name_local: Mapped[str | None] = mapped_column(String(255), nullable=True)
    """Native-language card name (e.g., リザードン). Use `name` for English."""

    parent_card_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True
    )
    """If this card is a translation of another, points to the source card id."""

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    set: Mapped["Set"] = relationship(back_populates="cards")  # noqa: F821
