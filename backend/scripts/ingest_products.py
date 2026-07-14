"""Ingest sealed / boxed products from TCGCSV.

Each TCGCSV group (roughly one Pokemon set) exposes both singles and
sealed items on the same `/tcgplayer/3/{group_id}/products` feed. The
existing card-focused ingest (`seed_promo_group.py`, `sync_tcgcsv_daily`)
skips anything that looks sealed; this script does the reverse — keeps
sealed and drops singles.

Usage:
    python -m scripts.ingest_products --group 24451              # one group
    python -m scripts.ingest_products --all                       # every mapped group
    python -m scripts.ingest_products --set-id sv09              # by our set id (needs mapping)
    python -m scripts.ingest_products --group 24451 --dry-run    # preview
"""

from __future__ import annotations

import argparse
import asyncio
import re
from typing import Iterable, Optional

import httpx
from sqlalchemy import select

from app.database import SessionLocal
from app.models.product import Product


TCGCSV = "https://tcgcsv.com/tcgplayer/3"
UA = "PullList-Products/1.0 (+https://pulllist.org)"


# Product-type classifier — order matters (most specific first).
_TYPE_RULES: list[tuple[str, re.Pattern[str]]] = [
    ("etb", re.compile(r"\belite\s+trainer\s+box\b", re.IGNORECASE)),
    ("premium_collection", re.compile(r"\b(premium\s+collection|ultra[- ]premium|special\s+collection|special\s+delivery)\b", re.IGNORECASE)),
    ("build_battle", re.compile(r"\b(build\s*[&x]\s*battle|prerelease\s+kit)\b", re.IGNORECASE)),
    ("booster_box", re.compile(r"\bbooster\s+(box|display|case)\b", re.IGNORECASE)),
    ("booster_bundle", re.compile(r"\bbooster\s+bundle\b", re.IGNORECASE)),
    ("tin", re.compile(r"\btin\b", re.IGNORECASE)),
    ("blister", re.compile(r"\b(blister|3[- ]pack|1[- ]pack\s+blister)\b", re.IGNORECASE)),
    ("sleeved_booster", re.compile(r"\bsleeved\s+booster\b", re.IGNORECASE)),
]

# Strong sealed keywords — presence means sealed no matter what other
# cues appear. Bracketed card references inside a tin's label
# ("30th Celebration Tin [Sylveon ex]") or "(48 ct)" quantity strings
# shouldn't overturn this.
_STRONG_SEALED_RE = re.compile(
    r"\b(?:"
    r"booster|elite\s+trainer|etb|bundle|blister|"
    r"build\s*[&x]\s*battle|build\s+and\s+battle|sleeved\s+booster|"
    r"trainer(?:'|’)s?\s+kit|"
    r"booster\s+pack|display\s+box|battle\s+stadium"
    r")\b",
    re.IGNORECASE,
)

# Weak sealed keywords — mean sealed ONLY when no card-shape pattern
# is also present. `tin` word-bounded avoids Gira*tin*a. `collection`
# / `premium` / `case` / `display` can be part of card names in some
# vintage sets, so they need the card-pattern gate.
_WEAK_SEALED_RE = re.compile(
    r"\b(?:tin|case|collection|premium|prerelease|display|sleeved|"
    r"figure)\b",
    re.IGNORECASE,
)

# Card-shape patterns. Presence in a WEAK-sealed name flips it back
# to a single card. Kept intentionally strict — pure numeric
# parentheticals like "(48 ct)" or "(6 packs)" are pack quantity
# strings on sealed listings, NOT card numbers, so they're excluded
# via the trailing unit-word negative lookahead.
_CARD_NAME_PATTERNS = [
    # `43/101` printed card number
    re.compile(r"\b\d+\s*/\s*\d+\b"),
    # named card treatment parentheticals — always cards
    re.compile(
        r"\((?:prerelease|full\s+art|alternate|reverse\s+holo|"
        r"secret|holo|shiny|rainbow|hyper|master\s+ball|"
        r"poke\s+ball|special\s+illustration|team\s+plasma)"
        r"[^)]*\)",
        re.IGNORECASE,
    ),
    # `[Staff]` / `[Prerelease]` / `[Jumbo]` etc — card variants
    re.compile(
        r"\[(?:staff|prerelease|jumbo|oversized)[^\]]*\]",
        re.IGNORECASE,
    ),
    # Set-code + number suffix (`SM151`, `XY117`, `BW32`) — always cards
    re.compile(r"\b(?:sm|xy|bw|dp|hgss|sv|swsh)\d+\b", re.IGNORECASE),
    # Bare `(N)` where N is a card number (small int, no unit word)
    re.compile(r"\(\s*\d{1,3}\s*\)"),
]

# Card variant tokens at END-OF-NAME. "Victini EX" and "Giratina EX"
# end in the variant marker; "EX Power Trio Tin" starts with "EX" as
# an era brand — the era prefix must NOT reject the tin. Anchoring
# on the end (allowing a trailing parenthetical like "(Full Art)")
# discriminates the two.
_CARD_LIKE_ENDING_RE = re.compile(
    r"\b(?:ex|gx|vmax|vstar|v-?union|prism\s+star)\s*(?:\([^)]*\))?\s*$",
    re.IGNORECASE,
)
# `1st Edition` is a card-only signal wherever it appears.
_FIRST_EDITION_RE = re.compile(r"\b1st\s+edition\b", re.IGNORECASE)


# ETBs and Premium Collections don't hold booster packs in a
# clean count; leave packs_per_box null for them. Booster boxes /
# bundles have known counts.
_PACKS_PER_TYPE: dict[str, int | None] = {
    "booster_box": 36,
    "booster_bundle": 6,
    "build_battle": 4,
    "sleeved_booster": 1,
    "blister": 3,       # typical modern 3-pack blister
    "etb": 9,           # modern ETB packs — Scarlet Violet era = 9
    "premium_collection": None,
    "tin": 4,           # standard modern tins
    "other": None,
}


def _classify_type(name: str) -> str:
    for tag, pattern in _TYPE_RULES:
        if pattern.search(name):
            return tag
    return "other"


def _looks_sealed(name: str) -> bool:
    lower = name.lower()
    # Digital-only code cards ride the same TCGCSV feed but aren't
    # physical sealed product — drop them so the /products browse
    # doesn't clutter with intangible SKUs.
    if lower.startswith("code card") or "code card - " in lower:
        return False

    # STRONG sealed keyword (booster, ETB, bundle, blister,
    # build & battle, sleeved booster, trainer kit) → always sealed.
    # Bracketed card names inside tin labels ("[Sylveon ex]") and
    # pack-count parentheticals ("(48 ct)") do NOT override this.
    if _STRONG_SEALED_RE.search(name):
        return True

    # WEAK sealed keyword (tin, case, collection, premium, prerelease,
    # display, sleeved, figure). Word-bounded regex so "tin" doesn't
    # fire on Gira*tin*a. Only accept as sealed when no card-shape
    # signal is present outside brackets.
    if not _WEAK_SEALED_RE.search(name):
        return False

    # Tin / Case products often carry a bracketed featured-card
    # description ("30th Celebration Tin [Sylveon ex]", "Kalos Power
    # Tin [Chesnaught EX]"). Strip bracket contents before running
    # card-shape checks so the featured-card label doesn't reclassify
    # the tin itself.
    bare = re.sub(r"\[[^\]]*\]", " ", name)

    for pat in _CARD_NAME_PATTERNS:
        if pat.search(bare):
            return False
    if _FIRST_EDITION_RE.search(bare):
        return False
    if _CARD_LIKE_ENDING_RE.search(bare):
        return False
    return True


def _tcgplayer_url(product_id: int, name: str) -> str:
    # Real product page URL — affiliate wrapping happens frontend-side
    # via lib/affiliate.ts before render.
    return f"https://www.tcgplayer.com/product/{product_id}"


def _extract_market(prices: list[dict]) -> tuple[float | None, float | None, float | None]:
    """Pull (market, low, high) from TCGCSV price payload if present."""
    if not prices:
        return None, None, None
    # TCGCSV groups by variant/subTypeName; take the first non-null.
    for p in prices:
        mid = p.get("marketPrice") or p.get("midPrice")
        if mid is None:
            continue
        return (
            float(mid) if mid is not None else None,
            float(p.get("lowPrice")) if p.get("lowPrice") is not None else None,
            float(p.get("highPrice")) if p.get("highPrice") is not None else None,
        )
    return None, None, None


async def _fetch_group_products(
    client: httpx.AsyncClient, group_id: int
) -> list[dict]:
    """Fetch products for a group. Returns raw TCGCSV product objects."""
    url = f"{TCGCSV}/{group_id}/products"
    r = await client.get(url, timeout=45)
    r.raise_for_status()
    payload = r.json()
    if isinstance(payload, dict):
        return payload.get("results") or []
    return payload or []


async def ingest_group(
    group_id: int,
    set_id: Optional[str] = None,
    dry_run: bool = False,
) -> dict[str, int]:
    stats = {"seen": 0, "sealed": 0, "singles_skipped": 0, "added": 0, "updated": 0}
    async with httpx.AsyncClient(headers={"User-Agent": UA}) as client:
        products = await _fetch_group_products(client, group_id)

    async with SessionLocal() as db:
        for p in products:
            stats["seen"] += 1
            name = p.get("name") or ""
            product_id = p.get("productId")
            if product_id is None or not name:
                continue

            if not _looks_sealed(name):
                stats["singles_skipped"] += 1
                continue
            stats["sealed"] += 1

            product_type = _classify_type(name)
            market, low, high = _extract_market(p.get("prices") or [])

            our_id = f"p-{product_id}"
            existing = await db.get(Product, our_id)
            fields = dict(
                id=our_id,
                name=name,
                set_id=set_id,
                product_type=product_type,
                packs_per_box=_PACKS_PER_TYPE.get(product_type),
                tcgplayer_product_id=int(product_id),
                tcgplayer_group_id=group_id,
                market_price_usd=market,
                low_price_usd=low,
                high_price_usd=high,
                image_url=p.get("imageUrl"),
                tcgplayer_url=_tcgplayer_url(int(product_id), name),
                description=(p.get("description") or None),
            )

            if dry_run:
                print(f"[dry] {our_id:>15}  {product_type:<20} {name[:60]}")
                continue

            if existing is None:
                db.add(Product(**fields))
                stats["added"] += 1
                print(f"[add ] {our_id:>15}  {product_type:<20} {name[:60]}")
            else:
                for k, v in fields.items():
                    setattr(existing, k, v)
                stats["updated"] += 1

        if not dry_run:
            await db.commit()

    return stats


async def main(argv: Iterable[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--group", type=int, help="TCGCSV group id")
    parser.add_argument("--set-id", help="Our set id to link (optional)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(list(argv) if argv is not None else None)

    if not args.group:
        parser.error("--group is required (use --set-id to link to our set)")

    stats = await ingest_group(
        args.group, set_id=args.set_id, dry_run=args.dry_run
    )
    print("\n[done]", stats)


if __name__ == "__main__":
    asyncio.run(main())
