"""Fill Pitch Black (me5) card metadata from Bulbapedia.

TCGCSV, pokemontcg.io, Limitless, TCGdex all still lag behind the
2026-07-17 launch — none of them expose individual me5 cards yet.
But Bulbapedia's set article ("Pitch Black (TCG)") already carries
a full Setlist / entry template listing with names, types, and
rarities for every card, plus the blister-exclusive promos.

This script parses the Setlist templates and patches our me5 rows
in place — name, rarity, types, supertype get real values while we
wait for TCGCSV to bring proper images + prices + TCGplayer product
ids.

Idempotent — re-runs simply upsert the same values.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import re
import sys
from pathlib import Path

import httpx

sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DEBUG", "false")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

from sqlalchemy import select  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import Card  # noqa: E402


log = logging.getLogger("backfill_pitchblack_from_bulbapedia")


WIKI_API = "https://bulbapedia.bulbagarden.net/w/api.php"
USER_AGENT = "PullList/1.0 (research; admin@pulllist.org)"
SET_ID = "me5"


# {{Setlist/entry|NNN/084|J|{{TCG ID|Pitch Black|Card Name|N|display}}|Type|extra|Rarity}}
# Card Name can be wrapped: {{TCG ID|...|Lurantis ex|4|Lurantis}}{{ex}} —
# the FIRST pipe-token after the set name is the canonical card name.
#
# 'entry' = main set; 'nmentry' = "non-master" variants (blister /
# Build & Battle Box / gift-with-purchase reprints). Same number can
# appear as both; we treat entry as the source of truth for main-set
# metadata and only consult nmentry for numbers that don't have one.
def _build_regex(kind: str) -> re.Pattern[str]:
    pat = (
        r"\{\{Setlist/" + kind +
        r"\|(\d{1,3})/\d{2,3}"
        r"\|(?:[^|]*\|)?"
        r"\{\{TCG ID\|[^|]+\|([^|]+)"
        r"\|[^\}]*\}\}"
        r"(?:\{\{[^\}]+\}\})*"
        r"\|([^|]*)"
        r"\|([^|]*)"
        r"\|?([^\}]*?)"
        r"\}\}"
    )
    return re.compile(pat)


_ENTRY_RE = _build_regex("entry")
_NMENTRY_RE = _build_regex("nmentry")


def _clean(s: str) -> str:
    return s.strip() or ""


def _parse_wikitext(wt: str) -> list[dict]:
    """Return list of dicts. Main-set entries first, then nmentry
    fallbacks for numbers the main set didn't cover."""
    seen: set[int] = set()
    out: list[dict] = []
    for regex in (_ENTRY_RE, _NMENTRY_RE):
      for m in regex.finditer(wt):
        num, name, energy, extra, rarity = m.groups()
        num_i = int(num)
        if num_i in seen:
            continue
        seen.add(num_i)
        num_i = int(num)
        # Suffix templates the regex may swallow; grab a wider window
        # to see whether {{ex}} / {{Mega ex}} / {{V}} follow the name.
        # Look for the suffix inside the raw matched text.
        raw = m.group(0)
        suffix = ""
        if re.search(r"\{\{Mega ex\}\}", raw):
            suffix = " ex"
            name_prefix = "Mega "
        elif re.search(r"\{\{ex\}\}", raw):
            suffix = " ex"
            name_prefix = ""
        elif re.search(r"\{\{V\}\}", raw):
            suffix = " V"
            name_prefix = ""
        elif re.search(r"\{\{VMAX\}\}", raw):
            suffix = " VMAX"
            name_prefix = ""
        elif re.search(r"\{\{VSTAR\}\}", raw):
            suffix = " VSTAR"
            name_prefix = ""
        else:
            name_prefix = ""

        # The template gives "Lurantis ex" as the canonical name already
        # in the middle field, so we don't need to append suffix ourselves.
        # But Mega variants are stored as "Mega Delphox ex" — that IS
        # already the canonical.
        clean_name = _clean(name)
        clean_energy = _clean(energy)
        clean_rarity = _clean(rarity)

        out.append({
            "number": num_i,
            "name": clean_name,
            "energy_type": clean_energy,
            "rarity": clean_rarity,
        })
    return out


def _guess_supertype(name: str, energy: str, rarity: str) -> str | None:
    """Rough classification. TCGCSV overwrites later anyway."""
    if energy in ("Energy",):
        return "Energy"
    if energy and energy != "Trainer":
        return "Pokémon"
    if energy == "Trainer" or "Trainer" in rarity:
        return "Trainer"
    return None


async def main(dry_run: bool) -> None:
    async with httpx.AsyncClient(
        timeout=30, headers={"User-Agent": USER_AGENT}
    ) as c:
        r = await c.get(
            WIKI_API,
            params={
                "action": "parse",
                "page": "Pitch Black (TCG)",
                "format": "json",
                "prop": "wikitext",
                "redirects": "true",
            },
        )
        r.raise_for_status()
        wt = r.json()["parse"]["wikitext"]["*"]
    log.info("fetched %d chars of wikitext", len(wt))

    entries = _parse_wikitext(wt)
    log.info("parsed %d setlist entries", len(entries))

    stats = {
        "matched_and_updated": 0,
        "no_matching_row": 0,
        "unchanged": 0,
    }
    async with SessionLocal() as db:
        # Load all me5 rows keyed by number_int
        rows = (
            await db.execute(
                select(Card).where(Card.set_id == SET_ID)
            )
        ).scalars().all()
        by_num: dict[int, Card] = {
            r.number_int: r for r in rows if r.number_int is not None
        }

        # _parse_wikitext already dedupes by "entry first, nmentry fallback"
        best_per_num: dict[int, dict] = {e["number"]: e for e in entries}

        for num, e in best_per_num.items():
            row = by_num.get(num)
            if row is None:
                stats["no_matching_row"] += 1
                log.warning("  no me5 row for #%d (%s)", num, e["name"])
                continue

            new_name = e["name"]
            new_rarity = e["rarity"] or None
            new_energy = [e["energy_type"]] if e["energy_type"] else None
            new_supertype = _guess_supertype(
                new_name, e["energy_type"], new_rarity or ""
            )

            changed = (
                row.name != new_name
                or row.rarity != new_rarity
                or row.types != new_energy
                or row.supertype != new_supertype
            )
            if not changed:
                stats["unchanged"] += 1
                continue

            log.info(
                "  #%03d  %r  rarity=%r  types=%s",
                num, new_name, new_rarity, new_energy,
            )
            if not dry_run:
                row.name = new_name
                row.rarity = new_rarity
                row.types = new_energy
                row.supertype = new_supertype
            stats["matched_and_updated"] += 1

        if not dry_run:
            await db.commit()

    log.info("=== summary ===")
    for k, v in stats.items():
        log.info("  %s: %s", k, v)
    log.info("  dry_run: %s", dry_run)


def cli() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    asyncio.run(main(args.dry_run))


if __name__ == "__main__":
    cli()
