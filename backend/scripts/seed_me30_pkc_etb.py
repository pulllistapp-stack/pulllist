"""Add the Pokemon Center ETB variant to me30 (30th Celebration).

TCGCSV / TCGplayer doesn't track this variant as a separate SKU —
the box artwork is identical to the regular Elite Trainer Box
(p-704143), only the distribution channel (Pokemon Center
exclusive) and typically a small print-run bump differ. So we
insert a synthetic product row referencing the regular ETB's
image.

Price fields are left NULL — no TCGplayer feed means no reliable
market signal until the graded/live-listings pipeline picks it
up on its own. The row still appears on the set's Sealed tab so
users can add it to collections / wishlists and see it in
Portfolio counts.

Idempotent — re-running does nothing after the first insert.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal
from app.models.product import Product


PRODUCT_ID = "p-me30-etb-pkc"
REGULAR_ETB_ID = "p-704143"
IMAGE_URL = "https://tcgplayer-cdn.tcgplayer.com/product/704143_200w.jpg"


async def main() -> None:
    async with SessionLocal() as db:
        existing = await db.get(Product, PRODUCT_ID)
        if existing is not None:
            print(f"[skip] {PRODUCT_ID} already exists — no-op")
            return

        row = Product(
            id=PRODUCT_ID,
            name="30th Celebration Elite Trainer Box (Pokemon Center)",
            set_id="me30",
            product_type="etb",
            packs_per_box=9,
            tcgplayer_product_id=None,
            tcgplayer_group_id=24722,
            msrp_usd=None,
            market_price_usd=None,
            low_price_usd=None,
            high_price_usd=None,
            image_url=IMAGE_URL,
            tcgplayer_url=None,
            description=(
                "Pokemon Center exclusive ETB. Same artwork as the "
                "regular 30th Celebration ETB; different distribution "
                "channel and typically slightly reduced print run."
            ),
        )
        db.add(row)
        await db.commit()
        print(f"[added] {PRODUCT_ID}")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(main())
