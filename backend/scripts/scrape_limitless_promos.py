"""Fill JPP-* promo eras from limitlesstcg.com.

Limitless TCG has dedicated promo set codes that map to our JPP-* eras.
We've already filled JPP-DP, JPP-SV, JPP-P partially via pokemon-card.com
scraping; this layers in the missing ones (S-P, SM-P, XY-P, BW-P, etc.)
plus any sub-eras the official site doesn't expose cleanly.

Mapping is hand-curated because Limitless splits some eras into sub-codes
(SP, SP1..SP6 are all S-P promos). All cards from a sub-code go under
the same JPP-* parent; the card_id is prefixed `JPP-{era}-{subcode}-{N}`
so dupes across sub-eras can't collide.

Usage:
    python -m scripts.scrape_limitless_promos
    python -m scripts.scrape_limitless_promos --dry-run
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import re
from dataclasses import dataclass

import httpx

from app.database import SessionLocal, init_db
from app.models import Card

log = logging.getLogger("scrape_limitless_promos")

BASE = "https://limitlesstcg.com"
SEM = 8


# Hand-curated: which Limitless promo set codes belong to which of our
# JPP-* eras. Verified against the Limitless /cards/jp index.
# Codes verified safe:
#   SVP/SVP1/SVJP -> SV-P (Scarlet/Violet era promos)
#   SP/SP1..SP6   -> S-P  (Sword & Shield era promos)
#   SMP/SMP1/SMP2 -> SM-P (Sun & Moon era promos)
#   XYP           -> XY-P
#   BWP           -> BW-P
# Codes that look right but aren't (verified by Limitless page titles):
#   HSP = "Starting Set BW Pikachu Edition" (SwSh starter), NOT HGSS promos
#   MP  = "Mega Promotional Cards" (XY-era Mega bundle), NOT McDonald's
# We don't claim coverage we don't have — old promo eras (PCG, ADV, PPP,
# DPt-P, DP-P, McD-P, World Collection, Southern Islands, Vending Machine,
# Pikachu Friends) are not on Limitless. Set rows stay but the API filter
# (see routes.py) hides eras with zero cards so the UI doesn't show them.
LIMITLESS_TO_JPP: dict[str, list[str]] = {
    "JPP-SV":  ["SVP", "SVP1", "SVJP"],
    "JPP-S":   ["SP", "SP1", "SP2", "SP3", "SP4", "SP5", "SP6"],
    "JPP-SM":  ["SMP", "SMP1", "SMP2"],
    "JPP-XY":  ["XYP"],
    "JPP-BW":  ["BWP"],
}


@dataclass
class PromoCard:
    jpp_era: str          # JPP-S
    limitless_set: str    # SP3
    number: str           # "12"
    name_jp: str
    image_small: str
    image_large: str


_TITLE_RE = re.compile(r'<title>([^<]+)</title>', re.IGNORECASE)


async def _fetch_list(client: httpx.AsyncClient, ll_set: str) -> list[tuple[str, str]]:
    r = await client.get(f"{BASE}/cards/jp/{ll_set}", timeout=20)
    if r.status_code != 200:
        log.warning(f"  ! {ll_set} HTTP {r.status_code}")
        return []
    html = r.text
    blocks = re.findall(
        rf'<a[^>]+href="(/cards/jp/{re.escape(ll_set)}/([A-Za-z0-9\-]+))"[^>]*>(.*?)</a>',
        html, re.DOTALL,
    )
    out = []
    seen = set()
    for _href, num, content in blocks:
        if num in seen:
            continue
        seen.add(num)
        img = re.search(r'src="([^"]+_SM\.png)"', content)
        if not img:
            continue
        out.append((num, img.group(1)))
    return out


async def _fetch_name(client: httpx.AsyncClient, ll_set: str, num: str) -> str:
    r = await client.get(f"{BASE}/cards/jp/{ll_set}/{num}", timeout=20)
    if r.status_code != 200:
        return ""
    m = _TITLE_RE.search(r.text)
    if not m:
        return ""
    return m.group(1).split(" - ", 1)[0].strip()


async def _scrape_subera(client: httpx.AsyncClient, jpp_era: str, ll_set: str) -> list[PromoCard]:
    listing = await _fetch_list(client, ll_set)
    if not listing:
        return []
    log.info(f"    {jpp_era} <- {ll_set}: {len(listing)} cards, fetching names…")
    sem = asyncio.Semaphore(SEM)

    async def one(num: str, sm: str) -> PromoCard | None:
        async with sem:
            name = await _fetch_name(client, ll_set, num)
        if not name:
            return None
        return PromoCard(
            jpp_era=jpp_era, limitless_set=ll_set, number=num, name_jp=name,
            image_small=sm, image_large=sm.replace("_SM.png", "_LG.png"),
        )

    results = await asyncio.gather(*[one(n, u) for n, u in listing])
    return [r for r in results if r]


async def _upsert(db, cards: list[PromoCard]) -> int:
    written = 0
    for c in cards:
        card_id = f"{c.jpp_era}-{c.limitless_set}-{c.number}"
        row = await db.get(Card, card_id)
        if row is not None and row.language != "ja":
            log.warning(f"  ! skip {card_id}: language={row.language!r}")
            continue
        if row is None:
            row = Card(id=card_id, language="ja", set_id=c.jpp_era)
            db.add(row)
        row.name = c.name_jp
        row.name_local = c.name_jp
        row.number = c.number
        try:
            row.number_int = int(c.number)
        except ValueError:
            row.number_int = None
        row.image_small = c.image_small
        row.image_large = c.image_large
        row.set_id = c.jpp_era
        row.language = "ja"
        written += 1
    await db.commit()
    return written


async def run(only_era: str | None, dry: bool) -> None:
    await init_db()

    headers = {"User-Agent": "PullList-Catalog/1.0 (+https://pulllist.org)"}
    async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
        for jpp_era, ll_sets in LIMITLESS_TO_JPP.items():
            if only_era and only_era != jpp_era:
                continue
            log.info(f"[{jpp_era}] sub-codes: {ll_sets}")
            era_cards: list[PromoCard] = []
            for ll in ll_sets:
                era_cards.extend(await _scrape_subera(client, jpp_era, ll))
            if not era_cards:
                continue
            if dry:
                log.info(f"  {jpp_era}: would write {len(era_cards)} cards")
                continue
            async with SessionLocal() as db:
                n = await _upsert(db, era_cards)
                log.info(f"  {jpp_era}: wrote {n} cards across {len(ll_sets)} sub-codes")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--era", dest="only_era", help="One JPP-* era to fill")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    asyncio.run(run(args.only_era, args.dry_run))


if __name__ == "__main__":
    main()
