"""Diagnose why a specific card's eBay snapshot succeeded or failed.

Hits eBay live with the same query the snapshot would build, then walks each
returned listing through the filter stack and prints the verdict. Useful
when a card surfaces 'No price history yet' and you need to know whether
the eBay catalog is empty, the noise filter is too aggressive, the chase-
rarity number gate dropped everything, or the sanity floor is biting.

Usage:
    python -m scripts.inspect_card_ebay me5-121
    python -m scripts.inspect_card_ebay me5-121 --max-results 100
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import SessionLocal, init_db
from app.models import Card
from app.services.ebay_client import (
    EbayClient,
    EbayClientError,
    build_card_query,
)


def _fmt_money(v: float | None) -> str:
    return "—".rjust(8) if v is None else f"${v:>7.2f}"


def _truncate(s: str, width: int) -> str:
    return s if len(s) <= width else s[: width - 1] + "…"


def _print_pass(p: dict, idx: int) -> None:
    cls = p["classifications"]
    kept = [c for c in cls if c.kept]
    print(
        f"\n--- Pass {idx + 1}: {p['label']}  "
        f"(eBay reports {p['total_listings_hint']} total, "
        f"fetched {len(cls)}, kept {len(kept)}) ---"
    )

    if not cls:
        print("  (no listings returned)")
        return

    print(f"  {'STATUS':<8} {'PRICE':>9}  {'REASON':<32}  TITLE")
    print(f"  {'-' * 8} {'-' * 9}  {'-' * 32}  {'-' * 56}")
    for c in cls:
        status = "KEPT" if c.kept else "drop"
        reason = c.drop_reason or ""
        print(
            f"  {status:<8} {_fmt_money(c.price_usd)}  "
            f"{_truncate(reason, 32):<32}  {_truncate(c.title, 56)}"
        )

    # Breakdown of drop reasons.
    drop_buckets: dict[str, int] = {}
    for c in cls:
        if not c.kept and c.drop_reason:
            key = c.drop_reason.split(":", 1)[0]
            drop_buckets[key] = drop_buckets.get(key, 0) + 1
    if drop_buckets:
        print("\n  drop reasons:")
        for k, v in sorted(drop_buckets.items(), key=lambda kv: -kv[1]):
            print(f"    {k:<24} {v}")


async def main_async(card_id: str, max_results: int) -> int:
    await init_db()

    async with SessionLocal() as db:
        stmt = (
            select(Card).options(selectinload(Card.set)).where(Card.id == card_id)
        )
        card = (await db.execute(stmt)).scalar_one_or_none()

    if card is None:
        print(f"Card not found: {card_id!r}")
        return 1

    set_ = card.set

    print("=" * 80)
    print(f"Card        : {card.id}")
    print(f"Name        : {card.name}")
    print(f"Set         : {set_.name if set_ else '(none)'}  ({card.set_id})")
    print(f"Number      : {card.number}  (printed_total={getattr(set_, 'printed_total', None)})")
    print(f"Rarity      : {card.rarity}")
    print(f"Language    : {card.language}")
    print(f"TCG ref ($) : {card.market_price_usd}")
    print("=" * 80)

    query = build_card_query(
        card_name=card.name,
        card_number=card.number,
        printed_total=set_.printed_total if set_ else None,
        set_name=set_.name if set_ else None,
        rarity=card.rarity,
    )
    print(f"\nBuilt query : {query!r}")

    try:
        async with EbayClient() as ebay:
            detail = await ebay.price_summary_with_trace(
                query,
                max_results=max_results,
                reference_price_usd=(
                    float(card.market_price_usd)
                    if card.market_price_usd is not None
                    else None
                ),
                card_number=card.number,
                rarity=card.rarity,
            )
    except EbayClientError as e:
        print(f"\neBay error: {e}")
        return 2

    cfg = detail["config"]
    print(f"Cleaned query: {detail['cleaned_query']!r}")
    print("\nFilter config:")
    print(f"  is_chase           : {detail['is_chase']}")
    print(f"  min_required       : {detail['min_required']} listings")
    print(f"  sanity_floor       : {cfg.sanity_floor}")
    print(f"  sanity_ceiling     : {cfg.sanity_ceiling}")
    print(
        f"  number_pattern     : "
        f"{cfg.number_pattern.pattern if cfg.number_pattern else '(disabled)'}"
    )

    for idx, p in enumerate(detail["passes"]):
        _print_pass(p, idx)

    print("\n" + "=" * 80)
    summary = detail["summary"]
    if summary is None:
        print("VERDICT: no usable price data (snapshot would write nothing for this card).")
        return 0

    print(
        f"VERDICT: aggregate computed from {summary['count_sampled']} listings.\n"
        f"  low    = ${summary['low']:.2f}\n"
        f"  median = ${summary['median']:.2f}\n"
        f"  high   = ${summary['high']:.2f}\n"
        f"  (eBay total_listings ≈ {summary['total_listings']})"
    )
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("card_id", help="Card ID, e.g. me5-121")
    parser.add_argument(
        "--max-results", type=int, default=50,
        help="Listings to ask eBay for in each pass (default 50, max 200)",
    )
    args = parser.parse_args()
    sys.exit(asyncio.run(main_async(args.card_id, args.max_results)))


if __name__ == "__main__":
    main()
