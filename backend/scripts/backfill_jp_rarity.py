"""Backfill rarity for JP cards by reading their English equivalent on Limitless.

Limitless TCG doesn't display rarity on Japanese card pages (they show
HP, type, attacks, etc. but no rarity label). But every JP card has an
"Int. Prints" table linking to its English equivalent print, and the
English page DOES expose rarity in the format

    <div class="prints-current-details">
        <span class="text-lg">Destined Rivals (DRI)</span>
        <span>#1 · Uncommon</span>
    </div>

So we fetch each JP card detail → extract the EN print link → fetch the
EN detail → extract rarity → write back to our DB.

The expensive operation is 2 HTTP fetches per card. With sem=8 that
runs roughly 4998 cards in ~20-25 minutes.

Usage:
    python -m scripts.backfill_jp_rarity                 # all NULL-rarity JP cards
    python -m scripts.backfill_jp_rarity --set M2a       # one set
    python -m scripts.backfill_jp_rarity --dry-run --limit 20
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import re

import httpx
from sqlalchemy import text

from app.database import SessionLocal, init_db
from app.models import Card

log = logging.getLogger("backfill_jp_rarity")

BASE = "https://limitlesstcg.com"
SEM = 8

# Match EN print links inside the JP detail page's Int. Prints table.
# We collect ALL of them — a JP secret rare typically has multiple EN
# equivalents (base print + reverse + holo + ultra + SAR variants), and
# the FIRST is the base (wrongly classifying SAR cards as Double Rare).
# Picking the highest-tier rarity across all candidates gives the right
# answer for both base prints (1 candidate, trivially correct) and
# secret rares (multiple candidates, pick the rarest tier).
_INT_PRINT_RE = re.compile(
    r'<a\s+[^>]*href="/cards/en/([A-Za-z0-9]+)/([A-Za-z0-9\-]+)"',
    re.IGNORECASE,
)

# On the EN detail page, rarity sits in prints-current-details right after
# the card number with a "·" separator: "#1 · Uncommon".
_EN_RARITY_RE = re.compile(
    r'#[A-Za-z0-9\-]+\s*·\s*([A-Za-z][A-Za-z\s]+?)\s*</span>',
    re.IGNORECASE,
)

# Reuse the canonicalization from import_jp_catalog to match
# pokemontcg.io conventions our frontend rarity filter expects.
_RARITY_REMAP: dict[str, str] = {
    "Holo Rare": "Rare Holo",
    "Double rare": "Double Rare",
    "Illustration rare": "Illustration Rare",
    "Art Rare": "Illustration Rare",                   # Limitless: AR tier
    "Special illustration rare": "Special Illustration Rare",
    "Special Art Rare": "Special Illustration Rare",   # Limitless: SAR tier
    "Shiny rare": "Shiny Rare",
    "Secret Rare": "Rare Secret",
}

# Rarity hierarchy — higher = rarer. When a JP card has multiple EN
# equivalents (base + reverse + ultra + SAR), we pick the rarest.
_RARITY_RANK: dict[str, int] = {
    "Common": 1,
    "Uncommon": 2,
    "Rare": 3,
    "Rare Holo": 4,
    "Double Rare": 5,
    "Triple Rare": 6,
    "Ultra Rare": 7,
    "Rare Ultra": 7,
    "Illustration Rare": 8,
    "Special Illustration Rare": 9,
    "Rare Secret": 10,
    "Shiny Rare": 10,
    "Amazing Rare": 10,
    "Radiant Rare": 10,
    "Hyper Rare": 11,
    "Mega Hyper Rare": 12,
}


def _normalize(value: str | None) -> str | None:
    if not value:
        return None
    v = value.strip()
    if not v or v == "None":
        return None
    return _RARITY_REMAP.get(v, v)


async def _extract_en_equivalents(
    client: httpx.AsyncClient, jp_set: str, jp_num: str
) -> list[tuple[str, str]]:
    """Return all EN print equivalents (set_id, num) from the JP detail page."""
    url = f"{BASE}/cards/jp/{jp_set}/{jp_num}"
    try:
        r = await client.get(url, timeout=20)
    except httpx.HTTPError:
        return []
    if r.status_code != 200:
        return []
    # Dedupe while preserving order
    seen: set[tuple[str, str]] = set()
    out: list[tuple[str, str]] = []
    for m in _INT_PRINT_RE.finditer(r.text):
        key = (m.group(1), m.group(2))
        if key not in seen:
            seen.add(key)
            out.append(key)
    return out


async def _extract_rarity(
    client: httpx.AsyncClient, en_set: str, en_num: str
) -> str | None:
    url = f"{BASE}/cards/en/{en_set}/{en_num}"
    try:
        r = await client.get(url, timeout=20)
    except httpx.HTTPError:
        return None
    if r.status_code != 200:
        return None
    m = _EN_RARITY_RE.search(r.text)
    if not m:
        return None
    return _normalize(m.group(1))


def _rarest(candidates: list[str]) -> str | None:
    """From a list of rarity strings, return the one ranked highest by
    _RARITY_RANK. Unknown rarities get rank 0 (treated as least rare)."""
    if not candidates:
        return None
    best = max(candidates, key=lambda r: _RARITY_RANK.get(r, 0))
    return best


def _en_num_int(s: str) -> int | None:
    """`'284'` -> 284. Returns None on non-numeric (e.g. 'TG01')."""
    try:
        return int(s)
    except ValueError:
        return None


# JP cards past this fraction of their set's total are "secret rare"
# territory (SIR / Ultra Rare / Hyper Rare variants live in the upper
# slice of the numbered range). Below this, treat as base print and
# pick the lowest-numbered EN equivalent (the base, lowest-rank
# rarity). Empirically 0.85 separates M2a's base prints from its SAR
# section; varies a bit set-to-set but holds for all the high-volume
# modern JP releases.
_SECRET_RARE_THRESHOLD = 0.85


async def _lookup_one(
    client: httpx.AsyncClient,
    card_id: str,
    set_id: str,
    number: str,
    set_total: int | None,
) -> tuple[str, str | None, str]:
    en_prints = await _extract_en_equivalents(client, set_id, number)
    if not en_prints:
        return card_id, None, "no EN equivalent on JP detail page"

    # Picker priority:
    #
    # 1) EXACT NUMBER MATCH — JP and EN sets occasionally agree on
    #    card numbering for the base prints (M2a/1 ↔ DRI/1). When they
    #    do, that's an unambiguous map — pick it.
    #
    # 2) JP POSITION HEURISTIC — when no exact number matches, look at
    #    where the JP card sits in its own set:
    #       - First 85% of set: base print. Use the LOWEST-numbered EN
    #         candidate (also a base print rarity — Uncommon, Rare,
    #         Double Rare, etc).
    #       - Last 15% of set: secret rare section. Use the HIGHEST-
    #         numbered EN candidate (SIR / UR / Hyper).
    #
    #    Why number-position-sorting beats rarity-rank-sorting:
    #    Limitless's prints table orders by EN set then by EN number.
    #    Higher EN numbers in modern EN sets ARE the SARs. Sorting by
    #    rank instead would pick "Rare Secret" (rank 10) over the
    #    actual SAR (rank 9) when both appear as candidates.
    #
    # 3) RAREST FALLBACK — last resort, when set_total is unknown.
    jp_num = _en_num_int(number)
    same_num = [(s, n) for (s, n) in en_prints if n == number]
    if same_num:
        r = await _extract_rarity(client, same_num[0][0], same_num[0][1])
        if r:
            return card_id, r, "ok (number match)"

    # Position-based picker — sort candidates by EN number ascending.
    candidates = sorted(en_prints, key=lambda p: (_en_num_int(p[1]) or 99999))
    if jp_num is not None and set_total and set_total > 0:
        is_secret = jp_num > _SECRET_RARE_THRESHOLD * set_total
        pick = candidates[-1 if is_secret else 0]
        r = await _extract_rarity(client, pick[0], pick[1])
        if r:
            return card_id, r, (
                f"ok ({'secret/last' if is_secret else 'base/first'})"
            )

    # Fallback when we can't compute position (set_total unknown) —
    # use the rarest-of-N picker.
    rarities = await asyncio.gather(
        *[_extract_rarity(client, s, n) for s, n in en_prints]
    )
    valid = [r for r in rarities if r]
    if not valid:
        return card_id, None, f"no rarity in any EN print ({len(en_prints)} tried)"
    return card_id, _rarest(valid), "ok (rarest fallback)"


async def run(only_set: str | None, dry: bool, limit: int | None, include_tagged: bool) -> None:
    await init_db()

    async with SessionLocal() as db:
        # Note: no image-source filter anymore. Earlier versions only
        # processed Limitless-sourced cards because that's where the
        # gap was; turned out TCGdex-sourced cards (SV9 Battle Partners,
        # SV4a Shiny Treasure ex, S12a VSTAR Universe etc.) also have
        # incomplete rarity from TCGdex's /ja API. Limitless's EN-
        # equivalent picker works on ANY JP card with set_id+number,
        # so widening the filter picks them up too.
        # Safety filter: skip DECK sets and STUB sets.
        # DECK sets (starter decks / build boxes / trainer boxes) hold
        # reprints of MAIN-set cards. When we pass a DECK reprint's
        # (set_id, number) to Limitless, the JP detail page lists the
        # SAME card's EN prints across every set it ever appeared in —
        # including SAR variants that live in totally unrelated sets.
        # The position heuristic then treats the reprint as a "secret
        # rare" (because DECK sets have small totals so any number
        # >85% of total looks late-in-set) and assigns the SAR rarity.
        # Result: 197 name-duplicate SIRs across DECK reprints, all
        # wrong. Bulbapedia JP set articles are the correct source for
        # reprint rarities — see scrape_bulbapedia_jp_rarity.py.
        sql = """
            SELECT c.id, c.set_id, c.number, COALESCE(s.total, s.printed_total) AS set_total
            FROM cards c
            JOIN sets s ON s.id = c.set_id
            WHERE c.language='ja'
              AND c.number IS NOT NULL
              AND s.id NOT LIKE 'JPP-%'
              AND (s.set_type IS NULL OR s.set_type NOT IN ('DECK', 'STUB'))
        """
        if not include_tagged:
            sql += " AND c.rarity IS NULL"
        params: dict = {}
        if only_set:
            sql += " AND c.set_id = :set_id"
            params["set_id"] = only_set
        sql += " ORDER BY c.set_id, c.number_int NULLS LAST, c.number"
        if limit:
            sql += f" LIMIT {int(limit)}"
        rows = (await db.execute(text(sql), params)).all()

    log.info(f"Targets: {len(rows)} JP cards with NULL rarity.")

    headers = {"User-Agent": "PullList-Catalog/1.0 (+https://pulllist.org)"}
    sem = asyncio.Semaphore(SEM)

    async def bounded(client, *args):
        async with sem:
            return await _lookup_one(client, *args)

    found = 0
    no_en = 0
    no_rarity = 0
    by_set_progress: dict[str, int] = {}

    async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
        # Chunk so we can report progress + commit incrementally.
        CHUNK = 200
        for i in range(0, len(rows), CHUNK):
            chunk = rows[i : i + CHUNK]
            results = await asyncio.gather(
                *[bounded(client, r[0], r[1], r[2], r[3]) for r in chunk]
            )
            async with SessionLocal() as db:
                for cid, rarity, reason in results:
                    if rarity is None:
                        if "no EN" in reason:
                            no_en += 1
                        else:
                            no_rarity += 1
                        continue
                    found += 1
                    set_id_for_card = next(
                        (r[1] for r in chunk if r[0] == cid), None
                    )
                    if set_id_for_card:
                        by_set_progress[set_id_for_card] = (
                            by_set_progress.get(set_id_for_card, 0) + 1
                        )
                    if not dry:
                        await db.execute(
                            text("UPDATE cards SET rarity=:r WHERE id=:i"),
                            {"r": rarity, "i": cid},
                        )
                if not dry:
                    await db.commit()
            log.info(
                f"  [{i+len(chunk)}/{len(rows)}] found={found} no_en={no_en} no_rarity={no_rarity}"
            )

    log.info("\n=== Summary ===")
    log.info(f"  rarity backfilled: {found}")
    log.info(f"  no EN equivalent:  {no_en}")
    log.info(f"  no rarity in EN:   {no_rarity}")
    if by_set_progress:
        log.info("  by set:")
        for set_id, n in sorted(by_set_progress.items()):
            log.info(f"    {set_id:8s} {n}")
    if dry:
        log.info("  MODE: DRY-RUN — no writes")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--set", dest="only_set", help="One JP set id (e.g. M2a)")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--limit", type=int, help="Cap total cards processed (testing)")
    p.add_argument(
        "--include-tagged",
        action="store_true",
        help="Also re-process cards that already have a rarity (use after improving the rarest-of-N picker to fix SAR variants previously stuck on the base print's rarity)",
    )
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    asyncio.run(run(args.only_set, args.dry_run, args.limit, args.include_tagged))


if __name__ == "__main__":
    main()
