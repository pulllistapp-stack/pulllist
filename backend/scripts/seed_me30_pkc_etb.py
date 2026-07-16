"""Add the Pokemon Center ETB variant to me30 (30th Celebration).

TCGCSV / TCGplayer doesn't track this variant as a separate SKU —
the box artwork is identical to the regular Elite Trainer Box
(p-704143), only the distribution channel (Pokemon Center
exclusive) and typically a small print-run bump differ. So we
insert a synthetic product row referencing the regular ETB's
image and price.

Price starts as a copy of the regular ETB's current market so the
row is immediately visible on the Sealed tab (which hides null-
priced rows by default). Conservative floor — PC exclusives
usually run 10-30% above the standard SKU — so this understates
until the eBay pipeline picks up real PC-marked sold listings.

Re-running the script REFRESHES the price from the regular ETB
(so it doesn't drift stale forever), but leaves the row otherwise
untouched.
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
        base = await db.get(Product, REGULAR_ETB_ID)
        if base is None:
            print(f"[error] regular ETB {REGULAR_ETB_ID} not found — abort")
            return

        market = base.market_price_usd
        low = base.low_price_usd
        high = base.high_price_usd
        print(
            f"copying prices from {REGULAR_ETB_ID}: "
            f"market={market} low={low} high={high}"
        )

        existing = await db.get(Product, PRODUCT_ID)
        if existing is not None:
            existing.market_price_usd = market
            existing.low_price_usd = low
            existing.high_price_usd = high
            await db.commit()
            print(f"[refreshed] {PRODUCT_ID} prices synced from regular ETB")
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
            market_price_usd=market,
            low_price_usd=low,
            high_price_usd=high,
            image_url=IMAGE_URL,
            tcgplayer_url=None,
            description=(
                "Pokemon Center exclusive ETB. Same artwork as the "
                "regular 30th Celebration ETB; different distribution "
                "channel and typically slightly reduced print run. "
                "Price mirrors the regular ETB until the eBay pipeline "
                "picks up PC-marked sold listings."
            ),
        )
        db.add(row)
        await db.commit()
        print(f"[added] {PRODUCT_ID}")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(main())
