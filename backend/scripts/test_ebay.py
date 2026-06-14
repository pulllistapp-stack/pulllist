"""Quick end-to-end check: get an eBay token, run one Browse search, print prices.

Usage:
    python -m scripts.test_ebay
    python -m scripts.test_ebay "Pokemon Charizard PSA 10"
    python -m scripts.test_ebay "Pokemon Mega Zygarde Premium Collection sealed"
"""
from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings
from app.services.ebay_client import POKEMON_CATEGORIES, EbayClient, EbayClientError, build_query


async def main(query: str) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    print(f"\neBay env: {settings.ebay_env}  base_url: {settings.ebay_base_url}")
    print(f"Raw query: {query!r}")
    print(f"Cleaned query: {build_query(query)!r}\n")

    try:
        async with EbayClient() as ebay:
            print("Step 1: requesting OAuth token…")
            token = await ebay._get_token()  # noqa: SLF001 — diagnostic
            print(f"  OK (token starts with {token[:30]}…)\n")

            # Search with Pokémon category + noise blocklist
            print("Step 2: filtered Browse search (Pokémon TCG cat + negative terms)…")
            cleaned = build_query(query)
            res = await ebay.browse_search(
                cleaned,
                limit=10,
                category_id=POKEMON_CATEGORIES["tcg_root"],
            )
            total = res.get("total", 0)
            items = res.get("itemSummaries") or []
            print(f"  total listings: {total}")
            print(f"  returned: {len(items)} items\n")

            for i, it in enumerate(items[:8], 1):
                title = (it.get("title") or "")[:80]
                price = (it.get("price") or {}).get("value", "?")
                cur = (it.get("price") or {}).get("currency", "")
                cond = it.get("condition", "?")
                seller = (it.get("seller") or {}).get("username", "?")
                print(f"  [{i}] {price} {cur}  ({cond}, {seller})")
                print(f"      {title}")

            print("\nStep 3: price_summary (Pokémon TCG cat + filters, 50 samples)…")
            summary = await ebay.price_summary(query, max_results=50)
            if summary is None:
                print("  No usable USD prices (verify keyset is Production)")
            else:
                print(json.dumps(summary, indent=2))

    except EbayClientError as e:
        print(f"\n[!] eBay client error: {e}")
        return 1
    except Exception as e:
        print(f"\n[!] Unexpected error: {type(e).__name__}: {e}")
        return 2

    print("\nDone.")
    return 0


if __name__ == "__main__":
    q = sys.argv[1] if len(sys.argv) > 1 else "pokemon charizard base set"
    raise SystemExit(asyncio.run(main(q)))
