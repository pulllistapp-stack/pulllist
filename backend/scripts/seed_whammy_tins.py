"""Add the 3 Triple Whammy Tin variants to sv09 (Journey Together)
and sv10 (Destined Rivals) sealed product lists.

Triple Whammy Tin is a cross-set supplemental release (TCGCSV
tracks it under "Miscellaneous Cards & Products", group 2374).
Each tin contains 3 booster packs from recent SV sets and comes
in 3 flavors distinguished by cover art:
  * Tyranitar  (pid 591145)
  * Darkrai    (pid 591146)
  * Slaking    (pid 591147)

LO wants all 3 visible on BOTH sv09 and sv10 Sealed tabs. Since
`Product.tcgplayer_product_id` is unique, the sv09 rows keep the
real TCGplayer id (future price syncs update them) and the sv10
rows are mirrors with tcgplayer_product_id=NULL. Both carry the
same image + price so users don't see a discrepancy.

Idempotent — re-running refreshes prices from TCGCSV but leaves
existing rows untouched otherwise.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal
from app.models.product import Product


MCAP_GROUP = 2374
TCGCSV_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/130.0.0.0 Safari/537.36"
)

WHAMMY_TINS = [
    {"pid": 591145, "pokemon": "Tyranitar"},
    {"pid": 591146, "pokemon": "Darkrai"},
    {"pid": 591147, "pokemon": "Slaking"},
]

MIRROR_SETS = [
    ("sv09", ""),      # canonical rows (keep tcgplayer_product_id)
    ("sv10", "-dri"),  # mirror rows (null tcgplayer_product_id)
]


async def _fetch_prices() -> dict[int, dict]:
    async with httpx.AsyncClient(headers={"User-Agent": TCGCSV_UA}, timeout=30) as c:
        r = await c.get(f"https://tcgcsv.com/tcgplayer/3/{MCAP_GROUP}/prices")
        r.raise_for_status()
        return {p["productId"]: p for p in r.json().get("results", [])}


async def main() -> None:
    prices_by_pid = await _fetch_prices()

    async with SessionLocal() as db:
        added = refreshed = 0
        for tin in WHAMMY_TINS:
            pid = tin["pid"]
            pok = tin["pokemon"]
            pr = prices_by_pid.get(pid, {})
            market = pr.get("marketPrice") or pr.get("midPrice") or 27.50
            low = pr.get("lowPrice")
            high = pr.get("highPrice")
            image = f"https://tcgplayer-cdn.tcgplayer.com/product/{pid}_200w.jpg"
            name = f"Triple Whammy Tin [{pok}]"

            for set_id, suffix in MIRROR_SETS:
                pid_col: int | None = pid if suffix == "" else None
                row_id = f"p-{pid}{suffix}"
                existing = await db.get(Product, row_id)
                if existing is not None:
                    existing.market_price_usd = market
                    existing.low_price_usd = low
                    existing.high_price_usd = high
                    refreshed += 1
                    print(f"[refresh] {row_id:<20} {set_id}  ${market:.2f}  {name}")
                    continue

                row = Product(
                    id=row_id,
                    name=name,
                    set_id=set_id,
                    product_type="tin",
                    packs_per_box=3,
                    tcgplayer_product_id=pid_col,
                    tcgplayer_group_id=MCAP_GROUP,
                    msrp_usd=None,
                    market_price_usd=market,
                    low_price_usd=low,
                    high_price_usd=high,
                    image_url=image,
                    tcgplayer_url=(
                        f"https://www.tcgplayer.com/product/{pid}"
                        if suffix == ""
                        else None
                    ),
                    description=(
                        "Triple Whammy Tin — 3 booster packs from recent "
                        "Scarlet & Violet sets. Cross-set supplemental "
                        "release; mirrored under sv09 and sv10 for "
                        "browsing convenience."
                    ),
                )
                db.add(row)
                added += 1
                print(f"[added]   {row_id:<20} {set_id}  ${market:.2f}  {name}")

        await db.commit()
        print(f"\ndone — added={added} refreshed={refreshed}")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(main())
