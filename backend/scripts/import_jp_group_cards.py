"""Import JP singles from a TCGCSV group into a specific PullList set.

Companion to ``ingest_jp_sealed.py`` — that script handles sealed
products, this one handles singles. Used to close gaps where a set
has known cards missing (e.g., S8a #030 Mew UR) or where an entire
sibling set was never seeded (e.g., s8a-P 25th Anniversary Promo
Card Pack).

Card fields populated from TCGCSV product + price feeds:
  - id: ``{set_id}-{number}`` (strips leading zeros)
  - name: TCGCSV product name (English — TCGCSV JP category doesn't
    surface JP names; JP `name` backfill happens via Bulbapedia
    scraper elsewhere if desired)
  - number: base number portion of "NNN/YYY" (e.g. "030/028" → "30")
  - rarity: TCGCSV Rarity attribute → JP-native code where possible,
    otherwise passed through (remap_jp_en_rarity_labels.py can
    normalize any EN labels that slip through)
  - image_small / image_large: TCGCSV imageUrl
  - market_price_usd / low / high / mid: from TCGCSV /prices
  - tcgplayer_product_id / tcgplayer_url

Idempotent — upserts on card id, skipping unchanged rows.

Usage:
    python -m scripts.import_jp_group_cards --group 23847 --set S8a-P
    python -m scripts.import_jp_group_cards --group 23638 --set S8a --only-missing
    python -m scripts.import_jp_group_cards --pairs 23847:S8a-P,23638:S8a
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
from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal, init_db  # noqa: E402
from app.models.card import Card  # noqa: E402
from app.models.set import Set  # noqa: E402


log = logging.getLogger("import_jp_group_cards")


TCGCSV_CAT = 85
TCGCSV_BASE = f"https://tcgcsv.com/tcgplayer/{TCGCSV_CAT}"
UA = "PullList-JPCards/1.0 (+https://pulllist.org)"


# Any of these fields in TCGCSV extendedData = single card, not sealed.
_CARD_ATTR_KEYS = {
    "Number", "HP", "CardType", "Attack 1", "Attack 2", "Retreat Cost",
    "Stage", "Weakness", "Resistance", "Rarity", "Flavor Text",
}


# EN → JP rarity code mapping (mirrors remap_jp_en_rarity_labels.py so
# imports land on the JP taxonomy directly rather than needing a
# follow-up remap pass).
_EN_TO_JP_RARITY: dict[str, str] = {
    "Common": "C",
    "Uncommon": "U",
    "Rare": "R",
    "Rare Holo": "R",
    "Rare Holo 1st Edition": "R",
    "Double Rare": "RR",
    "Triple Rare": "RRR",
    "Super Rare": "SR",
    "Special Rare": "SR",
    "Illustration Rare": "AR",
    "Special Illustration Rare": "SAR",
    "Ultra Rare": "UR",
    "Rare Ultra": "UR",
    "Rare Secret": "UR",
    "Rare Rainbow": "UR",
    "Hyper Rare": "HR",
    "Shiny Rare": "SSR",
    "Shiny Ultra Rare": "SSR",
    "Character Holo Rare": "CHR",
    "Character Super Rare": "CSR",
    "Rare Holo EX": "RR",
    "Rare Holo GX": "RR",
    "Rare Holo V": "RR",
    "Rare Holo VMAX": "RRR",
    "Rare Holo VSTAR": "RRR",
    "Rare Holo ex": "RR",
    "Rare ACE": "ACE",
    "Promo": "Promo",
}


# Any leading integer, optionally followed by "/YYY", optionally
# followed by an arbitrary parenthesized/suffix tail (TCGCSV appends
# things like "(Top Left)" for multi-panel cards e.g. Pikachu V-UNION
# 025-028). We take the leading integer only, so all four V-UNION
# panels collapse to their base numbers 25/26/27/28 instead of
# spawning bogus card ids like `S8a-025/028 (Top Left)`.
_NUM_LEADING_RE = re.compile(r"^\s*(\d+)")


def _normalize_number(raw: str | None) -> str | None:
    """'030/028' → '30'; '15' → '15'; '025/028 (Top Left)' → '25'."""
    if not raw:
        return None
    m = _NUM_LEADING_RE.match(raw)
    if not m:
        return None
    return str(int(m.group(1)))


def _ext(product: dict) -> dict[str, str]:
    return {e["name"]: e.get("value") for e in (product.get("extendedData") or [])}


def _map_rarity(tcgcsv_rarity: str | None) -> str | None:
    if not tcgcsv_rarity:
        return None
    return _EN_TO_JP_RARITY.get(tcgcsv_rarity.strip(), tcgcsv_rarity.strip())


def _pick_price(
    prices: list[dict],
) -> tuple[float | None, float | None, float | None, float | None]:
    if not prices:
        return None, None, None, None
    for p in prices:
        market = p.get("marketPrice")
        low = p.get("lowPrice")
        mid = p.get("midPrice")
        high = p.get("highPrice")
        if any(v is not None for v in (market, low, mid, high)):
            def _f(v: object) -> float | None:
                return float(v) if v is not None else None
            return _f(market), _f(low), _f(mid), _f(high)
    return None, None, None, None


async def _fetch(client: httpx.AsyncClient, path: str) -> list[dict]:
    r = await client.get(f"{TCGCSV_BASE}/{path}", timeout=45)
    r.raise_for_status()
    payload = r.json()
    if isinstance(payload, dict):
        return payload.get("results") or []
    return payload or []


async def import_pair(
    client: httpx.AsyncClient,
    group_id: int,
    target_set: str,
    only_missing: bool,
    dry_run: bool,
) -> dict[str, int]:
    stats = {
        "products_seen": 0,
        "sealed_skipped": 0,
        "cards_seen": 0,
        "added": 0,
        "updated": 0,
        "unchanged": 0,
        "skipped_no_number": 0,
    }

    async with SessionLocal() as db:
        # Validate target set exists so an FK violation doesn't tank
        # the whole run silently.
        target = await db.get(Set, target_set)
        if target is None:
            log.error(f"set '{target_set}' not in DB — seed it first")
            return stats

    products, prices = await asyncio.gather(
        _fetch(client, f"{group_id}/products"),
        _fetch(client, f"{group_id}/prices"),
    )
    prices_by_pid: dict[int, list[dict]] = defaultdict(list)
    for p in prices:
        pid = p.get("productId")
        if pid is not None:
            prices_by_pid[int(pid)].append(p)

    async with SessionLocal() as db:
        for p in products:
            stats["products_seen"] += 1
            name = p.get("name") or ""
            tcg_pid = p.get("productId")
            if tcg_pid is None or not name:
                continue

            ext = _ext(p)
            if not any(k in ext for k in _CARD_ATTR_KEYS):
                stats["sealed_skipped"] += 1
                continue
            stats["cards_seen"] += 1

            number = _normalize_number(ext.get("Number"))
            if number is None:
                stats["skipped_no_number"] += 1
                log.warning(
                    f"tcg_pid={tcg_pid} name={name!r} has no Number → skip"
                )
                continue

            card_id = f"{target_set}-{number}"
            rarity = _map_rarity(ext.get("Rarity"))
            image_url = p.get("imageUrl")
            image_large = image_url.replace("_200w", "_1000x1000") if image_url else None
            market, low, mid, high = _pick_price(prices_by_pid.get(int(tcg_pid), []))

            # Strip the trailing " - NNN/YYY" that TCGCSV sometimes
            # appends to disambiguate variants in list views.
            clean_name = re.sub(r"\s*-\s*\d+/\d+.*$", "", name).strip()

            fields = dict(
                id=card_id,
                name=clean_name,
                number=number,
                number_int=int(number) if number.isdigit() else None,
                rarity=rarity,
                image_small=image_url,
                image_large=image_large,
                market_price_usd=market,
                low_price_usd=low,
                high_price_usd=high,
                mid_price_usd=mid,
                tcgplayer_product_id=int(tcg_pid),
                tcgplayer_url=f"https://www.tcgplayer.com/product/{tcg_pid}",
                set_id=target_set,
                language="ja",
            )

            existing = await db.get(Card, card_id)

            if dry_run:
                state = "upd" if existing else "add"
                skip = " [SKIP: exists, only-missing]" if only_missing and existing else ""
                r_str = rarity or "?"
                m_str = f"${market}" if market else "$?"
                print(f"  [{state}] {card_id:15s} #{number:>4s} {r_str:5s} {m_str:>8s}  {clean_name}{skip}")
                continue

            if existing is not None and only_missing:
                stats["unchanged"] += 1
                continue

            if existing is None:
                db.add(Card(**fields))
                stats["added"] += 1
            else:
                changed = False
                for k, v in fields.items():
                    if k == "id":
                        continue
                    if getattr(existing, k) != v:
                        setattr(existing, k, v)
                        changed = True
                if changed:
                    stats["updated"] += 1
                else:
                    stats["unchanged"] += 1

        if not dry_run:
            await db.commit()

    return stats


async def run(pairs: list[tuple[int, str]], only_missing: bool, dry_run: bool) -> None:
    await init_db()
    grand = defaultdict(int)

    async with httpx.AsyncClient(headers={"User-Agent": UA}) as client:
        for gid, target in pairs:
            log.info(f"=== group {gid} → set {target} ===")
            stats = await import_pair(client, gid, target, only_missing, dry_run)
            for k, v in stats.items():
                log.info(f"  {k}: {v}")
                grand[k] += v

    log.info("=== grand total ===")
    for k, v in grand.items():
        log.info(f"  {k}: {v}")
    if dry_run:
        log.info("MODE: DRY-RUN — no writes")


def _parse_pairs(spec: str) -> list[tuple[int, str]]:
    out = []
    for chunk in spec.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        gid_s, sid = chunk.split(":", 1)
        out.append((int(gid_s.strip()), sid.strip()))
    return out


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--group", type=int, help="TCGCSV group id")
    p.add_argument("--set", help="Target PullList set id")
    p.add_argument(
        "--pairs",
        help="Comma-separated group:set pairs, e.g. '23847:S8a-P,23638:S8a'",
    )
    p.add_argument(
        "--only-missing",
        action="store_true",
        help="Only insert cards absent from DB; skip existing (no UPDATE).",
    )
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    if args.pairs:
        pairs = _parse_pairs(args.pairs)
    elif args.group and args.set:
        pairs = [(args.group, args.set)]
    else:
        p.error("provide --pairs OR both --group and --set")

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    asyncio.run(run(pairs, args.only_missing, args.dry_run))


if __name__ == "__main__":
    main()
