"""Ingest JP sealed products from TCGCSV (Pokemon Japan, categoryId=85).

Parallel to ``ingest_products.py`` (which covers EN, categoryId=3). Walks
every TCGCSV JP group whose abbreviation matches one of our JP set IDs
and pulls the sealed SKUs (booster boxes, decks, ETBs, card file sets,
etc.), inserting them into the ``products`` table with the current
market/low/high price in USD.

Prices are fetched during ingest so LO sees non-null values immediately,
without needing to wait for the next daily sync. The daily sync
(``sync_products_daily``) still needs a follow-up patch to route JP
groups through category 85 rather than 3.

Usage:
    python -m scripts.ingest_jp_sealed --dry-run    # match report + preview
    python -m scripts.ingest_jp_sealed              # commit
    python -m scripts.ingest_jp_sealed --only m6a   # single set
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import re
import sys
from collections import defaultdict
from pathlib import Path

import httpx
from sqlalchemy import select, text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal, init_db  # noqa: E402
from app.models.product import Product  # noqa: E402


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
)
log = logging.getLogger("ingest_jp_sealed")

TCGCSV_CAT = 85  # Pokemon Japan
TCGCSV_BASE = f"https://tcgcsv.com/tcgplayer/{TCGCSV_CAT}"
UA = "PullList-JPSealed/1.0 (+https://pulllist.org)"


# JP product-type classifier. Order matters — most specific first.
# JP boxes/kits go through TCGplayer with English product names, so
# English keywords are the right thing to match on. The tags mirror
# the existing EN taxonomy so the frontend renders them the same way.
_TYPE_RULES: list[tuple[str, re.Pattern[str]]] = [
    ("premium_collection", re.compile(
        r"\b(premium\s+collection|special\s+collection|special\s+box|futuristic\s+box|card\s+file\s+set|special\s+delivery)\b",
        re.IGNORECASE,
    )),
    ("build_battle", re.compile(
        r"\b(deck\s+build\s+box|build\s*[&x]\s*battle|prerelease\s+kit)\b",
        re.IGNORECASE,
    )),
    ("etb", re.compile(r"\belite\s+trainer\s+box\b", re.IGNORECASE)),
    # JP boxes: "Booster Box", "Booster Display", "Deluxe Booster Box"
    ("booster_box", re.compile(
        r"\bbooster\s+(box|display|case)\b",
        re.IGNORECASE,
    )),
    ("booster_bundle", re.compile(r"\bbooster\s+bundle\b", re.IGNORECASE)),
    ("tin", re.compile(r"\btin\b", re.IGNORECASE)),
    ("blister", re.compile(
        r"\b(blister|3[- ]pack|1[- ]pack\s+blister|jumbo\s+pack)\b",
        re.IGNORECASE,
    )),
    ("sleeved_booster", re.compile(r"\bsleeved\s+booster\b", re.IGNORECASE)),
    # JP-specific: decks / starter sets. Kept as "other" because
    # products.product_type is a free-form varchar — the frontend
    # already groups these under a generic "deck / kit" bucket.
    ("other", re.compile(
        r"\b(starter\s+(set|deck)|deck\s+set|premium\s+deck|construction\s+starter|vmax\s+special\s+set|vstar\s+special\s+set|special\s+deck\s+set|entry\s+pack|movie\s+commemoration)\b",
        re.IGNORECASE,
    )),
]

# Any of these substrings means "sealed" (not a single card). Includes
# JP-specific phrasing.
_SEALED_HINTS = (
    "booster", "bundle", "elite trainer", "premium", "prerelease",
    "build & battle", "build and battle", "tin", "blister", "sealed",
    "collection", "case", "display", "sleeved", "starter deck",
    "starter set", "deck build", "deck set", "premium deck",
    "card file set", "special box", "futuristic box", "vmax special",
    "vstar special", "construction starter", "special deck set",
    "entry pack", "movie commemoration",
)

# Guardrail — even if it matches a sealed hint, drop items that also
# smell like a single-card listing.
_CARD_LIKE_KEYWORDS = (
    " ex ", " gx ", " vmax ", " vstar ", " v-union", "1st edition",
    " promo)", " art rare", " full art",
)

# Card number pattern (e.g. "012/086", "097/086", "SM11a"). If a name
# contains one of these, it's a single card even if a sealed hint
# fires by substring accident (e.g. "Vic-TIN-i" matching "tin").
_CARD_NUMBER_RE = re.compile(r"\b\d{1,4}\s*/\s*\d{1,4}\b")

# JP boxes are almost always 30 packs (not 36 like modern EN). Deluxe
# variants and pre-modern boxes vary — leave null if we don't know.
_PACKS_PER_TYPE: dict[str, int | None] = {
    "booster_box": 30,
    "booster_bundle": None,
    "build_battle": None,
    "sleeved_booster": 1,
    "blister": None,
    "etb": None,
    "premium_collection": None,
    "tin": None,
    "other": None,
}


def _classify_type(name: str) -> str:
    for tag, pattern in _TYPE_RULES:
        if pattern.search(name):
            return tag
    return "other"


def _looks_sealed(name: str) -> bool:
    lower = name.lower()
    if lower.startswith("code card") or "code card - " in lower:
        return False
    # Kill single-card listings up front. TCGCSV names cards as
    # "Card Name - NNN/NNN"; a card number pattern is the fastest,
    # highest-precision "this is a card, not sealed" signal, and it
    # dodges substring accidents like "Vic-TIN-i" matching the "tin"
    # sealed hint.
    if _CARD_NUMBER_RE.search(lower):
        return False
    if not any(hint in lower for hint in _SEALED_HINTS):
        return False
    return not any(kw in lower for kw in _CARD_LIKE_KEYWORDS)


def _tcgplayer_url(product_id: int) -> str:
    return f"https://www.tcgplayer.com/product/{product_id}"


def _pick_price(prices: list[dict]) -> tuple[float | None, float | None, float | None]:
    if not prices:
        return None, None, None
    for p in prices:
        market = p.get("marketPrice") or p.get("midPrice")
        if market is None and p.get("lowPrice") is None:
            continue
        return (
            float(market) if market is not None else None,
            float(p["lowPrice"]) if p.get("lowPrice") is not None else None,
            float(p["highPrice"]) if p.get("highPrice") is not None else None,
        )
    return None, None, None


async def _fetch(client: httpx.AsyncClient, path: str) -> list[dict]:
    r = await client.get(f"{TCGCSV_BASE}/{path}", timeout=45)
    r.raise_for_status()
    payload = r.json()
    if isinstance(payload, dict):
        return payload.get("results") or []
    return payload or []


# Hand-curated aliases for TCGCSV abbreviations that don't line up with
# our PullList set IDs. Each entry maps TCGCSV abbr (lowercase) → the
# PullList set id its sealed products should attach to.
#
# Discovered during the first prod ingest (2026-07-14): 103 TCGCSV
# groups had abbreviations we didn't recognise, 18 of them held real
# sealed SKUs. These aliases pick up 18 of those 28 sealed products.
# The remaining 10 belong to groups whose parent set doesn't exist in
# our DB yet (SBC / M-P / svL / CLL / NPF1 / Pt Arceus LV.X Decks),
# so they need set-seeding work before their sealed can land.
_TCGCSV_ALIASES: dict[str, str] = {
    # SM-era High-Class packs — PullList uses "p" suffix instead of "+"
    "sm1+": "SM1p",  # Sun and Moon plus (Enhanced Expansion)
    "sm2+": "SM2p",  # Let's Face New Trials
    "sm3+": "SM3p",  # Shining Legends
    "sm4+": "SM4p",  # GX Battle Boost
    "sm5+": "SM5p",  # Ultra Force
    # 25th Anniversary sub-groups (Golden Box, Promo Card Pack) →
    # rolled up under the base 25th Anniv Collection set S8a.
    "s8a-g": "S8a",
    "s8a-p": "S8a",
    # Promo card sets — TCGCSV uses "{era}-P" naming, PullList uses
    # "JPP-{era}" for the same concept.
    "s-p":  "JPP-S",   # SW-era promos
    "sv-p": "JPP-SV",  # SV-era promos
    # XY5 half-decks — TCGCSV names them XY5-B{color}, PullList
    # already has them as XY5g / XY5t (single-letter suffix).
    "xy5-bg": "XY5g",  # Gaia Volcano
    "xy5-bt": "XY5t",  # Tidal Storm
}


async def _build_set_map() -> dict[str, str]:
    """Return {abbreviation.lower(): pullist_set_id}, with hand-curated
    aliases layered on top so TCGCSV groups whose abbreviation doesn't
    literally match a PullList set id still route to the right set."""
    async with SessionLocal() as db:
        rows = (await db.execute(
            text("SELECT id FROM sets WHERE language = 'ja'")
        )).all()
    base = {r.id.lower(): r.id for r in rows}
    # Aliases only fire when their target set actually exists — silently
    # drop stale mappings instead of shovelling products at a phantom
    # set id (would violate the products.set_id FK on insert).
    known = {sid.lower() for sid in base.values()}
    for tcgcsv_abbr, our_id in _TCGCSV_ALIASES.items():
        if our_id.lower() in known:
            base[tcgcsv_abbr] = our_id
    return base


async def ingest(
    only_abbr: str | None,
    dry_run: bool,
) -> None:
    await init_db()
    set_map = await _build_set_map()
    log.info(f"PullList JP sets available for linking: {len(set_map)}")

    async with httpx.AsyncClient(headers={"User-Agent": UA}) as client:
        groups = await _fetch(client, "groups")
        log.info(f"TCGCSV JP groups: {len(groups)}")

        # Filter to groups whose abbreviation matches a PullList set.
        candidates: list[tuple[dict, str]] = []
        for g in groups:
            abbr = (g.get("abbreviation") or "").strip()
            if not abbr:
                continue
            if only_abbr and abbr.lower() != only_abbr.lower():
                continue
            our_set = set_map.get(abbr.lower())
            if our_set is None:
                continue
            candidates.append((g, our_set))
        log.info(f"matched groups to process: {len(candidates)}")

        totals = {
            "groups_processed": 0,
            "products_seen": 0,
            "singles_skipped": 0,
            "sealed_found": 0,
            "added": 0,
            "updated": 0,
            "unchanged": 0,
            "fetch_errors": 0,
        }
        per_set: dict[str, int] = defaultdict(int)

        for g, our_set in candidates:
            gid = g["groupId"]
            abbr = g["abbreviation"]
            totals["groups_processed"] += 1

            try:
                products, price_rows = await asyncio.gather(
                    _fetch(client, f"{gid}/products"),
                    _fetch(client, f"{gid}/prices"),
                )
            except Exception as exc:
                totals["fetch_errors"] += 1
                log.warning(f"[{abbr}] fetch failed: {exc}")
                continue

            # Fold prices by productId for O(1) lookup.
            prices_by_id: dict[int, list[dict]] = defaultdict(list)
            for pr in price_rows:
                pid = pr.get("productId")
                if pid is not None:
                    prices_by_id[int(pid)].append(pr)

            async with SessionLocal() as db:
                for p in products:
                    totals["products_seen"] += 1
                    name = p.get("name") or ""
                    tcg_pid = p.get("productId")
                    if tcg_pid is None or not name:
                        continue
                    # Primary filter: any TCGCSV extendedData attribute
                    # that describes a card's rules text (HP, attack,
                    # retreat cost, etc.) marks it as a single card,
                    # not sealed. Modern JP cards carry "Number"; the
                    # vintage sets (Southern Island, PMCG-era) carry
                    # "HP" / "CardType" / "Attack 1" / "Rarity" but no
                    # "Number". Union of both catches everything.
                    _CARD_ATTR_KEYS = {
                        "Number", "HP", "CardType", "Attack 1", "Attack 2",
                        "Retreat Cost", "Stage", "Weakness", "Resistance",
                        "Rarity", "Flavor Text",
                    }
                    ext = p.get("extendedData") or []
                    is_card = any(
                        e.get("name") in _CARD_ATTR_KEYS for e in ext
                    )
                    if is_card:
                        totals["singles_skipped"] += 1
                        continue
                    # Secondary guard for the rare product that ships
                    # without extendedData at all (mostly ancient promo
                    # groups) — fall back to the name-based heuristic.
                    if not ext and not _looks_sealed(name):
                        totals["singles_skipped"] += 1
                        continue
                    totals["sealed_found"] += 1

                    ptype = _classify_type(name)
                    market, low, high = _pick_price(prices_by_id.get(int(tcg_pid), []))
                    our_id = f"p-{int(tcg_pid)}"

                    fields = dict(
                        id=our_id,
                        name=name,
                        set_id=our_set,
                        product_type=ptype,
                        packs_per_box=_PACKS_PER_TYPE.get(ptype),
                        tcgplayer_product_id=int(tcg_pid),
                        tcgplayer_group_id=int(gid),
                        market_price_usd=market,
                        low_price_usd=low,
                        high_price_usd=high,
                        image_url=p.get("imageUrl"),
                        tcgplayer_url=_tcgplayer_url(int(tcg_pid)),
                        description=(p.get("description") or None),
                    )

                    existing = await db.get(Product, our_id)

                    if dry_run:
                        state = "upd" if existing else "add"
                        print(f"[{state}] {our_set:10s} {ptype:20s} ${market or '?':>8}  {name[:55]}")
                        continue

                    if existing is None:
                        db.add(Product(**fields))
                        totals["added"] += 1
                        per_set[our_set] += 1
                    else:
                        changed = False
                        for k, v in fields.items():
                            if getattr(existing, k) != v:
                                setattr(existing, k, v)
                                changed = True
                        if changed:
                            totals["updated"] += 1
                        else:
                            totals["unchanged"] += 1

                if not dry_run:
                    await db.commit()

    log.info("=== summary ===")
    for k, v in totals.items():
        log.info(f"  {k}: {v}")
    if per_set and not dry_run:
        log.info("=== per-set new adds (top 20) ===")
        for sid, n in sorted(per_set.items(), key=lambda x: -x[1])[:20]:
            log.info(f"  {sid:12s} +{n}")
    if dry_run:
        log.info("MODE: DRY-RUN — no writes")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--only", help="limit to a single TCGCSV abbreviation, e.g. SV11B")
    args = p.parse_args()
    asyncio.run(ingest(args.only, args.dry_run))


if __name__ == "__main__":
    main()
